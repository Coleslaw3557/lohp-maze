import logging

logger = logging.getLogger(__name__)

SKY = (80, 150, 255)
SUCCESS = (120, 255, 160)
POP = (200, 255, 220)


def _step(t, total, r, g, b, w=0):
    return {
        "time": t,
        "channels": {
            "total_dimming": total, "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def create_image_enhancement_effect():
    """Guy Line Climb ascent, sized to the climb mixes (13.8-14.7s): rising
    sky-blue climb cycles (each starting higher than the last), exposed wind
    shimmer at the top, helicopter-extraction pops, success hold, fade."""
    steps = [_step(0.0, 0, *SKY)]

    # Three climb cycles from a rising floor: grip, pull up, settle, reach
    for start, floor in ((0.0, 40), (2.8, 70), (5.6, 100)):
        steps.append(_step(round(start + 0.15, 2), floor, *SKY))
        steps.append(_step(round(start + 2.1, 2), floor + 80, *SKY, w=15))
        steps.append(_step(round(start + 2.55, 2), floor + 55, *SKY))
        steps.append(_step(round(start + 2.75, 2), max(35, floor - 10), *SKY))

    # Final push to the top
    steps.append(_step(8.55, 130, *SKY))
    steps.append(_step(10.4, 210, *SKY, w=30))

    # Exposure: wind shimmer at altitude
    steps.append(_step(10.8, 190, *SKY, w=40))
    steps.append(_step(11.2, 215, *SKY, w=10))
    steps.append(_step(11.6, 195, *SKY, w=45))
    steps.append(_step(12.0, 220, *SKY, w=15))

    # Extraction: three rotor-strobe pops
    for t in (12.5, 12.9, 13.3):
        steps.append(_step(round(t - 0.05, 2), 90, *SKY))
        steps.append(_step(t, 255, *POP, w=0))
        steps.append(_step(round(t + 0.12, 2), 210, *SKY, w=40))

    # Success hold, then out
    steps.append(_step(13.8, 255, *SUCCESS, w=40))
    steps.append(_step(14.3, 200, *SUCCESS, w=40))
    steps.append(_step(15.0, 0, 0, 0, 0))

    effect = {
        "duration": 15.0,
        "description": "Guy Line Climb ascent: rising climb cycles, wind "
                       "shimmer, helicopter extraction pops, success hold",
        "steps": steps,
    }
    logger.info(f"Image Enhancement effect created with {len(steps)} steps over {effect['duration']} seconds")
    return effect
