/*
  Simpele UART-simulator voor het Elsner P03/3-RS485-CET dataformaat.
  Stuurt elke seconde één van 10 voorbeeldframes uit over de gewone
  seriële poort (UART), zoals het echte station elke seconde een frame
  stuurt.

  Formaat (40 bytes, ASCII):
    'W' + temperatuur + zon zuid/west/oost + schemering + daglicht
        + wind + regen + weekdag + datum + tijd + zomertijd
        + checksum (4 cijfers) + 0x03 (einde)

  Serial: 19200 baud, 8N1 -- zelfde instelling als het echte station.
*/

const uint8_t FRAME_LEN = 40;
const uint16_t SEND_INTERVAL_MS = 1000;

const char* frames[] = {
  "W+21.3451203N58303.4N4240926143207J1884\x03",  // Zonnige namiddag: 21.3C
  "W-02.1000000J00806.7J4240926064530N1863\x03",  // Koude regenachtige ochtend: -2.1C
  "W+12.0000000N00100.3N4240926231000J1836\x03",  // Heldere windstille nacht: 12.0C
  "W+09.4020101N04518.9J4240926160522J1879\x03",  // Storm met zware wind en regen: 9.4C
  "W+14.2030201J05501.1N4240926071500J1857\x03",  // Lichte ochtendschemering: 14.2C
  "W+31.7928820N99902.0N5250926130000J1898\x03",  // Hete zomerdag: 31.7C
  "W-09.6000000J00400.5N5250926034015N1864\x03",  // Strenge vorst 's nachts: -9.6C
  "W+07.8040302N12000.8N5250926090000J1869\x03",  // Mistige ochtend: 7.8C
  "W+16.5302510N70004.2N5250926113045J1875\x03",  // Gematigde voorjaarsdag: 16.5C
  "W+11.1010100J01205.6N5250926205510J1853\x03",  // Late avondschemering: 11.1C
};

const uint8_t NUM_FRAMES = sizeof(frames) / sizeof(frames[0]);
uint8_t frameIndex = 0;
unsigned long lastSendTime = 0;

void setup() {
  Serial.begin(19200);
  lastSendTime = millis();
}

void loop() {
  unsigned long now = millis();
  if (now - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime = now;
    Serial.write((const uint8_t*)frames[frameIndex], FRAME_LEN);
    frameIndex = (frameIndex + 1) % NUM_FRAMES;
  }
}
