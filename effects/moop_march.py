import logging

logger = logging.getLogger(__name__)

# Entry sting for the climb-DOWN shaft. Both pars run the same timeline (the
# step engine drives every fixture in a room identically — the true two-zone
# top-to-bottom cascade is the documented future engine capability, same as
# Guy Line Climb). Light-only for now: the Moop March audio pack is still on
# the to-author list (room-experience-audit-2026-07.md); time any future pack
# to this cadence rather than reflowing the lights.
DURATION = 4.5


def _step(t, total, r, g, b, w):
    return {
        "time": t,
        "channels": {
            "total_dimming": total, "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def create_moop_march_effect():
    """Vertical Moop March entry — the moop line falls in: leave-no-trace
    green pop, then a descending march cadence (each stomp a shade dimmer —
    the climb down), one hot amber moop-spotted snatch, and the line marches
    out into the dark. No white (no-white sweep)."""
    LNT_GREEN = (40, 230, 50)
    DUST = (120, 90, 15)
    KHAKI = (150, 110, 20)
    SPOTTED = (255, 90, 0)

    # Fall in! — green pop, dust settles
    steps = [
        _step(0.00, 255, *LNT_GREEN, 0),
        _step(0.18, 70, *DUST, 0),
    ]

    # The march down: stomp/half-step strides at ~133/min, each stride a
    # shade lower down the shaft
    t = 0.45
    for hi, lo in [(235, 110), (205, 95), (175, 80), (145, 65), (120, 55)]:
        steps.append(_step(round(t, 3), hi, *LNT_GREEN, 0))
        steps.append(_step(round(t + 0.22, 3), lo, *KHAKI, 0))
        t += 0.45

    # Moop spotted — hot amber snatch-and-grab double hit
    steps.append(_step(2.92, 250, *SPOTTED, 0))
    steps.append(_step(3.10, 90, 150, 60, 0, 0))
    steps.append(_step(3.24, 230, 255, 120, 0, 0))

    # Bag it, march on — fading strides out into the dark
    steps.append(_step(3.55, 110, *LNT_GREEN, 0))
    steps.append(_step(3.80, 55, *DUST, 0))
    steps.append(_step(4.05, 70, 30, 160, 35, 0))
    steps.append(_step(4.30, 25, 20, 90, 20, 0))
    steps.append(_step(DURATION, 0, 0, 0, 0, 0))

    effect = {
        "duration": DURATION,
        "description": "Vertical Moop March entry — leave-no-trace green "
                       "fall-in pop, descending march cadence, amber "
                       "moop-spotted snatch, march out dark",
        "steps": steps,
    }
    logger.info(f"MoopMarch effect created with {len(steps)} steps over {DURATION} seconds")
    return effect
