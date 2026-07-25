"""Sim stand-in for artnet_output_manager — by default the sim must never
unicast real ArtDMX at the room-node hostnames in dmx_nodes.json (they may
resolve to real hardware on the dev LAN). run_server.py installs this before
main.py loads, same pattern as virtual_dmx.

Per-room hardware bridge (2026-07-25, first real box): a node carrying
"hardware": true in dmx_nodes.json is a physically built box that SHOULD get
real unicast from the sim — those nodes get the real ArtNetOutputManager
(loaded by file path; sys.modules['artnet_output_manager'] is this shim),
every other room stays virtual. Production main.py never reads the flag —
the real from_config sends to every enabled node regardless.

The BlenderDMX mirror stays opt-in via SIM_ARTNET (virtual_dmx handles it)."""
import importlib.util
import json
import logging
import os

logger = logging.getLogger(__name__)

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _real_module():
    spec = importlib.util.spec_from_file_location(
        'artnet_output_manager_real', os.path.join(_REPO, 'artnet_output_manager.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ArtNetOutputManager:
    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    def from_config(cls, dmx_state_manager, path=None):
        path = path or os.path.join(_REPO, 'dmx_nodes.json')
        cfg = {}
        try:
            with open(path) as f:
                cfg = json.load(f)
        except (OSError, ValueError) as e:
            logger.warning(f"Virtual Art-Net: could not read {path}: {e}")
        hardware = {room: node for room, node in cfg.get('nodes', {}).items()
                    if node.get('enabled') and node.get('hardware')}
        if not hardware:
            logger.info("Virtual Art-Net: room-node unicast suppressed in the sim "
                        '(SIM_ARTNET env still mirrors to a visualizer; mark a built '
                        'box "hardware": true in dmx_nodes.json for real unicast)')
            return None
        real = _real_module()
        port = cfg.get('port', 6454)
        targets = [real._Target(room, node['host'], node.get('port', port))
                   for room, node in hardware.items()]
        logger.info(f"Sim Art-Net HARDWARE BRIDGE: real unicast to {sorted(hardware)} "
                    "— all other rooms stay virtual")
        return real.ArtNetOutputManager(dmx_state_manager, targets,
                                        universe=cfg.get('universe', 0))

    def start(self):
        pass

    def stop(self):
        pass
