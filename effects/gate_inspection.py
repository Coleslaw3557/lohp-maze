import logging

logger = logging.getLogger(__name__)

AMBER = (255, 110, 0)
GREEN = (40, 255, 90)
STAMP = (255, 60, 40)


def _step(t, total, r, g, b, w=0):
    return {
        "time": t,
        "channels": {
            "total_dimming": total, "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def create_gate_inspection_effect():
    """Checkpoint arc for the Gate pack mixes (9.4-14.6s) and the short legacy
    tickets-please jokes: HALT flash -> amber inspection sweeps with document
    pops -> two passport stamps -> gate opens green -> proceed and fade."""
    steps = [
        _step(0.0, 0, 170, 200, 255),
        _step(0.08, 255, 170, 200, 255),   # HALT — cold blue slam, not white (palette rule)
        _step(0.5, 255, 170, 200, 255),
        _step(0.9, 120, *AMBER),
        # Inspection sweeps with two white document-check pops
        _step(1.6, 180, *AMBER),
        _step(2.3, 95, *AMBER),
        _step(3.0, 175, *AMBER),
        _step(3.16, 110, *AMBER),
        _step(3.2, 255, 170, 200, 255),
        _step(3.34, 120, *AMBER),
        _step(3.9, 170, *AMBER),
        _step(4.6, 90, *AMBER),
        _step(5.06, 110, *AMBER),
        _step(5.1, 255, 170, 200, 255),
        _step(5.24, 120, *AMBER),
        _step(5.8, 160, *AMBER),
        _step(6.4, 100, *AMBER),
    ]

    # Two passport stamps
    for t in (7.0, 8.0):
        steps.append(_step(round(t - 0.1, 2), 40, *AMBER))
        steps.append(_step(t, 255, *STAMP, w=0))
        steps.append(_step(round(t + 0.15, 2), 255, *STAMP, w=0))
        steps.append(_step(round(t + 0.35, 2), 90, *AMBER))

    # Gate opens: amber gives way to a green rise, then proceed and fade
    steps.append(_step(8.8, 90, *AMBER))
    steps.append(_step(10.2, 200, *GREEN, w=40))
    steps.append(_step(11.5, 220, *GREEN, w=0))
    steps.append(_step(12.5, 140, *GREEN))
    steps.append(_step(14.0, 0, 0, 0, 0))

    effect = {
        "duration": 14.0,
        "description": "Gate checkpoint: HALT flash, amber inspection, passport "
                       "stamps, green gate-open release",
        "steps": steps,
    }
    logger.info(f"Gate Inspection effect created with {len(steps)} steps over {effect['duration']} seconds")
    return effect
