"""Elsner P03/3 weerstation - Home Assistant integratie.

Versie: 0.0.8
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .hub import ElsnerHub


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Zet de integratie op vanuit een config entry (instellingen via de UI)."""
    hub = ElsnerHub(hass, entry)
    entry.runtime_data = hub

    # Platforms eerst opzetten, zodat de entiteiten klaarstaan voordat de eerste frames binnenkomen.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, hub.async_stop)
    )
    # Een wijziging in de instellingen (poort of interval) laadt de integratie opnieuw.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hub.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Sluit de seriële poort en verwijder de platforms."""
    await entry.runtime_data.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Herlaad de integratie na een wijziging in de opties."""
    await hass.config_entries.async_reload(entry.entry_id)
