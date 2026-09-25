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
