import logging

logger = logging.getLogger(__name__)


def _step(t, total, r, g, b):
    return {"time": t, "channels": {
        "total_dimming": total, "r_dimming": r, "g_dimming": g, "b_dimming": b,
        "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}}


def create_backtrack_effect():
    """Reverse-travel warning — the one that plays with the coach's whistle.

    2026-08-17 (Tim, on seeing it in the room): this was the maze's only
    hardware STROBE (total_strobe 180/120 at 0.78 s and 1.18 s) — "strobe like
    and flashes" — and its amber peak was rgb(255,130,0), g/r 0.51, which reads
    YELLOW on a par whatever the sRGB hue maths says. Both are gone: the warning
    now pulses at the maze's own warm standard (EMBER/COPPER, g/r 0.24-0.37) and
    swings brightness instead of firing the fixture's strobe engine. It still
    reads as a warning; it no longer reads as a fault light.
    """
    RED = (255, 20, 0)          # g/r 0.08
    DEEP = (255, 60, 0)         # g/r 0.24 — deepest of the warm band
    EMBER = (255, 95, 10)       # g/r 0.37 — the warm standard, top of the band

    effect = {
        "duration": 2.4,
        "description": "Red/ember warning pulses for reverse maze travel "
                       "(no strobe channel, no amber)",
        "steps": [
            _step(0.0, 255, *RED),
            _step(0.18, 30, *RED),
            _step(0.36, 255, *EMBER),
            _step(0.54, 0, 0, 0, 0),
            _step(0.78, 235, *RED),
            _step(0.98, 40, *RED),
            _step(1.18, 200, *DEEP),
            _step(1.40, 45, *RED),
            _step(1.62, 235, *DEEP),
            _step(1.92, 80, *RED),
            _step(2.4, 0, 0, 0, 0),
        ],
    }
    logger.info(f"Backtrack effect created with {len(effect['steps'])} steps over {effect['duration']} seconds")
    return effect
