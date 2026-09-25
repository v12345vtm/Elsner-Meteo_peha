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

from .protocols import PROTOCOLS, DEFAULT_PROTOCOL, Field, Protocol, parse_frame

_LOGGER = logging.getLogger(__name__)

CONF_SERIAL_PORT = "serial_port"
CONF_VARIANT = "variant"

DEFAULT_NAME = "Weather station"
BAUDRATE = 19200

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SERIAL_PORT): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        # "cet" today; "gps" or "plain" once those Field tuples in
        # protocols.py are filled in - nothing else changes.
        vol.Optional(CONF_VARIANT, default=DEFAULT_PROTOCOL): vol.In(PROTOCOLS),
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
    protocol = PROTOCOLS[config.get(CONF_VARIANT)]

    hub = ElsnerHub(hass, port, BAUDRATE, protocol)

    entities = [
        ElsnerFieldSensor(hub, name, field)
        for field in protocol.fields
        # The checksum is for the hub's own validation, not something
        # you need as an entity. Drop this filter if you do want it
        # exposed (e.g. to watch for transmission errors).
        if field.key != protocol.checksum_field
    ]

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, hub.stop)
    async_add_entities(entities, True)
    await hub.async_start()


class ElsnerHub:
    """Owns the single serial connection and fans parsed frames out.

    One hub per configured `sensor: - platform: elsner` entry. All
    entities created from that entry share this hub instead of each
    opening their own connection to the same port.
    """

    def __init__(
            self,
            hass: HomeAssistant,
            port: str,
            baudrate: int,
            protocol: Protocol,
    ) -> None:
        self.hass = hass
        self._port = port
        self._baudrate = baudrate
        self._protocol = protocol
        self._task: asyncio.Task | None = None
        self._entities: list["ElsnerFieldSensor"] = []

    def register(self, entity: "ElsnerFieldSensor") -> None:
        self._entities.append(entity)

    async def async_start(self) -> None:
        self._task = self.hass.loop.create_task(self._read_loop())

    @callback
    def stop(self, event) -> None:
        if self._task:
            self._task.cancel()

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
                        "Unable to connect to the serial device %s. Will retry",
                        self._port,
                    )
                    logged_error = True
                await self._handle_error()
                continue

            _LOGGER.info("Serial device %s connected", self._port)
            logged_error = False
            while True:
                try:
                    # Frames are variable-length and terminated with an
                    # ETX (0x03) byte, so read up to and including that
                    # byte instead of a fixed number of bytes. A fixed
                    # readexactly() drifts out of sync with the frame
                    # boundaries and mixes the tail of one frame with the
                    # head of the next.
                    raw = await reader.readuntil(b"\x03")
                except asyncio.IncompleteReadError:
                    _LOGGER.exception(
                        "Incomplete frame from serial device %s", self._port
                    )
                    await self._handle_error()
                    break
                except asyncio.LimitOverrunError:
                    _LOGGER.exception(
                        "Frame from serial device %s exceeded buffer limit "
                        "without an ETX terminator",
                        self._port,
                    )
                    await self._handle_error()
                    break
                except SerialException:
                    _LOGGER.exception(
                        "Error while reading serial device %s", self._port
                    )
                    await self._handle_error()
                    break

                frame = raw[:-1].decode("utf-8", errors="replace").strip()
                if not frame.startswith(self._protocol.start_char):
                    # Out-of-sync or wrong `variant` configured - drop this
                    # one frame and resync on the next ETX rather than
                    # feeding garbage into every entity.
                    _LOGGER.debug("Discarding unexpected frame: %r", frame)
                    continue

                _LOGGER.debug("Received: %s", frame)
                values = parse_frame(self._protocol, frame)
                for entity in self._entities:
                    entity.handle_values(values)

    async def _handle_error(self) -> None:
        for entity in self._entities:
            entity.handle_values(None)
        await asyncio.sleep(5)


class ElsnerFieldSensor(SensorEntity):
    """One entity for one field of the configured protocol."""

    _attr_should_poll = False

    def __init__(self, hub: ElsnerHub, base_name: str, field: Field) -> None:
        self._hub = hub
        self._field = field
        self._attr_name = f"{base_name} {field.name}"
        self._attr_native_unit_of_measurement = field.unit
        self._attr_device_class = field.device_class
        self._attr_native_value = None

    async def async_added_to_hass(self) -> None:
        self._hub.register(self)

    def handle_values(self, values: dict[str, object] | None) -> None:
        self._attr_native_value = values.get(self._field.key) if values else None
        self.async_write_ha_state()
