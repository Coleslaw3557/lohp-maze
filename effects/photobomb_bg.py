import logging

logger = logging.getLogger(__name__)

CYAN = (100, 200, 255)
LAVENDER = (180, 140, 255)
PINK = (255, 150, 200)
MINT = (140, 255, 190)
CREAM = (255, 220, 170)
GLINT = (150, 205, 240)


def _step(t, total, r, g, b, w=0):
    return {
        "time": t,
        "channels": {
            "total_dimming": total, "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def create_photobomb_bg_effect():
    """Photo-studio gallery bed for the background tracks (14.8s): slow pastel
    drift (cyan -> lavender -> pink -> mint -> cream) with three tiny lens
    glints. Stays around brightness 90 — it's a bed, not an event."""
    steps = [
        _step(0.0, 0, *CYAN),
        _step(1.0, 90, *CYAN),
        _step(3.5, 135, *LAVENDER, w=40),    # glint
        _step(3.62, 90, *LAVENDER),
        _step(6.0, 90, *PINK),
        _step(8.5, 135, *MINT, w=40),        # glint
        _step(8.62, 90, *MINT),
        _step(11.0, 90, *CREAM),
        _step(12.4, 120, *GLINT, w=50),      # glint
        _step(12.52, 85, *GLINT),
        _step(13.6, 70, *CYAN),
        _step(15.0, 0, 0, 0, 0),
    ]

    effect = {
        "duration": 15.0,
        "description": "Photo Bomb background: slow pastel studio drift with "
                       "occasional lens glints",
        "steps": steps,
    }
    logger.info(f"Photo Bomb Background effect created with {len(steps)} steps over {effect['duration']} seconds")
    return effect
