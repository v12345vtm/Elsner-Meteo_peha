"""Seriële verbinding met het Elsner weerstation.

Versie: 0.0.8

De hub is de enige eigenaar van de seriële poort:
- Hij leest continu alle frames (gescheiden door ETX 0x03), zodat de buffer nooit volloopt.
- Hij analyseert maar één geldig datapakket per ingestelde interval (throttle).
- Hij kan op verzoek de poort sluiten en opnieuw openen (knop 'Reset USB connection').
- Hij herstelt zichzelf na fouten en sluit de oude poort altijd eerst af.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
import logging
import os
import time

from serial import SerialException
import serial_asyncio_fast as serial_asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    BAUDRATE,
    CONF_ANALYSE_INTERVAL,
    CONF_SERIAL_PORT,
    DEFAULT_ANALYSE_INTERVAL,
    DEFAULT_NAME,
    DOMAIN,
    ETX,
    FRAME_TIMEOUT,
    INTEGRATION_VERSION,
    RECONNECT_DELAY,
    STALE_TIMEOUT,
)
from .protocols import PROTOCOLS_BY_START, Protocol, parse_frame

_LOGGER = logging.getLogger(__name__)

# Leesbare naam van de variant per startteken
VARIANT_NAMES: dict[str, str] = {"W": "CET", "G": "GPS"}


class ElsnerHub:
    """Beheert de seriële verbinding, de analyse-throttle en de gedeelde meetdata."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        config = {**entry.data, **entry.options}
        self.name: str = config.get(CONF_NAME) or DEFAULT_NAME
        self.port: str = config[CONF_SERIAL_PORT]
        self.analyse_interval: float = float(
            config.get(CONF_ANALYSE_INTERVAL, DEFAULT_ANALYSE_INTERVAL)
        )
        # Basis voor de unique_id's. Die blijft vast (ook als de poort wijzigt),
        # zodat bestaande entiteiten en hun entity_id's behouden blijven.
        self.base_uid: str = entry.unique_id or f"elsner_{slugify(self.port)}"
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=self.name,
            manufacturer="Elsner",
            model="P03/3-RS485 weather station",
            sw_version=INTEGRATION_VERSION,
        )

        # Gedeelde status, gelezen door de entiteiten
        self.available = False
        self.values: dict[str, object] | None = None
        self.raw: str | None = None
        self.variant: str | None = None
        self.analysed_at: str | None = None

        # Tellers, zichtbaar als attributen op de raw-entiteit
        self.frames_received = 0
        self.frames_invalid = 0
        self.frames_analysed = 0
        self.frames_skipped = 0

        self._protocol: Protocol | None = None
        self._on_protocol: Callable[[Protocol], None] | None = None
        self._listeners: list[Callable[[], None]] = []
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._last_analysis = float("-inf")
        self._last_valid = float("-inf")
        self._open_error_logged = False

    # ------------------------------------------------------------------
    # Koppeling met de entiteiten
    # ------------------------------------------------------------------

    @callback
    def async_set_protocol_callback(
        self, on_protocol: Callable[[Protocol], None]
    ) -> None:
        """Wordt aangeroepen zodra het protocol (W of G) herkend is, om de sensoren te maken."""
        self._on_protocol = on_protocol

    @callback
    def async_add_listener(self, update: Callable[[], None]) -> Callable[[], None]:
        """Laat een entiteit meeluisteren; geeft een functie terug om af te melden."""
        self._listeners.append(update)

        @callback
        def _remove() -> None:
            if update in self._listeners:
                self._listeners.remove(update)

        return _remove

    @callback
    def _async_notify(self) -> None:
        for update in list(self._listeners):
            update()

    # ------------------------------------------------------------------
    # Levenscyclus en de reset-knop
    # ------------------------------------------------------------------

    async def async_start(self) -> None:
        """Start de leeslus."""
        async with self._lock:
            self._async_start_reader()

    async def async_stop(self, _event: object | None = None) -> None:
        """Stop de leeslus en sluit de seriële poort."""
        async with self._lock:
            await self._async_cancel_reader()

    async def async_reset_connection(self) -> None:
        """Sluit de seriële poort en open hem opnieuw (knop 'Reset USB connection')."""
        async with self._lock:
            _LOGGER.info(
                "Elsner (%s): reset requested - closing and reopening the serial port",
                self.port,
            )
            await self._async_cancel_reader()
            self._open_error_logged = False
            self._async_set_unavailable()
            self._async_start_reader()

    @callback
    def _async_start_reader(self) -> None:
        self._task = self.hass.async_create_background_task(
            self._async_run(), name=f"elsner_reader_{self.base_uid}"
        )

    async def _async_cancel_reader(self) -> None:
        task, self._task = self._task, None
        if task is None or task.done():
            return
        task.cancel()
        # Wacht tot de finally-blok de poort heeft gesloten voordat we opnieuw openen.
        await asyncio.wait({task})

    # ------------------------------------------------------------------
    # Leeslus
    # ------------------------------------------------------------------

    async def _async_run(self) -> None:
        """Hoofdlus: open de poort, lees frames en probeer opnieuw na elke fout."""
        while True:
            writer: asyncio.StreamWriter | None = None
            try:
                reader, writer = await serial_asyncio.open_serial_connection(
                    url=self.port, baudrate=BAUDRATE
                )
                _LOGGER.info("Elsner (%s): serial port connected", self.port)
                self._open_error_logged = False
                await self._async_read_frames(reader)
            except asyncio.CancelledError:
                raise
            except (SerialException, OSError) as err:
                if not self._open_error_logged:
                    _LOGGER.error(
                        "Elsner (%s): could not open the serial port (%s) - check the "
                        "port path and permissions. Will keep retrying every %s seconds.",
                        self.port,
                        err,
                        RECONNECT_DELAY,
                    )
                    self._open_error_logged = True
            except Exception:  # noqa: BLE001 - de leeslus mag nooit stoppen
                _LOGGER.exception(
                    "Elsner (%s): unexpected error in the serial reader - reconnecting",
                    self.port,
                )
            finally:
                # Sluit altijd de vorige verbinding. Anders blijft de poort open
                # en lezen er twee lezers tegelijk van dezelfde poort.
                await self._async_close_writer(writer)

            self._async_set_unavailable()
            await asyncio.sleep(RECONNECT_DELAY)

    @staticmethod
    async def _async_close_writer(writer: asyncio.StreamWriter | None) -> None:
        """Sluit de transport en wacht tot de poort echt dicht is."""
        if writer is None:
            return
        with suppress(Exception):
            writer.close()
            await asyncio.wait_for(writer.wait_closed(), timeout=5)

    async def _async_read_frames(self, reader: asyncio.StreamReader) -> None:
        """Lees frames tot er iets misgaat; keer dan terug zodat de poort gesloten wordt."""
        while True:
            try:
                raw = await asyncio.wait_for(
                    reader.readuntil(ETX), timeout=FRAME_TIMEOUT
                )
            except asyncio.TimeoutError:
                if not os.path.exists(self.port):
                    # Het apparaatbestand bestaat niet meer: de USB/RS485-adapter
                    # is hoogstwaarschijnlijk losgekoppeld.
                    _LOGGER.error(
                        "Elsner (%s): serial port no longer exists - the USB/RS485 adapter "
                        "appears to have been unplugged. Will reconnect automatically once "
                        "it's back.",
                        self.port,
                    )
                else:
                    _LOGGER.warning(
                        "Elsner (%s): no frame received for %s seconds - the port is still "
                        "present, so this looks like the station itself (power or A/B "
                        "wiring), not the USB adapter.",
                        self.port,
                        FRAME_TIMEOUT,
                    )
                return
            except asyncio.IncompleteReadError:
                _LOGGER.warning(
                    "Elsner (%s): incomplete frame - the connection was interrupted mid-frame.",
                    self.port,
                )
                return
            except asyncio.LimitOverrunError:
                _LOGGER.warning(
                    "Elsner (%s): frame exceeded buffer limit without an ETX terminator - "
                    "check the baud rate and wiring.",
                    self.port,
                )
                return
            except (SerialException, OSError) as err:
                _LOGGER.error(
                    "Elsner (%s): lost the serial connection (%s) - most likely the "
                    "USB/RS485 adapter was unplugged.",
                    self.port,
                    err,
                )
                return

            try:
                self._async_handle_raw(raw)
            except Exception:  # noqa: BLE001 - één vreemd frame mag de verbinding niet slopen
                _LOGGER.exception(
                    "Elsner (%s): could not process frame %r", self.port, raw
                )

    # ------------------------------------------------------------------
    # Frames verwerken
    # ------------------------------------------------------------------

    @callback
    def _async_handle_raw(self, raw: bytes) -> None:
        """Verwerk één ontvangen frame (het ETX-teken zit aan het eind van 'raw')."""
        self.frames_received += 1
        frame = raw[:-1].decode("utf-8", errors="replace").strip()

        protocol = PROTOCOLS_BY_START.get(frame[:1])
        if protocol is None:
            self._async_discard(frame, "unknown start character")
            return
        if self._protocol is not None and protocol is not self._protocol:
            self._async_discard(
                frame, f"station uses protocol '{self._protocol.start_char}'"
            )
            return
        if len(frame) != protocol.frame_length:
            self._async_discard(
                frame, f"length {len(frame)}, expected {protocol.frame_length}"
            )
            return

        now = time.monotonic()
        self._last_valid = now

        if self._protocol is None:
            # Het eerste geldige frame bepaalt het protocol (W = CET, G = GPS).
            # Eerst vastleggen en dan pas de sensoren maken: zo ontstaan nooit dubbele sensoren.
            self._protocol = protocol
            self.variant = VARIANT_NAMES.get(protocol.start_char, protocol.start_char)
            if self._on_protocol is not None:
                self._on_protocol(protocol)

        # Throttle: analyseer alleen als het ingestelde interval is verstreken.
        if self.analyse_interval > 0 and now - self._last_analysis < self.analyse_interval:
            self.frames_skipped += 1
            return
        self._last_analysis = now
        self._async_analyse(frame, protocol)

    @callback
    def _async_discard(self, frame: str, reason: str) -> None:
        self.frames_invalid += 1
        _LOGGER.debug("Elsner (%s): discarding frame %r: %s", self.port, frame, reason)
        self._async_check_stale()

    @callback
    def _async_analyse(self, frame: str, protocol: Protocol) -> None:
        self.values = parse_frame(protocol, frame)
        self.raw = frame
        self.analysed_at = dt_util.utcnow().isoformat()
        self.frames_analysed += 1
        self.available = True
        self._async_notify()

    @callback
    def _async_set_unavailable(self) -> None:
        if self.available:
            self.available = False
            self._async_notify()

    @callback
    def _async_check_stale(self) -> None:
        """Zet de sensoren op 'unavailable' als er al lang geen geldig datapakket komt."""
        if self.available and time.monotonic() - self._last_valid > STALE_TIMEOUT:
            _LOGGER.warning(
                "Elsner (%s): no valid data packet for %s seconds, only invalid frames - "
                "check the baud rate, the protocol and the wiring",
                self.port,
                STALE_TIMEOUT,
            )
            self._async_set_unavailable()
