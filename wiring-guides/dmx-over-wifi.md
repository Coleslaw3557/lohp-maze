# DMX over WiFi — per-room Art-Net into the node boxes (plan of record 2026-07-21)

> Companion docs: `db9-field-wiring.md` (port B carries this), `room-node-audio-plan.md`
> (the pin map this squeezes into), `camp-sign-plan.md` (the sign joins the same
> transport), `../enclosure/README.md` (port B is now a cut, not an etch).
> Status: **software DONE 2026-07-21; CUT OVER 2026-07-22** (Tim's call): every
> room + the sign enabled in `dmx_nodes.json`, `ftdi:false`, USB dongle retired,
> docker USB passthrough removed. Rooms light up as their nodes come online;
> hardware waits on the BOM adds below. Each room YAML carries its flash recipe
> (`# FLASH ADDS`) with the right `dmx_tx_pin`.

## What changed and why

The maze's one wired DMX home-run (Pi → FTDI Open-DMX → 20 fixtures daisy-chained
through every room) is replaced by **Art-Net UDP unicast over the existing camp
WiFi, terminating in each room's ESP32 node**, which converts it back to real
wired DMX512 for that room's 1–2 fixtures through a ~$1 RS-485 transceiver.

The alternative considered (2026-07-21) was a Dfi-style 2.4G wireless DMX
transceiver PCB in every box. Rejected: those modules frequency-hop across the
whole 2.4 GHz band and coexist badly with WiFi — and our WiFi now carries room
audio and sensor traffic, so ~15 of them inside a steel-decked maze would jam
the network we depend on. One radio system, made solid, beats two fighting.
Also: $1 vs $10–20 per room, ESPHome logs vs black-box blink codes, and after
cutover the Pi needs no DMX hardware at all — its DMX output is a UDP socket.

```text
RPi server ── artnet_output_manager.py ── 44Hz ArtDMX unicast, one shared universe
   │                                       (send-on-change + 1s heartbeat/node)
   ├─ ~ WiFi ~ ─ room node ESP32 ── MAX485 (TX-only) ── DB9-B ──► XLR ── room's
   │                └ re-clocks the wire locally at ~43Hz;      1–2 fixtures
   │                  holds the last frame through WiFi blips     └ 120Ω term
   ├─ ~ WiFi ~ ─ (× every room, same universe — fixtures keep their addresses)
   ├─ ~ WiFi ~ ─ sign bridge S3 (ch 161–352 → pixels; Dfi RX = fallback only)
   └─ FTDI USB-DMX ── legacy wired chain — RETIRED 2026-07-22 (ftdi:false; flag
                       + compose devices line resurrect it if ever needed)
```

**Nothing re-addresses.** Every node repeats the *same* universe on its local
wire; fixtures only hear their own start addresses. `light_config.json`, the
effect engine, themes, and the sim are untouched.

## Server side (implemented)

- `artnet.py` — the ArtDMX packet builder, shared by the server output manager
  and `sim/virtual_dmx.py` (one source of truth for the wire format; the sim's
  BlenderDMX mirror and the production packets are byte-identical).
- `artnet_output_manager.py` — a sibling thread to the FTDI `DMXOutputManager`,
  same deadline-paced 44 Hz loop against the same `dmx_state_manager`. Per tick
  it unicasts the frame to every **enabled** node in `dmx_nodes.json` — but only
  when the frame changed, plus a 1 s heartbeat per node so late joiners and a
  dropped final packet converge (bursts at 44 Hz while effects animate, ~1 Hz
  when the maze is static; keeps the AP clear for audio). Hostnames re-resolve
  lazily on failure and every 5 min, so a node that got a new DHCP lease heals.
- `dmx_nodes.json` — the room→node map. **Ships cut over** (2026-07-22): every
  node `"enabled": true`, `"ftdi": false` — the dongle stays unplugged and a
  room's fixtures light the moment its node joins the WiFi (an offline node
  costs one warning log + a silent 10s retry). `"ftdi": true` resurrects the
  legacy wired chain (the code path remains; a fixture is only ever on one
  chain, so running both during any re-transition is safe). With Art-Net nodes
  enabled, an FTDI init failure logs and continues instead of killing the
  server; with no output at all it still exits — a maze with zero DMX outputs
  should crash-loop visibly, not run dark. The sim's virtual sink is exempt
  from the ftdi flag (`VIRTUAL` marker) — it IS the sim's frame feed.
- Sim: `sim/run_server.py` stubs `artnet_output_manager` exactly like it stubs
  `dmx_interface` (`sim/virtual_artnet.py`) — the sim never unicasts to real
  rooms; its BlenderDMX mirror stays opt-in via `SIM_ARTNET`.
