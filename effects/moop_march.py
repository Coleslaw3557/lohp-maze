import logging

logger = logging.getLogger(__name__)

# VMM room lighting, third spec (Tim 2026-08-17 late): NO flashing on entry —
# while the room is occupied its pars run the medium-paced green/blue/red
# gradient (theme_manager ROOM_OCCUPIED_GRADIENTS), each button press flashes
# that button's own identity colour, and the win holds solid green till the
# radar reports empty. (The original 4.5s march-cadence entry choreography
# lived here until this rev — git history has it if the room ever wants an
# entry sting again.)


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
    """Vertical Moop March entry MARKER — no lights (Tim 2026-08-17: no
    flashing on entry). The POST still matters: it fires room_entry telemetry,
    route tracking, and the occupancy lock whose gradient owns the room's look
    while someone is inside. `no_lights` makes effects_manager skip the
    lighting takeover entirely."""
    effect = {
        "duration": 0.0,
        "description": "Vertical Moop March entry marker — no lights; the "
                       "occupied green/blue/red gradient owns the room "
                       "(theme_manager)",
        "steps": [],
        "no_lights": True,
    }
    logger.info("MoopMarch entry marker created (no lights — occupied gradient owns the room)")
    return effect


# The game's victory green (Tim 2026-08-17: win = SOLID green until the room
# empties; button 4's identity colour is the same green). Shared by the
# victory bloom's final frame and the theme_manager win hold (main.py
# registers the hook with these), so the effect->hold handoff is invisible.
# Hue ~126 deg — clear of the no-yellow arc (ends 108 deg) with margin.
MOOP_WIN_RGB = (30, 220, 50)
MOOP_WIN_TOTAL = 200

PRESS_FLASH_DURATION = 0.55
VICTORY_DURATION = 1.1

# Button identity colours (Tim 2026-08-17): each march button flashes ITS
# colour so the group can see which buttons have spoken. (r, g, b, w) — the
# white button drives the pars' W channel too; these flashes are
# palette-exempt (a deliberate identity colour, including the one white the
# no-white sweep would otherwise eat — Tim's call, exemption alongside
# Lightning's).
MOOP_BUTTON_COLORS = {
    "Moop Button 1": ((255, 120, 0), 0, "orange"),
    "Moop Button 2": ((30, 90, 255), 0, "blue"),
    "Moop Button 3": ((255, 255, 255), 200, "white"),
    "Moop Button 4": (MOOP_WIN_RGB, 0, "green"),
}


def create_moop_press_flash_effect(rgb=MOOP_WIN_RGB, w=0, label="green"):
    """One hard whole-room flash in a button's identity colour (the generic
    green build is the fallback for unlabeled presses). An instant
    full-brightness pop held ~0.3s, then a hard dip to black before the
    occupied gradient repaints. No fixture_role: both pars fire.
    palette_exempt: identity colours ship EXACTLY as authored (button 3 is
    white, which every clamp would otherwise rewrite)."""
    steps = [
        _step(0.00, 255, *rgb, w),
        _step(0.30, 255, *rgb, w),
        _step(0.42, 0, 0, 0, 0, 0),
        _step(PRESS_FLASH_DURATION, 0, 0, 0, 0, 0),
    ]
    effect = {
        "duration": PRESS_FLASH_DURATION,
        "description": f"Vertical Moop March press — one hard whole-room "
                       f"{label} flash with a blackout tail",
        "steps": steps,
        "palette_exempt": True,
    }
    logger.info(f"MoopMarch press flash ({label}) created with {len(steps)} "
                f"steps over {PRESS_FLASH_DURATION} seconds")
    return effect


def create_moop_victory_effect():
    """VerticalMoopMarch-RightAnswer — all four march buttons inside the 60s
    round. A short whole-room double-pop that lands ON the solid victory
    green: the effect's last frame equals the theme_manager win hold that the
    main.py hook set at effect start, so when this ends the room simply stays
    solid green until /api/room_vacated releases it."""
    steps = [
        _step(0.00, 255, *MOOP_WIN_RGB, 0),
        _step(0.18, 130, *MOOP_WIN_RGB, 0),
        _step(0.36, 255, *MOOP_WIN_RGB, 0),
        _step(VICTORY_DURATION, MOOP_WIN_TOTAL, *MOOP_WIN_RGB, 0),
    ]
    effect = {
        "duration": VICTORY_DURATION,
        "description": "Vertical Moop March victory — whole-room green "
                       "double-pop landing on the solid win hold (held until "
                       "the room empties)",
        "steps": steps,
    }
    logger.info(f"MoopMarch victory effect created with {len(steps)} steps "
                f"over {VICTORY_DURATION} seconds")
    return effect
