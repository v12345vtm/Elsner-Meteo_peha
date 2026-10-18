# Versie: 0.1.0
"""sensor-platform van de Elsner-component: één regel per numerieke meetwaarde."""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import sensor
from esphome.const import CONF_TYPE

from . import ElsnerComponent, with_defaults
from .const import CONF_ELSNER_ID, SENSOR_DEFAULTS

DEPENDENCIES = ["elsner"]

CONFIG_SCHEMA = cv.All(
    with_defaults(SENSOR_DEFAULTS),
    sensor.sensor_schema().extend(
        {
            cv.GenerateID(CONF_ELSNER_ID): cv.use_id(ElsnerComponent),
            cv.Required(CONF_TYPE): cv.one_of(*SENSOR_DEFAULTS, lower=True),
        }
    ),
)


async def to_code(config):
    hub = await cg.get_variable(config[CONF_ELSNER_ID])
    var = await sensor.new_sensor(config)
    cg.add(hub.add_sensor(config[CONF_TYPE], var))
