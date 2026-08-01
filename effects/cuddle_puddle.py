import logging

logger = logging.getLogger(__name__)

# Cuddle Cross is the projection room: the floor show IS the light. The pars
# must never wash the deck, so everything in here has a hard ceiling —
# total_dimming peaks at PEAK and the white channel stays at 0 throughout.
# The floor show also picks the COLOUR: whichever theme the projector is
# running (projection_engine.THEMES) selects a palette below, so the pars are
# the room's peripheral glow of the same story the deck is telling.
PEAK = 75          # hard cap for any Cuddle effect (see room_experience_audit)
AMBIENT_CAP = 48   # ceiling for the always-on maze-theme wash (theme_manager)

# Per floor theme: (primary, secondary) for the entry swell, plus the colour
# and ceiling the maze theme's ambient wash is squeezed into between effects.
# LAVA is the authored one (2026-07-30, with Tim's Lava sound pool); the other
# four are first-pass colour matches to their floor shows and want a tuning
# pass on the deck.
THEME_PALETTES = {
    'lava':    {'primary': (255, 65, 0),   'secondary': (190, 15, 0),
                'ambient': (255, 55, 0),   'cap': 44},
    'jungle':  {'primary': (45, 200, 70),  'secondary': (150, 175, 35),
                'ambient': (35, 175, 60),  'cap': 42},
    'temple':  {'primary': (255, 150, 40), 'secondary': (205, 95, 20),
                'ambient': (250, 140, 40), 'cap': 42},
    'water':   {'primary': (0, 165, 205),  'secondary': (0, 55, 195),
                'ambient': (0, 140, 190),  'cap': 46},
    'chamber': {'primary': (60, 170, 120), 'secondary': (30, 115, 165),
                'ambient': (50, 150, 120), 'cap': 40},
}
# No floor theme known yet (renderer not up): the pre-2026-07-30 rose/violet.
DEFAULT_PALETTE = {'primary': (255, 40, 90), 'secondary': (150, 40, 255),
                   'ambient': (255, 60, 110), 'cap': AMBIENT_CAP}


def palette_for(theme):
    return THEME_PALETTES.get(theme, DEFAULT_PALETTE)


def _step(t, total, r, g, b, w=0):
    return {
        "time": t,
        "channels": {
            "total_dimming": min(total, PEAK), "r_dimming": r, "g_dimming": g,
            "b_dimming": b, "w_dimming": w,
            "total_strobe": 0, "function_selection": 0, "function_speed": 0,
        },
    }


def _breathing_swell(primary, secondary):
    """The generic welcome swell: slow breathing that reads as a glow at the
    walls and leaves the floor show untouched. Used by every theme that has
    not been given a shape of its own yet."""
    return [
        _step(0.0, 0, *primary),
        _step(1.5, 45, *primary),
        _step(3.0, 60, *primary),
        _step(4.5, 38, *secondary),
        _step(6.0, 70, *secondary),
        _step(7.5, 42, *primary),
        _step(9.0, 75, *primary),
        _step(10.5, 40, *secondary),
        _step(12.0, 65, *secondary),
        _step(13.5, 35, *primary),
        _step(16.0, 0, 0, 0, 0),
    ]


def _lava_swell(primary, secondary):
    """LAVA welcome: the walls catching the light of the molten floor —
    irregular ember flicker over two slow heat swells, never steady, never
    bright. Same 16 s envelope as the generic swell."""
    return [
        _step(0.0, 0, *primary),
        # first heat swell, flickering as it comes up
        _step(1.1, 34, *primary),
        _step(1.7, 52, *primary),
        _step(2.2, 38, *secondary),
        _step(2.9, 61, *primary),
        _step(3.6, 44, *primary),
        _step(4.3, 70, *primary),
        _step(5.0, 47, *secondary),
        # a cooling crust: the dull crimson between swells
        _step(6.0, 28, *secondary),
        _step(6.9, 40, *secondary),
        _step(7.6, 25, *secondary),
        # second swell, the hot one
        _step(8.4, 55, *primary),
        _step(9.1, 75, *primary),
        _step(9.8, 50, *primary),
        _step(10.6, 68, *primary),
        _step(11.4, 42, *secondary),
        # settling back into the crust and out
        _step(12.4, 55, *primary),
        _step(13.3, 32, *secondary),
        _step(14.2, 44, *primary),
        _step(16.0, 0, 0, 0, 0),
    ]


_SWELLS = {'lava': _lava_swell}


