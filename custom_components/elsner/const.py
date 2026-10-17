"""Constanten voor de Elsner weerstation-integratie.

Versie: 0.0.8
"""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "elsner"
INTEGRATION_VERSION = "0.0.8"  # moet gelijk blijven aan manifest.json

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]

# Instellingen (config entry data / options)
CONF_SERIAL_PORT = "serial_port"
CONF_ANALYSE_INTERVAL = "analyse_interval"

DEFAULT_NAME = "Weather station"
DEFAULT_SERIAL_PORT = "/dev/ttyUSB0"
DEFAULT_ANALYSE_INTERVAL = 5  # seconden; 0 = elk datapakket analyseren
MAX_ANALYSE_INTERVAL = 300  # seconden

# Seriële communicatie
BAUDRATE = 19200
ETX = b"\x03"  # einde-van-frame teken van het Elsner protocol
FRAME_TIMEOUT = 10.0  # seconden zonder enige data -> opnieuw verbinden
RECONNECT_DELAY = 5.0  # seconden wachten tussen twee pogingen
STALE_TIMEOUT = 60.0  # seconden zonder geldig datapakket -> sensoren 'unavailable'