- **Docker note:** the production container is on a bridge network — outbound
  UDP is fine but **mDNS `.local` names will not resolve inside it**. On the real
  deployment either give nodes DHCP reservations on the travel router and put
  IPs in `dmx_nodes.json` (recommended — do it at bench-flash time), or switch
  the compose file to `network_mode: host`. `.local` names work when running
  outside docker (bench/dev).

Verify any of it with `tools/artnet_check.py`:

```bash
python3 tools/artnet_check.py --selftest   # offline regression: format+pacing
python3 tools/artnet_check.py --listen     # be a fake node: decode ch 1-16 live
```

## Node side (implemented — `sim/esphome/components/artnet_dmx/`)

An ESPHome external component, ESP-IDF only (the fleet standard). It owns one
hardware UART directly via the IDF driver (no `uart:` block — see allocation
note below): a dedicated FreeRTOS task re-clocks the last received frame out
the wire every ~23 ms — break (176 µs, TXD-invert), MAB, start code, 512 slots.
UDP receive happens in the same task (non-blocking drain), so there are no
cross-thread buffers.

- **WiFi loss = hold, not blackout.** The task keeps repeating the last frame
  forever; a blip mid-scene is a briefly stale look. An all-zero frame is a
  deliberate blackout and holds like anything else. (The sign has its own
  amber-breathe fallback — rooms don't, by design: a frozen room look beats 15
  rooms strobing to black on every AP hiccup.)
- **`signal` binary sensor** (optional, on by default in `dmx_out.yaml`):
  ArtDMX packet seen in the last 5 s — visible from the server laptop next to
  the RSSI sensor, the on-playa first question ("is it WiFi or is it wiring?").
- Sequence numbers are ignored (UDP reorder at 44 Hz is harmless — the next
  frame is 23 ms away); universes must match; short packets update leading
  channels only.

`packages/dmx_out.yaml` is a hardware-flash package like `audio_s3.yaml` — the
host-platform sim rooms never include it, so `validate_all.sh` is unaffected.
Per-room YAML adds:

```yaml
substitutions:
  dmx_tx_pin: "6"        # GPIO number — see the pin table below
packages:
  dmx: !include ../packages/dmx_out.yaml
```

### The pin, per room — D5 standard, two exceptions

The `room-node-audio-plan.md` pin map leaves exactly one clean output pin per
room, and it differs by sensor type. **DMX TX is D5 (GPIO6) everywhere except
the four ToF rooms, which use D7 (GPIO44), and Gate, which uses D0 (GPIO1):**

| Rooms | Sensor pins in use | DMX TX | why |
|---|---|---|---|
| 10 radar rooms (not Gate) | LD2410C on D6/D7 | **D5** (GPIO6) | I2C position unused — no ToF |
| Entrance, Exit, Guy Line, VMM | VL53L1X on D4/D5 (I2C) | **D7** (GPIO44) | radar position unused |
| Cuddle Cross | LD2450 D2/D3 + LD2410C D6/D7 | **D5** (GPIO6) | I2C position unused |
| Gate | LD2410C D6/D7 **+ 6 pads** | **D0** (GPIO1) | see below |

**Gate was pin-full** (6 pads D0–D5 + radar D6/D7 + I2S D8–D10 = 11/11). Its
pads move to an **MCP23017 on I2C D4/D5** — the exact growth path
`db9-field-wiring.md` reserved, arriving one room early. The DB9-A cable and
per-pin map are unchanged; inside the box the 6 signal wires land on MCP GPA0–5
instead of XIAO pads. `packages/game_gate_hw_mcp.yaml` provides the six
binary_sensors under the same ids `game_gate.yaml` expects, so the
bench-verified game logic is untouched — **re-run the gate bench test after
flashing anyway.** This frees D0–D3, and D0 becomes Gate's DMX TX.

UART allocation: the component defaults to **UART2**, which is free fleet-wide
under the S3's USB-JTAG logger — sensor UARTs auto-assign 0/1 (Cuddle uses both;
its DMX stays on 2). If `uart_driver_install` finds the port taken it logs an
error and disables itself rather than fighting; set `uart_num:` explicitly if a
room ever needs it.

## In the box — wiring (no crimping, per the field standard)

New parts per box: one **MAX485 module** (classic 8-pin blue breakout, DE/RE
broken out) VHB'd to the floor near port B, and the **port-B DB9 breakout**
(same female screw-terminal shell as port A).

