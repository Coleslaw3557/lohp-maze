#!/usr/bin/env python3
"""Bench + regression tool for the Art-Net room-node path (dmx-over-wifi.md).

    python3 tools/artnet_check.py --selftest
        Offline regression: spins a real DMXStateManager + ArtNetOutputManager
        against a loopback UDP listener and asserts packet format, change-
        detect bursting, the 1s heartbeat, and multi-target fanout. Run it
        like sim/tools/concurrency_test.py — no hardware, no server.

    python3 tools/artnet_check.py --listen [--port 6454]
        Be a fake node: decode incoming ArtDMX and print universe/seq/first
        16 channels. Point a dmx_nodes.json entry at this box to verify the
        server side, or run it next to a flashed node to sniff what it sees.
"""
import argparse
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from artnet import ARTNET_PORT, build_artdmx, parse_artdmx  # noqa: E402


def listen(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', port))
    print(f"listening for ArtDMX on :{port} — ctrl-c to stop")
    n = 0
    while True:
        packet, addr = sock.recvfrom(2048)
        parsed = parse_artdmx(packet)
        if not parsed:
            print(f"{addr[0]}: {len(packet)}B non-ArtDMX packet ignored")
            continue
        seq, universe, data = parsed
        n += 1
        print(f"#{n} {addr[0]} u{universe} seq{seq:3d} len{len(data)} "
              f"ch1-16: {' '.join(f'{b:3d}' for b in data[:16])}")


def selftest():
    from dmx_state_manager import DMXStateManager
    from artnet_output_manager import ArtNetOutputManager, _Target

    # -- packet format matches the parser and the documented layout ----------
    pkt = build_artdmx(7, 0, bytes([1, 2, 3]), pad_to=512)
    assert len(pkt) == 18 + 512, f"packet length {len(pkt)}"
    assert pkt[:8] == b'Art-Net\x00' and pkt[8:10] == b'\x00\x50'
    seq, universe, data = parse_artdmx(pkt)
    assert (seq, universe, data[:4]) == (7, 0, bytes([1, 2, 3, 0]))
    assert parse_artdmx(b'not artnet at all!') is None
    print("OK  packet format")

    # -- live loop against two loopback listeners ----------------------------
    listeners = []
    for _ in range(2):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(('127.0.0.1', 0))
        s.settimeout(2.0)
        listeners.append(s)

    state = DMXStateManager(44, 8)
    targets = [_Target(f'test{i}', '127.0.0.1', s.getsockname()[1])
               for i, s in enumerate(listeners)]
    mgr = ArtNetOutputManager(state, targets, universe=0)
    mgr.start()
    try:
        # first frame reaches every target
        for s in listeners:
            seq, universe, data = parse_artdmx(s.recvfrom(2048)[0])
            assert universe == 0 and data == bytes(512)
        print("OK  initial frame to all targets")

        # a state change shows up promptly with the new bytes
        state.update_fixture(2, [10, 20, 30, 40, 50, 60, 70, 80])
        deadline = time.monotonic() + 1.0
        got = None
        while time.monotonic() < deadline:
            _, _, data = parse_artdmx(listeners[0].recvfrom(2048)[0])
            if data[16:24] == bytes([10, 20, 30, 40, 50, 60, 70, 80]):
                got = time.monotonic()
                break
        assert got, "changed frame never arrived"
        print("OK  change propagates (fixture 2 -> ch17-24)")

        # static state throttles to the ~1s heartbeat, not 44Hz
        for s in listeners:  # drain anything queued
            s.setblocking(False)
            try:
                while True:
                    s.recvfrom(2048)
            except BlockingIOError:
                pass
            s.settimeout(3.0)
        t0 = time.monotonic()
        count = 0
        while time.monotonic() - t0 < 2.2:
            try:
                listeners[0].recvfrom(2048)
                count += 1
            except socket.timeout:
                break
        assert 1 <= count <= 4, f"heartbeat rate wrong: {count} packets in 2.2s"
        print(f"OK  static heartbeat ({count} packets in 2.2s)")
    finally:
        mgr.stop()
        mgr.join(timeout=2)
        for s in listeners:
            s.close()
    print("SELFTEST PASS")


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--selftest', action='store_true')
    mode.add_argument('--listen', action='store_true')
    ap.add_argument('--port', type=int, default=ARTNET_PORT)
    args = ap.parse_args()
    if args.selftest:
        selftest()
    else:
        listen(args.port)
