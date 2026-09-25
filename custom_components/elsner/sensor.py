from __future__ import annotations

import asyncio
import logging

from serial import SerialException
import serial_asyncio_fast as serial_asyncio
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

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
    """Owns the single serial connection and auto-detects protocol variant."""

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
                    _LOGGER.exception(
                        "Unable to connect to serial device %s. Will retry",
                        self._port,
                    )
                    logged_error = True
                await self._handle_error()
                continue

            _LOGGER.info("Serial device %s connected", self._port)
            logged_error = False
            while True:
                try:
                    raw = await reader.readuntil(b"\x03")
                except asyncio.IncompleteReadError:
                    _LOGGER.exception("Incomplete frame from %s", self._port)
                    await self._handle_error()
                    break
                except asyncio.LimitOverrunError:
                    _LOGGER.exception(
                        "Frame from %s exceeded buffer limit without ETX",
                        self._port,
                    )
                    await self._handle_error()
                    break
                except SerialException:
                    _LOGGER.exception("Error reading serial device %s", self._port)
                    await self._handle_error()
                    break

                frame = raw[:-1].decode("utf-8", errors="replace").strip()
                if not frame:
                    continue

                start_char = frame[0]
                if start_char not in PROTOCOLS_BY_START:
                    _LOGGER.debug("Discarding unrecognized frame start: %r", frame)
                    continue

                protocol = PROTOCOLS_BY_START[start_char]

                # Auto-initialize entities on first valid payload received
                if self._protocol is None:
                    self._setup_entities_for_protocol(protocol)

                # Validate frame length for detected protocol
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

    def __init__(self, hub: ElsnerHub, base_name: str, field: Field) -> None:
        self._hub = hub
        self._field = field
        self._attr_name = f"{base_name} {field.name}"
        self._attr_native_unit_of_measurement = field.unit
        self._attr_device_class = field.device_class
        self._attr_native_value = None

    def handle_values(self, values: dict[str, object] | None) -> None:
        self._attr_native_value = values.get(self._field.key) if values else None
        self.async_write_ha_state()
