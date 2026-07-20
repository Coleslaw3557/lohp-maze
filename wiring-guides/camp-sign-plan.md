# Camp sign: 24-zone DMX LED sign on the entrance towers

> Companion docs: `../cad-items/camp-sign.svg` (the elevation this implements —
> 28.35 SVG units = 1 ft), `../sim/README.md` (sim now renders the sign live),
> `../light_config.json` (the zone map is production config, not this doc).
> Status: **plan + software DONE, sim-verified 2026-07-19** — server, config and
> sim all drive the 24 zones today; hardware is not bought/cut yet.

## What it is

The 14 ft arched sign spanning the two entrance towers (`camp-sign.svg`):
**"Legends of the ◉ Hidden Playa"** — 23 channel-lit letters plus the round
logo disc between "the" and "Hidden". Per the CAD: towers 3 ft W × 8 ft T on
11 ft centers (8 ft clear walk-through, 3+8+3 = 14 ft overall), band ends flush
with the tower tops, crest +19 in, band 21.6 in tall, big letters ~14 in,
"of the" ~6 in, logo disc **28.8 in Ø in the drawing** (the earlier notes said
24 in — measure the real disc before cutting strip; it's 7.5 vs 6.3 ft of
perimeter).

Every letter and the logo is one individually controllable RGB zone: **24 zones**.

**Letters are halo-lit raised cut-outs** (`letters-raised.jpg`): each letter
is cut separately and stands off the **solid** band on spacers — nothing is
cut out of the backing. The strip serpentines on the letter's **back with the
LEDs facing the band**, clipped down like the reference photo, so the letter
face stays dark wood and the color reads as a glow ring spilling around the
silhouette. Bonus: the strip and solder joints ride protected between letter
and band.

**Logo construction is tiki-style piece-work** (`logo.svg` = 91 wood pieces;
the a–h/1–82 text in the file are assembly labels, not artwork): the pieces
mount over a backlit disc and the design lives in the **gaps between them** —
LED light glows through the gap line-work, the wood blocks. So the logo's
strip is a serpentine/loop field **behind** the disc washing a diffuser, not a
perimeter ring.

## Architecture — one decision that drives everything

The sign is **not** a standalone WLED/Art-Net island. The Pi remains the one
show controller, and the sign is 24 more fixtures on the same DMX universe it
already outputs (FTDI Open-DMX at 44 Hz) — with the final hop to the sign over
a **Dfi 2.4G wireless DMX link** instead of a long cable run:

```text
RPi (server rack, back wall)
  └─ FTDI USB-DMX ── existing maze chain (20 fixtures, ch 1-160) ── 120Ω stays
        │                                                    at the last fixture
        └─ Dfi 2.4G TX (Y-stub at the rack, or hung off the last fixture's OUT)
                    ~ ~ ~ 2.4 GHz, ~40-60 ft hop ~ ~ ~
        Dfi RX (inside the sign) ── short stub ── SIGN ESP32 BRIDGE (ch 161-352)
                                          ├─ data 1: "Legends"
                                          ├─ data 2: "of the" + logo
                                          ├─ data 3: "Hidden"
                                          └─ data 4: "Playa"
```

Consequences, all already in the repo:

