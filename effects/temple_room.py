import logging

logger = logging.getLogger(__name__)

# Temple Room entry — the room's first light show (it had no trigger, no
# effect and no audio until 2026-08-17: "future spec" in
# wiring-guides/room-experience-audit-2026-07.md).
#
# Slow on purpose: Temple wears the maze's slowest room profile (rate 0.58,
# jade-teal 35/145/130) and sits beside the Monkey Room's guard ambush — the
# stone room should wake and watch, not jump. Light-only for now; its audio
# pool is registered empty, so anything dropped in via the audio console plays
# without touching this timeline. Time a future pack to this cadence rather
# than reflowing the lights.
DURATION = 5.0


def _step(t, total, r, g, b, w):
    return {
        "time": t,
        "channels": {
            "total_dimming": total, "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def create_temple_wake_effect():
    """Temple Room entry — the temple notices you: cold stone breath, a wall
    torch catching, the jade idol waking and holding its look, then the room
    settling back to its watch. No white, no yellow (palette rule)."""
    STONE = (20, 105, 100)     # damp teal stone, the room's resting colour
    TORCH = (255, 105, 10)     # EMBER — the only warm note in the room
    JADE = (25, 230, 110)      # the idol
    DEEP = (10, 60, 70)        # the dark between breaths

    steps = [
        # Cold stone breath — the room registers a body in the doorway
        _step(0.00, 60, *DEEP, 0),
        _step(0.35, 130, *STONE, 0),
        _step(0.80, 85, *DEEP, 0),

        # A wall torch catches, gutters, holds
        _step(1.10, 175, *TORCH, 0),
        _step(1.28, 95, 200, 70, 5, 0),
        _step(1.46, 165, *TORCH, 0),
        _step(1.75, 100, *STONE, 0),

        # The idol wakes: jade rising out of the stone
        _step(2.10, 140, 20, 170, 105, 0),
        _step(2.45, 200, *JADE, 0),

        # It holds its look — two slow pulses, the second lower
        _step(2.95, 120, *STONE, 0),
        _step(3.30, 185, *JADE, 0),
        _step(3.75, 105, *STONE, 0),

        # Back to the watch, dark enough for the room's held colour to take over
        _step(4.20, 70, *DEEP, 0),
        _step(4.65, 30, *DEEP, 0),
        _step(DURATION, 0, 0, 0, 0, 0),
    ]

    effect = {
        "duration": DURATION,
        "description": "Temple Room entry — stone breath, a torch catching, "
                       "the jade idol waking and holding its look, settling "
                       "back to the watch",
        "steps": steps,
    }
    logger.info(f"TempleWake effect created with {len(steps)} steps over {DURATION} seconds")
    return effect
