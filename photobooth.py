"""Photo Bomb room game state.

The room is a fast-paced photo booth: entering starts the room bed
(PhotoBomb-BG), and each shutter-button press fires the camera flash —
one "shot". Shots are limited by a ROLLING WINDOW (Tim 2026-08-22,
supersedes the 5-per-visitor budget): up to MAX_SHOTS photos within any
WINDOW_S seconds. A press past that runs the failure effect instead of a
flash, and presses become shots again on their own as the window drains —
no turnover needed. Room turnover (the node reports the room vacated, or
a fresh entry trigger fires) still clears the window outright so the next
visitor starts full.

Pure state, no asyncio — main.py owns the wiring (which effects fire) and
camera_manager.py owns the photos.
"""
import time
from collections import deque


class PhotoBoothSession:
    MAX_SHOTS = 5
    WINDOW_S = 15.0

    def __init__(self, max_shots=MAX_SHOTS, window_s=WINDOW_S, clock=time.monotonic):
        self.max_shots = max_shots
        self.window_s = window_s
        self._clock = clock
        self._shots = deque()   # monotonic timestamps of shots still in the window

    @property
    def shots_used(self):
        self._prune(self._clock())
        return len(self._shots)

    def _prune(self, now):
        while self._shots and now - self._shots[0] > self.window_s:
            self._shots.popleft()

    def entered(self):
        """Entry trigger fired — treat as a fresh visitor."""
        self._shots.clear()

    def vacated(self):
        """The node reported the room empty — session over."""
        self._shots.clear()

    def press(self):
        """Record a shutter press. True = fire the shot; False = the window is
        full (max_shots in the last window_s seconds), run the failure cue
        instead. Unlike the old per-visitor budget, refusal is temporary: the
        oldest shot ages out of the window and presses work again."""
        now = self._clock()
        self._prune(now)
        if len(self._shots) >= self.max_shots:
            return False
        self._shots.append(now)
        return True
