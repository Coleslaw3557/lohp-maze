"""Drop-in replacement for dmx_interface — no FTDI hardware required.

run_server.py installs this module as `dmx_interface` in sys.modules before
main.py is executed, so the real server runs its normal 44Hz output loop
against a virtual sink instead of the USB-DMX dongle. The frame that would
have gone down the wire is published to sim_state for the web UI, and can
optionally also be unicast as Art-Net for external visualizers (BlenderDMX,
QLC+, ...):

    SIM_ARTNET=192.168.1.50        # or ip:port; universe 0, 44Hz
"""
import logging
import os
import socket
import threading
import time

import sim_state

logger = logging.getLogger(__name__)


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
        while self.running:
            self._send_frame()
            time.sleep(1 / self.FREQUENCY)

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
        data = frame.ljust(self.DMX_CHANNELS, b'\x00')
        packet = (
            b'Art-Net\x00'
            + bytes([0x00, 0x50])                        # OpDmx, little-endian
            + bytes([0x00, 0x0e])                        # protocol version 14
            + bytes([self._artnet_seq, 0x00])            # sequence, physical
            + self.universe.to_bytes(2, 'little')        # SubUni + Net
            + len(data).to_bytes(2, 'big')
            + data
        )
        try:
            self._artnet_sock.sendto(packet, self._artnet_addr)
        except OSError as e:
            logger.warning(f"Art-Net send failed: {e}")

    def stop(self):
        self.running = False
