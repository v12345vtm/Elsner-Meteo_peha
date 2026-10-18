# Versie: 0.1.0
"""button-platform van de Elsner-component: de reset-knop uit de HA-integratie."""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import button
from esphome.const import ENTITY_CATEGORY_CONFIG

from . import ElsnerComponent, elsner_ns
from .const import CONF_ELSNER_ID

DEPENDENCIES = ["elsner"]

ElsnerResetButton = elsner_ns.class_("ElsnerResetButton", button.Button)

CONFIG_SCHEMA = button.button_schema(
    ElsnerResetButton,
    icon="mdi:usb",
    entity_category=ENTITY_CATEGORY_CONFIG,
).extend(
    {cv.GenerateID(CONF_ELSNER_ID): cv.use_id(ElsnerComponent)}
)


async def to_code(config):
    var = await button.new_button(config)
    hub = await cg.get_variable(config[CONF_ELSNER_ID])
    cg.add(var.set_parent(hub))