| MAX485 pin | lands on |
|---|---|
| VCC | 5 V rail (same rail as the PCM5102A VIN) |
| GND | node GND |
| DI | XIAO DMX TX pad (D5 / D7 / D0 per the table — 3.3 V logic into a 5 V-fed MAX485 is in spec, V_IH = 2.0 V) |
| DE + RE | **jumpered together to VCC** — permanently transmitting; deterministic at 250 kbaud where auto-flow modules get marginal (the HiLetgo auto-flow stock stays for the sign's RX fallback, where auto-direction is moot) |
| RO | **leave unconnected** (5 V logic — never wire it to the S3) |
| A | DB9-B pin 3 (Data+) |
| B | DB9-B pin 4 (Data−) |

Power: the always-on driver into a single 120Ω termination adds ~30 mA @5 V —
noise next to the ~200 mA audio budget.

### DB9 port B pinout — every box, the DMX port

| DB9-B pin | Carries |
|---|---|
| 1 | 5 V (universal-pinout convention — unused by the DMX adapter, do wire it) |
| 2 | GND (DMX common / XLR 1) |
| 3 | Data+ (XLR 3) |
| 4 | Data− (XLR 2) |
| 5–9 | reserved (a future MCP23017's extra signals may share the shell) |

### The DB9→XLR adapter (one per room + spares)

Male DB9 screw-terminal breakout + a cheap XLR3 M-F cable with the **female end
cut off**, stripped, landed under the screws — no crimping, matches the system:

```text
DB9-B (box, F shell) ── straight M-F pigtail or direct ── DB9-M breakout
                                                            ├ pin 2 → XLR pin 1 (GND)
                                                            ├ pin 4 → XLR pin 2 (D−)
                                                            └ pin 3 → XLR pin 3 (D+)
XLR-M end → room fixture DMX IN → (second fixture, if any) → 120Ω terminator plug
```

Get the polarity right at the screw terminals once per adapter and label it —
swapped D+/D− is the classic "fixture flickers randomly" field failure. Every
room's chain gets a **120Ω XLR terminator plug** on the last fixture's OUT
(1–2 fixture stubs would usually survive unterminated; $2 says never debug it).
Room-scale runs (a few meters) on DB9-grade wire are fine at 250 kbaud; the
fixture-to-fixture hops use normal DMX/mic cable.

## Rollout — config is already cut over; build in this order

The config side finished 2026-07-22: all 16 targets enabled, `ftdi:false`, USB
passthrough dropped from docker-compose. What remains is hardware, in this
order:

1. **Bench (first S3):** flash `bench-xiao-s3.yaml` (includes `dmx_out`),
   wire the MAX485 + a real par, run `artnet_check.py --selftest` on the dev
   box, and watch the par track the sim UI ("Monkey Room" already points at
   the bench hostname). Scope the break/MAB if anything's off.
2. **Per room on hardware days:** flash the room YAML per its `# FLASH ADDS`
   comment (right `dmx_tx_pin` baked in), give the node a DHCP reservation and
   put the IP into `dmx_nodes.json` (the container can't resolve `.local`),
   build the box with MAX485 + port-B breakout, hang the room's fixtures off
   the node's XLR adapter. The room lights the moment the node joins.
3. **Sign:** per `camp-sign-plan.md` — Art-Net over WiFi is its primary feed
   (same packets, ch 161–352); the Dfi TX/RX pair is fallback, bought/kept
   only if the entrance-tower WiFi fails its on-site test.
4. **Fallback if ever needed:** `"ftdi": true` + the compose `devices:` line
   restore the wired chain; fixtures never re-dial either way.

## Field failure modes

| Symptom | First checks |
|---|---|
| Room lights frozen | node `signal` sensor false? → WiFi (RSSI, AP). true? → effects engine (sim shows same?) |
| Room dark, others fine | MAX485 5 V? DE/RE jumper? D+/D− swapped at an adapter? terminator missing on a long chain? |
| Flicker in one room | polarity, then cable route (not bundled with a PSU lead), then termination |
| All rooms frozen | server thread — `docker logs lohp-server \| grep -i artnet`; heartbeat should tick 1/s/node |
| One node never gets packets | container mDNS (use the IP in `dmx_nodes.json`), DHCP lease changed |

## BOM adds (rolled into shopping-list.xlsx)

| Item | Qty | Note |
|---|---|---|
| MAX485 TTL→RS485 module (DE/RE broken out) | 17 | 15 rooms + 2 spares; DE/RE tied high, TX-only |
| DB9 **female** screw-terminal breakout | +16 | port B in all 15 boxes + spare (port A's 9 already counted) |
| DB9 **male** screw-terminal breakout | +16 | 15 XLR adapters + spare (pod-end 9 already counted) |
| XLR3 M-F cable, 6 ft | 17 | cut the female end off → adapter tail; 2 spares stay whole as fixture hops |
| DMX 120Ω XLR terminator plug | 17 | one per room chain + spares |
| MCP23017 breakout | 2 | Gate now + 1 spare (was "0 now" — the growth path arrived) |

Removed/demoted: per-room Dfi 2.4G modules (never bought — this plan replaces
them); the sign's Dfi kit + HiLetgo RS485 + XLR pigtail rows are **fallback
only** pending the tower WiFi test.
