"""Knop om de USB/RS485-verbinding te resetten.

Versie: 0.0.8
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .hub import ElsnerHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Voeg de reset-knop toe."""
    hub: ElsnerHub = entry.runtime_data
    async_add_entities([ElsnerResetButton(hub)])


class ElsnerResetButton(ButtonEntity):
    """Sluit de seriële poort en open hem opnieuw."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:usb"

    def __init__(self, hub: ElsnerHub) -> None:
        self._hub = hub
        self._attr_name = f"{hub.name} Reset USB connection"
        self._attr_unique_id = f"{hub.base_uid}_reset_connection"
        self._attr_device_info = hub.device_info

    async def async_press(self) -> None:
        """Reset de verbinding met de poort."""
        await self._hub.async_reset_connection()
