# Cuddle Cross WATER floor projection — plan (2026-07-24)

The fourth theme for the Cuddle Cross floor projection: **the lava
crossing reskinned as a jungle ford** — stepping stones over running
water. `WaterShow(LavaShow)` in `projection_engine.py` inherits the lava
skeleton verbatim (the numbered chain stones sink underfoot, the spare
rises off to the side, something big swims beneath and breaches — see
`wiring-guides/cuddle-lava-plan.md` for all mechanics, events and
choreography); only the skin changes:

- **Field semantics unchanged** (the field IS the picture): the
  `_WATER_STOPS` palette runs deep channel → ripple foam, so bubbles read
  as ripple bursts and embers as sun sparks. The octave drift is one-way —
  the current.
- **Stones** = wet river rock (`stone_skin_water.npz` generated faces;
  splash froth stands in for melt heat while sinking/rising).
- **The monster is a CROCODILE**: olive scutes, ridge crest, amber eyes,
  waterline sheen on the snout — same swim/breach/sink state machine as
  Kukulkan.
- **Video base**: `base_loop_water_192.npy` / `base_loop_water.mp4`
  (bridge-loop pipeline, `experiments/video-base/README.md`);
  `VIDEO_OWNS = ('stones',)` — the loop bakes boulder understudies the
  current parts around, so the sim paints closed water swirls over vacated
  spots and the croc overlay stays live. Light ramp over the footage =
  near-neutral `_WATER_LIGHT_STOPS` (the full palette would drown the
  video in color).

No new tuning knobs beyond the class-attribute colors and octaves; no new
tests (the lava sections exercise the shared machinery). Sim: Floor button
cycles it like any theme; log lines swap to the water phrasing ("something
big glides beneath the water…", "the CROCODILE breaches!").
