// Versie: 0.1.0
//
// Elsner P03/3 - protocol en frame-analyse (pure C++, geen ESPHome-afhankelijkheden).
//
// Dit bestand is een 1-op-1 vertaling van custom_components/elsner/protocols.py en
// de frame-logica uit custom_components/elsner/hub.py. Omdat het los van ESPHome
// compileert, kan de parity-test (esphome/tests/) dezelfde frames door deze code
// en door de HA-code halen en de uitkomsten vergelijken.
#pragma once

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>
#include <utility>

namespace elsner_core {

inline constexpr char COMPONENT_VERSION[] = "0.1.0";

inline constexpr uint8_t ETX = 0x03;             // einde-van-frame (zelfde als HA ETX)
inline constexpr uint32_t BAUDRATE = 19200;      // zelfde als HA BAUDRATE
inline constexpr uint32_t FRAME_TIMEOUT_MS = 10000;   // HA FRAME_TIMEOUT: geen frame -> waarschuwing
inline constexpr uint32_t STALE_TIMEOUT_MS = 60000;   // HA STALE_TIMEOUT: geen geldig frame -> unavailable
inline constexpr size_t MAX_FRAME_BUFFER = 256;  // bescherming tegen een frame zonder ETX

enum class Kind : uint8_t { FLOAT, INT, FLAG, TEXT };

struct FieldDef {
  const char *key;  // zelfde sleutel als in protocols.py
  uint8_t start;    // 0-based, ETX niet meegerekend
  uint8_t end;      // exclusief
  Kind kind;
};

struct ProtocolDef {
  char start_char;        // eerste teken van het frame: 'W' of 'G'
  uint8_t frame_length;   // lengte zonder ETX
  const FieldDef *fields;
  size_t field_count;
  const char *variant;    // leesbare naam: CET of GPS
};

// --- CET-variant (start 'W', 39 tekens) ---
inline constexpr FieldDef CET_FIELDS[] = {
    {"temperature", 1, 6, Kind::FLOAT},
    {"sun_south", 6, 8, Kind::INT},
    {"sun_west", 8, 10, Kind::INT},
    {"sun_east", 10, 12, Kind::INT},
    {"twilight", 12, 13, Kind::FLAG},
    {"daylight", 13, 16, Kind::INT},
    {"wind", 16, 20, Kind::FLOAT},
    {"rain", 20, 21, Kind::FLAG},
    {"weekday", 21, 22, Kind::TEXT},
    {"day", 22, 24, Kind::INT},
    {"month", 24, 26, Kind::INT},
    {"year", 26, 28, Kind::INT},
    {"hour", 28, 30, Kind::INT},
    {"minute", 30, 32, Kind::INT},
    {"second", 32, 34, Kind::INT},
    {"summer_time", 34, 35, Kind::TEXT},
    {"checksum", 35, 39, Kind::INT},
};

// --- GPS-variant (start 'G', 60 tekens) ---
inline constexpr FieldDef GPS_FIELDS[] = {
    {"temperature", 1, 6, Kind::FLOAT},
    {"sun_south", 6, 8, Kind::INT},
    {"sun_west", 8, 10, Kind::INT},
    {"sun_east", 10, 12, Kind::INT},
    {"twilight", 12, 13, Kind::FLAG},
    {"daylight", 13, 16, Kind::INT},
    {"wind", 16, 20, Kind::FLOAT},
    {"rain", 20, 21, Kind::FLAG},
    {"weekday", 21, 22, Kind::TEXT},
    {"day", 22, 24, Kind::INT},
    {"month", 24, 26, Kind::INT},
    {"year", 26, 28, Kind::INT},
    {"hour", 28, 30, Kind::INT},
    {"minute", 30, 32, Kind::INT},
    {"second", 32, 34, Kind::INT},
    {"gps_status", 34, 35, Kind::INT},
    {"azimuth", 35, 40, Kind::FLOAT},
    {"elevation", 40, 45, Kind::FLOAT},
    {"longitude_direction", 45, 46, Kind::TEXT},
    {"longitude", 46, 51, Kind::FLOAT},
    {"latitude_direction", 51, 52, Kind::TEXT},
    {"latitude", 52, 56, Kind::FLOAT},
    {"checksum", 56, 60, Kind::INT},
};

inline constexpr ProtocolDef CET_PROTOCOL{
    'W', 39, CET_FIELDS, sizeof(CET_FIELDS) / sizeof(CET_FIELDS[0]), "CET"};
inline constexpr ProtocolDef GPS_PROTOCOL{
    'G', 60, GPS_FIELDS, sizeof(GPS_FIELDS) / sizeof(GPS_FIELDS[0]), "GPS"};

inline const ProtocolDef *protocol_for_start(char c) {
  switch (c) {
    case 'W': return &CET_PROTOCOL;
    case 'G': return &GPS_PROTOCOL;
    default: return nullptr;
  }
}

inline const FieldDef *find_field(const ProtocolDef &p, const char *key) {
  for (size_t i = 0; i < p.field_count; i++) {
    if (std::strcmp(p.fields[i].key, key) == 0) return &p.fields[i];
  }
  return nullptr;
}

// --- Tekst-hulpfuncties (gedrag gelijk aan Python str.strip / float / int) ---

inline bool is_py_space(unsigned char c) {
  // ' ', \t \n \v \f \r en de bestandsscheiders 0x1C-0x1F (Python str.isspace)
  return c == ' ' || (c >= 9 && c <= 13) || (c >= 0x1C && c <= 0x1F);
}

inline std::string strip_ws(const char *p, size_t n) {
  size_t b = 0;
  size_t e = n;
  while (b < e && is_py_space(static_cast<unsigned char>(p[b]))) b++;
  while (e > b && is_py_space(static_cast<unsigned char>(p[e - 1]))) e--;
  return std::string(p + b, e - b);
}

inline bool parse_float(const char *p, size_t n, double &out) {
  std::string s = strip_ws(p, n);
  if (s.empty()) return false;
  char *end = nullptr;
  double v = std::strtod(s.c_str(), &end);
  if (end != s.c_str() + s.size()) return false;
  out = v;
  return true;
}

inline bool parse_int(const char *p, size_t n, int64_t &out) {
  std::string s = strip_ws(p, n);
  size_t i = 0;
  bool neg = false;
  if (i < s.size() && (s[i] == '+' || s[i] == '-')) {
    neg = (s[i] == '-');
    i++;
  }
  if (i >= s.size()) return false;
  int64_t v = 0;
  for (; i < s.size(); i++) {
    if (s[i] < '0' || s[i] > '9') return false;
    v = v * 10 + (s[i] - '0');  // velden zijn maximaal 4 cijfers: geen overloop
  }
  out = neg ? -v : v;
  return true;
}

// Leest een FLOAT- of INT-veld. Bij een fout wordt out NaN en geeft de functie false.
inline bool read_number(const FieldDef &f, const std::string &frame, double &out) {
  out = NAN;
  if (f.end > frame.size()) return false;
  const char *p = frame.data() + f.start;
  const size_t n = f.end - f.start;
  if (f.kind == Kind::FLOAT) return parse_float(p, n, out);
  if (f.kind == Kind::INT) {
    int64_t v = 0;
    if (!parse_int(p, n, v)) return false;
    out = static_cast<double>(v);
    return true;
  }
  return false;
}

// 'J' (ja) -> true, alles anders -> false (zelfde als HA _flag).
inline bool read_flag(const FieldDef &f, const std::string &frame) {
  if (f.end > frame.size()) return false;
  std::string s = strip_ws(frame.data() + f.start, f.end - f.start);
  return s == "J" || s == "j";
}

inline std::string read_text(const FieldDef &f, const std::string &frame) {
  if (f.end > frame.size()) return std::string();
  return strip_ws(frame.data() + f.start, f.end - f.start);
}

// ASCII-som van alle tekens vóór de checksum, modulo 10^(breedte checksum).
// Let op: alleen diagnostisch. De HA-integratie gebruikt deze controle ook niet
// om frames te verwerpen.
inline bool checksum_valid(const ProtocolDef &p, const std::string &frame) {
  const FieldDef *cs = find_field(p, "checksum");
  if (cs == nullptr || cs->end > frame.size()) return false;
  uint64_t computed = 0;
  for (size_t i = 0; i < cs->start; i++) {
    computed += static_cast<unsigned char>(frame[i]);
  }
  int64_t reported = 0;
  if (!parse_int(frame.data() + cs->start, cs->end - cs->start, reported) || reported < 0) {
    return false;
  }
  uint64_t modulus = 1;
  for (int i = 0; i < cs->end - cs->start; i++) modulus *= 10;
  return computed % modulus == static_cast<uint64_t>(reported);
}

// Maakt een tekst veilig voor Home Assistant (geldig ASCII, geen rare bytes).
inline std::string sanitize_ascii(const std::string &s) {
  std::string out = s;
  for (auto &c : out) {
    const unsigned char u = static_cast<unsigned char>(c);
    if (u < 0x20 || u > 0x7E) c = '?';
  }
  return out;
}

// --- Frame-verwerking (port van ElsnerHub._async_handle_raw) ---

enum : uint8_t {
  FLAG_NONE = 0,
  FLAG_PROTOCOL_LOCKED = 1 << 0,  // eerste geldige frame: variant (W/G) vastgelegd
  FLAG_ANALYSED = 1 << 1,         // frame geanalyseerd: publiceren
  FLAG_SKIPPED = 1 << 2,          // binnen het analyse-interval (throttle)
  FLAG_INVALID = 1 << 3,          // frame afgewezen
  FLAG_OVERFLOW = 1 << 4,         // frame te lang zonder ETX
};

class FrameParser {
 public:
  explicit FrameParser(uint32_t analyse_interval_ms = 5000)
      : analyse_interval_ms_(analyse_interval_ms) {}

