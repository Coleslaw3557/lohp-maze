import logging

logger = logging.getLogger(__name__)

GOLD = (255, 180, 40)
TEAL = (0, 190, 170)
EMBER = (255, 120, 20)


def _step(t, total, r, g, b, w=0):
    return {
        "time": t,
        "channels": {
            "total_dimming": total, "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def create_exit_effect():
    """FINISH arch payoff, the mirror of the Entrance torches across the hex
    divider: a fast achievement-unlocked swell and white-gold pop, then a
    triumphant gold breath with teal Hidden-Temple accents under the voice
    line, and an ember send-off back to the street. Timed against the 7.4 s
    achievements gag — the pop lands on its opening, the breath carries the
    line, and the send-off starts after it ends."""
    steps = [
        _step(0.0, 0, *GOLD),
        # Achievement-unlocked swell into the pop
        _step(0.35, 90, *GOLD),
        _step(0.7, 45, *GOLD),
        _step(1.0, 160, *GOLD),
        _step(1.25, 60, *GOLD),
        _step(1.5, 255, *GOLD, w=110),
        _step(1.9, 190, *GOLD),
        # Teal accents against the gold while the line plays
        _step(2.6, 170, *TEAL),
        _step(3.2, 210, *GOLD),
        _step(3.9, 165, *TEAL),
        _step(4.5, 215, *GOLD),
        # Triumphant breathing through the rest of the line
        _step(5.4, 140, *GOLD),
        _step(6.2, 200, *GOLD),
        _step(7.0, 145, *TEAL),
        _step(7.6, 205, *GOLD),
        # Ember send-off to the street, then out
        _step(8.6, 170, *EMBER),
        _step(9.6, 120, *EMBER),
        _step(10.8, 70, *EMBER),
        _step(12.0, 0, 0, 0, 0),
    ]

    effect = {
        "duration": 12.0,
        "description": "Exit: achievement-unlocked gold pop, triumphant breath "
                       "with teal accents, ember send-off to the street",
        "steps": steps,
    }
    logger.info(f"Exit effect created with {len(steps)} steps over {effect['duration']} seconds")
    return effect
