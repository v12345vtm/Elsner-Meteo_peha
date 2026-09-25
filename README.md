# Elsner Sensor

### Installation

Copy this elsner folder to `<config_dir>/custom_components/elsner/`.

Add the following to your `configuration.yaml` file:

```yaml
# configuration.yaml entry
#sensor:
  - platform: elsner
    name: weather_station
    serial_port: /dev/ttyACM1
    variant: cet   # optioneel, "cet" is de default
    
```
 Architectuur-voorstel

In plaats van 1 ruwe string-sensor + losse template:-sensoren met handmatige slices (foutgevoelig, zoals we al zagen), splits ik het in drie lagen:

protocols.py — puur data: per variant (cet, gps, plain) een lijst van velden met hun byte-offsets, eenheid en type-cast. Dit is het enige bestand dat je aanpast om GPS of de kale variant toe te voegen.
Eén gedeelde ElsnerHub — leest de seriële poort (met de readuntil(b"\x03")-fix van hiervoor), kiest het protocol op basis van config, parsed elk frame naar een dict, en verspreidt die naar alle entiteiten.
ElsnerFieldSensor — één sensor-entiteit per veld uit het protocol, automatisch aangemaakt. Geen template: YAML meer nodig.



Dit levert automatisch aparte entiteiten op: sensor.weather_station_temperature, ..._wind, ..._sun_south, ..._daylight, ..._rain, ..._day, ..._month, ..._year, ..._hour, ..._minute, ..._second, ..._summer_time, enz. — elk al correct getypeerd (float/int/bool) en met de juiste eenheid.






De checksum klopt zelfs voor alle testframes — dat is een mooie bevestiging dat de veldindeling exact goed is (en je kunt verify_checksum() later gebruiken om corrupte frames automatisch te laten weggooien).





Later GPS of "plain" toevoegen

Als je ooit een GPS- of niet-CET-variant wilt uitlezen, hoef je alleen in protocols.py:

GPS_FIELDS (of PLAIN_FIELDS) te vullen met de byte-offsets uit de betreffende datasheet-tabel (zelfde patroon als CET_FIELDS),
de bijbehorende regel in PROTOCOLS te uncommenten,

en dan variant: gps te zetten in je YAML. sensor.py en de hub-logica blijven ongewijzigd — dat is precies de modulariteit die je zocht.


