// Versie: 0.1.0
//
// Paritytest-binary voor components/elsner/elsner_core.h.
// Leest regels van stdin:
//   I <interval_ms>          stel het analyse-interval in
//   T <tijd_ms> <hex>        voer de bytes (inclusief ETX 0x03) in op dit tijdstip
// en schrijft voor elke T-regel één JSON-regel met de toestand van de parser.
// Vóór het inlezen draaien een paar zelftests (overflow, stale, reset-buffer).
//
// Bouwen: g++ -std=c++17 -O1 -I../../components/elsner test_parity.cpp -o test_parity
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <string>

#include "elsner_core.h"

using namespace elsner_core;

namespace {

void expect(bool cond, const char *what) {
  if (!cond) {
    std::fprintf(stderr, "SELFTEST FAILED: %s\n", what);
    std::exit(1);
  }
}

std::string with_checksum(const std::string &payload) {
  uint64_t sum = 0;
  for (unsigned char c : payload) sum += c;
  char buf[8];
  std::snprintf(buf, sizeof buf, "%04u", static_cast<unsigned>(sum % 10000));
  return payload + buf;
}

void feed_all(FrameParser &p, const std::string &bytes, uint32_t t, uint8_t &flags) {
  for (unsigned char c : bytes) flags |= p.feed(c, t);
}

void self_tests() {
  const std::string payload = "W+12.3" "45" "12" "03" "N" "120" "03.5" "J" "3" "18" "10" "26" "12" "34" "56" "S";
  const std::string good = with_checksum(payload);
  expect(good.size() == 39, "CET test frame has 39 characters");

  // 1. Overflow: meer dan MAX_FRAME_BUFFER bytes zonder ETX
  {
    FrameParser p(0);
    uint8_t flags = 0;
    for (size_t i = 0; i < MAX_FRAME_BUFFER + 44; i++) flags |= p.feed('A', 0);
    expect(flags & FLAG_OVERFLOW, "overflow is signalled");
    uint8_t f = p.feed(ETX, 0);
    expect(f & FLAG_INVALID, "the overflowed frame is discarded at its ETX");
    flags = 0;
    feed_all(p, good, 1, flags);
    flags |= p.feed(ETX, 1);
    expect(flags & FLAG_ANALYSED, "parser recovers after overflow");
  }

  // 2. Stale: na STALE_TIMEOUT zonder geldig frame wordt de status unavailable
  {
    FrameParser p(0);
    uint8_t flags = 0;
    feed_all(p, good, 1000, flags);
    flags |= p.feed(ETX, 1000);
    expect(p.available(), "available after a valid frame");
    expect(!p.check_stale(1000 + STALE_TIMEOUT_MS), "not stale exactly at the timeout");
    expect(p.check_stale(1000 + STALE_TIMEOUT_MS + 1), "stale after the timeout");
    expect(!p.check_stale(1000 + STALE_TIMEOUT_MS + 2), "stale is reported once");
    expect(!p.available(), "unavailable after stale");
  }

  // 3. Reset-buffer: een half frame wordt weggegooid
  {
    FrameParser p(0);
    uint8_t flags = 0;
    feed_all(p, good.substr(0, 20), 0, flags);
    p.drop_partial();
    flags = 0;
    feed_all(p, good.substr(20), 0, flags);
    flags |= p.feed(ETX, 0);
    expect(flags & FLAG_INVALID, "the rest of a dropped frame is not a valid frame");
    flags = 0;
    feed_all(p, good, 0, flags);
    flags |= p.feed(ETX, 0);
    expect(flags & FLAG_ANALYSED, "a complete frame after drop_partial is analysed");
  }

  std::fprintf(stderr, "selftests OK\n");
}

std::string json_for(const FrameParser &p) {
  std::string o = "{";
  o += "\"received\":" + std::to_string(p.frames_received());
  o += ",\"analysed\":" + std::to_string(p.frames_analysed());
  o += ",\"skipped\":" + std::to_string(p.frames_skipped());
  o += ",\"invalid\":" + std::to_string(p.frames_invalid());
  o += ",\"variant\":";
  o += p.protocol() ? std::string("\"") + p.protocol()->variant + "\"" : std::string("null");
  o += ",\"checksum_ok\":";
  if (p.frames_analysed() == 0) {
    o += "null";
  } else {
    o += p.checksum_ok() ? "true" : "false";
  }
  o += ",\"values\":";
  if (p.frames_analysed() == 0 || p.protocol() == nullptr) {
    o += "null";
    o += "}";
    return o;
  }
  o += "{";
  const ProtocolDef &pr = *p.protocol();
  for (size_t i = 0; i < pr.field_count; i++) {
    const FieldDef &f = pr.fields[i];
    if (i > 0) o += ",";
    o += "\"";
    o += f.key;
    o += "\":";
    if (f.kind == Kind::FLAG) {
      o += read_flag(f, p.frame()) ? "true" : "false";
    } else if (f.kind == Kind::TEXT) {
      o += "\"" + read_text(f, p.frame()) + "\"";
    } else {
      double v = NAN;
      if (read_number(f, p.frame(), v)) {
        char buf[64];
        std::snprintf(buf, sizeof buf, "%.17g", v);
        o += buf;
      } else {
        o += "null";
      }
    }
  }
  o += "}}";
  return o;
}

}  // namespace

int main() {
  self_tests();

  FrameParser parser(5000);
  std::string line;
  while (std::getline(std::cin, line)) {
    if (line.empty()) continue;
    std::istringstream in(line);
    char kind = 0;
    in >> kind;
    if (kind == 'I') {
      uint32_t ms = 0;
      in >> ms;
      parser.set_analyse_interval(ms);
    } else if (kind == 'T') {
      uint32_t t = 0;
      std::string hex;
      in >> t >> hex;
      for (size_t i = 0; i + 1 < hex.size(); i += 2) {
        const auto b = static_cast<uint8_t>(std::stoul(hex.substr(i, 2), nullptr, 16));
        parser.feed(b, t);
      }
      std::cout << json_for(parser) << "\n";
    }
  }
  return 0;
}
