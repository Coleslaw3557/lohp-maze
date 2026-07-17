import logging

logger = logging.getLogger(__name__)

# Shared timeline for the Photo Bomb camera sequence (seconds from effect start).
# tools/make_photobomb_audio.py renders audio_files/photobomb-countdown.mp3 from
# these numbers, and main.py schedules the webcam capture off SHUTTER_OFFSET —
# change them here, regenerate the mp3, and everything stays in sync.
POWERUP_END = 0.9
BEEP_TIMES = [1.0, 2.0, 3.0]   # "3... 2... 1..." — the 3 seconds to strike a pose
SHUTTER_OFFSET = 4.0           # shutter click, white flash, photo capture
DURATION = 6.5


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
    """Camera sequence: power-up chase, 3-2-1 countdown pops, white FLASH at the
    shutter, then a sparkle outro. Steps bracket each hit tightly because the
    engine linearly interpolates between steps."""
    steps = [_step(0.0, 20, 255, 180, 120, 0)]

    # Power-up: cyan/magenta studio chase ramping in brightness
    for t, bright, (r, g, b) in [
        (0.15, 90, (0, 220, 255)), (0.35, 120, (255, 0, 220)),
        (0.55, 160, (0, 220, 255)), (0.75, 200, (255, 0, 220)),
        (POWERUP_END, 120, (255, 230, 200)),
    ]:
        steps.append(_step(t - 0.06, 45, 120, 120, 140, 0))
        steps.append(_step(t, bright, r, g, b, 20))

    # Countdown: warm amber pop on each beep, settling between them
    for beep in BEEP_TIMES:
        steps.append(_step(beep - 0.03, 70, 255, 190, 60, 0))
        steps.append(_step(beep, 255, 255, 190, 40, 120))
        steps.append(_step(beep + 0.12, 200, 255, 190, 40, 60))
        steps.append(_step(beep + 0.40, 90, 255, 200, 90, 10))

    # Anticipation dip, then the FLASH
    steps.append(_step(3.5, 60, 255, 210, 120, 0))
    steps.append(_step(SHUTTER_OFFSET - 0.05, 25, 255, 220, 160, 0))
    steps.append(_step(SHUTTER_OFFSET, 255, 255, 255, 255, 255))
    steps.append(_step(SHUTTER_OFFSET + 0.15, 255, 255, 255, 255, 255))
    steps.append(_step(SHUTTER_OFFSET + 0.45, 90, 255, 240, 220, 60))
    steps.append(_step(SHUTTER_OFFSET + 0.70, 35, 255, 220, 180, 0))

    # Sparkle outro: decaying colour pops
    for t, bright, (r, g, b) in [
        (4.9, 180, (255, 200, 40)), (5.2, 150, (0, 220, 255)),
        (5.5, 120, (255, 0, 220)), (5.8, 90, (255, 200, 40)),
        (6.05, 60, (120, 200, 255)),
    ]:
        steps.append(_step(t - 0.06, 30, 200, 180, 160, 0))
        steps.append(_step(t, bright, r, g, b, 15))

    steps.append(_step(6.4, 5, 120, 110, 100, 0))
    steps.append(_step(DURATION, 0, 0, 0, 0, 0))

    effect = {
        "duration": DURATION,
        "description": "Photo booth camera sequence: power-up, 3-2-1 countdown, "
                       "white FLASH at the shutter (photo taken), sparkle outro",
        "steps": steps,
    }
    logger.info(f"PhotoBomb-Shot effect created with {len(steps)} steps over {DURATION} seconds")
    return effect
