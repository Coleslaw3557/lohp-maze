import logging

logger = logging.getLogger(__name__)

# Shared timeline for the Photo Bomb camera sequence (seconds from effect start).
# The trigger sound assigned to PhotoBomb-Shot in the audio console should fit
# this: press -> 3 seconds to strike a pose -> shutter. main.py schedules the
# webcam capture off SHUTTER_OFFSET and tools/make_photobomb_audio.py renders a
# synthesized fallback from these numbers — change them here and everything
# stays in sync.
POWERUP_END = 0.4
BEEP_TIMES = [0.75, 1.5, 2.25]  # countdown pops inside the 3s pose window
SHUTTER_OFFSET = 3.0            # shutter click, white flash, photo capture
DURATION = 4.4


def _step(t, total, r, g, b, w):
    return {
        "time": t,
        "channels": {
            "total_dimming": total, "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def create_photobomb_shot_effect():
    """Fast camera sequence: a blink of studio power-up, countdown pops through
    the 3-second pose window, white FLASH at the shutter, short sparkle outro.
    Steps bracket each hit tightly because the engine linearly interpolates
    between steps."""
    steps = [_step(0.0, 20, 255, 180, 120, 0)]

    # Power-up: one quick cyan/magenta studio blink ramping in
    for t, bright, (r, g, b) in [
        (0.14, 110, (0, 220, 255)), (0.28, 160, (255, 0, 220)),
        (POWERUP_END, 120, (255, 230, 200)),
    ]:
        steps.append(_step(t - 0.05, 45, 120, 120, 140, 0))
        steps.append(_step(t, bright, r, g, b, 20))

    # Countdown: warm amber pop on each beep, settling between them
    for beep in BEEP_TIMES:
        steps.append(_step(beep - 0.03, 70, 255, 190, 60, 0))
        steps.append(_step(beep, 255, 255, 190, 40, 120))
        steps.append(_step(beep + 0.10, 200, 255, 190, 40, 60))
        steps.append(_step(beep + 0.32, 90, 255, 200, 90, 10))

    # Anticipation dip, then the FLASH
    steps.append(_step(2.62, 45, 255, 210, 120, 0))
    steps.append(_step(SHUTTER_OFFSET - 0.05, 25, 255, 220, 160, 0))
    steps.append(_step(SHUTTER_OFFSET, 255, 255, 255, 255, 255))
    steps.append(_step(SHUTTER_OFFSET + 0.15, 255, 255, 255, 255, 255))
    steps.append(_step(SHUTTER_OFFSET + 0.40, 90, 255, 240, 220, 60))
    steps.append(_step(SHUTTER_OFFSET + 0.60, 35, 255, 220, 180, 0))

    # Sparkle outro: three quick decaying colour pops
    for t, bright, (r, g, b) in [
        (3.75, 160, (255, 200, 40)), (3.95, 120, (0, 220, 255)),
        (4.12, 90, (255, 0, 220)),
    ]:
        steps.append(_step(t - 0.05, 30, 200, 180, 160, 0))
        steps.append(_step(t, bright, r, g, b, 15))

    steps.append(_step(4.3, 5, 120, 110, 100, 0))
    steps.append(_step(DURATION, 0, 0, 0, 0, 0))

    effect = {
        "duration": DURATION,
        "description": "Photo booth camera sequence: power-up blink, 3-second "
                       "pose countdown, white FLASH at the shutter (photo "
                       "taken), sparkle outro",
        "steps": steps,
    }
    logger.info(f"PhotoBomb-Shot effect created with {len(steps)} steps over {DURATION} seconds")
    return effect
