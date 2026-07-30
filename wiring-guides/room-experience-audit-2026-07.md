# Room experience audit — walk order to the Deep Playa handoff (2026-07-29)

Deep per-room review of the full chain — sensors → triggers → game logic →
effects → audio → lights — in player walk order (`sim/maze_layout.json`
`route`). Boundary: Deep Playa Handshake. Fixture inventory from
`light_config.json` `room_layout`; audio state from `audio_config.json` +
`audio_files/rooms/README.md`.

Legend: **DONE** = themed audio pack wired + lights redesigned to it.
**PENDING** = placeholder audio and/or future game logic.

---

## The walk, Entrance → Deep Playa Handshake

### 1. Entrance — hex east half, ground. Par @1
- Laser → `Entrance` effect. No game.
- Audio: OLD test set (doom / pornhub / bjbjbj) — **pack pending**.
- Lights: redesigned 07-29 — torches catch, gold temple reveal, teal accents.
- Open: audio pack (retheme lights again with it if its arc differs).

### 2. Cop Dodge — ground. Par @9. FIRST REAL NODE (LD2410 radar, flashed 07-25)
- Radar/laser → `PoliceLights`. No game.
- Audio: **DONE** — 5 HL2 pursuit mixes, anti-repeat.
- Lights: **DONE** — scanner sweeps → beacon rotation → pursuit w/ searchlights → strobe climax.

### 3. Gate — ground. Par @17. Gate game (2 banks × 3 body-press pads, MCP23017)
- Laser → `GateInspection`; game: bank 1 → `CorrectAnswer` chime → bank 2 → `GateInspection`.
- Audio: **DONE** — 2 legacy tickets-please (Tim: keep) + 5 checkpoint mixes.
- Lights: **DONE** — HALT flash → amber inspection → passport stamps → green gate-open.
- `GateGreeters`: manual/panel only, never trigger-wired (verified in git history).
  Rethemed 07-29 (amber waves + prosper shimmer). **Its final step must stay
  bright** — `concurrency_test.py` uses it as the bright-hold-clears case.

### 4. Guy Line Climb — full-height shaft, climb UP. TWO pars (@25 lower, @33 upper)
- Radar at the top of the room pointed straight down → `ImageEnhancement` (name
  is historical; it carries the room). Replaced the ToF-across-the-arch beam
  2026-07-30: it has to catch someone at the bottom whether they walked in or
  climbed down the ropes/scaffolding.
- Audio: **DONE** — 5 climb mixes.
- Lights: **DONE** — rising climb cycles → wind shimmer → helicopter pops → success.
- The unused `GuyLineClimb` placeholder effect was **removed** 07-29.
- Limitation: the step engine drives every fixture in a room identically —
  a true two-zone bottom-to-top climb across the two pars needs per-fixture
  steps (future engine capability; also affects Vertical Moop March).

### 5. Sparkle Pony Room — upper. Par @41
- Laser → `SparkPony`. No game.
- Audio: **DONE** — 3 non-TTS mixes (generated-speech files quarantined in `legacy_tts/`).
- Lights: **DONE** — straining heaves → GLaDOS teal deadpan → sparkle cascade → whinny.

### 6. Porto Room — upper. Par @49. Knock game (3 piezos; 1 random pass per entry)
- Laser → `PortoStandBy`: **DONE** — 5 temple/playa beds; ember+jungle glow ≤90.
- Piezos → node `game_porto.yaml`: doorway entry randomizes one winning pad.
  Attempt 1 always fires `PortoHit`; attempts 2-3 pass only on that pad; attempt
  4 passes regardless. Vacate clears the seed and attempt count so the next
  entry re-rolls.

### 7. Cuddle Cross — hex deck, upper. TWO pars (@57/@65) + FLOOR PROJECTION + Olmec orb
- **The projection is the room's light.** Hard rule (violated until 07-29,
  now enforced + documented): par effects cap at total ~75, zero white.
  `CuddlePuddle` = rose/violet breathing glow. All-rooms `Lightning` storm
  strikes are the intentional bright exception (~3.5 s).
- Audio: dance.mp3 retired 07-29. **Pending**: sounds that follow the five
  floor themes (LAVA/JUNGLE/TEMPLE/WATER/CHAMBER). Needs a small server
  change first — the server relays `/theme/next` to the projection Pi
  without tracking which theme is active, so theme-matched audio has nothing
  to key off yet.
