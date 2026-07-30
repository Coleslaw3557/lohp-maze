import logging

logger = logging.getLogger(__name__)

WASH = (255, 40, 160)
AFTER = (255, 230, 250)

# Paparazzi shutter bursts: dense opening flurry, scattered mid pops, a late
# triple-burst finale. Spacing never dips under 0.35s so the tight flash
# brackets can't overlap.
FLASH_TIMES = (0.4, 0.9, 1.25, 1.8, 2.15, 2.5, 2.85, 3.2, 3.55, 3.9,
               4.25, 4.6, 4.95, 5.3, 5.9, 6.6, 7.4, 7.75, 8.6, 9.5,
               9.85, 10.7, 11.05, 11.4, 11.75)


def _step(t, total, r, g, b, w=0):
    return {
        "time": t,
        "channels": {
            "total_dimming": total, "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def create_photobomb_spot_effect():
    """Paparazzi swarm for the photo-reaction sequences (3.7-13.6s): magenta
    glamour wash under a hail of white camera flashes, front-loaded so the
    short reaction clips still catch the thick of it."""
    steps = [_step(0.0, 0, *WASH), _step(0.25, 70, *WASH)]

    for t in FLASH_TIMES:
        steps.append(_step(round(t - 0.04, 2), 70, *WASH))
        steps.append(_step(t, 255, 255, 255, 255, 255))
        steps.append(_step(round(t + 0.09, 2), 200, *AFTER, w=140))
        steps.append(_step(round(t + 0.28, 2), 70, *WASH))

    steps.append(_step(12.6, 60, *WASH))
    steps.append(_step(14.0, 0, 0, 0, 0))

    effect = {
        "duration": 14.0,
        "description": "Photo Bomb spotted: magenta glamour wash under an "
                       "accelerating hail of paparazzi camera flashes",
        "steps": steps,
    }
    logger.info(f"PhotoBomb-Spot effect created with {len(steps)} steps over {effect['duration']} seconds")
    return effect
