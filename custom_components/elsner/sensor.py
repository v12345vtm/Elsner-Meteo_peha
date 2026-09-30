from __future__ import annotations

import asyncio
import logging
import os

from serial import SerialException
import serial_asyncio_fast as serial_asyncio
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from .protocols import PROTOCOLS_BY_START, Field, Protocol, parse_frame

_LOGGER = logging.getLogger(__name__)

CONF_SERIAL_PORT = "serial_port"

DEFAULT_NAME = "Weather station"
BAUDRATE = 19200

# Sensor variant is auto-detected based on 'W' (CET) or 'G' (GPS) start character.
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SERIAL_PORT): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    name = config.get(CONF_NAME)
    port = config.get(CONF_SERIAL_PORT)

    hub = ElsnerHub(hass, port, BAUDRATE, name, async_add_entities)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, hub.stop)
    await hub.async_start()


class ElsnerHub:
    """ v0.0.6 Owns the single serial connection and auto-detects protocol variant."""

    def __init__(
        self,
        hass: HomeAssistant,
        port: str,
        baudrate: int,
        base_name: str,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self.hass = hass
        self._port = port
        self._baudrate = baudrate
        self._base_name = base_name
        self._async_add_entities = async_add_entities
        self._task: asyncio.Task | None = None
        self._entities: dict[str, ElsnerFieldSensor] = {}
        self._protocol: Protocol | None = None

    async def async_start(self) -> None:
        self._task = self.hass.loop.create_task(self._read_loop())

    @property
    def port(self) -> str:
        return self._port

    @callback
    def stop(self, event) -> None:
        if self._task:
            self._task.cancel()

    def _setup_entities_for_protocol(self, protocol: Protocol) -> None:
        """Create entities dynamically when a protocol is detected."""
        self._protocol = protocol
        new_entities = []
        for field in protocol.fields:
            if field.key == protocol.checksum_field:
                continue
            entity = ElsnerFieldSensor(self, self._base_name, field)
            self._entities[field.key] = entity
            new_entities.append(entity)

        if new_entities:
            self._async_add_entities(new_entities, True)
            _LOGGER.info(
                "Initialized %d entities for Elsner station protocol '%s'",
                len(new_entities),
                protocol.start_char,
            )

    async def _read_loop(self) -> None:
        logged_error = False
        while True:
            try:
                reader, _ = await serial_asyncio.open_serial_connection(
                    url=self._port,
                    baudrate=self._baudrate,
                )
            except SerialException:
                if not logged_error:
                    _LOGGER.error(
                        "Elsner (%s): could not open the serial port - check "
                        "the port path and permissions. Will keep retrying "
                        "every 5 seconds.",
                        self._port,
                    )
                    logged_error = True
                await self._handle_error()
                continue

            _LOGGER.info("Elsner (%s): serial port connected", self._port)
            logged_error = False
            while True:
                try:
                    raw = await asyncio.wait_for(reader.readuntil(b"\x03"), timeout=10.0)
                except asyncio.TimeoutError:
                    if not os.path.exists(self._port):
                        # The device node itself is gone - the USB/RS485
                        # adapter was very likely unplugged, not just the
                        # weather station's A/B wiring.
                        _LOGGER.error(
                            "Elsner (%s): serial port no longer exists - the "
                            "USB/RS485 adapter appears to have been "
                            "unplugged. Will reconnect automatically once "
                            "it's back.",
                            self._port,
                        )
                    else:
                        # Port is still there, so this is the adapter/OS
                        # still being fine but the station itself going
                        # quiet (powered off, A/B disconnected, etc.).
                        _LOGGER.warning(
                            "Elsner (%s): no frame received for 10 seconds - "
                            "the port is still present, so this looks like "
                            "the station itself (power or A/B wiring), not "
                            "the USB adapter.",
                            self._port,
                        )
                    await self._handle_error()
                    break
                except asyncio.IncompleteReadError:
                    _LOGGER.warning(
                        "Elsner (%s): incomplete frame - the connection was "
                        "interrupted mid-frame.",
                        self._port,
                    )
                    await self._handle_error()
                    break
                except asyncio.LimitOverrunError:
                    _LOGGER.warning(
                        "Elsner (%s): frame exceeded buffer limit without an "
                        "ETX terminator - check the baud rate and wiring.",
                        self._port,
                    )
                    await self._handle_error()
                    break
                except (SerialException, OSError) as err:
                    # Covers both pyserial's own SerialException and a bare
                    # OSError (e.g. "No such device") that a vanished
                    # USB-serial adapter can raise directly, depending on
                    # the OS/driver - either way this means the connection
                    # itself broke, almost always because the adapter was
                    # unplugged.
                    _LOGGER.error(
                        "Elsner (%s): lost the serial connection (%s) - most "
                        "likely the USB/RS485 adapter was unplugged.",
                        self._port,
                        err,
                    )
                    await self._handle_error()
                    break

                frame = raw[:-1].decode("utf-8", errors="replace").strip()
                if not frame:
                    continue

                start_char = frame[0]
                if start_char not in PROTOCOLS_BY_START:
                    _LOGGER.debug("Discarding unrecognized frame start: %r", frame)
                    continue

                if self._protocol is None:
                    self._setup_entities_for_protocol(PROTOCOLS_BY_START[start_char])
                elif start_char != self._protocol.start_char:
                    _LOGGER.debug(
                        "Discarding frame with unexpected start byte %r "
                        "(locked onto protocol '%s')",
                        start_char,
                        self._protocol.start_char,
                    )
                    continue

                protocol = self._protocol

                if len(frame) != protocol.frame_length:
                    _LOGGER.debug(
                        "Frame length mismatch for protocol '%s': expected %d, got %d",
                        start_char,
                        protocol.frame_length,
                        len(frame),
                    )
                    continue

                _LOGGER.debug("Received frame (%s): %s", start_char, frame)
                values = parse_frame(protocol, frame)
                for entity in self._entities.values():
                    entity.handle_values(values)

    async def _handle_error(self) -> None:
        for entity in self._entities.values():
            entity.handle_values(None)
        await asyncio.sleep(5)


class ElsnerFieldSensor(SensorEntity):
    """One entity for one field of the detected protocol."""

    _attr_should_poll = False
    _attr_available = False

    def __init__(self, hub: ElsnerHub, base_name: str, field: Field) -> None:
        self._hub = hub
        self._field = field
        self._attr_name = f"{base_name} {field.name}"
        self._attr_native_unit_of_measurement = field.unit
        self._attr_device_class = field.device_class
        self._attr_icon = field.icon
        self._attr_native_value = None
        self._attr_unique_id = f"elsner_{slugify(hub.port)}_{field.key}"
        
        # FIX: Vertel Home Assistant expliciet dat deze entiteit 3 decimalen moet tonen
        if field.unit in ("lx", "klx"):
            self._attr_suggested_display_precision = 3

    def handle_values(self, values: dict[str, object] | None) -> None:
        if values is None:
            if self._attr_available:
                self._attr_available = False
                self.async_write_ha_state()
            return

        new_value = values.get(self._field.key)
        
        # Zorg ervoor dat het intern als float verwerkt wordt, HA regelt de weergave 
        # op basis van de suggested_display_precision (3)
        if self._field.unit in ("lx", "klx") and new_value is not None:
            try:
                new_value = float(new_value)
            except (ValueError, TypeError):
                pass
        
        if not self._attr_available or self._attr_native_value != new_value:
            self._attr_native_value = new_value
            self._attr_available = True
            self.async_write_ha_state()
