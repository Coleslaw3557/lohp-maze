"""Pi-local ESPHome OTA push (playa 2026-08-31): espota2.py verbatim from the
dev box's esphome 2026.7.0 + stdlib shims — pip on camp WiFi times out.
Usage: python3 runner.py <node-ip> <password> <firmware.ota.bin>"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from esphome.espota2 import run_ota

rc, _ = run_ota(sys.argv[1], 3232, sys.argv[2], Path(sys.argv[3]))
sys.exit(rc)
