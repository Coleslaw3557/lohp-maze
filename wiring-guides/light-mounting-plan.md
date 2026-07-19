# DMX light → scaffold mounting plan (standardized, cheap)

> Companion docs: `room-node-enclosure-plan.md` (node boxes use the same clamp
> fleet), `../sim/README.md` (structure + "all lights mount on the back
> scaffolding/cross members, tilted down").
> Status: **due-diligence / recommendation** — nothing bought or cut yet.

## What we're mounting (spec-sheet due diligence)

| Fixture | Qty | Weight | Body size | Body | Factory mounting provision |
|---|---|---|---|---|---|
| U'King **ZQ01424** 14×6W RGBW par | 18 | 1.0–1.15 kg | 22 × 9.6 × 20.8 cm | Plastic | **2 stamped-steel U-handles + 2 plastic star knobs** into threaded bosses on the body sides. One handle = hanging yoke, both = A-frame floor stand. Holes in the yoke's base span for a hanging bolt/clamp. |
| U'King **ZQ07010** pinspot (orig. ZQ-B93B), 10W RGBW, the "spots" in Photo Bomb + Monkey | 2 | ~0.45 kg | 16.3 × 14 × 9.1 cm | ABS | **1 small U-bracket + 2 screws** into the cylinder sides; hole/slot in the bracket base. |

Sources: uking-online.com ZQ01424 product page + official manual PDF
(`ZQ01424-14PCS-4-in-1-Par-Light.pdf` — packing list "2 handles, 2 knobs";
weight 1 kg), Amazon/reseller listings for the ZQ07010 pinspot (6.4 × 5.5 ×
3.6 in, ~1 lb, ABS, "1 × Bracket, 2 × Screws").

Two facts that drive everything:

1. **Both fixtures already have a steel yoke with a hole in its base.** The
   standard interface should be *yoke-to-scaffold*, never clamp-the-body —
   the bodies are plastic/ABS and the manual (safety note 9) says to secure
   via the bracket screw holes, on structure good for **≥10× fixture weight**.
2. **They're light.** Worst case 1.15 kg. Almost anything holds them; the real
   enemies are *rotation/sag of aim* under wind + vibration, and playa
   UV/heat/dust killing nylon.

## What we're mounting to

- **Frame tube: 1.6925" OD (43 mm)**, 0.095" wall Q235 — every leg, header,
  arch tube on the ScaffoldExpress S-style frames (PSV-610 fleet).
- **Scissor cross braces (PSV-303): ~1" (25 mm) tube** — the wide flat X's on
  the front/back planes, crossing just above mid-height.
- Keep mounts clear of the brace-stud/toggle-pin zones (8.5" down from frame
  tops) and coupling-pin collars — same rule as the node boxes.

## Options considered (per-fixture cost, 20 fixtures + spares)

| # | Option | Cost/fixture | Verdict |
|---|---|---|---|
| A | **Laser-cut ply "scaffold shoe" + 2 hose clamps** (recommended) | ~$1.50–2 | One standard part for both fixture models and both tube sizes. Indexed aim, best anti-rotation, engraved labels, uses xTool + ply scrap we already have. |
| B | **Hose clamp straight through the yoke base holes** | ~$0.60 | Cheapest possible; fine for the 2 pinspots and as the emergency spare method. Single clamp on a round tube = aim creeps unless rubber-lined and torqued hard. |
| C | 1-1/2" EMT **conduit hanger + carriage bolt** through yoke hole | ~$1.30 | All-metal, zero fab, Home-Depot-shelf. Sized for 1.74" OD so it closes fine on 43 mm. Same single-point rotation weakness as B; doesn't fit the 1" braces. |
| D | **30–50 mm stage C-clamps** (e.g. WorldLite 8-packs, ~$26–35/8) | ~$3.50 (~$75–90 fleet) | The "just buy it" answer: real wing-bolt clamps, M10 bolt into the yoke, quick on/off. Note most cheap DJ clamps are **48–52 mm only — those do NOT grip our 43 mm tube**; must be the 30–50 mm ones. Won't fit the 1" braces. |
| E | Nylon zip ties as the primary attachment | ~$0.20 | **No** as primary: playa UV + 45 °C + wind cycling embrittles nylon in one season. Fine as install aid / third-hand / backup loop (buy UV-black 120 lb). Stainless zip ties (~$0.25) are acceptable structurally but aim still creeps. |

**Recommendation: Option A as the fleet standard**, Option B kept as the
documented fallback (it's what the shoe degrades to if one breaks — same
clamps). If zero fab time is worth ~$70 extra, Option D (30–50 mm C-clamps)
is the legit store-bought alternative.

## The standard part: laser-cut ply scaffold shoe

One shoe design, cut on the xTool from two 6 mm Baltic-birch layers glued
(12 mm stack, same ply fleet as the node boxes):

```
  side view on tube                    face view of shoe
                                     ┌───────────────────┐
   fixture yoke                      │  ◄──  90 mm  ──►  │
      ║                              │   ┌─┐       ┌─┐   │  clamp slots
  ════╩════ M8 carriage bolt +       │   └─┘       └─┘   │  (2×, 20×8 mm)
  ┌───────┐ fender washer + wing nut │       ┌───┐       │
  │ SHOE  │                          │       │▪ ▪│ ◄──── │  square hole =
  ╰──◠────╯ ◄─ 43 mm radius saddle   │       └───┘       │  captive M8
 ────○──────── scaffold tube         │    22 mm-r notch  │  carriage head
   (2 hose clamps through slots)     ╰───◡───────────◡───╯
```

- **Saddle notch:** 21.6 mm radius (43 mm tube) cut into the bottom edge; a
  second, smaller shoe variant (or the shoe flipped to a 13 mm-radius notch on
  its top edge) keys onto the 25 mm cross-brace tube. The notch is what stops
  aim-creep: the shoe can't rock, and two clamps 60+ mm apart can't spin.
- **Captive carriage bolt:** laser-cut square hole holds an M8 × 30 carriage
  bolt head; yoke drops over the bolt, fender washer + M8 wing nut. Loosen
  wing nut = pan; yoke star knobs = tilt; hose clamps = position on tube.
- **Rubber liner:** strip of bike inner tube in the saddle → friction + no
  paint-on-steel rattle.
- **Engrave each shoe** with room name + DMX start address (`Monkey 121`,
  `PhotoBomb spot 89`…) — shoes stay bolted to their fixture's yoke from now
  on; on-playa install is just: hook notch on tube, 2 hose clamps, aim, done.
- Ply + UV: two coats of exterior poly or paint, or cut spares (they cost
  pennies; cut 6 extra).

**Measure before cutting the fleet:** the yoke base-hole diameter and the
side-boss thread on one real ZQ01424 and one pinspot (expected ~9–10 mm hole →
M8 passes; drill to 8.5 mm if not). Cut 2 prototype shoes, clamp on the bench
frame from the C3 bench setup, then batch the rest.

## Hardware BOM (fleet of 20 + spares)

| Item | Size / spec | Qty | ~Cost |
|---|---|---|---|
| Worm-gear hose clamps | **SAE #28** (33–57 mm range: covers bare 43 mm tube AND 43 mm + 12 mm shoe stack) | 50 (2/fixture + spares) | ~$40 |
| Worm-gear hose clamps | **SAE #20** (21–44 mm) for 25 mm cross-brace mounts | 10 | ~$8 |
| M8 × 30 carriage bolts + fender washers + wing nuts | zinc | 25 sets | ~$15 |
| 6 mm Baltic birch | scrap from node-box fleet | ~0.3 m² | ~$0 |
| Bike inner tube (liner strips) | any dead 26"/700c | 1–2 | ~$0 |
| UV-black zip ties (backup loops / cable dressing, NOT primary) | 11", 120 lb | 100 | ~$10 |
| Safety lanyards: 1/16" galv. wire rope + alu ferrules (loop yoke→tube, above a stud/pin collar) | ~30 cm each | 25 m + 50 ferrules | ~$15 |
| **Total** | | | **~$90** |

(Store-bought comparison: 3 × 8-pack 30–50 mm stage C-clamps ≈ $80–100 and
still needs the safety lanyards; no labels, no brace-tube fit.)

## Aiming + install procedure (per fixture)

1. At home: bolt shoe to yoke (wing nut), engrave label, thread 2 hose clamps
   through the slots so they travel with the fixture.
2. On playa: hook shoe saddle onto the planned tube (back header / back leg /
   brace per room), hand-tighten clamps.
3. Pan: rotate whole shoe around tube (or swing yoke on wing nut) → snug
   clamps. Tilt: star knobs. Nut-driver-snug everything (don't crush the ply).
4. Loop the wire-rope safety through the yoke and around the tube **above a
   brace stud or pin collar** so it can't slide down a leg.
5. Sharpie a witness mark tube→shoe so re-rig next year is aim-free.

## Open items

- [ ] Measure yoke hole + boss thread on one par + one pinspot (blocks the SVG).
- [ ] Confirm 12 mm stack clears the yoke's bent ends on the ZQ01424 (else go 9 mm).
- [ ] Cut + bench-test 2 prototype shoes on the XIAO-bench scaffold frame.
- [ ] Generate the parametric SVG cut file (offer: script it so notch radius /
      bolt size are variables — one file cuts both 43 mm and 25 mm variants).
- [ ] Decide per-room mount tube (header vs leg vs brace) off the sim's
      fixture positions and add a column to the room table here.
