"""ArtDMX (Art-Net) receiver -> wired DMX512 output for the room nodes.

The node side of wiring-guides/dmx-over-wifi.md: listens for the server's
unicast ArtDMX frames (artnet.py builds them) and re-clocks the latest frame
out a hardware UART at ~43Hz — break, MAB, start code, channels — through a
MAX485 into the room's fixture chain. WiFi loss = hold the last frame.

ESP-IDF builds get the full UART path; a host-platform build compiles to the
UDP receiver + signal sensor only (so a sim room including it still validates).
"""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import pins
from esphome.components import binary_sensor
from esphome.const import CONF_ID, CONF_PORT

AUTO_LOAD = ["binary_sensor"]

CONF_TX_PIN = "tx_pin"
CONF_UNIVERSE = "universe"
CONF_UART_NUM = "uart_num"
CONF_CHANNELS = "channels"
CONF_SIGNAL = "signal"

artnet_dmx_ns = cg.esphome_ns.namespace("artnet_dmx")
ArtnetDMX = artnet_dmx_ns.class_("ArtnetDMX", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(ArtnetDMX),
        cv.Required(CONF_TX_PIN): pins.internal_gpio_output_pin_number,
        cv.Optional(CONF_UNIVERSE, default=0): cv.int_range(min=0, max=32767),
        cv.Optional(CONF_PORT, default=6454): cv.port,
        # Default UART2: free fleet-wide under the S3's USB-JTAG logger — the
        # sensor UARTs auto-assign 0/1 (Cuddle uses both). See dmx-over-wifi.md.
        cv.Optional(CONF_UART_NUM, default=2): cv.int_range(min=0, max=2),
        cv.Optional(CONF_CHANNELS, default=512): cv.int_range(min=24, max=512),
        cv.Optional(CONF_SIGNAL): binary_sensor.binary_sensor_schema(),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_tx_pin(config[CONF_TX_PIN]))
    cg.add(var.set_universe(config[CONF_UNIVERSE]))
    cg.add(var.set_port(config[CONF_PORT]))
    cg.add(var.set_uart_num(config[CONF_UART_NUM]))
    cg.add(var.set_channels(config[CONF_CHANNELS]))
    if CONF_SIGNAL in config:
        sens = await binary_sensor.new_binary_sensor(config[CONF_SIGNAL])
        cg.add(var.set_signal_sensor(sens))
