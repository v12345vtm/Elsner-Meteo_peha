// Versie: 0.1.0
//
// ESPHome-glue voor het Elsner weerstation: leest de UART, houdt de timers bij
// en publiceert de waarden naar de entiteiten. De frame-logica zit in elsner_core.h.
#include "elsner.h"

#include "esphome/core/hal.h"
#include "esphome/core/log.h"

namespace esphome {
namespace elsner {

static const char *const TAG = "elsner";
static constexpr uint32_t COUNTER_PUBLISH_MS = 10000;  // tellers elke 10 s naar HA

using elsner_core::FieldDef;
using elsner_core::ProtocolDef;

void ElsnerComponent::setup() {
  ESP_LOGI(TAG, "Elsner-component v%s gestart", elsner_core::COMPONENT_VERSION);
  this->check_uart_settings(elsner_core::BAUDRATE);
  const uint32_t now = millis();
  last_frame_ms_ = now;
  last_counter_publish_ms_ = now;
}

void ElsnerComponent::loop() {
  const uint32_t now = millis();

  // 1. Lees alle beschikbare bytes; de parser zet ze om in frames.
  while (this->available() > 0) {
    uint8_t byte = 0;
    if (!this->read_byte(&byte)) break;
    if (byte == elsner_core::ETX) {
      last_frame_ms_ = now;
      timeout_logged_ = false;
    }
    handle_flags_(parser_.feed(byte, now));
  }

  // 2. Geen frame binnen FRAME_TIMEOUT: waarschuwen en de waarden unavailable maken.
  if (!timeout_logged_ && now - last_frame_ms_ > elsner_core::FRAME_TIMEOUT_MS) {
    timeout_logged_ = true;
    ESP_LOGW(TAG,
             "no frame received for %u seconds - check the station (power, A/B wiring) "
             "and the RS485 transceiver",
             static_cast<unsigned>(elsner_core::FRAME_TIMEOUT_MS / 1000));
    if (parser_.set_unavailable()) publish_unavailable_();
  }

  // 3. Geen geldig frame binnen STALE_TIMEOUT: waarden unavailable.
  if (parser_.check_stale(now)) {
    ESP_LOGW(TAG, "no valid data packet for %u seconds - sensors are unavailable",
             static_cast<unsigned>(elsner_core::STALE_TIMEOUT_MS / 1000));
    publish_unavailable_();
  }

  // 4. Tellers periodiek publiceren (in HA-integratie waren dit attributen).
  if (now - last_counter_publish_ms_ >= COUNTER_PUBLISH_MS) {
    last_counter_publish_ms_ = now;
    publish_counters_();
  }
}

void ElsnerComponent::handle_flags_(uint8_t flags) {
  if (flags == elsner_core::FLAG_NONE) return;

  if (flags & elsner_core::FLAG_OVERFLOW) {
    ESP_LOGW(TAG, "frame longer than %u bytes without ETX (0x03) - check the baud rate and wiring",
             static_cast<unsigned>(elsner_core::MAX_FRAME_BUFFER));
  }
  if (flags & elsner_core::FLAG_INVALID) {
    ESP_LOGD(TAG, "frame discarded: %s", parser_.last_reason());
  }
  if (flags & elsner_core::FLAG_PROTOCOL_LOCKED) {
    const ProtocolDef *p = parser_.protocol();
    ESP_LOGI(TAG, "station protocol recognised: %s (start '%c')", p->variant, p->start_char);
    if (variant_sensor_ != nullptr) variant_sensor_->publish_state(p->variant);
    warn_missing_fields_();
  }
  if (flags & elsner_core::FLAG_ANALYSED) {
    publish_values_();
  }
}

void ElsnerComponent::publish_values_() {
  const ProtocolDef *proto = parser_.protocol();
  const std::string &frame = parser_.frame();
  if (proto == nullptr) return;

  for (auto &b : sensors_) {
    double v = NAN;  // NaN = unavailable in Home Assistant
    const FieldDef *f = elsner_core::find_field(*proto, b.key.c_str());
    if (f != nullptr) elsner_core::read_number(*f, frame, v);
    b.entity->publish_state(static_cast<float>(v));
  }
  for (auto &b : binary_sensors_) {
    const FieldDef *f = elsner_core::find_field(*proto, b.key.c_str());
    if (f != nullptr) b.entity->publish_state(elsner_core::read_flag(*f, frame));
  }
  for (auto &b : text_sensors_) {
    const FieldDef *f = elsner_core::find_field(*proto, b.key.c_str());
    if (f != nullptr) b.entity->publish_state(elsner_core::read_text(*f, frame));
  }
  if (checksum_sensor_ != nullptr) checksum_sensor_->publish_state(parser_.checksum_ok());
  if (raw_sensor_ != nullptr) raw_sensor_->publish_state(elsner_core::sanitize_ascii(frame));
}

void ElsnerComponent::publish_unavailable_() {
  for (auto &b : sensors_) b.entity->publish_state(NAN);
}

void ElsnerComponent::publish_counters_() {
  for (auto &c : counters_) {
    uint32_t v = 0;
    switch (c.counter) {
      case Counter::RECEIVED: v = parser_.frames_received(); break;
      case Counter::ANALYSED: v = parser_.frames_analysed(); break;
      case Counter::SKIPPED: v = parser_.frames_skipped(); break;
      case Counter::INVALID: v = parser_.frames_invalid(); break;
    }
    c.entity->publish_state(static_cast<float>(v));
  }
}

void ElsnerComponent::warn_missing_fields_() {
  const ProtocolDef *p = parser_.protocol();
  if (p == nullptr) return;
  auto check = [p](const std::string &key) {
    if (elsner_core::find_field(*p, key.c_str()) == nullptr) {
      ESP_LOGW(TAG, "field '%s' does not exist in the %s protocol - this entity will not get a value",
               key.c_str(), p->variant);
    }
  };
  for (auto &b : sensors_) check(b.key);
  for (auto &b : binary_sensors_) check(b.key);
  for (auto &b : text_sensors_) check(b.key);
}

void ElsnerComponent::add_sensor(const std::string &key, sensor::Sensor *s) {
  if (key == "frames_received") {
    counters_.push_back({Counter::RECEIVED, s});
  } else if (key == "frames_analysed") {
    counters_.push_back({Counter::ANALYSED, s});
  } else if (key == "frames_skipped") {
    counters_.push_back({Counter::SKIPPED, s});
  } else if (key == "frames_invalid") {
    counters_.push_back({Counter::INVALID, s});
  } else {
    sensors_.push_back({key, s});
  }
}

void ElsnerComponent::add_binary_sensor(const std::string &key, binary_sensor::BinarySensor *s) {
  if (key == "checksum_valid") {
    checksum_sensor_ = s;
  } else {
    binary_sensors_.push_back({key, s});
  }
}

void ElsnerComponent::add_text_sensor(const std::string &key, text_sensor::TextSensor *s) {
  if (key == "raw_packet") {
    raw_sensor_ = s;
  } else if (key == "variant") {
    variant_sensor_ = s;
  } else {
    text_sensors_.push_back({key, s});
  }
}

void ElsnerComponent::reset_connection() {
  ESP_LOGI(TAG, "reset requested - draining the UART receive buffer");
  uint8_t byte = 0;
  while (this->available() > 0 && this->read_byte(&byte)) {
  }
  parser_.drop_partial();
  if (parser_.set_unavailable()) publish_unavailable_();
  last_frame_ms_ = millis();
  timeout_logged_ = false;
}

void ElsnerComponent::dump_config() {
  ESP_LOGCONFIG(TAG, "Elsner weather station (component v%s):", elsner_core::COMPONENT_VERSION);
  LOG_UART_DEVICE(this);
  ESP_LOGCONFIG(TAG, "  Analyse interval: %u ms", static_cast<unsigned>(analyse_interval_ms_));
}

void ElsnerResetButton::press_action() {
  if (parent_ != nullptr) parent_->reset_connection();
}

}  // namespace elsner
}  // namespace esphome
