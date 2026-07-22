"""Drop-in replacement for dmx_interface — no FTDI hardware required.

run_server.py installs this module as `dmx_interface` in sys.modules before
main.py is executed, so the real server runs its normal 44Hz output loop
against a virtual sink instead of the USB-DMX dongle. The frame that would
have gone down the wire is published to sim_state for the web UI, and can
optionally also be unicast as Art-Net for external visualizers (BlenderDMX,
QLC+, ...):

    SIM_ARTNET=192.168.1.50        # or ip:port; universe 0, sent on change (1s heartbeat when static)
"""
import logging
import os
import socket
import threading
import time

import sim_state
from artnet import build_artdmx  # repo root — the production packet builder

logger = logging.getLogger(__name__)

# main.py checks this: the virtual sink is the sim's whole frame feed, so it
# must be constructed even when dmx_nodes.json says ftdi:false (that flag
# retires the FTDI *hardware*, which this module replaces anyway).
VIRTUAL = True


class DMXOutputManager(threading.Thread):
    DMX_CHANNELS = 512
    FREQUENCY = 44  # same cadence as the real FTDI output thread

    def __init__(self, dmx_state_manager, url=None, universe=0):
        super().__init__(daemon=True)
        self.dmx_state_manager = dmx_state_manager
        self.universe = universe
        self.running = True
        self._last_frame = None
        self._last_publish = 0.0
        self._artnet_seq = 0
        self._artnet_addr = None
        self._artnet_sock = None

        target = os.environ.get('SIM_ARTNET')
        if target:
            host, _, port = target.partition(':')
            self._artnet_addr = (host, int(port) if port else 6454)
            self._artnet_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            logger.info(f"Virtual DMX: mirroring universe {universe} as Art-Net to {self._artnet_addr}")
        logger.info("Virtual DMX output initialized (simulation — no FTDI hardware)")

    def run(self):
        # Deadline-based pacing, mirroring the real dmx_interface loop.
        next_frame = time.monotonic()
        while self.running:
            self._send_frame()
            next_frame += 1 / self.FREQUENCY
            delay = next_frame - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            else:
                next_frame = time.monotonic()

    def _send_frame(self):
        state = self.dmx_state_manager.get_full_state()
        frame = bytes(max(0, min(255, int(v))) for v in state)
        now = time.time()
        # Publish on change, with a 1s heartbeat so late-joining clients sync.
        if frame != self._last_frame or now - self._last_publish >= 1.0:
            sim_state.publish_frame(frame)
            self._last_frame = frame
            self._last_publish = now
            if self._artnet_sock:
                self._send_artnet(frame)

    def _send_artnet(self, frame: bytes):
        self._artnet_seq = self._artnet_seq % 255 + 1  # 1..255, 0 means "disabled"
        packet = build_artdmx(self._artnet_seq, self.universe, frame,
                              pad_to=self.DMX_CHANNELS)
        try:
            self._artnet_sock.sendto(packet, self._artnet_addr)
        except OSError as e:
            logger.warning(f"Art-Net send failed: {e}")

    def stop(self):
        self.running = False
