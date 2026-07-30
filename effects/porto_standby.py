import logging

logger = logging.getLogger(__name__)

EMBER = (255, 140, 30)
JUNGLE = (70, 200, 90)


def _step(t, total, r, g, b, w=0):
    return {
        "time": t,
        "channels": {
            "total_dimming": total, "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def create_porto_standby_effect():
    """Porto Room ambience bed (temple/playa packs, 14.8s): low bonfire ember
    flicker with two slow jungle-green breaths. Deliberately subtle — peaks
    stay under ~90 so the room reads as a glow, not an event."""
    steps = [_step(0.0, 0, *EMBER)]

    # Ember flicker (irregular, hand-placed)
    for t, level in ((0.5, 55), (1.2, 80), (1.9, 60), (2.4, 88),
                     (3.3, 50), (4.0, 75), (4.8, 62)):
        steps.append(_step(t, level, *EMBER))

    # First jungle breath
    steps.append(_step(5.8, 66, *JUNGLE))
    steps.append(_step(6.6, 78, *JUNGLE))

    # Back to embers
    for t, level in ((7.4, 58), (8.1, 84), (8.9, 52), (9.6, 76)):
        steps.append(_step(t, level, *EMBER))

    # Second jungle breath
    steps.append(_step(10.4, 68, *JUNGLE))
    steps.append(_step(11.2, 80, *JUNGLE))

    # Embers settle and fade out with the bed
    for t, level in ((12.0, 60), (12.8, 82), (13.6, 48)):
        steps.append(_step(t, level, *EMBER))
    steps.append(_step(15.0, 0, 0, 0, 0))

    effect = {
        "duration": 15.0,
        "description": "Porto Room standby: subtle bonfire ember flicker with "
                       "slow jungle-green breaths",
        "steps": steps,
    }
    logger.info(f"Porto Standby effect created with {len(steps)} steps over {effect['duration']} seconds")
    return effect
