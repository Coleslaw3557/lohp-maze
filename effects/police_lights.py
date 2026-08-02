import logging

logger = logging.getLogger(__name__)

RED = (255, 20, 10)
BLUE = (30, 40, 255)


def _step(t, total, r, g, b, w=0):
    return {
        "time": t,
        "channels": {
            "total_dimming": total, "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def create_police_lights_effect():
    """Cop Dodge escalation arc, sized to the HL2 pursuit mixes (10.8-14.8s):
    scanner detection -> alarm rotation -> full pursuit with searchlight
    sweeps -> checkpoint strobe climax -> hard stop and red afterglow."""
    steps = [_step(0.0, 0, *BLUE)]

    # Detection: three dim blue scanner sweeps
    for t in (0.6, 1.4, 2.2):
        steps.append(_step(round(t - 0.25, 2), 30, *BLUE))
        steps.append(_step(t, 110, *BLUE))
        steps.append(_step(round(t + 0.25, 2), 30, *BLUE))

    # Alarm: red/blue beacon rotation, half-second crossfades
    t, color = 2.6, RED
    while t < 6.0:
        steps.append(_step(t, 210, *color))
        color = BLUE if color == RED else RED
        t = round(t + 0.5, 2)

    # Pursuit: rotation doubles speed; every 6th swap a white searchlight pass
    swap = 0
    while t < 11.0:
        w = 0  # searchlight pass de-whited (palette rule 2026-08-01)
        steps.append(_step(t, 255, *color, w=w))
        color = BLUE if color == RED else RED
        swap += 1
        t = round(t + 0.25, 2)

    # Checkpoint climax: rapid strobing pops
    for i in range(8):
        tt = round(11.05 + i * 0.22, 2)
        c = RED if i % 2 == 0 else BLUE
        steps.append(_step(round(tt - 0.04, 2), 40, *c))
        steps.append(_step(tt, 255, *c))

    # Hard stop, one red afterglow breath, out
    steps.append(_step(13.0, 0, 0, 0, 0))
    steps.append(_step(13.4, 70, *RED))
    steps.append(_step(15.0, 0, 0, 0, 0))

    effect = {
        "duration": 15.0,
        "description": "Cop Dodge pursuit: scanner sweeps, red/blue rotation "
                       "accelerating into a checkpoint strobe climax",
        "steps": steps,
    }
    logger.info(f"Police Lights effect created with {len(steps)} steps over {effect['duration']} seconds")
    return effect
