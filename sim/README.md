# LoHP Maze Simulator

Full virtual emulation of the maze for development and testing without hardware:
the **real, unmodified server** runs against a virtual DMX universe, a browser-based
3D sim renders the lights and fires the sensors, and (optionally) real ESPHome node
firmware runs natively as the sensor layer.

Everything lives in this folder — **zero changes to production code**. The launcher
injects `virtual_dmx.py` in place of `dmx_interface` (the FTDI driver, the server's
only hardware dependency) and then executes `main.py` verbatim.

## The structure (matches the real build)

The maze is a **two-story, open-faced scaffold structure** on playa (Burning Man):
every room's street face is open, so the whole piece reads like a dollhouse from
the street — `rooms.png` in the repo root is the street **elevation**, not a floor
plan. **Real dimensions**: each room bay is **7 ft wide × 5 ft deep × 6.5 ft tall**
(2.13 × 1.52 × 1.98 m); adjacent rooms **share one scaffold frame**, so bays abut
with no gaps (the sim renders the shared verticals as doubled tubes, like real
couplers). The whole run is 9 bays ≈ 63 ft long, ~13 ft tall.

Ground floor: Entrance, Cop Dodge, Gate, Monkey, Temple, No Friends Monday, Exit.
Upper floor (+6.7 ft): Sparkle Pony, Porto, Cuddle Cross (double-wide), Photo Bomb,
Deep Playa Handshake, Bike Lock. Full-height climb rooms connect the floors:
visitors climb **up in Guy Line Climb** (east end) and **down in Vertical Moop
March** (west end).

Canonical visitor route: Entrance → Cop Dodge → Gate → *up* Guy Line Climb →
Sparkle Pony → Porto → Cuddle Cross → Photo Bomb → Deep Playa Handshake → Bike Lock
→ *down* Vertical Moop March → Monkey → Temple → No Friends Monday → Exit.

**Getting upstairs in first-person**: walk into Guy Line Climb (or Vertical Moop
March) — a "Press E to climb" prompt appears near the ladder; press **E** (no need
to aim at it). Same to come back down. In street/overhead views you can also click
a ladder, or click any upper-floor deck to teleport up.

## Quick start

```bash
sim/run.sh -d        # background; logs to sim/sim.log — or omit -d for foreground
```

| Port | What |
|---|---|
| **5001** | 3D sim UI (this folder) — open in any browser on the LAN |
| 5000 | real server REST API + stock control panel (unchanged) |
| 8765 | real server unit-audio WebSocket (unchanged) |

Stop with `sim/stop.sh`. First run creates `sim/.venv` automatically.

**Views** (M cycles): **Street** (default — the whole facade at once, drag to pan,
wheel to dolly, the way the piece reads on playa) · **First-person** (WASD + mouse-
look, E to use buttons/pads/ladders, walk through red doorway beams to trip sensors)
· **Overhead plan** (Ground/Upper/Both floor filter, click floor to teleport).

## Editing workflow — what's real vs. sim-only

We iterate here, then the same files drive physical equipment. Everything the sim
shows comes from **production configs and code**, with one sim-only exception:

| You want to change | Edit | Real or sim-only? |
|---|---|---|
| Effect timing/colors per room | `../effects/*.py` (+ register in `../effects_manager.py`) | **REAL** — this is the production effect engine |
| Ambient themes | `../theme_manager.py` | **REAL** |
| Which sound an effect plays, volumes | `../audio_config.json` | **REAL** |
| Sound/music files | `../audio_files/`, `../music/` | **REAL** |
| Which effect a sensor/room triggers | `../client/config-unit-*.json` (today's Pis) and `esphome/rooms/*.yaml` (ESP32 nodes) | **REAL** — sim reads the unit configs live |
| Fixtures: rooms, models, DMX addresses | `../light_config.json` | **REAL** |
| Buttons (what the 4 arcade buttons do) | `../client/config-unit-a.json` | **REAL** |
| 3D geometry: room bays, floor levels, beam/button/pad positions, route, spawn, playa environment | `maze_layout.json` (+ `web/app.js` for looks) | **sim-only** (visualization) |

Restart needed after editing Python (`sim/stop.sh && sim/run.sh -d`); JSON config
changes only need a browser refresh (`/sim/config` re-reads them per request).
So: design an effect in the sim → it's already production code → deploy to the
physical server → identical behavior on real fixtures (once addressing is fixed,
below).

## Rooms without designed lighting/audio yet (checked 2026-07-16)

Every room has fixtures patched and a trigger wired, but four rooms still fire the
generic **Lightning** placeholder because no bespoke effect exists: **Temple Room,
Monkey Room, Vertical Moop March, Exit** (matches the old aspirational names
MoopMarch/MonkeyBusiness/TempleAmbience that were never written). Marked ⚠ in the
sim's trigger list. Other design gaps found:

- **Bespoke effects that exist but nothing triggers**: GateGreeters, GuyLineClimb
  (the Guy Line sensor fires ImageEnhancement instead — intentional?), PortoHit,
  PhotoBomb-BG, DeepPlaya-BG, LightningStorm.
- **Effects with no audio mapped**: GuyLineClimb, PortoHit, PhotoBomb-BG.
- The two U'King fixtures ignore all effects/themes (channel-name mismatch:
  `master_dimmer`/`red`/… vs `total_dimming`/`r_dimming`/…).

