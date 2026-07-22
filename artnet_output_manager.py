"""Art-Net unicast to the per-room ESP32 DMX nodes (wiring-guides/dmx-over-wifi.md).

Sibling of dmx_interface.DMXOutputManager: same 44Hz deadline-paced loop over
the same dmx_state_manager, but the sink is UDP — one shared universe unicast
to every enabled node in dmx_nodes.json. The nodes re-clock the wire locally
and hold the last frame through WiFi blips, so this sends on CHANGE plus a 1s
per-node heartbeat (late joiners / a dropped final packet converge within 1s)
instead of streaming 44Hz all the time — keeps the AP clear for room audio.

Hostname resolution is lazy and cached: a node that is down or unresolvable
never blocks the frame loop for the others, and a failed target re-resolves
with backoff so a DHCP re-lease heals on its own.
"""
import json
import logging
import os
import socket
import threading
import time

from artnet import ARTNET_PORT, build_artdmx

logger = logging.getLogger(__name__)

CONFIG_FILE = 'dmx_nodes.json'
RERESOLVE_OK = 300      # re-resolve a working target every 5 min
RERESOLVE_FAIL = 10     # a failing one every 10s


class _Target:
    def __init__(self, room, host, port):
        self.room = room
        self.host = host
        self.port = port
        self.addr = None            # resolved (ip, port)
        self.next_resolve = 0.0
        self.last_sent = 0.0
        self.warned = False

    def resolve(self, now):
        if now < self.next_resolve:
            return
        try:
            self.addr = (socket.getaddrinfo(self.host, self.port, socket.AF_INET,
                                            socket.SOCK_DGRAM)[0][4])
            self.next_resolve = now + RERESOLVE_OK
            if self.warned:
                logger.info(f"Art-Net node {self.room} ({self.host}) resolved: {self.addr[0]}")
                self.warned = False
        except OSError as e:
            self.addr = None
            self.next_resolve = now + RERESOLVE_FAIL
            if not self.warned:
                logger.warning(f"Art-Net node {self.room} ({self.host}) unresolvable: {e} "
                               f"(retrying every {RERESOLVE_FAIL}s — container mDNS? use an IP)")
                self.warned = True


class ArtNetOutputManager(threading.Thread):
    FREQUENCY = 44          # pacing of the change-detect loop (matches the FTDI thread)
    HEARTBEAT = 1.0         # per-node resend interval while the frame is static

    def __init__(self, dmx_state_manager, targets, universe=0):
        super().__init__(daemon=True)
        self.dmx_state_manager = dmx_state_manager
        self.universe = universe
        self.targets = targets
        self.running = True
        self.sequence = 0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._last_frame = None
        logger.info(f"Art-Net output initialized: universe {universe} -> "
                    f"{[t.room for t in targets]}")

    @classmethod
    def from_config(cls, dmx_state_manager, path=CONFIG_FILE):
        """Build from dmx_nodes.json, or None if it's absent / has no enabled
        nodes (FTDI-only operation — the pre-cutover default)."""
        if not os.path.exists(path):
            return None
        with open(path) as f:
            cfg = json.load(f)
        port = cfg.get('port', ARTNET_PORT)
        targets = [_Target(room, node['host'], node.get('port', port))
                   for room, node in cfg.get('nodes', {}).items()
                   if node.get('enabled')]
        if not targets:
            logger.info("dmx_nodes.json present but no nodes enabled — Art-Net output idle")
            return None
        return cls(dmx_state_manager, targets, universe=cfg.get('universe', 0))

    def run(self):
        next_frame = time.monotonic()
        while self.running:
            self.send_frame()
            next_frame += 1 / self.FREQUENCY
            delay = next_frame - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            else:
                next_frame = time.monotonic()  # fell behind; don't burst to catch up
        self.sock.close()

    def send_frame(self):
        state = self.dmx_state_manager.get_full_state()
        frame = bytes(max(0, min(255, int(v))) for v in state)
        now = time.monotonic()
        changed = frame != self._last_frame
        self._last_frame = frame
        packet = None
        for t in self.targets:
            if not (changed or now - t.last_sent >= self.HEARTBEAT):
                continue
            t.resolve(now)
            if t.addr is None:
                continue
            if packet is None:                    # build once, first needed
                self.sequence = self.sequence % 255 + 1
                packet = build_artdmx(self.sequence, self.universe, frame)
            try:
                self.sock.sendto(packet, t.addr)
                t.last_sent = now
            except OSError as e:
                logger.warning(f"Art-Net send to {t.room} ({t.addr[0]}) failed: {e}")
                t.addr = None                     # force re-resolve
                t.next_resolve = now + RERESOLVE_FAIL

    def stop(self):
        self.running = False