  // Verwerkt één ontvangen byte. Geeft een bitmasker met FLAG_* terug.
  uint8_t feed(uint8_t byte, uint32_t now_ms) {
    if (byte != ETX) {
      if (overflow_) return FLAG_NONE;  // wachten tot het ETX van het te lange frame komt
      if (buffer_.size() >= MAX_FRAME_BUFFER) {
        buffer_.clear();
        overflow_ = true;
        return FLAG_OVERFLOW;
      }
      buffer_.push_back(static_cast<char>(byte));
      return FLAG_NONE;
    }
    if (overflow_) {
      overflow_ = false;
      buffer_.clear();
      frames_received_++;
      return discard_("frame longer than the buffer (no ETX)");
    }
    std::string raw;
    raw.swap(buffer_);
    return handle_frame_(raw, now_ms);
  }

  // Leegt een half ontvangen frame (gebruikt door de reset-knop).
  void drop_partial() {
    buffer_.clear();
    overflow_ = false;
  }

  // Zet de status op 'niet beschikbaar'. Geeft true als dat iets veranderde.
  bool set_unavailable() {
    if (!available_) return false;
    available_ = false;
    return true;
  }

  // Zet op 'niet beschikbaar' als er te lang geen geldig frame kwam. Geeft true bij wijziging.
  bool check_stale(uint32_t now_ms) {
    if (!available_ || now_ms - last_valid_ms_ <= STALE_TIMEOUT_MS) return false;
    available_ = false;
    return true;
  }

