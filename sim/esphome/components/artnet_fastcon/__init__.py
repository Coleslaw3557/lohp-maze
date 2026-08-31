"""ArtDMX (Art-Net) receiver -> Fastcon BLE flood commands.

The Exterior node's counterpart to artnet_dmx: same unicast ArtDMX frames
from the server (artnet.py builds them), but instead of re-clocking a wired
universe it slots each flood's 8-channel fixture block and broadcasts the
decoded colour to the BLE mesh via the fastcon controller. Decode mirrors
the Camp Sign zone spec so the sim preview matches the field:
    out = min(255, colour + 0.92*w) * (total_dimming applied as brightness)
    total_strobe > 5 gates on/off (rate clamped to the BLE command budget)

BLE is fire-and-forget, so unlike the wired path we can't re-clock at 43Hz:
sends are change-detected (deadband 3), rate-limited per flood, and each
flood is refreshed every few seconds regardless — a power-cycled flood
(generator evenings) repaints itself within one refresh. WiFi loss = hold.
"""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import binary_sensor
from esphome.const import CONF_ID, CONF_PORT

AUTO_LOAD = ["binary_sensor"]
DEPENDENCIES = ["fastcon"]

CONF_UNIVERSE = "universe"
CONF_CONTROLLER_ID = "controller_id"
CONF_FLOODS = "floods"
CONF_LIGHT_ID = "light_id"
CONF_START_ADDRESS = "start_address"
CONF_SIGNAL = "signal"

artnet_fastcon_ns = cg.esphome_ns.namespace("artnet_fastcon")
ArtnetFastcon = artnet_fastcon_ns.class_("ArtnetFastcon", cg.Component)

# Match by C++ type: the class is declared in components/fastcon
fastcon_ns = cg.esphome_ns.namespace("fastcon")
FastconController = fastcon_ns.class_("FastconController", cg.Component)

FLOOD_SCHEMA = cv.Schema(
    {
        cv.Required(CONF_LIGHT_ID): cv.int_range(min=1, max=255),
        cv.Required(CONF_START_ADDRESS): cv.int_range(min=1, max=505),
    }
)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(ArtnetFastcon),
        cv.Optional(CONF_CONTROLLER_ID, default="fastcon_controller"): cv.use_id(
            FastconController
        ),
        cv.Optional(CONF_UNIVERSE, default=0): cv.int_range(min=0, max=32767),
        cv.Optional(CONF_PORT, default=6454): cv.port,
        cv.Required(CONF_FLOODS): cv.ensure_list(FLOOD_SCHEMA),
        cv.Optional(CONF_SIGNAL): binary_sensor.binary_sensor_schema(),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    controller = await cg.get_variable(config[CONF_CONTROLLER_ID])
    cg.add(var.set_controller(controller))
    cg.add(var.set_universe(config[CONF_UNIVERSE]))
    cg.add(var.set_port(config[CONF_PORT]))
    for flood in config[CONF_FLOODS]:
        cg.add(var.add_flood(flood[CONF_LIGHT_ID], flood[CONF_START_ADDRESS]))
    if CONF_SIGNAL in config:
        sens = await binary_sensor.new_binary_sensor(config[CONF_SIGNAL])
        cg.add(var.set_signal_sensor(sens))
