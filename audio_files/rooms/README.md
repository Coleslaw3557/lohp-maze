# Per-room audio packs

Themed replacement audio for the maze rooms, replacing the flat test MP3s in
`audio_files/` root. One directory per room, named **exactly** after the
canonical room key used in `light_config.json` / `triggers.json`, so
room → folder joins are mechanical.

Packs are authored in Tim's Codex workspace and delivered as zips into
`../codex-prepped/`. This tree is the extracted, installation-facing copy.

## Status (2026-07-29)

| Room key | Pack zip | Status | Wired into (audio_config.json) |
|---|---|---|---|
| `Cop Dodge` | Cop_Dodge_pack.zip | **wired 2026-07-29** | `PoliceLights` ← 5 mixes |
| `Gate` | Gate_pack.zip | **wired 2026-07-29** | `GateInspection` ← 2 legacy tickets-please + 5 mixes |
| `Guy Line Climb` | GuyLineClimb_pack.zip | **wired 2026-07-29** | `ImageEnhancement` ← 5 mixes |
| `Sparkle Pony Room` | SparklePony_pack.zip | **wired 2026-07-29** (TTS quarantined) | `SparkPony` ← 3 non-TTS mixes |
| `Porto Room` | PortoRoom_pack.zip | **wired 2026-07-29** | `PortoStandBy` ← 5 ambience; `PortoHit` ← 9 occupied denials (untriggered until the knock game lands; victory = maze-wide `CorrectAnswer`) |
| `Photo Bomb Room` | PhotoBomb_pack.zip | **wired 2026-07-29** | `PhotoBomb-Spot` ← 5 photo_triggers; `PhotoBomb-BG` ← 5 backgrounds (untriggered); `PhotoBomb-Shot` keeps the camera-synced countdown |
| `Bike Lock Room` | Bike_Lock_Room_pack.zip | **wired 2026-07-29** | `BikeLockRoom` ← 5 victory unlocks (the game's chime-then payoff); `BikeLock-Entry` (new effect, entry laser retargeted in triggers.json) ← 2 entry prompts. Per-button acks, duplicate-denied, and wrong-pair failure files are node-firmware phase (controller logic in the pack README); failure stays shared `WrongAnswer` |
| `Deep Playa Handshake` | Deep_Playa_Handshake_pack.zip | **rejected** → `../rejected/` | — |
| `Cuddle Cross` | — | **floor-theme audio, LAVA wired 2026-07-30** | Not a pack and not sensor-fired: the room follows the floor projection (`floor_show_manager.py`). Per theme, a looping `Cuddle-<theme>-Bed` on the ambience channel plus accent pools the projection's own events fire. LAVA is live from Tim's `uploads/Lava/` — `Cuddle-Lava-Bed` ← lava.wav, `Cuddle-Lava-Hit` ← lava1/2/3 (a stone sinking, a bubble bursting), `Cuddle-Lava-Breach` ← lava4/5/2 (Kukulkan). JUNGLE / TEMPLE / WATER / CHAMBER light correctly and stay silent until their sounds land. `CuddlePuddle` stays lights-only on purpose |
| `Entrance`, `No Friends Monday`, `Temple Room`, `Monkey Room`, `Vertical Moop March`, `Exit`, `Camp Sign` | — | no pack yet | old test sounds still active. `Exit` is new 2026-07-30: a one-clip pool (`uploads/Do_you_know_how_many_of_these_achievements.mp3`) behind the new `Exit` effect, not a pack — more send-off lines can just be added to the pool |

Light shows: all seven pack rooms' effects were redesigned 2026-07-29 to match
the pack audio arcs (`effects/*.py`, keyframe style per `photobomb_shot.py` —
the engine linearly interpolates between steps, so pops are tightly bracketed).
`PhotoBomb-Shot` is untouched: its timeline is camera-synced (capture at 4.0 s).
Cuddle Cross is projection-safe and now floor-theme-driven (2026-07-30): the
floor show owns the room, so every effect there caps at total 75 with zero
white (`effects/cuddle_puddle.py` PEAK), and the always-on maze-theme wash is
squeezed under 44–48 and tinted to the running theme
(`theme_manager.ROOM_LIGHT_PROFILES`) instead of washing the deck at up to 255.
Never brighten Cuddle lighting without checking the projection. Still
placeholder-grade, awaiting
their packs: `Entrance`, `DeepPlaya-BG`/`DeepPlaya-Hit`, `NoFriendsMonday`
(bright-white hold), `GateGreeters` (white-heavy, untriggered).

## Pack layout (upstream convention)

- `clips/` — individual ingredients (dialogue, soundscapes, sound effects) for remixing or direct trigger playback.
- `mixes/` — complete sequences that play as one event.
- `ambience/`, `background/` — room beds to loop or rotate.
- `sensor_responses/`, `photo_triggers/`, `entry/`, … — finished files assigned to particular sensors.
- `README.md` — playback concept and per-file description. `SOURCES.md` — source and rights documentation.
- `TRIGGER_MAP.csv` — suggested sensor mapping, selection weight, cooldown (where present).

Deliverables are 16-bit PCM WAV, 48 kHz, mono or stereo, ≤15 s. Node cues are
transcoded to 22.05 kHz mono by `sim/esphome/make_node_audio.py` at build time,
so 48 kHz masters here are fine.

## Local conventions (added here, not part of upstream packs)

- `legacy_tts/` inside a room — files containing generated speech, kept on disk
  but excluded from wiring (no-TTS rule). Currently only `Sparkle Pony Room`:
  clips 13–17 and mixes 19 + 22. **Re-extracting a pack zip restores these into
  `clips/`/`mixes/` — re-apply the quarantine after any re-delivery.**
- `../rejected/` — packs retained on disk but not approved for installation.

## Wiring notes (for room-by-room cutover)

`audio_config.json` maps effect name → paths relative to `audio_files/` —
pack files are referenced as `rooms/<Room>/<subdir>/<file>.wav`. How subpaths
survive the delivery chain (all landed 2026-07-29):

- `remote_host_manager.py` basenames `file_name` before WS/node fan-out (by
  design); the `/api/audio/` route in `main.py` falls back to a unique-basename
  search under `rooms/` so lazy fetchers (sim web client) resolve bare names.
- `client/audio_manager.py` downloads by full path but caches/keys by basename.
- Node cue ids collapse to basename stems on both sides (`node_audio_manager.cue_id`),
  so config paths and fan-out names always agree.

**Basenames must stay unique across all rooms and the flat files** — the
fallback route, the flat client cache, and cue ids all depend on it (verified
2026-07-29). Bare-name compatibility requests resolve to the first matching
file under `audio_files/`.

Selection (`audio_manager.get_random_audio_file`):

- **Anti-repeat**: each effect remembers its last `len//2` picks and excludes
  them from the next draw, so files rotate before repeating (a 2-file effect
  strictly alternates). Added 2026-07-29 after true-random repeats felt broken.
- **Weights**: an effect may carry an optional `audio_weights` array parallel
  to `audio_files` (`PortoHit`, `PhotoBomb-BG`, `PhotoBomb-Spot` carry the pack
  TRIGGER_MAP.csv weights); weights bias the draw among non-recent files.
  Absent → uniform; length mismatch → warning + uniform.
- The approved packs' CSVs have no cooldown column — overlap protection is the
  server's per-room effect locks, not per-file cooldowns.

Shared game-language effects (per wiring-guides/room-games-plan.md): rooms get
their own sounds, victory/fail stay shared — `CorrectAnswer` is the single
ff9 victory chime (MechWarrior Betty lines removed 2026-07-29), `WrongAnswer`
keeps its 6-file fail set.

Cutover checklist per room: edit `audio_config.json` → delete that room's
retired test mp3s from `audio_files/` root → re-run
`sim/esphome/make_node_audio.py` (wipe `cues/` first; it validates every
referenced path) → restart the sim/server → `sim/tools/concurrency_test.py`.
2026-07-29 pass retired 11 test mp3s (police/porto/sparkle/photobomb/
image-enhancement sets); the unused `GuyLineClimb` placeholder effect was
removed (the room's laser fires `ImageEnhancement`).
