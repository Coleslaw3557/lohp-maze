"""Shared state between the virtual DMX output thread and the sim web UI.

The virtual DMX thread publishes the latest raw universe frame here; the
sim UI's websocket loop reads it. Plain module globals — assignment is
atomic under the GIL, and readers only ever need "the latest frame".
"""
import time

# Raw DMX channels 1..168 (21 fixtures x 8 channels), exactly what the FTDI
# interface would put on the wire after the start code.
latest_frame = bytes(168)
frame_seq = 0
started_at = time.time()


def publish_frame(frame: bytes):
    global latest_frame, frame_seq
    latest_frame = frame
    frame_seq += 1
