<!-- Versie: 0.1.2 (readme; components/elsner v0.1.0, esphome/*.yaml v0.1.2) -->

# Elsner P03/3 weerstation: ESPHome-variant

Deze map bevat een ESPHome-versie van de Home Assistant-integratie (`custom_components/elsner`, v0.0.8). De ESP32 leest het RS485-protocol van het weerstation en stuurt de meetwaarden via de ESPHome-API naar Home Assistant. Je hebt geen USB-adapter en geen Home Assistant-host nodig voor het uitlezen.

Het protocol, de velden en de throttle zijn gelijk aan de HA-versie. De timers en de reset-knop werken op ESP-manier (zie sectie 6). De code is wel anders: ESPHome-componenten zijn C++ met Python voor de configuratie. Het HA-Python kan daarom niet op de ESP draaien en is hier opnieuw geschreven.

**Status:** ik heb deze code niet met de echte ESPHome-compiler gebouwd (die was in mijn omgeving niet beschikbaar). Het protocol is wel getest tegen de echte HA-code, en de C++-glue tegen nep-ESPHome-headers. Zie [Testen](#7-testen) en [Bekende beperkingen](#9-bekende-beperkingen).

---

## Inhoud

- [Mapstructuur](#mapstructuur)
- [1. ESPHome koppelen aan GitHub](#1-esphome-koppelen-aan-github)
- [2. Hardware en bedrading](#2-hardware-en-bedrading)
- [3. Het protocol (inside information)](#3-het-protocol-inside-information)
- [4. Hoe de code werkt](#4-hoe-de-code-werkt)
- [5. Configuratie](#5-configuratie)
- [6. Verschillen met de HA-integratie](#6-verschillen-met-de-ha-integratie)
- [7. Testen](#7-testen)
- [8. Logmeldingen en problemen oplossen](#8-logmeldingen-en-problemen-oplossen)
- [9. Bekende beperkingen](#9-bekende-beperkingen)
- [10. Versies](#10-versies)

---

## Mapstructuur

```
Elsner-Meteo_peha/                          (root van de repo)
├── components/elsner/                       ESPHome-component (v0.1.0)  <- ESPHome haalt deze map op
│   ├── __init__.py                          hub: UART en analyse_interval
│   ├── const.py                             meetvelden met eenheid, icoon en device_class
│   ├── sensor.py                            sensor-platform
│   ├── binary_sensor.py                     binary_sensor-platform (regen, schemering, checksum)
│   ├── text_sensor.py                       text_sensor-platform (tekst en diagnose)
│   ├── button.py                            reset-knop
│   ├── elsner_core.h                        protocol + frame-parser, pure C++ (testbaar zonder ESPHome)
│   └── elsner.h / elsner.cpp                ESPHome-glue: UART-lus, timers, publicatie
├── custom_components/elsner/                HA-integratie (ongewijzigd, v0.0.8)
└── ESPHOME_alternative/elsner-esphome/esphome/
    ├── readme.md                            deze uitleg
    ├── elsner-package.yaml                  package: UART, hub en alle entiteiten
    ├── example-bluetooth-proxy.yaml         voorbeeld naast jouw Bluetooth-proxy
    └── tests/
        ├── test_parity.cpp                  C++-kant van de paritytest
        └── parity_ha.py                     vergelijkt de C++-parser met de echte HA-code
```

De map `components/elsner/` staat in de root van de repo, want daar zoekt ESPHome standaard. De package en de tests staan in `ESPHOME_alternative/elsner-esphome/esphome/`. De HA-integratie in `custom_components/` blijft zoals hij is.

---

## 1. ESPHome koppelen aan GitHub

Je hoeft de code niet te kopiëren. ESPHome haalt de component en de package bij het compileren op uit je GitHub-repo. Dat gebeurt met twee mechanismen:

| Mechanisme | Wat het ophaalt | Waarvoor |
|---|---|---|
| `external_components` (type `git`) | de map `components/elsner/` (C++ en Python) | de code van de component |
| `packages:` met `github://...` | een YAML-bestand | de hele configuratie (UART, hub, entiteiten) |

Het package `elsner-package.yaml` bevat zelf al een `external_components`-blok. Daarom is één regel genoeg in je eigen YAML:

```yaml
packages:
  esphome.bluetooth-proxy: github://esphome/bluetooth-proxies/esp32-generic/esp32-generic.yaml@main
  elsner: github://v12345vtm/Elsner-Meteo_peha/ESPHOME_alternative/elsner-esphome/esphome/elsner-package.yaml@main
```

De ketting bij compileren is dan:

```
esphome compile
 ├─ packages: haalt ESPHOME_alternative/elsner-esphome/esphome/elsner-package.yaml op uit GitHub
 │    └─ external_components: haalt components/elsner/ op uit de root van de repo (branch main)
 └─ jouw eigen YAML + Bluetooth-proxy-package
```

**Zelf doen als je het explicieter wilt**, zonder package:

```yaml
external_components:
  - source:
      type: git
      url: https://github.com/v12345vtm/Elsner-Meteo_peha
      ref: main
    refresh: 0s           # tijdens ontwikkelen: altijd opnieuw ophalen
    components: [elsner]

uart:
  id: uart_elsner
  rx_pin: 16
  tx_pin: 17
  baud_rate: 19200
  rx_buffer_size: 1024

elsner:
  id: elsner_hub
  uart_id: uart_elsner
```

**Praktische punten:**

- **Plaats van de component.** ESPHome zoekt de component standaard in `components/` in de root van de repo. Daarom staat `components/elsner/` daar, en heb je geen `path:` nodig. Een `path:` in `external_components` geeft in ESPHome een fout ("invalid option"), dus niet gebruiken.
- **Eén versie.** Zet `components/elsner/` op één plek. Maak geen kopie onder `ESPHOME_alternative/`, want dan krijg je twee versies die uit elkaar lopen.
- **Pushen.** De versie op GitHub moet de bijgewerkte bestanden bevatten, dus pushen naar `main` na elke wijziging. Pas `ref:` aan als je op een andere branch of tag werkt.
- **Controle.** Open de volgende links in de browser. Krijg je de inhoud te zien (en geen 404), dan vindt ESPHome de bestanden ook:
  - `https://raw.githubusercontent.com/v12345vtm/Elsner-Meteo_peha/main/ESPHOME_alternative/elsner-esphome/esphome/elsner-package.yaml`
  - `https://raw.githubusercontent.com/v12345vtm/Elsner-Meteo_peha/main/components/elsner/__init__.py`
- **Publieke repo.** `github://` werkt zonder login alleen bij een publieke repo.
- **Cache.** ESPHome bewaart de opgehaalde code en haalt hem op na `refresh`. Standaard is dat 1 dag. Zet `refresh: 0s` tijdens het ontwikkelen. Wil je de cache leegmaken, verwijder dan de map `.esphome/external_components` of gebruik `esphome clean`.
- **Privé-repo.** ESPHome kan ook een privé-repo ophalen met credentials (token). Zie de ESPHome-documentatie over `external_components`. Een publieke repo is eenvoudiger.
- **Lokaal ontwikkelen.** Wil je zonder GitHub werken, dan kun je de map lokaal kopiëren en `source: local` gebruiken (zie de ESPHome-docs).

---

## 2. Hardware en bedrading

Het weerstation praat RS485 (differentieel, A/B). De ESP32 praat TTL (3,3 V, één draad per richting). Daartussen heb je een **RS485-transceiver** nodig, bijvoorbeeld een MAX485/MAX3485-module of een TTL-RS485-board. Die vertaalt A/B naar TTL.

| Transceiver | ESP32 | Opmerking |
|---|---|---|
| RO (receiver output) | GPIO16 (`rx_pin`) | Dit is het belangrijke signaal |
| DI (driver input) | GPIO17 (`tx_pin`) | Optioneel, want we sturen niets naar het station |
| DE en RE | GND (of GPIO laag) | Laag = ontvangen. Zonder dit schakelt de chip niet goed |
| VCC | 3,3 V | Zie waarschuwing hieronder |
| A, B | A en B van het weerstation | Let op: A en B niet verwisselen |
| GND | GND | Gemeenschappelijke massa, anders veel ruis |

**Let op:**

- **5 V-modules.** Veel MAX485-modules zijn voor 5 V en geven op RO dan 5 V. Dat is te veel voor een ESP32-GPIO. Gebruik een 3,3 V-module of een level shifter.
- **A/B verwisseld.** Dan krijg je geen geldige frames. De log meldt dan een timeout of ongeldige frames. Verwissel A en B als het niet werkt.
- **Termination.** Bij een lange kabel of meerdere apparaten kan een 120 Ω-weerstand over A/B nodig zijn. Bij een korte kabel is dat meestal niet nodig.
- **PSRAM.** Sommige ESP32-modules (bijv. WROVER) gebruiken GPIO16 en GPIO17 intern voor PSRAM. Gebruik je zo'n module, kies dan andere pinnen via de substitutions `elsner_rx_pin` en `elsner_tx_pin`.
- **Seriële instellingen.** 19200 baud, 8 databits, geen pariteit, 1 stopbit (8N1). De component zet dat zelf goed.

---

## 3. Het protocol (inside information)

Alles hieronder komt uit `protocols.py` van de HA-integratie en is ook in `elsner_core.h` overgenomen.

### Frames

- Een frame is ASCII-tekst die begint met een **startteken** en eindigt met **ETX (0x03)**. Het ETX-teken is het enige scheidingsteken. Er is geen aparte CR/LF nodig.
- Het station stuurt twee varianten:
  - **`W` = CET** (Centraal-Europese tijd): 39 tekens, zonder ETX.
  - **`G` = GPS** (UTC plus positie en zon): 60 tekens, zonder ETX.
- De **eerste geldige frame bepaalt de variant**. Daarna worden frames van de andere variant genegeerd, tot een herstart.
- Spaties, CR en LF rond een frame worden verwijderd voordat het gecontroleerd wordt. Die worden dus niet als fout gezien.

### Velden

Posities zijn Python-slices: `[1:6]` betekent de tekens op index 1 t/m 5. Index 0 is het startteken.

| Sleutel | CET `W` | GPS `G` | Type | Opmerking |
|---|---|---|---|---|
| `temperature` | `[1:6]` | `[1:6]` | getal | °C, bijv. `+12.3` of `-05.3` |
| `sun_south` | `[6:8]` | `[6:8]` | geheel | klx |
| `sun_west` | `[8:10]` | `[8:10]` | geheel | klx |
| `sun_east` | `[10:12]` | `[10:12]` | geheel | klx |
| `twilight` | `[12:13]` | `[12:13]` | J/N | schemering |
| `daylight` | `[13:16]` | `[13:16]` | geheel | lx |
| `wind` | `[16:20]` | `[16:20]` | getal | m/s |
| `rain` | `[20:21]` | `[20:21]` | J/N | regen |
| `weekday` | `[21:22]` | `[21:22]` | tekst | GPS: UTC-weekdag |
| `day` | `[22:24]` | `[22:24]` | geheel | GPS: UTC |
| `month` | `[24:26]` | `[24:26]` | geheel | GPS: UTC |
| `year` | `[26:28]` | `[26:28]` | geheel | twee cijfers, bijv. `26` |
| `hour` | `[28:30]` | `[28:30]` | geheel | GPS: UTC |
| `minute` | `[30:32]` | `[30:32]` | geheel | GPS: UTC |
| `second` | `[32:34]` | `[32:34]` | geheel | GPS: UTC |
| `summer_time` | `[34:35]` | - | tekst | 1 teken. Betekenis niet in de code vastgelegd |
| `gps_status` | - | `[34:35]` | geheel | |
| `azimuth` | - | `[35:40]` | getal | ° |
| `elevation` | - | `[40:45]` | getal | ° |
| `longitude_direction` | - | `[45:46]` | tekst | |
| `longitude` | - | `[46:51]` | getal | ° |
| `latitude_direction` | - | `[51:52]` | tekst | |
| `latitude` | - | `[52:56]` | getal | ° |
| `checksum` | `[35:39]` | `[56:60]` | geheel | zie hieronder |

Voor getallen geldt: spaties worden genegeerd, en een ongeldig getal geeft `unavailable` (NaN) voor dat veld. Een J/N-veld is `aan` alleen bij `J` of `j`. Alles anders is `uit`.

### Checksum

De checksum is de som van de ASCII-waarden van alle tekens vóór de checksum, modulo 10⁴ (vier cijfers). Voorbeeld: bij een CET-frame reken je over `[0:35]` en vergelijk je met `[35:39]`.

De HA-code definieert deze controle, maar **gebruikt hem niet**: frames met een foute checksum worden gewoon verwerkt. De ESP-versie doet hetzelfde. De uitkomst zie je in de binary sensor `checksum_valid` (diagnose). Die is bedoeld om de formule op echte data te controleren. Als `checksum_valid` bij jouw station steeds `uit` is, klopt de formule niet en is de meetwaarde toch gewoon bruikbaar.

### Timing

- **Throttle (`analyse_interval`).** Het station stuurt vaker dan je wilt analyseren. Alleen een frame dat ten minste `analyse_interval` na de vorige analyse komt, wordt verwerkt. De andere tellen als `frames_skipped`. Standaard 5 s; `0s` = elk frame.
- **Frame-timeout (10 s).** Komt er 10 s geen frame binnen, dan krijg je een waarschuwing en worden de numerieke sensoren `unavailable`.
- **Stale (60 s).** Komt er 60 s geen **geldig** frame binnen (alleen ongeldige frames of niets), dan worden de sensoren `unavailable`.

---

## 4. Hoe de code werkt

### De keten van één byte

```
UART-byte
  └─ FrameParser.feed()                  (elsner_core.h)
       ├─ geen ETX  -> opslaan in buffer (max 256 bytes, anders overflow)
       └─ ETX       -> frame afsluiten
            ├─ strip whitespace
            ├─ startteken W of G?            nee -> INVALID ("unknown start character")
            ├─ zelfde variant als eerder?    nee -> INVALID ("another protocol")
            ├─ lengte klopt (39 of 60)?      nee -> INVALID ("wrong frame length")
            ├─ eerste geldige frame?         -> PROTOCOL_LOCKED (variant vastleggen)
            ├─ binnen analyse_interval?      -> SKIPPED
            └─ analyseren                    -> ANALYSED (checksum_valid, frame_ bijwerken)
  └─ ElsnerComponent::handle_flags_()    (elsner.cpp)
       ├─ PROTOCOL_LOCKED -> variant-sensor vullen, waarschuwen voor ontbrekende velden
       └─ ANALYSED        -> alle entiteiten vullen
```

### Bestanden en hun taak

- **`elsner_core.h`.** Bevat de protocoltabellen (CET en GPS), de tekstfuncties (strippen, getal, J/N), de checksum en de `FrameParser`. Dit bestand heeft geen ESPHome-afhankelijkheden. Daardoor kan de paritytest het direct testen.
- **`elsner.h` / `elsner.cpp`.** De ESPHome-component. Leest de UART in `loop()`, houdt de timers bij (frame-timeout, stale, tellers) en zet waarden op de entiteiten. Publiceert `NaN` voor numerieke sensoren om ze `unavailable` te maken.
- **`__init__.py`.** De hub: de UART-koppeling en het `analyse_interval`. Registreert de C++-klasse.
- **`const.py`.** Per meetveld de standaardwaarden: eenheid, icoon, device_class, aantal decimalen en entiteit-categorie. Die gelden als je ze zelf niet opgeeft.
- **`sensor.py`, `binary_sensor.py`, `text_sensor.py`.** Elke entiteit in je YAML wordt hier gevalideerd. De `with_defaults()`-functie in `__init__.py` vult de standaardwaarden in vóór de validatie.
- **`button.py`.** De reset-knop.

### Timers en tellers

- `loop()` leest alle beschikbare bytes. Daarna controleert hij frame-timeout en stale, en publiceert de tellers elke 10 s.
- De tellers `frames_received`, `frames_analysed`, `frames_skipped` en `frames_invalid` zijn sensoren met `state_class: total_increasing`.
- `raw_packet` is de laatst geanalyseerde frame, zonder ETX en zonder spaties eromheen. Niet-ASCII-tekens worden vervangen door `?`, zodat Home Assistant er geen last van heeft.

---

## 5. Configuratie

### Hub

```yaml
elsner:
  id: elsner_hub             # verplicht als je hem later wilt koppelen
  uart_id: uart_elsner       # de UART die bij het station hoort
  analyse_interval: 5s       # standaard 5s, 0s = elk frame
```

### Entiteiten

Elke entiteit heeft `platform: elsner`, `type:` (de sleutel uit de tabel in sectie 3) en `name:`. Met `elsner_id:` koppel je aan een hub, en dat mag weg als je maar één hub hebt.

| Platform | Types |
|---|---|
| `sensor` | `temperature`, `sun_south`, `sun_west`, `sun_east`, `daylight`, `wind`, `day`, `month`, `year`, `hour`, `minute`, `second`, `gps_status`, `azimuth`, `elevation`, `longitude`, `latitude`, `frames_received`, `frames_analysed`, `frames_skipped`, `frames_invalid` |
| `binary_sensor` | `twilight`, `rain`, `checksum_valid` |
| `text_sensor` | `weekday`, `summer_time`, `longitude_direction`, `latitude_direction`, `variant`, `raw_packet` |
| `button` | `reset_connection` (geen `type:`, alleen `name:`) |

De eenheid, het icoon en de device_class komen uit `const.py`. Wat je zelf opgeeft wint altijd:

```yaml
sensor:
  - platform: elsner
    elsner_id: elsner_hub
    type: temperature
    name: "Buitentemperatuur"
    accuracy_decimals: 2          # overschrijft de standaard van 1
```

### Meerdere stations

Elke hub heeft zijn eigen UART en zijn eigen `id`. De entiteiten moeten dan een andere `name:` krijgen, anders krijg je dubbele namen.

---

## 6. Verschillen met de HA-integratie

| Onderwerp | HA-integratie (0.0.8) | ESPHome-component (0.1.0) |
|---|---|---|
| Configuratie | via de UI (config flow) | via YAML |
| Checksum | berekend, maar niet gebruikt | berekend en als `checksum_valid` getoond; frames niet verworpen |
| Stale-controle | alleen als er een ongeldig frame binnenkomt | elke `loop()`, ook als er helemaal niets binnenkomt |
| Frame-timeout | verbinding met de poort opnieuw opbouwen | waarschuwing en `unavailable`; er is geen poort om te heropenen |
| Reset-knop | sluit en opent de seriële poort | leegt de RX-buffer, zet `unavailable`; het protocol blijft vergrendeld |
| `unavailable` | alle sensoren | alleen numerieke sensoren (NaN). Binary- en tekstsensoren houden de laatste waarde |
| Attributen van de raw-sensor | `variant`, `analysed_at`, tellers | aparte entiteiten (`variant`, `raw_packet`, `frames_*`). `analysed_at` is niet overgenomen |
| Tellers | attributen, bij elke analyse | sensoren, elke 10 s |
| Overflow-grens | 64 KiB (asyncio-standaard) | 256 bytes; ruim voor 60-tekens-frames |
| Velden | alle velden van de variant worden automatisch entiteit | je kiest zelf welke velden je wilt (zuiniger op de ESP) |
| Naamgeving | `<naam> Temperature` | ESPHome-apparaatnaam plus jouw `name:` |

---

## 7. Testen

### Paritytest (protocol)

Dit test of de C++-parser dezelfde uitkomst geeft als de echte HA-code. Het gebruikt geen ESPHome.

```bash
cd esphome/tests
g++ -std=c++17 -O1 -I../../../../components/elsner test_parity.cpp -o test_parity
python3 parity_ha.py --binary ./test_parity
```

Vereist: `g++` en Python 3 (geen extra pakketten).

Het script zoekt de map `custom_components` automatisch (omhoog vanaf het script). Het laadt daar `elsner/hub.py` en `protocols.py` zoals ze zijn. Alleen Home Assistant zelf wordt vervangen door stubs. Daarna stuurt het dezelfde frames naar beide kanten en vergelijkt per frame:

- de tellers (`received`, `analysed`, `skipped`, `invalid`)
- de variant (CET of GPS) en de checksum-uitkomst
- alle veldwaarden, inclusief `None` bij een ongeldig getal

De scenario's omvatten: CR/LF en spaties rond een frame, negatieve temperaturen, ongeldige getallen, een foute checksum, een frame van de verkeerde variant, een te kort frame, een leeg frame, en throttle over 5 s.

Het C++-binary draait ook zelftests: overflow, stale en het leegmaken van de buffer.

### Wat het niet test

- De UART-lus, de timers en de publicatie in ESPHome. Dat controleer je met `esphome compile` en een echt apparaat.
- De echte checksum-formule en de echte frames. Die zijn in de test gebouwd volgens dezelfde formule als de HA-code, niet uit een echt weerstation.

### Wat ik zelf nog heb gedaan (niet in de repo)

- De C++-glue gecompileerd tegen nep-ESPHome-headers (`-Wall -Wextra` schoon), met een test die de UART-invoer, de frame-timeout, stale, de reset-knop en de overflow doorloopt.
- De Python-modules geladen met een nep-`esphome`-package. Daarbij controleerde ik de defaults-functie en alle `to_code`-paden.
- De YAML gecontroleerd: geldige syntax en per `type:` of het bestaat voor het betreffende platform.

---

## 8. Logmeldingen en problemen oplossen

| Melding (niveau) | Betekenis | Wat te doen |
|---|---|---|
| `station protocol recognised: CET` (I) | Het eerste geldige frame is binnen. | Niets. |
| `frame discarded: ...` (D) | Eén frame is verworpen. De reden staat erbij. | Alleen zien bij `logger: level: DEBUG`. Een paar per minuut is normaal. |
| `unknown start character` (D) | Het frame begint niet met W of G. | Veel hiervan: baudrate, bedrading of ruis. |
| `wrong frame length` (D) | Het frame is niet 39 of 60 tekens. | Baudrate controleren; veel hiervan wijst op ruis of een afgekapt frame. |
| `station uses another protocol` (D) | Er komt een andere variant binnen dan het eerste frame. | Herstart de ESP. Waarschijnlijk is het station vervangen of gewisseld. |
| `no frame received for 10 seconds` (W) | Geen enkel frame. | Stroom van het station, A/B en de transceiver controleren. |
| `no valid data packet for 60 seconds` (W) | Er komen alleen ongeldige frames binnen. | Baudrate, protocolvariant en bedrading. |
| `frame longer than 256 bytes without ETX` (W) | Er komt veel ruis binnen zonder scheidingsteken. | Baudrate, bedrading en GND. |
| `field 'X' does not exist in the CET protocol` (W) | Je hebt een GPS-entiteit maar het station stuurt CET. | Verwijder die entiteit of gebruik de GPS-variant. |
| `reset requested ...` (I) | De reset-knop is ingedrukt. | Niets. |

**Snelle diagnose:** zet `logger: level: DEBUG` aan en kijk naar de tellers. Veel `frames_invalid` met `unknown start character` wijst op een verkeerde baudrate of verwisselde draden. Geen enkel `frames_received` wijst op de bedrading of de transceiver.

---

## 9. Bekende beperkingen

- **Niet met echte ESPHome gecompileerd.** Eerst `esphome compile` draaien. Stuur me de fouten als die er zijn. De aannames over de ESPHome-API (`uart`, `sensor_schema`, `button_schema`, `publish_state` met NaN) zijn gebaseerd op bekende patronen, maar ik kon ze niet tegen de echte bibliotheek controleren.
- **Geen echt weerstation getest.** De protocollogica is getest met synthetische frames die volgens de HA-code zijn opgebouwd. Of het station precies dit formaat stuurt, weet ik niet zeker zonder echte data.
- **Checksum niet bevestigd.** Zie de sectie over de checksum.
- **Aantal decimalen van lengte- en breedtegraad** (`accuracy_decimals: 4`) is een schatting. Pas het aan op wat je station levert.
- **`summer_time`** is 1 teken; de betekenis is niet in de HA-code vastgelegd.
- **Tekst- en binary sensoren worden niet `unavailable`.** Ze houden de laatste waarde. Dat kan ESPHome niet op dezelfde manier als voor numerieke sensoren.
- **Reset-knop** leegt alleen de buffer. Het protocol blijft vergrendeld zoals in de HA-versie.
- **Eén variant per station.** Wisselt het station van CET naar GPS, dan moet je de ESP herstarten.
- **Tijdstempel `analysed_at`** is niet overgenomen (ESPHome heeft geen tijdsbron zonder `time:`-component).

---

## 10. Versies

| Versie | Wat |
|---|---|
| 0.1.0 | Eerste ESPHome-variant van HA-integratie 0.0.8. Protocol, velden, throttle, timers, reset-knop en paritytest. |
| 0.1.1 | Package-URL naar `ESPHOME_alternative/elsner-esphome/esphome/`. Testscript zoekt `custom_components` automatisch. |
| 0.1.2 | `components/elsner/` verplaatst naar de root van de repo. `path:` verwijderd uit `external_components`, omdat ESPHome die optie niet accepteert op dat niveau. |