## ⚠ The sim exposes a real hardware bug (left unfixed on purpose)

`light_config.json` daisy-chains DMX addresses by each fixture's true channel count
(the U'King at 89 is 6-channel, so the next par starts at 95), but the server code
assumes uniform 8-channel slots (`(start-1)//8` in theme/effect application). Every
fixture from address 95 onward is therefore misaligned — those rooms render
dark/garbled in the sim, which is exactly what physical fixtures would do:

```
Photo Bomb U'King  @89  slot 11 writes ch  89–96 | reads  89–94  OK (collides with ↓)
Deep Playa         @95  slot 11 writes ch  89–96 | reads  95–102 MISALIGNED
No Friends Monday @103  slot 12 writes ch  97–104| reads 103–110 MISALIGNED
Temple            @111  slot 13 writes 105–112   | reads 111–118 MISALIGNED
Monkey            @119  slot 14 writes 113–120   | reads 119–126 MISALIGNED
Monkey U'King     @127  slot 15 writes 121–128   | reads 127–132 MISALIGNED
Bike Lock         @133  slot 16 writes 129–136   | reads 133–140 MISALIGNED
Moop March        @141  slot 17 writes 137–144   | reads 141–148 MISALIGNED
Moop March        @149  slot 18 writes 145–152   | reads 149–156 MISALIGNED
```

Fix is a decision for hardware day: re-address the physical fixtures to 8-aligned
starts (1,9,…,153 — then just update `light_config.json`), or teach the code real
addressing. Until then the sim shows the truth.

## "Sensors firing at idle?"

They aren't — the server is **shared**. Every connected browser tab, test script
(`tools/`), ESPHome node, and curl fires the same real API, and lights/audio react
everywhere; your tab's event log only records **your own** actions. Verified from
the access log (2026-07-16): every trigger attributes to a real source (your
browser's clicks/walks, the scripted walkthrough, the ESPHome bench node). The
scripted tools announce themselves in this README — run them yourself with the page
open and you'll see the "ghost" activity they produce.

## What is emulated, and how faithfully

| Layer | How | Fidelity |
|---|---|---|
| DMX output | `virtual_dmx.py` replaces the FTDI thread; same 44Hz loop over `DMXStateManager` | Same frames that would hit the wire |
| Fixtures | Each 3D fixture decodes the **raw universe at its configured start address** using the channel map from `light_config.json` | Reproduces addressing bugs |
| Sensors | Beam/button/pad geometry in `maze_layout.json` (floor-aware), actions verbatim from `client/config-unit-*.json`; piezo 3-attempt/25% logic mirrors `trigger_manager.py`; 5s cooldowns | Same HTTP POSTs as the Pis / planned ESP32s |
| Audio | The page connects to `:8765` speaking the unit protocol, claims all 15 rooms, plays served MP3s via Web Audio, spatialized at room+floor positions | Same messages a Pi unit receives |
| ESP32 nodes | Real ESPHome YAML compiled for the `host` platform → native Linux processes that fire real `http_request` POSTs (`esphome/`, verified end-to-end) | Real firmware engine, virtual sensor input |

Extra: set `SIM_ARTNET=<ip>` before launch to also unicast the universe as Art-Net —
point BlenderDMX (or QLC+, Capture, …) at it. Don't run an Art-Net *listener* on
this same machine (UDP 6454 clash).

## Test tools (they light up the maze for everyone connected!)

```bash
sim/.venv/bin/python sim/tools/smoke_test.py     # headless end-to-end: frames, trigger→DMX, theme, audio protocol
sim/.venv/bin/python sim/tools/walkthrough.py    # scripted visitor walks the full two-story route; all triggers must 200
```

Note: the server holds `/api/run_effect` open until the effect finishes (up to ~20s);
test tooling fires triggers concurrently rather than waiting serially.

## Known limits

- No collision — you can walk through walls; floors change only via ladders (E) or
  teleporting. Sensors fire only on their beams (level-aware) and clicks.
- One browser tab should own audio: the server routes each room to the first client
  that claimed it (same rule as the real units).
- `function_selection`/`function_speed` channels aren't visualized; strobe is approximated.
- Headless/software-GL browsers run slowly; use a real GPU browser.
