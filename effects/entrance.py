import logging

from effect_utils import COPPER, EMBER

logger = logging.getLogger(__name__)

# Torch tones come from the shared standard (effect_utils): COPPER g/r 0.35
# for the catching flicker, EMBER 0.37 for the reveal/glow. The old local
# EMBER (255,120,20) ran g/r 0.47 — high enough green drive to read yellow
# on a par (2026-08-17). The reveal is carried by brightness, not by a
# yellower hue.
FLICKER = COPPER           # (230, 80, 20)
GOLD = EMBER               # (255, 95, 10)
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
        _step(0.0, 0, *FLICKER),
        # Torches catching — irregular ember flicker upward
        _step(0.5, 60, *FLICKER),
        _step(0.9, 35, *FLICKER),
        _step(1.3, 85, *FLICKER),
        _step(1.7, 50, *FLICKER),
        _step(2.1, 110, *FLICKER),
        _step(2.6, 70, *FLICKER),
        # Build and reveal
        _step(3.5, 150, *GOLD),
        _step(4.0, 40, *GOLD),
        _step(4.1, 230, *GOLD, w=0),
        _step(4.35, 180, *GOLD),
        # Teal shimmer accents against the gold
        _step(5.0, 160, *TEAL),
        _step(5.6, 190, *GOLD),
        _step(6.2, 150, *TEAL),
        _step(6.8, 200, *GOLD),
        # Welcome glow breathing, then out
        _step(8.0, 140, *GOLD),
        _step(9.5, 180, *FLICKER),
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
