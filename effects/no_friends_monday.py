import logging

logger = logging.getLogger(__name__)

INDIGO = (60, 60, 255)
GOLD = (255, 190, 40)
MAGENTA = (255, 40, 180)
CYAN = (0, 200, 255)


def _step(t, total, r, g, b, w=0):
    return {
        "time": t,
        "channels": {
            "total_dimming": total, "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def create_no_friends_monday_effect():
    """Lonely-Monday gag that turns into the survival disco: dim indigo
    nobody-came open, one hesitant pulse, then a four-on-the-floor
    gold/magenta/cyan disco build with a mirror-ball pop, and a last lonely
    indigo wink out. (Audio still the placeholder set — retheme with its pack.)"""
    steps = [
        _step(0.0, 0, *INDIGO),
        _step(1.0, 55, *INDIGO),
        _step(2.0, 40, *INDIGO),
        # One hesitant pulse
        _step(2.6, 90, *INDIGO),
        _step(3.0, 45, *INDIGO),
    ]

    # Disco build: steady beat, colors rotating. Capped at 220 so the par
    # wash can't swamp the truck's 5V lamp chain — the game's readout.
    colors = (GOLD, MAGENTA, CYAN)
    for i in range(10):
        t = round(3.6 + i * 0.5, 2)
        c = colors[i % 3]
        level = min(220, 200 + i * 6)
        steps.append(_step(t, level, *c))
        steps.append(_step(round(t + 0.25, 2), 90, *c))

    # Mirror-ball pop and a gold hit
    steps.append(_step(8.55, 80, *CYAN))
    steps.append(_step(8.6, 255, 255, 255, 255, 170))
    steps.append(_step(8.72, 140, *CYAN))
    steps.append(_step(9.0, 255, *GOLD))
    steps.append(_step(9.15, 120, *GOLD))

    # Last lonely wink, out
    steps.append(_step(10.0, 60, *INDIGO))
    steps.append(_step(10.8, 85, *INDIGO))
    steps.append(_step(11.4, 40, *INDIGO))
    steps.append(_step(12.0, 0, 0, 0, 0))

    effect = {
        "duration": 12.0,
        "description": "No Friends Monday: lonely indigo open into a "
                       "survival-disco build with a mirror-ball pop",
        "steps": steps,
    }
    logger.info(f"NoFriendsMonday effect created with {len(steps)} steps over {effect['duration']} seconds")
    return effect