  void set_analyse_interval(uint32_t ms) { analyse_interval_ms_ = ms; }

  const ProtocolDef *protocol() const { return protocol_; }
  const std::string &frame() const { return frame_; }  // laatst geanalyseerde frame (gestript)
  bool checksum_ok() const { return checksum_ok_; }
  bool available() const { return available_; }
  const char *last_reason() const { return last_reason_; }
  uint32_t frames_received() const { return frames_received_; }
  uint32_t frames_analysed() const { return frames_analysed_; }
  uint32_t frames_skipped() const { return frames_skipped_; }
  uint32_t frames_invalid() const { return frames_invalid_; }

 private:
  uint8_t discard_(const char *reason) {
    frames_invalid_++;
    last_reason_ = reason;
    return FLAG_INVALID;
  }

  uint8_t handle_frame_(const std::string &raw, uint32_t now_ms) {
    frames_received_++;
    std::string frame = strip_ws(raw.data(), raw.size());
    const ProtocolDef *proto = frame.empty() ? nullptr : protocol_for_start(frame[0]);
    if (proto == nullptr) return discard_("unknown start character");
    if (protocol_ != nullptr && proto != protocol_) return discard_("station uses another protocol");
    if (frame.size() != proto->frame_length) return discard_("wrong frame length");

    last_valid_ms_ = now_ms;
    uint8_t flags = FLAG_NONE;
    if (protocol_ == nullptr) {
      protocol_ = proto;  // het eerste geldige frame bepaalt W (CET) of G (GPS)
      flags |= FLAG_PROTOCOL_LOCKED;
    }

    // Throttle: analyseer alleen als het interval voorbij is (0 = altijd analyseren)
    if (analyse_interval_ms_ > 0 && has_analysed_ &&
        now_ms - last_analysis_ms_ < analyse_interval_ms_) {
      frames_skipped_++;
      return static_cast<uint8_t>(flags | FLAG_SKIPPED);
    }

    has_analysed_ = true;
    last_analysis_ms_ = now_ms;
    frame_ = std::move(frame);
    checksum_ok_ = checksum_valid(*proto, frame_);
    frames_analysed_++;
    available_ = true;
    return static_cast<uint8_t>(flags | FLAG_ANALYSED);
  }

  uint32_t analyse_interval_ms_;
  std::string buffer_;
  bool overflow_{false};
  const ProtocolDef *protocol_{nullptr};
  std::string frame_;
  bool checksum_ok_{false};
  bool available_{false};
  bool has_analysed_{false};
  uint32_t last_analysis_ms_{0};
  uint32_t last_valid_ms_{0};
  const char *last_reason_{""};
  uint32_t frames_received_{0};
  uint32_t frames_analysed_{0};
  uint32_t frames_skipped_{0};
  uint32_t frames_invalid_{0};
};

}  // namespace elsner_core
