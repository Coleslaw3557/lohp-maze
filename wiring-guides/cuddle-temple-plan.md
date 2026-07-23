# Cuddle Cross TEMPLE floor projection — plan (2026-07-23)

The third theme for the Cuddle Cross floor projection (`TempleShow` in
`projection_engine.py`, registry key `temple`). Born from the jungle
background comparison: Tim picked leaf litter for the jungle floor and
promoted the flagstone candidate to its own show. Same rig, same `FloorShow`
skeleton as lava/jungle (`wiring-guides/cuddle-lava-plan.md`,
`wiring-guides/cuddle-jungle-plan.md`); switching works the same everywhere
(sim **Floor** button, `POST http://<pi>:5002/theme/temple`).

## The show — the calm one

The temple floor itself, swept and torch-lit. A static flagstone base
texture (dark weathered flags, brick-offset with wandering joints, moss
veining the gaps and creeping onto the stone, long cracks) is painted once
at init; the drifting light field multiplies over it through a torch-warm
ramp (`_TEMPLE_STOPS`), with a low-amplitude two-sine **torch flicker**
breathing across the whole floor.

- **Carved flags**: `CARVED_FLAGS` (3) flagstones carry glyphs chiseled
  into the base texture (shell-zero + dots-and-bars, `_numeral_carve`).
  Walk near one and the carve **fills with gold** (glint streams per glyph;
  the sim page draws the same gold carve sprite at the streamed alpha).
- **Dust motes**: up to `MOTE_N` (5) slow golden motes drifting through the
  light, blinking on and off gently (streamed under the same `flies` key
  the page already draws).
- **Walker light-pool**: the same warm pool as the jungle's sun-pool —
  torchlight finds you.
- **The altar**: the carved sun-stone around the mast base, warm stone
  colors.
- **SCARABS** (2026-07-23, Tim: "think of the movie The Mummy"): every
  18–45 s (first ~13 s in) a swarm of 24–36 scarabs — tiny dark ovals with
  a split-elytra seam and a bronze-green iridescent sheen, 16 precomputed
  rotations — **pours out of one of six VISIBLE pits** (chipped near-black
  holes with a bright fractured rim, baked into the floor at fixed spots —
  Tim: "static holes they come out of and go into"; a dust puff catches
  the light on eruption), skitters
  across as a loose dash-and-pause mass that **carries its own shadow**
  (the torchlight dims under the swarm), **circles a tracked walker's feet
  for a few seconds** (0.55 m ring — swarm the feet, never touch), then
  funnels into another crack and drains away (formation offsets shrink
  with distance so they spiral in). Events `scarab_erupt` /
  `scarab_drain`; 25 s hard cap on a swarm's life. Knobs: `SCARAB_*`.
- **The fallen torch** (2026-07-23, Tim: "think Indiana Jones… a bone
  wrapped in cloth on fire" — v2 after the wooden handle didn't read on
  dark stone): a pale **femur** — twin condyle knobs at the free end, dome
  highlight down the shaft — with a **mummy-cloth wrap** at the burning
  end (diagonal bandage bands charring toward the fire), a contact shadow
  lifting it off the floor, and a soot **scorch on the stone**, all baked
  into the base texture. Dropped near the deck edge (placement prefers the
  farthest clear spot from center; bone trails toward the rim, flame licks
  toward the interior). The **flame is live** — a sheared three-zone
  teardrop (white-hot core → gold → orange rim) flickering with a two-sine
  + jitter envelope and lateral sway, casting its own **guttering pool** in
  the light field (`TORCH_POOL_R_M` 0.55 m, amount rides the flicker).
  Every 20–50 s it **sputters** — gutters down to a third, flares past
  full, settles (`torch_sputter` event; the sim logs "the fallen torch
  gutters…"). State streams `torch` {x, y, ang, len, sway, glow}; the page
  draws the same three-layer flame. Knobs: `TORCH_*`.
- Presence cue + 60 s timeout, identical to the other themes.

Expansion ideas if it ever wants more: footfall echoes (brief ring where a
walker stops), a processional glyph path that lights in sequence, scattered
offering bowls with ember glow.

## Mechanism notes (shared with jungle since 2026-07-23)

`FloorShow.render()` supports a static `self._base` texture: the palette
becomes a LIGHT ramp, `rgb = base * lut[field] / 255`. The sim page mirrors
it exactly — the base ships in the hello and the palette-mapped field
canvas multiplies over it (`globalCompositeOperation = 'multiply'`). Lava
keeps the field-is-the-picture path untouched (golden-hash guarded).

## Perf

Cheapest of the three: ~1.2 ms/frame dev at 256×192 (scarabs are ~20 tiny sprite pastes);
verified on the Pi via live switch — fb readback warm (R > B), service
holds the locked 20 fps. Base build adds a moment to the renderer's
startup prebuild.

## Test

`sim/tools/lava_test.py` sections 13–14: base built, carved flags placed,
glint rises on approach, motes drift, warm-floor render check, texture
export shapes (glow flags), torch on deck + flame burns hot, perf budget;
scarab lifecycle (erupt → swarm renders mid-flight → drain, all gone
after) + a forced sputter.
