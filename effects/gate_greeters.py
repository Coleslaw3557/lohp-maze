import logging

logger = logging.getLogger(__name__)

AMBER = (255, 170, 60)
TEAL = (0, 200, 150)
GREEN = (60, 255, 120)


def _step(t, total, r, g, b, w=0):
    return {
        "time": t,
        "channels": {
            "total_dimming": total, "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def create_gate_greeters_effect():
    """Greeters outside the gate: two friendly amber waves, a green-teal
    live-long-and-prosper shimmer, warm close. Not wired to a trigger today;
    kept themed for panel/manual use.

    Deliberately ENDS ON A BRIGHT WARM HOLD: sim/tools/concurrency_test.py
    uses this effect to prove completion clears a bright final frame instead
    of latching it. Keep the last step bright."""
    steps = [
        _step(0.0, 0, *AMBER),
        # Two friendly waves
        _step(0.8, 120, *AMBER),
        _step(1.6, 190, *AMBER),
        _step(2.4, 110, *AMBER),
        _step(3.2, 200, *AMBER),
        _step(4.0, 120, *AMBER),
        # Prosper shimmer
        _step(4.8, 150, *TEAL),
        _step(5.6, 190, *GREEN),
        _step(6.4, 150, *TEAL),
        _step(7.2, 185, *GREEN),
        # Warm close on a bright hold (completion clears it — see docstring)
        _step(8.2, 140, *AMBER),
        _step(9.0, 170, *AMBER),
        _step(10.0, 160, *AMBER),
    ]

    effect = {
        "duration": 10.0,
        "description": "Gate greeters: friendly amber waves and a green-teal "
                       "prosper shimmer",
        "steps": steps,
    }
    logger.info(f"Gate Greeters effect created with {len(steps)} steps over {effect['duration']} seconds")
    return effect
