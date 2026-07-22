"""Sim stand-in for artnet_output_manager — the sim must never unicast real
ArtDMX at the room-node hostnames in dmx_nodes.json (they may resolve to real
hardware on the dev LAN). run_server.py installs this before main.py loads,
same pattern as virtual_dmx. The BlenderDMX mirror stays opt-in via SIM_ARTNET
(virtual_dmx handles it)."""
import logging

logger = logging.getLogger(__name__)


class ArtNetOutputManager:
    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    def from_config(cls, dmx_state_manager, path=None):
        logger.info("Virtual Art-Net: room-node unicast suppressed in the sim "
                    "(SIM_ARTNET env still mirrors to a visualizer)")
        return None

    def start(self):
        pass

    def stop(self):
        pass
