# Arcade Button DB9 Prewire Guide

Use this for the DB9 Port A breakout to arcade button pods. DB9 is only a
passive field connector here. Do not feed RS-232 voltage into these pins.

## DB9 Port A Pinout

| DB9 pin | Use |
|---|---|
| 1 | +5V for button LEDs / lamps |
| 2 | GND for LED-, switch COM, sensor common |
| 3 | signal 1 |
| 4 | signal 2 |
| 5 | signal 3 |
| 6 | signal 4 |
| 7 | signal 5 |
| 8 | signal 6 |
| 9 | spare / signal 7 |

Button signals are normally-open closures to GND. Firmware uses pull-ups, so
pressed = signal shorted to DB9 pin 2.

## One Button Connector

Use one 4-pin JST-SM pigtail per arcade button.

| JST pin | Button terminal |
|---|---|
| 1 | LED+ |
| 2 | LED- |
| 3 | switch COM |
| 4 | switch NO |

Use bulk 22 AWG 4-conductor stranded cable between the pod JST and the button
JST. Keep the pinout straight through.

Recommended color map for common RGB cable:

| Cable color | JST pin | Use |
|---|---:|---|
| red | 1 | LED+ / +5V |
| black | 2 | LED- / GND |
| green | 3 | switch COM / GND |
| blue | 4 | switch NO / signal |

## Pod Breakout Wiring

All of this lives in the laser-cut **button pod enclosure**
(`../enclosure/button-pod/`, 2026-08-15): DB9 male breakout in the left
wall's window, the 91 x 30 six-circuit terminal block as the +5V/GND
buses ONLY (left 2 circuits linked = 5V, right 4 = GND; each pigtail's
LED-/COM pair lands under one GND screw), each signal wire straight on
its DB9 pin's own breakout screw — no WAGOs in the standard build — and
one Ø7 front-wall exit hole per JST pigtail (hole n = signal n, hole 1
at the DB9 corner; tape unused holes).

```text
DB9 male breakout in pod

pin 1 +5V ---- +5V bus ---- all JST pin 1 / LED+
pin 2 GND ---- GND bus ---- all JST pin 2 / LED-
                         \-- all JST pin 3 / switch COM

pin 3 signal 1 ---------- JST for button 1 pin 4 / switch NO
pin 4 signal 2 ---------- JST for button 2 pin 4 / switch NO
pin 5 signal 3 ---------- JST for button 3 pin 4 / switch NO
pin 6 signal 4 ---------- JST for button 4 pin 4 / switch NO
pin 7 signal 5 ---------- JST for button 5 pin 4 / switch NO
pin 8 signal 6 ---------- JST for button 6 pin 4 / switch NO
pin 9 spare ------------- leave empty unless the room map uses it
```

Bench labels: label both ends of every JST with room and button number, for
example `GATE-1`, `GATE-2`, `DPH-1`.

## Room Maps

| Room | Buttons / inputs | DB9 signals |
|---|---:|---|
| Gate | 6 buttons | pin 3 pad 1, pin 4 pad 2, pin 5 pad 3, pin 6 pad 4, pin 7 pad 5, pin 8 pad 6 |
| Deep Playa Handshake | 5 buttons | pin 3 btn 1, pin 4 btn 2, pin 5 btn 3, pin 6 btn 4, pin 7 btn 5 |
| Bike Lock Room | 4 buttons | pin 3 Q1 TRUE, pin 4 Q1 FALSE, pin 5 Q2 TRUE, pin 6 Q2 FALSE |
| Vertical Moop March | 4 buttons | pin 3 btn 1, pin 4 btn 2, pin 5 btn 3, pin 6 btn 4 |
| Photo Bomb Room | 1 button | pin 3 shutter |
| Monkey Room | 1 switch | pin 3 pedestal switch |
| Porto Room | 3 piezos | pin 2 piezo common, pin 3 piezo 1+, pin 4 piezo 2+, pin 5 piezo 3+ |
| No Friends Monday | special | pin 1 +5V, pin 2 GND, pin 3 ladder ADC, pin 4 WS2812 data |

No Friends Monday is not wired as five normal always-lit button LEDs. Use the
resistor ladder and 5V addressable lamp chain from `room-games-plan.md`.

## Recommended Exact Listings

- DB9 breakouts: ANMBEST 10PCS DB9 solderless breakout, 5 male + 5 female:
  https://www.amazon.com/ANMBEST-Breakout-Connector-Solderless-Terminal/dp/B09WD2V37T
- DB9 field cable: PNGKNYOCN / YOUCHENG straight-through DB9 male-to-female
  extension cable, 4.5 ft or 8.5 ft options:
  https://www.amazon.com/Straight-Extension-YOUCHENG-Computers-Printers/dp/B08GYFQ4GG
- 4-pin button pigtails: BTF-LIGHTING 10 pairs 4-pin JST-SM pigtails:
  https://www.amazon.com/BTF-LIGHTING-pairs-Female-connectors-WS2801/dp/B01DC0KKJU
- Lever splices for small buses: WAGO 221-415 5-conductor lever nuts, 50 pack:
  https://www.amazon.com/Wago-221-415-LEVER-NUTS-Conductor-Connectors/dp/B01M6Y2UEK
- Screw bus / pod terminal strip: MILAPEAK 6-circuit dual-row terminal strip,
  5 sets, with cover:
  https://www.amazon.com/Terminal-Block-Circuits-Screw-Strip/dp/B07CLY5N9T
- Button lead cable: EvZ 22 AWG 4-pin RGB extension wire, 33 ft / 10 m roll:
  https://www.amazon.com/EvZ-22AWG-Electric-Conductor-Extension/dp/B00DPQMKBS

Use straight-through DB9 extension cables only. Do not use null-modem cables.

## Order Status

Status as of 2026-08-13:

| Item | Status |
|---|---|
| DB9 breakouts | already owned |
| WAGO lever connectors | already owned |
| Straight-through DB9 cables | already owned |
| 4-pin JST-SM pigtail pairs | ordered |
| 22 AWG 4-conductor cable, 33 ft rolls | ordered |
| Screw terminal strip / pod bus blocks | ordered |

## Ordered Quantities

| Item | Minimum | Recommended |
|---|---:|---:|
| 4-pin JST-SM pigtail pairs | 2 packs of 10 pairs | 3 packs of 10 pairs |
| 22 AWG 4-conductor cable, 33 ft rolls | 2 rolls | 3 rolls |
| Screw terminal strip / pod bus blocks | 2 packs of 5 | 2 packs of 5 |

Ordered quantities follow the recommended column. Minimum cable assumes the 17
normal DB9 button leads average about 3 ft each: Gate 6, Deep Playa Handshake
5, Bike Lock 4, Photo Bomb 1, Monkey 1. The third 33 ft roll covers longer
onsite cuts, No Friends Monday bench harness work, and field spares.
