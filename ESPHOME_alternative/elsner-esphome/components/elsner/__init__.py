# Versie: 0.1.0
"""Elsner P03/3 weerstation (RS485) - ESPHome-component.

De hub leest het RS485-protocol van het weerstation via een UART en koppelt de
meetwaarden aan sensor-, binary_sensor-, text_sensor- en button-entiteiten.
De platform-bestanden (sensor.py, binary_sensor.py, text_sensor.py, button.py)
voegen de entiteiten toe. Uitleg: esphome/readme.md.
"""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import uart
from esphome.const import CONF_ID, CONF_TYPE

from .const import CONF_ANALYSE_INTERVAL

CODEOWNERS = ["@v12345vtm"]
DEPENDENCIES = ["uart"]
MULTI_CONF = True

elsner_ns = cg.esphome_ns.namespace("elsner")
ElsnerComponent = elsner_ns.class_("ElsnerComponent", cg.Component, uart.UARTDevice)

CONFIG_SCHEMA = (
    cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(ElsnerComponent),
            # Hoe vaak een geldig datapakket geanalyseerd wordt. 0s = elk pakket.
            cv.Optional(CONF_ANALYSE_INTERVAL, default="5s"): cv.positive_time_period_milliseconds,
        }
    )
    .extend(cv.COMPONENT_SCHEMA)
    .extend(uart.UART_DEVICE_SCHEMA)
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    await uart.register_uart_device(var, config)
    cg.add(var.set_analyse_interval(config[CONF_ANALYSE_INTERVAL].total_milliseconds))


def with_defaults(defaults):
    """Vult ontbrekende eigenschappen per meetveld in, vóór de schema-validatie.

    Zo krijgt elke sensor de juiste eenheid, icoon en device_class zonder dat je die
    zelf hoeft op te geven. Wat je wél opgeeft, wordt nooit overschreven.
    """

    def _validate(config):
        if isinstance(config, dict):
            field_type = str(config.get(CONF_TYPE, "")).lower()
            for key, value in defaults.get(field_type, {}).items():
                config.setdefault(key, value)
        return config

    return _validate
