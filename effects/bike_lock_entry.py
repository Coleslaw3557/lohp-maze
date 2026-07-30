import logging

logger = logging.getLogger(__name__)


def create_bike_lock_entry_effect():
    """Entry prompt for the four-button pair puzzle: door powers up, then four
    quick 'input ready' blips (mirrors the pack's rapid/entry audio cues; the
    victory show stays BikeLockRoom)."""
    effect = {
        "duration": 3.0,
        "description": "Quake-style door activation prompt for Bike Lock Room entry",
        "steps": []
    }

    def step(time, total, r, g, b, w=0):
        effect["steps"].append({
            "time": time,
            "channels": {
                "total_dimming": total,
                "r_dimming": r,
                "g_dimming": g,
                "b_dimming": b,
                "w_dimming": w,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })

    # Door power-up: green-cyan ramp
    for i in range(7):
        step(i * 0.1, int(200 * i / 6), 0, 255, 120)
    step(0.8, 70, 0, 255, 120)

    # Four quick blips — one per button input going live
    for i in range(4):
        t = 1.0 + i * 0.4
        step(t, 255, 60, 255, 60, 40)
        step(t + 0.2, 70, 0, 255, 120)

    step(3.0, 0, 0, 0, 0)

    logger.info(f"BikeLock-Entry effect created with {len(effect['steps'])} steps over {effect['duration']} seconds")
    return effect
