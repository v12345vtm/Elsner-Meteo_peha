# Versie: 0.1.0
"""text_sensor-platform van de Elsner-component: tekstvelden en diagnose-tekst."""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import text_sensor
from esphome.const import CONF_TYPE

from . import ElsnerComponent, with_defaults
from .const import CONF_ELSNER_ID, TEXT_SENSOR_DEFAULTS

DEPENDENCIES = ["elsner"]

CONFIG_SCHEMA = cv.All(
    with_defaults(TEXT_SENSOR_DEFAULTS),
    text_sensor.text_sensor_schema().extend(
        {
            cv.GenerateID(CONF_ELSNER_ID): cv.use_id(ElsnerComponent),
            cv.Required(CONF_TYPE): cv.one_of(*TEXT_SENSOR_DEFAULTS, lower=True),
        }
    ),
)


async def to_code(config):
    hub = await cg.get_variable(config[CONF_ELSNER_ID])
    var = await text_sensor.new_text_sensor(config)
    cg.add(hub.add_text_sensor(config[CONF_TYPE], var))
