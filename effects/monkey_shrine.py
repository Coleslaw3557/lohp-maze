import logging

logger = logging.getLogger(__name__)

# Timeline mirrors audio_files/temple-guard-entry.mp3 — the Legends of the
# Hidden Temple TEMPLE GUARD sting (sampled by tools/fetch_guard_sound.sh).
# Measured envelope: ambush slam at 0.00s, sustained roar to the 2.85s fade,
# hall-echo tail out to ~4.57s.
ROAR_END = 2.85
DURATION = 4.6


def _step(t, total, r, g, b, w):
    return {
        "time": t,
        "channels": {
            "total_dimming": total, "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def create_shrine_guard_effect():
    """Monkey Room entry — a temple guard ambush: hard torch-orange slam the
    instant the radar trips, aggressive torch-flare throb with emerald jungle
    stabs under the sustained roar, then firelight dying down the echo tail.
    Synced to temple-guard-entry.mp3. No white (no-white sweep)."""
    TORCH = (255, 120, 0)
    RUST = (220, 50, 0)
    EMERALD = (30, 255, 60)
    AMBER = (230, 190, 20)

    # Ambush: full slam on the guard's first frame, quick settle into menace
    steps = [
        _step(0.0, 255, *TORCH, 0),
        _step(0.15, 200, *RUST, 0),
    ]

    # Torch-flare throb under the roar: ~3.3Hz torch/rust alternation with an
    # emerald jungle stab every third flare
    t = 0.30
    beat = 0
    while t < ROAR_END - 0.05:
        if beat % 6 == 4:
            steps.append(_step(round(t, 3), 235, *EMERALD, 0))
        elif beat % 2 == 0:
            steps.append(_step(round(t, 3), 245, *TORCH, 0))
        else:
            steps.append(_step(round(t, 3), 150, *RUST, 0))
        beat += 1
        t += 0.15

    # Roar fades — drop to embers, then firelight bumps riding the echo tail
    steps.append(_step(ROAR_END, 140, *AMBER, 0))
    for t, bright, color in [
        (3.00, 170, TORCH), (3.20, 110, AMBER), (3.45, 130, EMERALD),
        (3.75, 85, TORCH), (4.10, 45, RUST),
    ]:
        steps.append(_step(t - 0.06, 60, *RUST, 0))
        steps.append(_step(t, bright, *color, 0))

    steps.append(_step(4.40, 15, 120, 60, 0, 0))
    steps.append(_step(DURATION, 0, 0, 0, 0, 0))

    effect = {
        "duration": DURATION,
        "description": "Monkey Room entry — temple guard ambush: torch slam, "
                       "flare throb with emerald stabs under the roar, "
                       "firelight decay on the echo tail",
        "steps": steps,
    }
    logger.info(f"ShrineGuard effect created with {len(steps)} steps over {DURATION} seconds")
    return effect