def create_cuddle_puddle_effect(theme=None):
    """Projection-safe welcome swell for Cuddle Cross, in the colours of the
    floor theme currently on the deck (None = the renderer has not reported
    one yet, so the original rose/violet)."""
    pal = palette_for(theme)
    shape = _SWELLS.get(theme, _breathing_swell)
    steps = shape(pal['primary'], pal['secondary'])

    effect = {
        "duration": 16.0,
        "description": f"Cuddle Cross welcome ({theme or 'no floor theme'}): "
                       f"low {'ember flicker' if theme in _SWELLS else 'breathing glow'}, "
                       f"no white, capped at {PEAK} so the floor projection owns the room",
        "steps": steps,
    }
    logger.info(f"Cuddle Puddle effect created for floor theme '{theme or 'none'}' "
                f"with {len(steps)} steps over {effect['duration']} seconds")
    return effect


def create_cuddle_lava_hit_effect():
    """LAVA accent: one stone going under, or a bubble bursting. A fast ember
    flare that decays like the heat leaving the wall — 2.6 s, sized to the
    lava1/2/3 accent files."""
    primary = THEME_PALETTES['lava']['primary']
    secondary = THEME_PALETTES['lava']['secondary']
    steps = [
        _step(0.0, 12, *primary),
        _step(0.22, 70, *primary),      # the flare, right on the splash
        _step(0.55, 44, *primary),
        _step(0.95, 58, *primary),      # the lava closing back over it
        _step(1.5, 30, *secondary),
        _step(2.1, 16, *secondary),
        _step(2.6, 0, 0, 0, 0),
    ]
    effect = {
        "duration": 2.6,
        "description": "Cuddle Cross LAVA accent: ember flare for a sinking "
                       "stone or a bursting bubble (capped at 75, no white)",
        "steps": steps,
    }
    logger.info(f"Cuddle lava hit effect created with {len(steps)} steps over {effect['duration']} seconds")
    return effect


def create_cuddle_chamber_trap_effect():
    """CHAMBER accent: a trap door taking someone's step (projection_engine
    trap_open, linger-open and sprint-slam alike). The room light falls away
    with the slab, then the pit's amber glow flares and settles — 3.0 s,
    sized to the merged MGS trap hit (2.7 s)."""
    primary = THEME_PALETTES['chamber']['primary']
    secondary = THEME_PALETTES['chamber']['secondary']
    steps = [
        _step(0.0, 14, *primary),
        _step(0.18, 6, *secondary),      # the slab drops — light falls into the pit
        _step(0.55, 62, 230, 140, 40),   # grind/slam flare, amber pit-glow
        _step(1.1, 48, 230, 140, 40),
        _step(1.7, 34, 200, 110, 30),    # the eyes settling to a glow
        _step(2.4, 18, *primary),
        _step(3.0, 0, 0, 0, 0),
    ]
    effect = {
        "duration": 3.0,
        "description": "Cuddle Cross CHAMBER accent: trap door opening under a "
                       "step — dip, then amber pit flare (capped at 75, no white)",
        "steps": steps,
    }
    logger.info(f"Cuddle chamber trap effect created with {len(steps)} steps over {effect['duration']} seconds")
    return effect


def create_cuddle_lava_breach_effect():
    """LAVA accent: Kukulkan. The approach glow under the crust, the head
    breaking the surface, then the long sink back down — 5.4 s, covering both
    the fast lava4 punch and the slower lava5 swell."""
    primary = THEME_PALETTES['lava']['primary']
    secondary = THEME_PALETTES['lava']['secondary']
    steps = [
        _step(0.0, 10, *secondary),
        _step(0.30, 55, *primary),      # something big is right under there
        _step(0.75, 40, *primary),
        _step(1.30, 62, *primary),
        _step(1.75, 75, *primary),      # breach — the room's own hard ceiling
        _step(2.30, 58, *primary),
        _step(2.90, 72, *primary),
        _step(3.50, 45, *primary),
        _step(4.20, 26, *secondary),
        _step(4.90, 14, *secondary),
        _step(5.40, 0, 0, 0, 0),
    ]
    effect = {
        "duration": 5.4,
        "description": "Cuddle Cross LAVA accent: Kukulkan surfacing — slow "
                       "under-crust glow into a breach flare (capped at 75, no white)",
        "steps": steps,
    }
    logger.info(f"Cuddle lava breach effect created with {len(steps)} steps over {effect['duration']} seconds")
    return effect