- Orb = the room's control surface (music toggle, storm, floor theme, calm).

### 8. Photo Bomb Room — upper. Par @81 + U'King spot @89 (1 of only 2 spots in the maze)
- Laser → `PhotoBomb-Spot`: **DONE** — 5 paparazzi reaction sequences; magenta
  wash + camera-flash hail (front-loaded for the short clips).
- Shutter button → `PhotoBomb-Shot`: **NEVER RETHEME** — timeline is
  camera-synced (webcam capture at the 4.0 s shutter; regression-tested).
- `PhotoBomb-BG` pre-loaded (5 studio beds + pastel drift lights), untriggered.
  Open: decide what starts the bed (presence loop? photobooth idle?).

### 9. ═══ DEEP PLAYA HANDSHAKE — the handoff. Par @97 ═══
- Boundary of this audit. Current state: laser → `DeepPlaya-Hit` (old test
  sounds, 3 s solid-amber placeholder lights); 5-button game → shared effects;
  `DeepPlaya-BG` still plays `dance-distance-muffled.mp3` — an orphaned gag
  (the Cuddle song it muffles was retired). Merchant/BioShock pack was
  REJECTED (kept in `audio_files/rejected/`). Everything here waits on the
  replacement pack; retheme lights with it.

---

## Past the handoff (state for completeness)

- **Bike Lock Room** (par @137): **DONE** 07-29 — victory unlocks →
  `BikeLockRoom`, entry prompts → new `BikeLock-Entry`; the pack's rapid
  four-button pair game (per-button acks, duplicate-denied, wrong-pair
  failure) is the node-firmware spec; answer key TBD until the sign is made.
- **Vertical Moop March** (shaft down, pars @145/@153): 4 wireless button
  pucks. **Fixed 07-29**: pucks fired shared `WrongAnswer` in `triggers.json`
  while the plan of record and the sim both chime — all four now fire
  `CorrectAnswer`. No room effect yet (future `MoopMarch` + game rule TBD);
  same two-zone engine limitation as Guy Line Climb.
- **Monkey Room** (par @121 + spot @129): button → `MonkeyBusiness` —
  current and correct; its light hits are synced to the sampled fanfare
  (0.06 s / 1.56 s) — keep those onsets in any future retheme. Night-dance
  win condition is a documented TBD (LD2450 jitter candidate).
- **Temple Room** (par @113): no trigger, no effect, no audio — future spec
  only per `room-games-plan.md`; node stays an API bench node.
- **No Friends Monday** (par @105 + the truck's 5V addressable lamp chain):
  laser + lights-out win → `NoFriendsMonday` — rethemed 07-29 (lonely indigo
  → survival disco), disco capped at 220 because the truck lamps are the
  game's readout. **Hardware-day check: verify lamp readability under the
  par wash.**
- **Exit** (par @73): ToF → `Exit` — designed 07-30. Achievement-unlocked
  gold pop, teal-accented triumphant breath, ember send-off to the street;
  deliberately the mirror of `Entrance` across the hex divider. Audio pool
  is Tim's one uploaded achievements gag (7.4 s) — the 12 s lighting is timed
  against it, so re-check the beats if the pool grows clips of other lengths.
  This is also the route terminus, so route tokens now retire at Exit
  instead of at No Friends Monday.

## Cross-cutting findings

1. **Hardware day**: physical fixtures from @95 up still need re-addressing
   to the 8-aligned map (`sim/README.md` "HARDWARE DAY" section).
2. **Engine limitation**: no per-fixture steps within a room — both shaft
   rooms (2 pars each) and both spot rooms get identical channel values per
   fixture. Worth a small engine extension if two-zone designs are wanted.
3. **Selection semantics** (server-wide): anti-repeat excludes each effect's
   last `len//2` picks; optional `audio_weights` arrays bias the remainder.
4. Every effect ends dark except `GateGreeters` (deliberate, test-critical).
5. Audio packs still to author: Entrance, Cuddle (theme-aware), Deep Playa
   replacement, No Friends Monday, Monkey, Temple, Moop March, Exit (Exit now
   has a one-clip pool, not a pack).
6. All of the above is **uncommitted** working-tree state as of 2026-07-29.
