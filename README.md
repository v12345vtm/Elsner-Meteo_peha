# Elsner P03/3-RS485 weerstation voor Home Assistant

Deze custom integratie leest de datapakketten van een Elsner P03/3-RS485 weerstation en maakt er sensoren van in Home Assistant. Het weerstation sluit je via RS485 en een RS485-naar-USB-adapter aan op de computer waarop Home Assistant draait. Alles werkt lokaal, zonder cloud.

**Versie 0.0.8** · domein `elsner`


![Elsner OEM or Peha meteo](https://i.imgur.com/j1rQMRT.png)


## Inhoud

- [Wat doet de integratie](#wat-doet-de-integratie)
- [Wat je nodig hebt](#wat-je-nodig-hebt)
- [Installatie](#installatie)
- [Instellingen](#instellingen)
- [Overnemen van je YAML-configuratie](#overnemen-van-je-yaml-configuratie)
- [Entiteiten](#entiteiten)
- [Analyse-interval](#analyse-interval)
- [Automatisch resetten bij uitval](#automatisch-resetten-bij-uitval)
- [Probleemoplossing](#probleemoplossing)
- [Technische details](#technische-details)
- [Wijzigingen](#wijzigingen)
- [Problemen melden](#problemen-melden)

## Wat doet de integratie

- Leest elk datapakket van het weerstation via de USB/RS485-poort.
- Maakt per meetwaarde een sensor: temperatuur, wind, regen, zonlicht, schemering, datum en tijd. De GPS-variant voegt daar positie (breedte- en lengtegraad), azimut, elevatie en GPS-status aan toe.
- Toont het laatst geanalyseerde ruwe datapakket in een diagnose-sensor, zodat je ziet wat het weerstation stuurt.
- Heeft een knop om de USB-verbinding opnieuw op te zetten.
- Wordt helemaal ingesteld in de gebruikersinterface van Home Assistant.

De integratie herkent zelf welke variant je weerstation heeft: **CET** (datapakketten die beginnen met `W`) of **GPS** (beginnen met `G`).

## Wat je nodig hebt

- Home Assistant, een recente versie.
- Een Elsner P03/3-RS485 weerstation met CET- of GPS-uitvoer.
- Een RS485-naar-USB-adapter, aangesloten op de A- en B-aansluitingen van het weerstation. Volg de bedradingsinstructies van het weerstation.
- Toegang tot de USB-poort vanuit Home Assistant. Zie [De poort vinden](#de-poort-vinden).

De benodigde Python-bibliotheek (`pyserial-asyncio-fast`) wordt automatisch geïnstalleerd.

## Installatie

1. Kopieer de map `custom_components/elsner` naar de map `custom_components` in je Home Assistant-configuratiemap. Dat is de map waarin ook `configuration.yaml` staat. Het resultaat is `config/custom_components/elsner/`.
2. Controleer of de map de bestanden bevat zoals in [Mappenstructuur](#mappenstructuur), inclusief de map `translations`.
3. Herstart Home Assistant volledig. Een herlaad van de integratie is niet genoeg, omdat het manifest is veranderd.
4. Ga naar **Instellingen > Apparaten en diensten**, klik op **Integratie toevoegen** en zoek op **Elsner**.

## Instellingen

Bij het toevoegen vul je drie velden in:

| Veld | Betekenis | Standaard |
|---|---|---|
| **Naam** | Voorvoegsel voor de namen van de entiteiten, bijvoorbeeld `Weather station`. | `Weather station` |
| **USB/RS485-poort** | Het pad naar de adapter, bijvoorbeeld `/dev/serial/by-id/...`. | `/dev/ttyUSB0` |
| **Analyse-interval (seconden)** | Minimale tijd tussen twee geanalyseerde datapakketten. `0` betekent elk datapakket analyseren. | `5` |

### De poort vinden

Het pad `/dev/ttyUSB0` kan na een herstart of herplaatsing veranderen. Kies daarom bij voorkeur een vast pad uit `/dev/serial/by-id/`:

```bash
ls -l /dev/serial/by-id/
```

Kies de regel die bij jouw adapter hoort. Voer het commando uit in de terminal van de machine waarop Home Assistant draait. Op Home Assistant OS heb je daarvoor een terminal-add-on nodig die toegang heeft tot USB.

### Instellingen wijzigen

1. Ga naar **Instellingen > Apparaten en diensten** en open **Elsner**.
2. Klik op **Configureren**, pas de waarden aan en sla op.

De integratie laadt daarna opnieuw. De entity_id's blijven hetzelfde, dus dashboards en automatiseringen blijven werken. Een andere naam verandert alleen de weergavenaam van de entiteiten.

## Overnemen van je YAML-configuratie

Had je de integratie eerder in `configuration.yaml` staan?

```yaml
sensor:
  - platform: elsner
    serial_port: /dev/ttyUSB0
    name: Weather station
```

Dan wordt die instelling bij de eerste start automatisch overgenomen in de gebruikersinterface. Verwijder daarna het blok uit `configuration.yaml`. Bij het overnemen krijgt het analyse-interval de standaardwaarde van 5 seconden. Wijzig dat via **Configureren** als je elk datapakket wilt analyseren.

## Entiteiten

Elke entiteit krijgt de naam die je bij **Naam** hebt ingevuld, gevolgd door de veldnaam. Met de standaardnaam ontstaan bijvoorbeeld `sensor.weather_station_temperature` en `sensor.weather_station_wind`. De veldnamen staan in het Engels, zoals ze in Home Assistant verschijnen. Alle entiteiten horen bij één apparaat met dezelfde naam.

### Meetsensoren

Welke sensoren je krijgt, hangt af van de variant van je weerstation. Bij de CET-variant zijn datum en tijd Centraal-Europese tijd. Bij de GPS-variant zijn ze in UTC. Schemering (Twilight) en regen (Rain) tonen `True` of `False`.

De kolom **Tekens** geeft de posities in het datapakket, geteld vanaf 0. Het startteken staat op positie 0.

<details>
<summary>Sensoren van de CET-variant (startteken W)</summary>

| Veld | Tekens | Eenheid | Type |
|---|---|---|---|
| Temperature | 1–5 | °C | decimaal getal |
| Sun south | 6–7 | klx | geheel getal |
| Sun west | 8–9 | klx | geheel getal |
| Sun east | 10–11 | klx | geheel getal |
| Twilight | 12 | - | True / False |
| Daylight | 13–15 | lx | geheel getal |
| Wind | 16–19 | m/s | decimaal getal |
| Rain | 20 | - | True / False |
| Weekday | 21 | - | tekst |
| Day | 22–23 | - | geheel getal |
| Month | 24–25 | - | geheel getal |
| Year | 26–27 | - | geheel getal |
| Hour | 28–29 | - | geheel getal |
| Minute | 30–31 | - | geheel getal |
| Second | 32–33 | - | geheel getal |
| Summer time | 34 | - | tekst |

</details>

<details>
<summary>Sensoren van de GPS-variant (startteken G)</summary>

| Veld | Tekens | Eenheid | Type |
|---|---|---|---|
| Temperature | 1–5 | °C | decimaal getal |
| Sun south | 6–7 | klx | geheel getal |
| Sun west | 8–9 | klx | geheel getal |
| Sun east | 10–11 | klx | geheel getal |
| Twilight | 12 | - | True / False |
| Daylight | 13–15 | lx | geheel getal |
| Wind | 16–19 | m/s | decimaal getal |
| Rain | 20 | - | True / False |
| UTC weekday | 21 | - | tekst |
| UTC day | 22–23 | - | geheel getal |
| UTC month | 24–25 | - | geheel getal |
| UTC year | 26–27 | - | geheel getal |
| UTC hour | 28–29 | - | geheel getal |
| UTC minute | 30–31 | - | geheel getal |
| UTC second | 32–33 | - | geheel getal |
| GPS Status | 34 | - | geheel getal |
| Azimuth | 35–39 | ° | decimaal getal |
| Elevation | 40–44 | ° | decimaal getal |
| Longitude Direction | 45 | - | tekst |
| Longitude | 46–50 | ° | decimaal getal |
| Latitude Direction | 51 | - | tekst |
| Latitude | 52–55 | ° | decimaal getal |

</details>

### Raw packet (diagnose)

De sensor **Raw packet** is een diagnose-sensor. Zijn status is het laatst geanalyseerde datapakket. Een Home Assistant-status mag maximaal 255 tekens lang zijn, daarom staat de volledige tekst in het attribuut `raw`.

| Attribuut | Betekenis |
|---|---|
| `raw` | Het volledige datapakket, zonder het afsluitende ETX-teken |
| `variant` | `CET` of `GPS` |
| `length` | Lengte van het datapakket |
| `analysed_at` | Tijdstip van de laatste analyse (UTC) |
| `analyse_interval` | Het ingestelde analyse-interval in seconden |
| `frames_received` | Aantal ontvangen datapakketten sinds de laatste start of herlaad |
| `frames_analysed` | Aantal geanalyseerde datapakketten |
| `frames_skipped` | Aantal datapakketten dat door het interval is overgeslagen |
| `frames_invalid` | Aantal afgekeurde datapakketten (verkeerd startteken, verkeerde lengte of andere variant) |

### Knop Reset USB connection

Met de knop **Reset USB connection** sluit de integratie de seriële poort en opent die opnieuw. De entiteit heet standaard `button.weather_station_reset_usb_connection`.

Gebruik de knop als de sensoren niet meer worden bijgewerkt, of na het losmaken en opnieuw aansluiten van de adapter. De variant blijft daarbij bewaard. Heeft de adapter een ander pad gekregen, dan helpt de knop niet. Pas de poort dan eerst aan via **Configureren**.

## Analyse-interval

Het weerstation stuurt regelmatig datapakketten. Het analyse-interval bepaalt hoe vaak de integratie er één verwerkt:

- **5** (standaard): er wordt hooguit één datapakket per 5 seconden geanalyseerd. De sensoren worden dan ongeveer elke 5 seconden bijgewerkt.
- **0**: elk datapakket wordt geanalyseerd, zoals in versie 0.0.6.

Pakketten die worden overgeslagen, worden wel ontvangen en geteld. De verbinding blijft dus actief, en Home Assistant hoeft minder werk te doen.

## Automatisch resetten bij uitval

Wil je dat de integratie zichzelf herstelt als de sensoren te lang onbeschikbaar zijn? Maak dan een automatisering die de reset-knop indrukt. Pas de entity_id's aan als je een andere naam hebt gekozen. Dit voorbeeld werkt vanaf Home Assistant 2024.10.

```yaml
automation:
  - alias: Elsner weerstation resetten bij uitval
    triggers:
      - trigger: state
        entity_id: sensor.weather_station_temperature
        to: unavailable
        for: "00:02:00"
    actions:
      - action: button.press
        target:
          entity_id: button.weather_station_reset_usb_connection
```

Let op: deze automatisering reset ook als het weerstation zelf uitstaat. Dat is meestal geen probleem, maar je ziet het wel in het logboek.

## Probleemoplossing

Begin bij het logboek: ga naar **Instellingen > Systeem > Logboeken** en filter op `elsner`. Wil je meer details, zet dan debug-logging aan in `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.elsner: debug
```

Deze meldingen komen het vaakst voor:

| Melding in het logboek | Waarschijnlijke oorzaak | Wat je kunt doen |
|---|---|---|
| `could not open the serial port` | De poort bestaat niet, of Home Assistant heeft er geen toegang toe. | Controleer het pad met `ls -l /dev/serial/by-id/`. Draait Home Assistant in een Docker-container, geef de poort dan door aan de container, bijvoorbeeld met `--device`. |
| `serial port no longer exists` | De adapter is losgekoppeld of heeft een ander pad gekregen. | Sluit de adapter opnieuw aan. Heeft hij een ander pad, pas de poort dan aan via **Configureren**. |
| `no frame received` | De poort bestaat, maar er komt geen data binnen. | Controleer de voeding van het weerstation en de bedrading van A en B. Probeer A en B eens om te wisselen. |
| `only invalid frames` | Er komen datapakketten binnen, maar ze worden afgekeurd. | Controleer de bedrading en de variant. Kijk ook naar `frames_invalid` in de Raw packet-sensor. |
| `frame exceeded buffer limit` | Pakketten worden niet met het ETX-teken afgesloten. | Dat wijst meestal op een verkeerd signaal of bedrading. Controleer de aansluiting van de adapter. |

Verder komen deze situaties regelmatig voor:

- **Na het wisselen van weerstation** (van CET naar GPS of omgekeerd) komen er geen waarden meer. De variant wordt bij het eerste geldige datapakket vastgelegd. Herlaad de integratie via het menu met de drie puntjes, met **Herladen**.
- **De waarden lopen achter.** Het analyse-interval staat waarschijnlijk hoger dan je wilt. Zet het op `0`.
- **De integratie reageert niet meer.** Druk op **Reset USB connection**. Helpt dat niet, herstart dan Home Assistant en meld het probleem met de logregels, zie [Problemen melden](#problemen-melden).

## Technische details

### Datapakket

- Een datapakket begint met het startteken `W` (CET) of `G` (GPS) en eindigt met het teken ETX (`0x03`).
- De lengte is vast: 39 tekens voor `W` en 60 tekens voor `G`, zonder het ETX-teken.
- De seriële verbinding gebruikt 19200 baud.
- Het eerste geldige datapakket bepaalt de variant. Die blijft vastgelegd tot de integratie opnieuw wordt geladen.
- De checksum wordt uitgelezen, maar nog niet gecontroleerd, en niet als sensor getoond.

### Tijdgedrag

| Instelling | Waarde | Betekenis |
|---|---|---|
| Wachttijd op een datapakket | 10 seconden | Komt er binnen 10 seconden geen volledig datapakket, dan wordt de poort opnieuw geopend. |
| Pauze tussen twee pogingen | 5 seconden | Wachttijd voordat de integratie de poort opnieuw probeert te openen. |
| Geen geldig datapakket | 60 seconden | Komen er 60 seconden geen geldige datapakketten binnen, maar wel ongeldige, dan worden de sensoren onbeschikbaar. |

### Mappenstructuur

```text
Elsner-Meteo_peha/
├── README.md
└── custom_components/
    └── elsner/
        ├── __init__.py
        ├── button.py
        ├── config_flow.py
        ├── const.py
        ├── hub.py
        ├── manifest.json
        ├── protocols.py
        ├── sensor.py
        └── translations/
            ├── en.json
            └── nl.json
```

## Wijzigingen

### 0.0.8

- Instellingen via de gebruikersinterface: naam, poort en analyse-interval.
- Eenmalige overname van de YAML-configuratie.
- Analyse-interval, standaard 5 seconden.
- Diagnose-sensor **Raw packet** met het ruwe datapakket en tellers.
- Knop **Reset USB connection**.
- De seriële verbinding wordt altijd eerst gesloten voordat er opnieuw wordt geopend.
- Sensoren worden onbeschikbaar als er alleen ongeldige datapakketten binnenkomen.

### 0.0.6

- Configuratie via `configuration.yaml`.

## Problemen melden

Heb je een probleem of een idee? Open dan een [issue](https://github.com/v12345vtm/Elsner-Meteo_peha/issues). Voeg de versie van de integratie, de logregels (filter op `elsner`) en de waarde van `frames_invalid` toe.
