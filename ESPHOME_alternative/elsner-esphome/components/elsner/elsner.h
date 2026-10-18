// Versie: 0.1.0
//
// ESPHome-component voor het Elsner P03/3 weerstation (RS485).
// Protocol en frame-logica staan in elsner_core.h; dit bestand koppelt die aan
// de UART, de timers en de ESPHome-entiteiten (sensor, binary_sensor, text_sensor, button).
#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "esphome/core/component.h"
#include "esphome/components/binary_sensor/binary_sensor.h"
#include "esphome/components/button/button.h"
#include "esphome/components/sensor/sensor.h"
#include "esphome/components/text_sensor/text_sensor.h"
#include "esphome/components/uart/uart.h"

#include "elsner_core.h"

namespace esphome {
namespace elsner {

class ElsnerComponent : public Component, public uart::UARTDevice {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;

  void set_analyse_interval(uint32_t ms) {
    analyse_interval_ms_ = ms;
    parser_.set_analyse_interval(ms);
  }

  // Koppelingen die vanuit de Python-configuratie worden aangeroepen.
  void add_sensor(const std::string &key, sensor::Sensor *s);
  void add_binary_sensor(const std::string &key, binary_sensor::BinarySensor *s);
  void add_text_sensor(const std::string &key, text_sensor::TextSensor *s);

  // Aangeroepen door de reset-knop: leegt de ontvangstbuffer en zet de status op unavailable.
  void reset_connection();

 protected:
  enum class Counter : uint8_t { RECEIVED, ANALYSED, SKIPPED, INVALID };

  template <typename T>
  struct Binding {
    std::string key;
    T *entity;
  };
  struct CounterBinding {
    Counter counter;
    sensor::Sensor *entity;
  };

  void handle_flags_(uint8_t flags);
  void publish_values_();
  void publish_unavailable_();
  void publish_counters_();
  void warn_missing_fields_();

  elsner_core::FrameParser parser_{};
  uint32_t analyse_interval_ms_{5000};
  uint32_t last_frame_ms_{0};
  uint32_t last_counter_publish_ms_{0};
  bool timeout_logged_{false};

  std::vector<Binding<sensor::Sensor>> sensors_;
  std::vector<Binding<binary_sensor::BinarySensor>> binary_sensors_;
  std::vector<Binding<text_sensor::TextSensor>> text_sensors_;
  std::vector<CounterBinding> counters_;
  binary_sensor::BinarySensor *checksum_sensor_{nullptr};
  text_sensor::TextSensor *raw_sensor_{nullptr};
  text_sensor::TextSensor *variant_sensor_{nullptr};
};

// Knop 'Reset USB connection' uit de HA-integratie.
class ElsnerResetButton : public button::Button {
 public:
  void set_parent(ElsnerComponent *parent) { parent_ = parent; }

 protected:
  void press_action() override;

  ElsnerComponent *parent_{nullptr};
};

}  // namespace elsner
}  // namespace esphome