- **Zones are ordinary fixtures.** `light_config.json` room **"Camp Sign"**,
  model `Camp Sign Zone - WS2811 via ESP32 DMX bridge`, 24 × 8-ch slots at
  **161–352** (8-aligned so the engine's `(start-1)//8` slotting holds).
  `main.py NUM_FIXTURES = 44` sizes the state, the FTDI frame and the sim
  universe from that one constant. 353 bytes @ 250 kbaud ≈ 15.6 ms — still
  comfortably 44 Hz.
- **Themes/effects need zero new code.** The theme engine already breathes the
  sign with the maze (verified: theme bytes on @161/@257/@345 in the sim), the
  panel's room list grows a "Camp Sign" entry, and any effect —
  Lightning, PoliceLights — runs on the sign like on any room.
- **Brightness is managed centrally** (master-brightness slider scales themes;
  effects are deliberate full-power moments). **No firmware brightness cap** —
  the wiring and fuses below are sized for 100% full-white instead, so software
  is never the overcurrent protection.
- The sim renders the sign from the same configs: per-letter live-DMX glyphs on
  the arch (Sign button; letter swatch strip above the fixture grid).

## DMX zone map (production config — change only via light_config.json)

Reading order, one 8-ch slot each. Byte layout matches the ZQ01424 par, so raw
effect frames land identically: `0=total_dimming 1=R 2=G 3=B 4=W 5=strobe
6-7=unused`.

| Zones | @DMX | Letters |
|---|---|---|
| 0–6 | 161, 169, 177, 185, 193, 201, 209 | L e g e n d s |
| 7–8 | 217, 225 | o f |
| 9–11 | 233, 241, 249 | t h e |
| 12 | 257 | ◉ logo disc |
| 13–18 | 265, 273, 281, 289, 297, 305 | H i d d e n |
| 19–23 | 313, 321, 329, 337, 345 | P l a y a |

Free above the sign: **353–512** (20 more 8-ch slots). First reservation if the
tiki niches in the pillar faces (30×48 in rounded panels in the CAD detail)
ever get backlights: 4 zones @353–384, `NUM_FIXTURES 44→48`.

## The ESP32 bridge

**Board: XIAO ESP32-S3** — fleet standard, already stocked for room audio, and
it has 4 RMT TX channels = exactly the 4 pixel outputs (the C3 only has 2).

**Firmware is net-new** (nothing in `sim/esphome/` does DMX or addressable
LEDs — ESPHome has no DMX input; a custom Arduino/IDF sketch with
[`esp_dmx`](https://github.com/someweisguy/esp_dmx) + FastLED is the right
shape; [`ESP32S3DMX`](https://github.com/TimRosener/ESP32S3DMX) is an
S3-specific RX alternative if esp_dmx fights Arduino Core 3.x on bench day). It is deliberately dumb — all show logic stays on the Pi:

1. Receive the universe on UART1 via a plain RS485→TTL module **fed 3.3V**
   (HiLetgo auto-flow class). The old plan's isolated Waveshare converter was
   dropped 2026-07-19 after reading its listing: its differentiators —
   galvanic power/digital isolation, TVS surge, lightning-proofing, onboard
   120R — all defend a long copper run between separately-powered structures,
   and the radio hop eliminated that run. The RX and the ESP32 share one PSU
   inches apart; plain conversion is the whole remaining job (and RX-only use
   makes auto-direction timing moot at 250 kbaud).
2. For each zone `k` (0–23): slot base = `160 + 8k` (0-indexed). Decode
   **exactly like the sim's `decodeFixture`** so preview == wire:
   `R = min(255, r + 0.92w) × total/255`, same for G, `B = min(255, b + 0.85w)
   × total/255`; `strobe > 5` gates the zone at `1 + (strobe/255)×11` Hz, 50%
   duty.
3. Write each zone's value to its letter's pixel range (table below) on the
   group's output. Bytes 6–7 ignored.
4. **DMX-loss fallback**: no valid frame for 3 s → slow amber breathe (the camp
   sign shouldn't go black because the Pi rebooted); resume on the next frame.
   An all-zero frame is NOT loss — a deliberate blackout stays a blackout.

```text
12V PSU ── buck 12→5V 3A ──► XIAO S3 + 74AHCT125 (+ Dfi RX if its barrel takes 5V)
              └── S3 3V3 pin ──► RS485→TTL module VCC (3.3V feed = 3.3V RO, S3-safe;
                                 a 5V-fed module would put 5V on the S3 UART pin)
Dfi RX XLR out ── female pigtail: pin3 Data+ → A · pin2 Data− → B · pin1 → G
                  120Ω across A-B at the module (the RX stub is its own tiny bus;
                  the wired maze chain keeps its own 120Ω at its last fixture)
S3 D4 (GPIO5)  ◄── RS485→TTL RO
S3 D0..D3 (GPIO1-4) ──► 74AHCT125 ──► 33-100Ω ──► data 1..4 (5V, matches 12V WS2811 logic)
grounds: PSU− = strip− = buck− = S3 GND = RX stub G (single common)
```

The on-hand **TXS0108E modules are not a substitute** for the AHCT here
(considered 2026-07-19): auto-direction translators drive through one-shot
accelerators and hold with weak ~10 k pull-ups — fine between chips on a PCB,
but into wire + a WS2811 input the weak hold and reflection-retriggered
one-shots produce random sparkle that reads as broken firmware. The AHCT is
bought specifically for its strong push-pull line drive. (Keep the TXS stock
for bidirectional short-haul buses like I2C.)

Controller lives behind the removable logo disc; strips run center-out so every
group's pixel 0 is near it ("Legends" runs s→L, reversed in the zone table;
"Hidden"/"Playa" run outward normally; "of the"+logo starts at center).

**Letter→pixel table** (firmware constant, filled in during the build — count
pixels as installed, 1 pixel = one 3-LED WS2811 group ≈ 2 in):

| Output | Zone | Letter | px start | px end |
|---|---|---|---|---|
| 1 | 6→0 | s…L (reversed) | _ | _ |
| 2 | 7–11, 12 | o f t h e, ◉ | _ | _ |
| 3 | 13–18 | H…n | _ | _ |
| 4 | 19–23 | P…a | _ | _ |

## LED strip + per-letter budget

**12V WS2811, 60 LED/m, IP65 silicone-coat, black PCB** — 20 pixels/m,
cuttable every ~2 in — IP65 over IP67 tube on purpose: thinner, clips flat to
the letter backs and takes the serpentine bends, still dust-sealed,
≤14.4 W/m. From the CAD letter sizes:

Per-letter strip = the back-fill serpentine (LEDs toward the band), not an
outline trace:

| Item | Strip | Pixels |
|---|---|---|
| 18 big letters (~14 in) | ~0.7 m each → 12.6 m | ~14 px each |
| 5 small letters (~6 in) | ~0.3 m each → 1.5 m | ~6 px each |
| Logo backlight field (28.8 in Ø disc, serpentine behind the diffuser) | ~2.5–3 m | ~50–60 px |
| **Installed total** | **~17–19 m** | **~340–390 px** |

**Buy four 5 m reels** (20 m): covers the ~17–19 m install + per-letter cut
waste; add a fifth only if you want repair stock. Full-white worst case ≈ 17–19 m × 14.4 W/m = **245–275 W,
20–23 A @ 12V** — the 500 W/42A ABI supply loafs at ~60% (treat it as 400 W
continuous; bring the second ABI as the onsite spare).

## Power distribution (sized for full white, no software cap)

```text
PSU+ ── 35A main fuse ── distribution block (left pillar, with PSU + controller)
          ├─ 10A ── 14AWG ── "Legends" feed + mid-string injection
          ├─ 7.5A ── 14AWG ── "of the" + logo feed
          ├─ 2A ──── 18AWG ── buck/controller
          └─ 20A ── 10AWG trunk across the arch ── right-pillar fuse block
                      ├─ 7.5A ── "Hidden" feed + injection
                      └─ 7.5A ── "Playa" feed
PSU− ── common negative bus (both pillars bridged by the trunk's return)
```

- Fuse math: `strip meters × 1.2 A`, fuse the next size up; **fuses protect the
  wire**, so never fuse above the wire's rating (14 AWG→15 A max, 16→10, 18→7).
- **Inject 12V every ~8 ft** and at the far end of each group — never carry
  power across the whole sign on strip copper. Every injection + is fused at
  its block; all returns to the common bus. One PSU feeds everything, so
  both-ends feeding is fine.
- PSU mounted vertically inside a pillar: baffled vent path, fan clearance,
  rain/dust shielded but **not airtight** (it's fan-cooled), strain relief,
  terminals reachable.
- 120V: inverter-generator feed, **no GFCI in the chain** (floating-neutral
  inverter sets nuisance-trip and protect nothing without an N-G bond) →
  outdoor 3-conductor cord → covered mains terminals, chassis ground bonded to
  the PSU housing, accessible disconnect. ~300 W LED load ≈ 3 A @ 120V.
- AC section physically separated from DMX/data/12V runs.

## Connectors + playa-proofing

- xConnect-style 3-pin waterproof connectors at every group boundary and the
  logo disc (it's removable — controller access); separate 2-pin pigtails for
  injection points.
- Every cut end: sealed, adhesive-lined heat shrink, **neutral-cure** silicone
  only (acidic silicone corrodes the copper), strain relief so solder pads
  never carry cable tension.
- The Dfi RX rides inside the sign (dry, antenna clear of the steel-adjacent
  clutter); its short stub to the RS485 module is terminated at the module.
  Nothing long enters the pillar but the AC cord.

## BOM (new parts only — PSUs owned)

> Live shopping copy with links/quantities/pack math:
> **`../sign-shopping-list.xlsx`** (same format as the node-fleet list).
> This table is the summary.

Electronics to buy — essentials only, listings verified via browser
2026-07-19 (mirrors the xlsx):

| Part | Qty | Price |
|---|---|---|
| BTF WS2811 12V 60/m **IP65** 5 m reels (`dp/B01CNL6LLA`, 4.4★ ×1,685) | 4 | $22.99 ea |
| XIAO ESP32-S3 (pull from fleet order) | 1 | — |
| Donner Dfi 2.4G wireless DMX, 1 TX + 1 RX (`dp/B00URFIZZA`, 4.3★ ×348) | 1 kit | $50.99 |
| HiLetgo TTL↔RS485 5-pack, fed 3.3V (`dp/B082Y19KV9`, 4.4★) | 1 pack | $7.39 |
| SN74AHCT125N 10-pack (`dp/B08R6BCSYC`, 4.7★) | 1 pack | $7.99 |
| DIANN 12V→5V 3A buck (`dp/B0BPRV1K6Q`, 4.5★) | 1 | $5.99 |
| MAYWILLA XLR female pigtail (`dp/B0FFMY896F`) | 1 | $9.99 |
| BTF 3-pin pigtail pairs (`dp/B01LCV8LGA`, 4.6★) | 1 pack | $9.99 |
| BTF 2-pin 18AWG pigtail pairs (`dp/B01LCV97AY`, 4.5★) | 2 packs | $12.99 ea |

New spend ≈ **$197**.

**Shop stock, not bought** (rules still specced above): 120Ω terminator +
33–100Ω data resistors, 35A main fuse/holder + blade fuses + blocks,
10/14/18 AWG wire, crimp terminals, adhesive heat shrink, neutral-cure
silicone, letter standoffs/strip clips, logo diffuser sheet.

## Build + bench sequence

1. Bench the bridge first, indoors, before any strip is cut: S3 + RS485→TTL
   module with the Dfi pair inline (TX on the bench chain behind a par, RX →
   stub) → verify frame reception at @161+ (same bench flow as the C3 node
   bring-up). Bench the same TX placement you'll rig (Y-stub vs chain end).
2. Install tape letter by letter; **count pixels per letter into the firmware
   table as you go**.
3. Wire groups center-out, injection stubs every 8 ft, nothing fused yet.
4. Measure each group's actual meters → final fuse sizes (×1.2 A rule).
5. Flash the zone table; test each output alone, then all four.
6. Full white soak: measure 12V at the farthest pixel of every group; add
   injection anywhere below ~11.5V.
7. Run the sign 8+ hours on the bench PSU before transport.
8. Pack: spare ABI PSU, a spare S3 from the fleet, the extra HiLetgo modules
   (5-pack), a coiled DMX cable (wired fallback), fuses, connectors.

## Open items

- [ ] Logo disc: 24 in (notes) vs **28.8 in (CAD)** — measure before strip buy.
- [ ] Logo diffuser between the strip field and the wood pieces (opal acrylic
      vs sanded poly sheet) — gap lines are ~thin, so evenness matters more
      than output.
- [ ] Dfi 2.4G at playa RF density: pair + channel-select at camp, verify the
      ~50 ft hop is solid with camp WiFi up, and keep a DMX cable coiled as
      the wired fallback (LumenRadio CRMX is the $$$ escalation). TX tap =
      Y-stub at the rack or the last fixture's OUT — either way the wired
      chain keeps its own 120Ω at its far end.
- [ ] Letter standoff depth: the halo needs ~0.75–1.5 in of air behind each
      letter to bloom (reference photo uses ~1 in metal standoffs) — pick one
      spacer length fleet-wide and it doubles as the wiring chase.
- [ ] Tiki niche backlights in the pillar faces (4 × 30×48 in panels): zones
      reserved @353–384, not built.
- [ ] Per-letter chase/marquee effects: the engine currently applies one
      effect uniformly per room — a sign-specific runner that phases an effect
      across zones 0–23 would unlock marquee sweeps (sim previews it the day
      it exists).
- [ ] When no theme runs, the maze resets fixtures to zero → sign goes dark
      (correct for blackouts). If the sign should idle-glow all night, that's
      a Pi-side decision (always-run a theme, or a tiny "sign idle" writer) —
      not firmware.
