import logging

logger = logging.getLogger(__name__)

RED = (255, 30, 20)
AMBER = (255, 150, 40)


def _step(t, total, r, g, b, w=0):
    return {
        "time": t,
        "channels": {
            "total_dimming": total, "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def create_porto_hit_effect():
    """Occupied-door knock denial (pack responses run 1.1-3.4s): two hard red
    strikes, an amber handle-jiggle tremble, a dim red locked hold, out.
    Front-loaded so even the shortest denial clip gets the full red hit."""
    steps = [
        _step(0.0, 0, *RED),
        _step(0.05, 255, *RED, w=40),
        _step(0.18, 255, *RED),
        _step(0.4, 60, *RED),
        _step(0.55, 240, *RED),
        _step(0.68, 240, *RED),
        _step(0.9, 50, *RED),
    ]

    # Handle-jiggle tremble
    for t, level in ((1.05, 95), (1.17, 45), (1.29, 88),
                     (1.41, 42), (1.53, 80), (1.65, 40)):
        steps.append(_step(t, level, *AMBER))

    # Locked: dim red hold, then out
    steps.append(_step(1.9, 70, *RED))
    steps.append(_step(2.5, 70, *RED))
    steps.append(_step(3.5, 0, 0, 0, 0))

    effect = {
        "duration": 3.5,
        "description": "Porto knock denied: double red strike, handle-jiggle "
                       "tremble, locked red hold",
        "steps": steps,
    }
    logger.info(f"Porto Hit effect created with {len(steps)} steps over {effect['duration']} seconds")
    return effect
