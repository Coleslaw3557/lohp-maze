# PortoRoom sound pack

All deliverables are PCM WAV at 48 kHz and no longer than 15 seconds. The room ambience is playful but restrained: recognizable temple-exploration and playa music with only light environmental accents. There are no spoken words in the ambience.

## Recommended playback layout

- Loop or rotate files from `ambience/` through the room speakers.
- When an occupied-door knock sensor fires, randomly select from `sensor_responses/occupied/`.
- When the correct unoccupied-door sensor fires, select from `sensor_responses/victory/`.
- The physical knock is normally supplied by the player. The knock clips in `clips/` are optional reinforcement or test sounds.
- Add a short sensor cooldown so one knock does not trigger several overlapping responses.

## Source and utility clips

| File | Length | Contents |
|---|---:|---|
| `clips/01_crash_temple_ruins.wav` | 14.80 s | Crash Bandicoot Temple Ruins music excerpt |
| `clips/02_dkc_voices_of_temple.wav` | 14.80 s | Donkey Kong Country “Voices of the Temple” excerpt |
| `clips/03_zelda_lost_woods.wav` | 14.80 s | Ocarina of Time Lost Woods excerpt |
| `clips/04_monolink_mayan_warrior_playa.wav` | 14.80 s | Mellow Monolink/Mayan Warrior playa excerpt |
| `clips/05_playful_ambient_cc0.wav` | 14.80 s | Soft, upbeat melodic ambience, CC0 |
| `clips/06_kalimba_percussion_cc0.wav` | 14.80 s | Filtered kalimba and light percussion groove, CC0 |
| `clips/07_soft_bonfire_cc0.wav` | 14.80 s | Quiet real beach-bonfire texture, CC0 |
| `clips/08_light_knock_cc0.wav` | 2.08 s | Light door knock, CC0 |
| `clips/09_heavy_knock_cc0.wav` | 0.68 s | Three heavy knocks, CC0 |
| `clips/10_frantic_knock_cc0.wav` | 2.00 s | Rapid knock pattern derived from the CC0 heavy knock |
| `clips/11_plastic_door_rattle.wav` | 1.90 s | Fast plastic/mechanical door rattle |
| `clips/12_handle_jiggle.wav` | 1.40 s | Repeated handle/lock movement |
| `clips/13_latch_click.wav` | 0.59 s | Short latch click |
| `clips/14_available_victory_chime_original.wav` | 1.17 s | Original three-note available-door cue |
| `clips/15_mario_64_star_get.wav` | 3.61 s | Super Mario 64 star-get cue |
| `clips/16_sonic_checkpoint.wav` | 0.56 s | Sonic checkpoint cue |
| `clips/17_starfox_cant_let_you_do_that.wav` | 2.66 s | Star Fox 64 denial line |

## Five ambience mixes

| File | Length | Intended use |
|---|---:|---|
| `ambience/16_crash_temple_walk.wav` | 14.80 s | Crash temple music with a very quiet fire layer |
| `ambience/17_dkc_temple_passage.wav` | 14.80 s | Donkey Kong temple music with subtle firelight texture |
| `ambience/18_lost_woods_doorway.wav` | 14.80 s | Lost Woods music with barely audible high kalimba percussion |
| `ambience/19_mellow_playa_firelight.wav` | 14.80 s | Gentler Mayan Warrior/Monolink passage with quiet fire |
| `ambience/20_playful_playa_stroll.wav` | 14.80 s | Soft melodic ambience, light kalimba groove, and faint fire |

## Correct-door victory responses

| File | Length | Response |
|---|---:|---|
| `sensor_responses/victory/01_satisfying_unlatch.wav` | 0.79 s | Clean mechanical unlatch only |
| `sensor_responses/victory/02_tf2_well_done_mate.wav` | 3.00 s | Unlatch → TF2 “Well done, mate!” → success chime |
| `sensor_responses/victory/03_zelda_chime_door_opens.wav` | 3.29 s | Unlatch → door opens → Zelda success cue |
| `sensor_responses/victory/04_mario_64_star_get.wav` | 3.96 s | Unlatch → Super Mario 64 star-get cue |
| `sensor_responses/victory/05_sonic_checkpoint.wav` | 0.91 s | Unlatch → Sonic checkpoint cue |

## Occupied-door / antivictory responses

| File | Length | Response |
|---|---:|---|
| `sensor_responses/occupied/01_hl2_hold_it.wav` | 1.13 s | Lock click → Half-Life 2 “Hold it right there.” |
| `sensor_responses/occupied/02_papers_please_denied.wav` | 3.00 s | Locked handle → Papers, Please stamp → closed-door rattle |
| `sensor_responses/occupied/03_mgs_alert_denied.wav` | 1.95 s | Lock click → Metal Gear Solid alert cue |
| `sensor_responses/occupied/04_portal_nice_job_hero.wav` | 1.93 s | Portal “Nice job breaking it, hero” sampled response |
| `sensor_responses/occupied/05_starfox_cant_let_you_do_that.wav` | 2.96 s | Door rattle → Star Fox “Can't let you do that” line |
| `sensor_responses/occupied/06_tf2_where_learn_to_push.wav` | 2.30 s | Handle jiggle → TF2 pushing insult |
| `sensor_responses/occupied/07_duke_warning_door_rattle.wav` | 3.36 s | Plastic-door rattle with Duke Nukem Pig Cop warning |
| `sensor_responses/occupied/09_no_response_silence.wav` | 1.50 s | Intentional silence for uncertainty |
| `sensor_responses/occupied/10_locked_handle_jiggle.wav` | 1.45 s | Handle jiggle and locked latch, no voice |

All spoken sensor responses are short samples from the listed games; no generated speech remains in PortoRoom. Dialogue and game effects remain the property of their respective rights holders. This pack is prepared for personal-project use; check licensing before redistribution or commercial use.
