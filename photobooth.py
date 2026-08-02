"""Photo Bomb room game state.

The room is a fast-paced photo booth: entering starts the room bed
(PhotoBomb-BG), and each shutter-button press runs the camera countdown —
one "shot". A visitor gets MAX_SHOTS shots; presses past the budget are the
cue to leave, so main.py swaps them to the failure effect instead of a
countdown. The budget resets when the room turns over:

  - the node reports the room vacated (leave_action in triggers.json), or
  - a fresh entry trigger fires (next visitor walked in), or
  - COOLDOWN_S passes with no presses (the radar never saw the last
    visitor leave — the 1-minute cooldown is the failsafe reset).

Pure state, no asyncio — main.py owns the wiring (which effects fire) and
camera_manager.py owns the photos.
"""
import time


class PhotoBoothSession:
    MAX_SHOTS = 5
    COOLDOWN_S = 60.0

    def __init__(self, max_shots=MAX_SHOTS, cooldown_s=COOLDOWN_S, clock=time.monotonic):
        self.max_shots = max_shots
        self.cooldown_s = cooldown_s
        self._clock = clock
        self._shots = 0
        self._last_press = None

    @property
    def shots_used(self):
        return self._shots

    def entered(self):
        """Entry trigger fired — treat as a fresh visitor."""
        self._shots = 0
        self._last_press = None

    def vacated(self):
        """The node reported the room empty — session over."""
        self._shots = 0
        self._last_press = None

    def press(self):
        """Record a shutter press. True = run the countdown; False = budget
        blown, run the failure cue instead. Over-budget presses keep failing
        (and keep the cooldown clock running) until a reset."""
        now = self._clock()
        if self._last_press is not None and now - self._last_press > self.cooldown_s:
            self._shots = 0
        self._last_press = now
        if self._shots >= self.max_shots:
            return False
        self._shots += 1
        return True
