import logging

logger = logging.getLogger(__name__)

# Shared timeline for the Photo Bomb camera sequence (seconds from effect start).
# INSTANT BOOTH (2026-08-22, Tim): the 3s pose countdown is gone — press IS the
# shutter. The flash fires at t=0 and HOLDS ~2.2s: the real capture (fswebcam,
# C930e) takes ~1.7-2.0s end to end — device open + 10 skipped auto-exposure
# warm-up frames — and the frame is grabbed at the END of that, so the hold
# must outlast it or night photos land in a dark room (bench-measured
# 2026-08-22). Feels instant to the person: light hits at the press.
# main.py schedules the webcam capture off SHUTTER_OFFSET and
# tools/make_photobomb_audio.py renders a synthesized fallback from these
# numbers — change them here and everything stays in sync.
POWERUP_END = 0.05   # audio-tool anchor only; there is no power-up blink now
BEEP_TIMES = []      # countdown removed — no pose window
SHUTTER_OFFSET = 0.0            # shutter fires the moment the effect starts
DURATION = 2.6


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
    """Instant camera sequence: white FLASH the moment the button lands, held
    long enough that the real webcam's frame (grab starts immediately, lands
    ~1.7-2.0s later) is taken under full light, then a quick sparkle outro. Steps
    bracket each hit tightly because the engine linearly interpolates between
    steps."""
    steps = [
        _step(SHUTTER_OFFSET, 255, 255, 255, 255, 255),   # FLASH at press
        _step(2.20, 255, 255, 255, 255, 255),             # hold: real frame lands lit
        _step(2.35, 90, 255, 240, 220, 60),               # decay
    ]

    # Sparkle outro: one quick gold pop on the way out
    steps.append(_step(2.45, 160, 255, 200, 40, 15))
    steps.append(_step(DURATION, 0, 0, 0, 0, 0))

    effect = {
        "duration": DURATION,
        "description": "Photo booth camera sequence: instant white FLASH at "
                       "the shutter (photo taken during the hold), sparkle "
                       "outro",
        "steps": steps,
        "palette_exempt_windows": [(SHUTTER_OFFSET, 2.25)],
    }
    logger.info(f"PhotoBomb-Shot effect created with {len(steps)} steps over {DURATION} seconds")
    return effect
