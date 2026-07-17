import logging

logger = logging.getLogger(__name__)

# Timeline mirrors audio_files/monkey-shrine-complete.mp3 — the Shrine of the
# Silver Monkey assembly cue from Legends of the Hidden Temple (sampled by
# tools/fetch_monkey_sound.sh). Measured onsets: fanfare hit at 0.06s, sustained
# brass to ~1.45s, final head-snap stinger at 1.56s, echo tail to ~2.6s.
FANFARE_HIT = 0.06
STINGER_HIT = 1.56
DURATION = 5.0


def _step(t, total, r, g, b, w):
    return {
        "time": t,
        "channels": {
            "total_dimming": total, "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def create_monkey_business_effect():
    """Silver-monkey-assembled celebration: blackout, gold fanfare flash, brassy
    temple shimmer, a white-gold MEGA flash on the final stinger, then gold and
    emerald twinkles decaying out. Synced to monkey-shrine-complete.mp3."""
    GOLD = (255, 160, 0)
    AMBER = (230, 190, 20)
    EMERALD = (30, 255, 60)

    # Instant blackout for drama, then the fanfare hit in temple gold
    steps = [
        _step(0.0, 0, 0, 0, 0, 0),
        _step(FANFARE_HIT - 0.02, 0, 0, 0, 0, 0),
        _step(FANFARE_HIT, 255, *GOLD, 70),
        _step(0.20, 210, *GOLD, 40),
    ]

    # Brassy shimmer under the sustained fanfare: ~4Hz gold/amber throb
    t = 0.325
    hi = True
    while t < 1.42:
        if hi:
            steps.append(_step(round(t, 3), 225, *GOLD, 30))
        else:
            steps.append(_step(round(t, 3), 150, *AMBER, 0))
        hi = not hi
        t += 0.125

    # Pre-stinger dip, then the MEGA flash on the head-snap
    steps.append(_step(1.50, 110, *GOLD, 10))
    steps.append(_step(STINGER_HIT - 0.02, 110, *GOLD, 10))
    steps.append(_step(STINGER_HIT, 255, 255, 255, 200, 255))
    steps.append(_step(1.75, 255, 255, 220, 120, 200))
    steps.append(_step(2.00, 160, *GOLD, 60))

    # Echo bumps riding the reverb tail
    steps.append(_step(2.10, 195, *GOLD, 40))
    steps.append(_step(2.25, 120, *AMBER, 10))
    steps.append(_step(2.40, 150, *GOLD, 20))
    steps.append(_step(2.60, 90, *AMBER, 0))

    # Gold/emerald twinkles decaying out (jungle temple vibes)
    for t, bright, color in [
        (2.80, 140, GOLD), (3.10, 110, EMERALD), (3.40, 90, GOLD),
        (3.75, 65, EMERALD), (4.10, 45, GOLD), (4.45, 25, EMERALD),
    ]:
        steps.append(_step(t - 0.07, 20, *AMBER, 0))
        steps.append(_step(t, bright, *color, 0))

    steps.append(_step(4.85, 5, 120, 80, 0, 0))
    steps.append(_step(DURATION, 0, 0, 0, 0, 0))

    effect = {
        "duration": DURATION,
        "description": "Monkey puzzle completed — Shrine of the Silver Monkey "
                       "fanfare with synced gold flashes, a mega flash on the "
                       "stinger, and emerald twinkle decay",
        "steps": steps,
    }
    logger.info(f"MonkeyBusiness effect created with {len(steps)} steps over {DURATION} seconds")
    return effect
