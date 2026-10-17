"""Config flow voor de Elsner weerstation-integratie.

Versie: 0.0.8

Naam, USB/RS485-poort en analyse-interval staan voortaan in de integratie zelf
(Instellingen > Apparaten en diensten). Een oude YAML-instelling wordt eenmalig
overgenomen.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)
from homeassistant.util import slugify

from .const import (
    CONF_ANALYSE_INTERVAL,
    CONF_SERIAL_PORT,
    DEFAULT_ANALYSE_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_SERIAL_PORT,
    DOMAIN,
    MAX_ANALYSE_INTERVAL,
)


def _unique_id_for_port(port: str) -> str:
    """Dezelfde basis als de unique_id's van de entiteiten, zodat die behouden blijven."""
    return f"elsner_{slugify(port)}"


def _settings_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Formulier met de instellingen; 'defaults' zijn de huidige waarden."""
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)
            ): TextSelector(),
            vol.Required(
                CONF_SERIAL_PORT,
                default=defaults.get(CONF_SERIAL_PORT, DEFAULT_SERIAL_PORT),
            ): TextSelector(),
            vol.Required(
                CONF_ANALYSE_INTERVAL,
                default=defaults.get(CONF_ANALYSE_INTERVAL, DEFAULT_ANALYSE_INTERVAL),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=MAX_ANALYSE_INTERVAL,
                    step=1,
                    unit_of_measurement="s",
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


class ElsnerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Instellen van het weerstation via de UI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Eerste instelling via Instellingen > Apparaten en diensten."""
        errors: dict[str, str] = {}
        if user_input is not None:
            port = user_input[CONF_SERIAL_PORT].strip()
            if not port:
                errors[CONF_SERIAL_PORT] = "invalid_port"
            else:
                name = user_input[CONF_NAME].strip() or DEFAULT_NAME
                await self.async_set_unique_id(_unique_id_for_port(port))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_NAME: name,
                        CONF_SERIAL_PORT: port,
                        CONF_ANALYSE_INTERVAL: user_input[CONF_ANALYSE_INTERVAL],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_settings_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Oude YAML-instelling (sensor: - platform: elsner) eenmalig overnemen."""
        port = import_data[CONF_SERIAL_PORT].strip()
        name = import_data.get(CONF_NAME) or DEFAULT_NAME
        await self.async_set_unique_id(_unique_id_for_port(port))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=name,
            data={
                CONF_NAME: name,
                CONF_SERIAL_PORT: port,
                CONF_ANALYSE_INTERVAL: DEFAULT_ANALYSE_INTERVAL,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Koppelt de knop 'Configureren' aan de opties-pagina."""
        return ElsnerOptionsFlow()


class ElsnerOptionsFlow(OptionsFlow):
    """Naam, poort en analyse-interval wijzigen zonder de integratie te verwijderen."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Opties-pagina (knop 'Configureren')."""
        errors: dict[str, str] = {}
        if user_input is not None:
            port = user_input[CONF_SERIAL_PORT].strip()
            if not port:
                errors[CONF_SERIAL_PORT] = "invalid_port"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_NAME: user_input[CONF_NAME].strip() or DEFAULT_NAME,
                        CONF_SERIAL_PORT: port,
                        CONF_ANALYSE_INTERVAL: user_input[CONF_ANALYSE_INTERVAL],
                    },
                )

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_settings_schema(user_input or current),
            errors=errors,
        )
