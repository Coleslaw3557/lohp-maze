#!/usr/bin/env python3
"""Run the real LoHP server with a virtual DMX output plus the sim web UI.

Zero changes to production code: this injects sim/virtual_dmx.py in place of
dmx_interface *before* main.py loads, then executes main.py exactly as
`python main.py` would. Delete the sim/ folder and the repo is untouched.

    Real server API      :5000   (unchanged, same endpoints as production)
    Real server audio WS :8765   (unchanged)
    Sim 3D web UI        :5001   (this folder)
"""
import os
import sys
import runpy
import threading

SIM_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SIM_DIR)

sys.path.insert(0, SIM_DIR)
sys.path.insert(0, REPO_DIR)
os.chdir(REPO_DIR)  # main.py reads light_config.json etc. relative to cwd

import virtual_dmx  # noqa: E402
import virtual_artnet  # noqa: E402
sys.modules['dmx_interface'] = virtual_dmx
sys.modules['artnet_output_manager'] = virtual_artnet

import sim_ui  # noqa: E402
threading.Thread(target=sim_ui.run, name='sim-ui', daemon=True).start()

print(f"[sim] virtual DMX active; sim UI on :{sim_ui.PORT}; launching real server...")
runpy.run_module('main', run_name='__main__')
