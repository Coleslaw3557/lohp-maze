import logging

logger = logging.getLogger(__name__)

EMBER = (255, 120, 20)
GOLD = (255, 180, 40)
TEAL = (0, 190, 170)


def _step(t, total, r, g, b, w=0):
    return {
        "time": t,
        "channels": {
            "total_dimming": total, "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def create_entrance_effect():
    """Temple mouth at the START sign: torches catch one by one, a gold
    reveal swell with teal Hidden-Temple accents, then an inviting glow.
    (Audio is still the placeholder gag set — retheme again with its pack.)"""
    steps = [
        _step(0.0, 0, *EMBER),
        # Torches catching — irregular ember flicker upward
        _step(0.5, 60, *EMBER),
        _step(0.9, 35, *EMBER),
        _step(1.3, 85, *EMBER),
        _step(1.7, 50, *EMBER),
        _step(2.1, 110, *EMBER),
        _step(2.6, 70, *EMBER),
        # Build and reveal
        _step(3.5, 150, *GOLD),
        _step(4.0, 40, *GOLD),
        _step(4.1, 230, *GOLD, w=60),
        _step(4.35, 180, *GOLD),
        # Teal shimmer accents against the gold
        _step(5.0, 160, *TEAL),
        _step(5.6, 190, *GOLD),
        _step(6.2, 150, *TEAL),
        _step(6.8, 200, *GOLD),
        # Welcome glow breathing, then out
        _step(8.0, 140, *GOLD),
        _step(9.5, 180, *EMBER),
        _step(11.0, 130, *GOLD),
        _step(12.5, 160, *GOLD),
        _step(15.0, 0, 0, 0, 0),
    ]

    effect = {
        "duration": 15.0,
        "description": "Entrance: torches catch, gold temple reveal with teal "
                       "accents, inviting glow",
        "steps": steps,
    }
    logger.info(f"Entrance effect created with {len(steps)} steps over {effect['duration']} seconds")
    return effect
