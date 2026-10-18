# Versie: 0.1.0
"""binary_sensor-platform van de Elsner-component: regen, schemering en checksum."""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import binary_sensor
from esphome.const import CONF_TYPE

from . import ElsnerComponent, with_defaults
from .const import BINARY_SENSOR_DEFAULTS, CONF_ELSNER_ID

DEPENDENCIES = ["elsner"]

CONFIG_SCHEMA = cv.All(
    with_defaults(BINARY_SENSOR_DEFAULTS),
    binary_sensor.binary_sensor_schema().extend(
        {
            cv.GenerateID(CONF_ELSNER_ID): cv.use_id(ElsnerComponent),
            cv.Required(CONF_TYPE): cv.one_of(*BINARY_SENSOR_DEFAULTS, lower=True),
        }
    ),
)


async def to_code(config):
    hub = await cg.get_variable(config[CONF_ELSNER_ID])
    var = await binary_sensor.new_binary_sensor(config)
    cg.add(hub.add_binary_sensor(config[CONF_TYPE], var))
