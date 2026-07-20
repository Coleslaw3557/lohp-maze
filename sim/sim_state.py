"""Shared state between the virtual DMX output thread and the sim web UI.

The virtual DMX thread publishes the latest raw universe frame here; the
sim UI's websocket loop reads it. Plain module globals — assignment is
atomic under the GIL, and readers only ever need "the latest frame".
"""
import time

# Raw DMX channels 1..352 (44 fixtures x 8 channels: 20 maze pars/spots + the
# 24 Camp Sign zones), exactly what the FTDI interface would put on the wire
# after the start code. Placeholder until the first real frame is published —
# keep the size in sync with main.py NUM_FIXTURES.
latest_frame = bytes(352)
frame_seq = 0
started_at = time.time()


def publish_frame(frame: bytes):
    global latest_frame, frame_seq
    latest_frame = frame
    frame_seq += 1
