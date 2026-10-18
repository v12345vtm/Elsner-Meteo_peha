# Versie: 0.1.0
"""Constanten en standaardwaarden voor de ESPHome-variant van de Elsner-integratie.

De sleutels (bijv. "temperature") zijn gelijk aan de veldnamen in protocols.py van de
HA-integratie, zodat beide varianten dezelfde namen gebruiken.
"""
from esphome.const import (
    CONF_ACCURACY_DECIMALS,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_ICON,
    CONF_STATE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
)

CONF_ELSNER_ID = "elsner_id"
CONF_ANALYSE_INTERVAL = "analyse_interval"

_DIAG = "diagnostic"
_MEAS = "measurement"
_COUNTER = "total_increasing"

# Numerieke meetvelden en diagnose-tellers.
SENSOR_DEFAULTS = {
    "temperature": {CONF_UNIT_OF_MEASUREMENT: "°C", CONF_DEVICE_CLASS: "temperature",
                    CONF_ACCURACY_DECIMALS: 1, CONF_STATE_CLASS: _MEAS, CONF_ICON: "mdi:thermometer"},
    "sun_south": {CONF_UNIT_OF_MEASUREMENT: "klx", CONF_ACCURACY_DECIMALS: 0,
                  CONF_STATE_CLASS: _MEAS, CONF_ICON: "mdi:sun-compass"},
    "sun_west": {CONF_UNIT_OF_MEASUREMENT: "klx", CONF_ACCURACY_DECIMALS: 0,
                 CONF_STATE_CLASS: _MEAS, CONF_ICON: "mdi:sun-compass"},
    "sun_east": {CONF_UNIT_OF_MEASUREMENT: "klx", CONF_ACCURACY_DECIMALS: 0,
                 CONF_STATE_CLASS: _MEAS, CONF_ICON: "mdi:sun-compass"},
    "daylight": {CONF_UNIT_OF_MEASUREMENT: "lx", CONF_DEVICE_CLASS: "illuminance",
                 CONF_ACCURACY_DECIMALS: 0, CONF_STATE_CLASS: _MEAS, CONF_ICON: "mdi:brightness-5"},
    "wind": {CONF_UNIT_OF_MEASUREMENT: "m/s", CONF_ACCURACY_DECIMALS: 1,
             CONF_STATE_CLASS: _MEAS, CONF_ICON: "mdi:weather-windy"},
    # Datum- en tijdvelden: in de HA-integratie gewone sensoren, hier diagnose om het dashboard rustig te houden.
    "day": {CONF_ACCURACY_DECIMALS: 0, CONF_ENTITY_CATEGORY: _DIAG, CONF_ICON: "mdi:calendar"},
    "month": {CONF_ACCURACY_DECIMALS: 0, CONF_ENTITY_CATEGORY: _DIAG, CONF_ICON: "mdi:calendar-month"},
    "year": {CONF_ACCURACY_DECIMALS: 0, CONF_ENTITY_CATEGORY: _DIAG, CONF_ICON: "mdi:calendar"},
    "hour": {CONF_ACCURACY_DECIMALS: 0, CONF_ENTITY_CATEGORY: _DIAG, CONF_ICON: "mdi:clock-outline"},
    "minute": {CONF_ACCURACY_DECIMALS: 0, CONF_ENTITY_CATEGORY: _DIAG, CONF_ICON: "mdi:clock-outline"},
    "second": {CONF_ACCURACY_DECIMALS: 0, CONF_ENTITY_CATEGORY: _DIAG, CONF_ICON: "mdi:clock-outline"},
    # GPS-variant
    "gps_status": {CONF_ACCURACY_DECIMALS: 0, CONF_ICON: "mdi:crosshairs-gps"},
    "azimuth": {CONF_UNIT_OF_MEASUREMENT: "°", CONF_ACCURACY_DECIMALS: 1,
                CONF_STATE_CLASS: _MEAS, CONF_ICON: "mdi:compass-outline"},
    "elevation": {CONF_UNIT_OF_MEASUREMENT: "°", CONF_ACCURACY_DECIMALS: 1,
                  CONF_STATE_CLASS: _MEAS, CONF_ICON: "mdi:angle-acute"},
    # Aantal decimalen is een schatting: het protocol geeft 4 tekens door voor lat/lon.
    "longitude": {CONF_UNIT_OF_MEASUREMENT: "°", CONF_ACCURACY_DECIMALS: 4,
                  CONF_STATE_CLASS: _MEAS, CONF_ICON: "mdi:map-marker"},
    "latitude": {CONF_UNIT_OF_MEASUREMENT: "°", CONF_ACCURACY_DECIMALS: 4,
                 CONF_STATE_CLASS: _MEAS, CONF_ICON: "mdi:map-marker"},
    # Diagnose-tellers (in de HA-integratie attributen van de raw-sensor)
    "frames_received": {CONF_ACCURACY_DECIMALS: 0, CONF_STATE_CLASS: _COUNTER,
                        CONF_ENTITY_CATEGORY: _DIAG, CONF_ICON: "mdi:counter"},
    "frames_analysed": {CONF_ACCURACY_DECIMALS: 0, CONF_STATE_CLASS: _COUNTER,
                        CONF_ENTITY_CATEGORY: _DIAG, CONF_ICON: "mdi:counter"},
    "frames_skipped": {CONF_ACCURACY_DECIMALS: 0, CONF_STATE_CLASS: _COUNTER,
                       CONF_ENTITY_CATEGORY: _DIAG, CONF_ICON: "mdi:counter"},
    "frames_invalid": {CONF_ACCURACY_DECIMALS: 0, CONF_STATE_CLASS: _COUNTER,
                       CONF_ENTITY_CATEGORY: _DIAG, CONF_ICON: "mdi:counter"},
}

# Aan/uit-velden. J = aan, N = uit (zie protocols.py _flag).
BINARY_SENSOR_DEFAULTS = {
    "twilight": {CONF_ICON: "mdi:weather-sunset"},
    "rain": {CONF_DEVICE_CLASS: "moisture", CONF_ICON: "mdi:weather-pouring"},
    # Aan = checksum klopt. Geen device_class problem, zodat aan de gezonde toestand is.
    "checksum_valid": {CONF_ENTITY_CATEGORY: _DIAG, CONF_ICON: "mdi:check-network-outline"},
}

# Tekstvelden en diagnose-tekst.
TEXT_SENSOR_DEFAULTS = {
    "weekday": {CONF_ICON: "mdi:calendar-week"},
    "summer_time": {CONF_ICON: "mdi:sun-clock"},
    "longitude_direction": {CONF_ICON: "mdi:map-marker"},
    "latitude_direction": {CONF_ICON: "mdi:map-marker"},
    "variant": {CONF_ENTITY_CATEGORY: _DIAG, CONF_ICON: "mdi:information-outline"},
    "raw_packet": {CONF_ENTITY_CATEGORY: _DIAG, CONF_ICON: "mdi:code-braces"},
}
