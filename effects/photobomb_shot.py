import logging

logger = logging.getLogger(__name__)

# Shared timeline for the Photo Bomb camera sequence (seconds from effect start).
# INSTANT BOOTH (2026-08-22, Tim): the 3s pose countdown is gone — press IS
# the shutter. Same night the WARM GRABBER landed (camera_manager: the webcam
# streams continuously, capture = copy the current frame), so the photo lands
# ~0.3s after the press and the 0.55s flash hold covers it. Degraded mode: if
# the warm grabber is down, the cold fswebcam fallback's frame lands ~1.8s in,
# after this flash — photo still taken, just not flash-lit. Light hits at the
# press; the snap plays on the node itself.
# main.py schedules the webcam capture off SHUTTER_OFFSET and
# tools/make_photobomb_audio.py renders a synthesized fallback from these
# numbers — change them here and everything stays in sync.
POWERUP_END = 0.05   # audio-tool anchor only; there is no power-up blink now
BEEP_TIMES = []      # countdown removed — no pose window
SHUTTER_OFFSET = 0.0            # shutter fires the moment the effect starts
DURATION = 1.0


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
    long enough that the warm-stream frame (copied ~0.3s in) is taken under
    full light, then a quick sparkle outro. Steps
    bracket each hit tightly because the engine linearly interpolates between
    steps."""
    steps = [
        _step(SHUTTER_OFFSET, 255, 255, 255, 255, 255),   # FLASH at press
        _step(0.55, 255, 255, 255, 255, 255),             # hold: warm frame lands lit
        _step(0.72, 90, 255, 240, 220, 60),               # decay
    ]

    # Sparkle outro: one quick gold pop on the way out
    steps.append(_step(0.82, 160, 255, 200, 40, 15))
    steps.append(_step(DURATION, 0, 0, 0, 0, 0))

    effect = {
        "duration": DURATION,
        "description": "Photo booth camera sequence: instant white FLASH at "
                       "the shutter (photo taken during the hold), sparkle "
                       "outro",
        "steps": steps,
        "palette_exempt_windows": [(SHUTTER_OFFSET, 0.60)],
    }
    logger.info(f"PhotoBomb-Shot effect created with {len(steps)} steps over {DURATION} seconds")
    return effect
