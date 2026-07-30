# Bike Lock Room — rapid replacement pack

This version replaces the rejected Skyrim/Tomb Raider trigger direction.

- Sound effects only.
- No dialogue or TTS.
- No television-show audio.
- No simulated Burning Man ambience.
- All files are stereo 48 kHz, 16-bit PCM WAV.
- Every trigger response is 3.45 seconds or shorter.
- Button acknowledgments peak near -0.3 dBFS for immediate feedback.

## Controller logic

The room has four buttons representing four statements. Exactly two statements are true.

1. The entry radar plays one file from `rapid/entry/`. Entry playback must not block button input.
2. Buttons 1–4 immediately play their corresponding `rapid/button_responses/` files.
3. Store the first unique button selection.
4. A repeated button plays `05_duplicate_denied.wav` and does not advance.
5. After the second unique selection, evaluate the unordered pair immediately.
6. A wrong pair starts one `rapid/failure/` file and clears the pair after a 0.20-second debounce.
7. The correct pair starts one `rapid/victory/` file, energizes the physical unlock output, and latches the solved state.
8. Do not wait for the second button sound to finish before starting failure or victory playback.

## Entry sensor

| File | Length | Purpose |
|---|---:|---|
| `rapid/entry/01_quake_door_activates.wav` | 2.20 s | Quake-style door activation followed by a ready cue. |
| `rapid/entry/02_four_inputs_ready.wav` | 2.40 s | Four rapid input sounds indicating that the puzzle is live. |

## Button responses

| Input | File | Length |
|---|---|---:|
| Button 1 | `rapid/button_responses/01_button_1_quake.wav` | 0.60 s |
| Button 2 | `rapid/button_responses/02_button_2_quake.wav` | 0.62 s |
| Button 3 | `rapid/button_responses/03_button_3_quake.wav` | 0.62 s |
| Button 4 | `rapid/button_responses/04_button_4_quake.wav` | 0.62 s |
| Duplicate | `rapid/button_responses/05_duplicate_denied.wav` | 0.61 s |

The four acknowledgments are different Quake item/rune sounds. They identify which physical input registered without revealing correctness.

## Wrong-pair responses

| File | Length | Purpose |
|---|---:|---|
| `rapid/failure/01_goldeneye_alarm.wav` | 1.50 s | Immediate GoldenEye alarm rejection. |
| `rapid/failure/02_goldeneye_mission_fail.wav` | 2.20 s | Short GoldenEye failure sting. |
| `rapid/failure/03_quake_door_reject.wav` | 1.55 s | Quake door closes immediately. |
| `rapid/failure/04_double_denied.wav` | 1.15 s | Two hard denied-input sounds. |
| `rapid/failure/05_lock_and_denied.wav` | 1.45 s | Combination movement ending in a denied cue. |

## Correct-pair / final victory

| File | Length | Purpose |
|---|---:|---|
| `rapid/victory/01_doom_secret_unlock.wav` | 2.45 s | Doom secret-found cue with physical lock release. |
| `rapid/victory/02_diablo_quest_unlock.wav` | 3.25 s | Diablo II quest completion with lock release. |
| `rapid/victory/03_diablo_quest_unlock_alt1.wav` | 3.25 s | Alternate Diablo II completion. |
| `rapid/victory/04_diablo_quest_unlock_alt2.wav` | 3.25 s | Alternate Diablo II completion. |
| `rapid/victory/05_diablo_quest_unlock_alt3.wav` | 3.45 s | Fourth Diablo II completion variant. |

## Review sequences

These files demonstrate the complete sensor timing and are not required by the controller.

| File | Length | Demonstration |
|---|---:|---|
| `rapid/review_sequences/01_doom_success.wav` | 3.90 s | Two button presses and Doom victory. |
| `rapid/review_sequences/02_diablo_success.wav` | 4.70 s | Two button presses and Diablo victory. |
| `rapid/review_sequences/03_diablo_success_alt.wav` | 4.70 s | Alternate Diablo victory. |
| `rapid/review_sequences/04_goldeneye_failure.wav` | 2.90 s | Two button presses and immediate GoldenEye rejection. |
| `rapid/review_sequences/05_quake_failure.wav` | 2.95 s | Two button presses and Quake door rejection. |

## Source clips

The `clips/` directory contains:

- Real combination-lock dialing and release.
- Four isolated Quake item/rune effects.
- Doom secret-found cue.
- Quake door opening and closing.
- GoldenEye alarm and mission-failure stings.
- Four Diablo II quest-completion variants.

All game audio remains the property of its respective rights holders. This pack is prepared for personal-project review; check licensing before redistribution or commercial use.
