import logging

logger = logging.getLogger(__name__)

GOLD = (255, 195, 25)
GREEN = (70, 255, 100)
BRIGHT = (255, 220, 90)


def _step(t, total, r, g, b, w=0):
    return {
        "time": t,
        "channels": {
            "total_dimming": total, "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def create_bike_lock_room_effect():
    """Victory payoff for the correct pair (Doom secret / Diablo quest unlocks,
    2.45-3.45s): double gold secret-found flash, gold/green celebration
    shimmer, triumphant swell, fade."""
    steps = [
        _step(0.0, 10, 40, 30, 0),
        _step(0.1, 255, *GOLD, w=140),       # secret found!
        _step(0.25, 255, *GOLD, w=90),
        _step(0.45, 120, *GOLD),
        _step(0.6, 245, *GOLD, w=60),
        _step(0.75, 130, *GOLD),
        # Celebration shimmer
        _step(0.95, 200, *GREEN),
        _step(1.25, 210, *GOLD),
        _step(1.55, 220, *GREEN),
        _step(1.85, 230, *GOLD),
        _step(2.15, 210, *GREEN),
        # Triumphant swell, then out
        _step(2.5, 220, *GOLD, w=60),
        _step(3.1, 255, *BRIGHT, w=110),
        _step(3.5, 160, *GOLD),
        _step(4.0, 0, 0, 0, 0),
    ]

    effect = {
        "duration": 4.0,
        "description": "Bike Lock victory: gold secret-found flashes, "
                       "gold/green shimmer, triumphant swell",
        "steps": steps,
    }
    logger.info(f"BikeLockRoom effect created with {len(steps)} steps over {effect['duration']} seconds")
    return effect
