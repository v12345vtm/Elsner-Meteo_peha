"""Sensoren van het Elsner weerstation.

Versie: 0.0.8

- Eén sensor per meetveld van het gedetecteerde protocol (W of G).
- Eén diagnose-sensor 'Raw packet' met het laatst geanalyseerde ruwe datapakket.
- Oude YAML-configuratie (sensor: - platform: elsner) wordt eenmalig naar de UI geïmporteerd.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME, EntityCategory
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_SERIAL_PORT, DEFAULT_NAME, DOMAIN
from .hub import ElsnerHub
from .protocols import Field, Protocol

_LOGGER = logging.getLogger(__name__)

# Alleen nog nodig om oude YAML-instellingen te kunnen lezen en importeren.
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
    """Oude YAML-configuratie: importeer die eenmalig naar een config entry."""
    _LOGGER.warning(
        "Elsner: setup found in configuration.yaml - it is being imported into the UI. "
        "You can remove the 'sensor: - platform: elsner' block once the integration "
        "shows under Settings > Devices & services."
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_SERIAL_PORT: config[CONF_SERIAL_PORT],
                CONF_NAME: config[CONF_NAME],
            },
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Maak de sensoren aan voor deze config entry."""
    hub: ElsnerHub = entry.runtime_data

    @callback
    def _add_field_sensors(protocol: Protocol) -> None:
        """Wordt door de hub aangeroepen zodra het protocol (W of G) herkend is."""
        entities = [
            ElsnerFieldSensor(hub, field)
            for field in protocol.fields
            if field.key != protocol.checksum_field
        ]
        async_add_entities(entities)
        _LOGGER.info(
            "Initialized %d entities for Elsner station protocol '%s'",
            len(entities),
            protocol.start_char,
        )

    hub.async_set_protocol_callback(_add_field_sensors)
    async_add_entities([ElsnerRawPacketSensor(hub)])


class ElsnerFieldSensor(SensorEntity):
    """Eén entiteit per meetveld van het gedetecteerde protocol."""

    _attr_should_poll = False

    def __init__(self, hub: ElsnerHub, field: Field) -> None:
        self._hub = hub
        self._field = field
        # Entiteitnamen en unique_id's blijven gelijk aan de vorige versie,
        # zodat bestaande entity_id's en dashboards blijven werken.
        self._attr_name = f"{hub.name} {field.name}"
        self._attr_unique_id = f"{hub.base_uid}_{field.key}"
        self._attr_device_info = hub.device_info
        self._attr_native_unit_of_measurement = field.unit
        self._attr_device_class = field.device_class
        self._attr_icon = field.icon
        # lx/klx: toon 3 decimalen (HA regelt de weergave)
        if field.unit in ("lx", "klx"):
            self._attr_suggested_display_precision = 3

    async def async_added_to_hass(self) -> None:
        """Abonneer op de hub zodra de entiteit in HA staat."""
        self.async_on_remove(self._hub.async_add_listener(self._handle_hub_update))
        self._apply_hub_state()

    @callback
    def _handle_hub_update(self) -> None:
        self._apply_hub_state()
        self.async_write_ha_state()

    @callback
    def _apply_hub_state(self) -> None:
        hub = self._hub
        self._attr_available = hub.available and hub.values is not None
        value = hub.values.get(self._field.key) if hub.values else None
        if value is not None and self._field.unit in ("lx", "klx"):
            try:
                value = float(value)
            except (TypeError, ValueError):
                pass
        self._attr_native_value = value


class ElsnerRawPacketSensor(SensorEntity):
    """Diagnose-sensor: toont het laatst geanalyseerde ruwe datapakket."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:code-braces"
    # Deze velden wijzigen bij elke analyse; niet in de recorder opslaan (minder database-groei).
    _unrecorded_attributes = frozenset(
        {"raw", "analysed_at", "length", "frames_received", "frames_analysed",
         "frames_skipped", "frames_invalid"}
    )

    def __init__(self, hub: ElsnerHub) -> None:
        self._hub = hub
        self._attr_name = f"{hub.name} Raw packet"
        self._attr_unique_id = f"{hub.base_uid}_raw_packet"
        self._attr_device_info = hub.device_info

    async def async_added_to_hass(self) -> None:
        """Abonneer op de hub zodra de entiteit in HA staat."""
        self.async_on_remove(self._hub.async_add_listener(self._handle_hub_update))
        self._apply_hub_state()

    @callback
    def _handle_hub_update(self) -> None:
        self._apply_hub_state()
        self.async_write_ha_state()

    @callback
    def _apply_hub_state(self) -> None:
        hub = self._hub
        self._attr_available = hub.available
        # Een HA-status mag maximaal 255 tekens zijn; de volledige tekst staat in 'raw'.
        self._attr_native_value = hub.raw[:255] if hub.raw else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        hub = self._hub
        return {
            "raw": hub.raw,
            "variant": hub.variant,
            "length": len(hub.raw) if hub.raw else 0,
            "analysed_at": hub.analysed_at,
            "analyse_interval": hub.analyse_interval,
            "frames_received": hub.frames_received,
            "frames_analysed": hub.frames_analysed,
            "frames_skipped": hub.frames_skipped,
            "frames_invalid": hub.frames_invalid,
        }
