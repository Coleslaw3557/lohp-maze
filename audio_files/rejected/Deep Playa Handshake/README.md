# Deep Playa Handshake sound pack — replacement version

This is a complete rebuild of the rejected first version. It uses clean individual *Resident Evil 4* Merchant files, official BioShock vending-machine masters, real CC0 transaction recordings, and short game-native pickup sounds.

- Music files are 30 seconds, as requested.
- Every dialogue, entry, presence, victory, and failure file remains under 15 seconds.
- All deliverables are stereo 48 kHz, 16-bit PCM WAV.
- No generated voices or TTS are used.
- Music is kept separate from every spoken trigger cue.

## Recommended installation

- Choose or rotate one file from `music/` as the room bed.
- Fire `entry/26_welcome_whatre_ya_buyin.wav` from the entry sensor.
- If the player stalls, choose from `presence_prompts/` with a minimum 10-second cooldown.
- Fire one file from `result_sequences/victory/` after a successful handoff.
- Fire one file from `result_sequences/failure/` after an incorrect or incomplete handoff.
- Duck the music approximately 10 dB whenever a spoken cue plays, then restore it over 0.4–0.6 seconds.
- Do not layer multiple result sequences. Each file is already a complete response.

## Five 30-second music beds

| File | Length | Use |
|---|---:|---|
| `music/01_drugs_from_amsterdam_intro.wav` | 30.00 s | Primary recognizable tech-house section |
| `music/02_drugs_from_amsterdam_afterhours.wav` | 30.00 s | Quieter, darker section of the same track |
| `music/03_born_slippy_opening.wav` | 30.00 s | Restrained Underworld opening |
| `music/04_born_slippy_drive.wav` | 30.00 s | Stronger rave pulse |
| `music/05_re4_serenity.wav` | 30.00 s | Dark game-centered Merchant atmosphere |

These are plain music excerpts with short endpoint fades. There is no added wind, synthetic ambience, or dialogue.

## Clean source clips

| File | Length | Contents |
|---|---:|---|
| `clips/06_re4_merchant_welcome.wav` | 1.53 s | Clean Merchant “Welcome!” file |
| `clips/07_re4_merchant_whatre_ya_buyin.wav` | 1.55 s | Clean Merchant purchase prompt |
| `clips/08_re4_merchant_thank_you.wav` | 2.04 s | Clean Merchant laugh and thanks |
| `clips/09_re4_not_enough_cash.wav` | 2.29 s | Clean Merchant insufficient-cash response |
| `clips/10_re4_high_price.wav` | 4.30 s | Merchant “I’ll buy it at a high price!” |
| `clips/11_re4_something_interesting.wav` | 3.81 s | Merchant shady-sales invitation |
| `clips/12_re4_come_back_anytime.wav` | 1.91 s | Merchant farewell |
| `clips/13_bioshock_circus_of_values.wav` | 7.81 s | Official BioShock vending-machine master |
| `clips/14_bioshock_come_back_with_money.wav` | 8.39 s | Official BioShock insufficient-money response |
| `clips/15_bioshock_no_refunds.wav` | 8.54 s | Official BioShock “No refunds” response |
| `clips/16_real_paper_money_cc0.wav` | 4.20 s | Real paper-money handling, CC0 |
| `clips/17_real_hatch_open_cc0.wav` | 4.75 s | Real metal hatch opening, CC0 |
| `clips/18_real_hatch_close_cc0.wav` | 2.65 s | Real metal hatch closing, CC0 |
| `clips/19_cash_drawer_receipt_cc0.wav` | 2.32 s | Real cash drawer and receipt, CC0 |
| `clips/20_re4_pesetas_pickup.wav` | 1.05 s | Resident Evil 4 pesetas sound |
| `clips/21_re4_inventory_click.wav` | 0.65 s | Resident Evil 4 inventory click |
| `clips/22_re4_key_item_pickup.wav` | 3.10 s | Resident Evil 4 key-item cue |
| `clips/23_zelda_silver_rupee.wav` | 1.25 s | Ocarina of Time silver-rupee sound |
| `clips/24_papers_please_denial_stamp.wav` | 0.81 s | Papers, Please stamp response |
| `clips/25_unlock_clunk.wav` | 0.59 s | Short mechanical unlock |

## Entry and presence

| File | Length | Sequence |
|---|---:|---|
| `entry/26_welcome_whatre_ya_buyin.wav` | 5.30 s | “Welcome!” → clean pause → “What’re ya buyin’?” |
| `entry/27_something_interesting_welcome.wav` | 5.75 s | “Got somethin’ that might interest ya” → “Welcome!” |
| `presence_prompts/28_merchant_waiting.wav` | 2.55 s | Inventory click → “What’re ya buyin’?” |
| `presence_prompts/29_circus_of_values.wav` | 7.81 s | Occasional BioShock vending-machine prompt |

## Five victory sequences

| File | Length | Sequence |
|---|---:|---|
| `result_sequences/victory/30_primary_clean_exchange.wav` | 13.80 s | Real money handling → real hatch → pesetas → Merchant thanks → RE4 key-item cue → unlock |
| `result_sequences/victory/31_high_price_rupee.wav` | 9.55 s | Cash drawer → Merchant high-price line → Zelda rupee → unlock |
| `result_sequences/victory/32_circus_vendor_exchange.wav` | 14.65 s | Cash drawer → BioShock vendor → RE4 key-item cue → unlock |
| `result_sequences/victory/33_thank_you_come_back.wav` | 9.65 s | Paper money → Merchant thanks → “Come back anytime” → unlock |
| `result_sequences/victory/34_fast_game_pickup.wav` | 7.75 s | RE4 inventory → pesetas → key item → Zelda rupee → unlock; no dialogue |

## Four failure sequences

| File | Length | Sequence |
|---|---:|---|
| `result_sequences/failure/35_not_enough_cash.wav` | 5.45 s | Real hatch closes → Merchant “Not enough cash” |
| `result_sequences/failure/36_come_back_with_money.wav` | 11.65 s | Real hatch closes → BioShock money response |
| `result_sequences/failure/37_no_refunds.wav` | 11.15 s | Cash drawer → BioShock “No refunds” |
| `result_sequences/failure/38_papers_please_denied.wav` | 5.20 s | Real hatch closes → Papers, Please denial stamp |

The music, dialogue, and game effects remain the property of their respective rights holders. The CC0 recordings are identified in `SOURCES.md`. This pack is prepared for the requested personal-project use; check licensing before redistribution, public release, or commercial use.
