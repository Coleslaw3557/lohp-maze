import logging

logger = logging.getLogger(__name__)

ORANGE = (255, 120, 20)
TEAL = (0, 190, 170)
PINK = (255, 40, 180)
VIOLET = (190, 40, 255)
GOLD = (255, 200, 40)
WHITE = (255, 255, 255)


def _step(t, total, r, g, b, w=0):
    return {
        "time": t,
        "channels": {
            "total_dimming": total, "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def create_spark_pony_effect():
    """Sparkle Pony arc for the door-lift mixes (14.0-14.8s): three straining
    orange heave pulses, a deadpan GLaDOS teal beat, an EXCESSIVE pink/white
    sparkle cascade, and a gold whinny bounce to finish."""
    steps = [_step(0.0, 0, *ORANGE)]

    # Effortful heaves — the third one bigger
    for start, peak in ((0.3, 170), (1.8, 175), (3.3, 190)):
        steps.append(_step(start, 60, *ORANGE))
        steps.append(_step(round(start + 0.8, 2), peak, *ORANGE))
        steps.append(_step(round(start + 1.2, 2), 85, *ORANGE))

    # Door clunks into place; GLaDOS deadpan in flat teal
    steps.append(_step(4.75, 30, *ORANGE))
    steps.append(_step(5.1, 70, *TEAL))
    steps.append(_step(6.0, 85, *TEAL))
    steps.append(_step(6.9, 65, *TEAL))
    steps.append(_step(7.7, 80, *TEAL))

    # Excessive sparkle cascade
    colors = (PINK, WHITE, VIOLET, GOLD)
    for i in range(12):
        t = round(8.0 + i * 0.4, 2)
        c = colors[i % 4]
        w = 180 if c == WHITE else 30
        steps.append(_step(round(t - 0.05, 2), 60, *PINK))
        steps.append(_step(t, 240, *c, w=w))
        steps.append(_step(round(t + 0.15, 2), 120, *PINK))

    # Whinny bounce, then out
    steps.append(_step(12.9, 200, *GOLD, w=60))
    steps.append(_step(13.15, 90, *GOLD))
    steps.append(_step(13.4, 230, *GOLD, w=80))
    steps.append(_step(13.7, 110, *GOLD))
    steps.append(_step(15.0, 0, 0, 0, 0))

    effect = {
        "duration": 15.0,
        "description": "Sparkle Pony door lift: straining heaves, GLaDOS "
                       "deadpan, excessive sparkle cascade, whinny bounce",
        "steps": steps,
    }
    logger.info(f"Spark Pony effect created with {len(steps)} steps over {effect['duration']} seconds")
    return effect
