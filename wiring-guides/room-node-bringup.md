# Room node bring-up — program + test each box (2026-08-17)

The one-by-one room build runbook, distilled from the boxes done so far
(Cop Dodge 07-25, Monkey 08-16, Vertical Moop March 08-17). Wiring lives
in `room-node-wiring-guide.md` / `db9-field-wiring.md`; this is the
firmware + network + validation pass once the box is assembled and its
XIAO S3 is on the bench USB.

## Program

1. **Hardware-ize the room yaml** (`sim/esphome/rooms/<room>.yaml` —
   `monkey.yaml` and `vertical-moop-march.yaml` are the live reference
   conversions; each keeps a "to run in the sim again" note):
   - `platform:` → `hardware_s3.yaml` (S3 = fleet standard, PSRAM audio)
   - `server_host: "192.168.252.231"` (the server Pi)
   - packages per room: radar rooms `tripwire.yaml` + `ld2410.yaml`
     (+ `effect:` substitution — the entry effect must exist in
     `effects_manager`); button rooms `button.yaml` +
     `button_gpio_c3.example.yaml` (+ `button_pin: GPIO2` — S3's D1);
     game rooms their `game_*.yaml` + `game_*_hw.yaml`; every room
     `dmx: dmx_out.yaml` + `dmx_tx_pin` + the `external_components`
     block; speaker rooms `audio: audio_s3.yaml`
   - `wifi: ap:` rescue AP `LoHP-<Room>` / `hiddenplaya`. **No
     `fast_connect`, no bssid pin** (single-AP LAN; Cop Dodge's pin is
     the dead pre-cutover AP — drop it at its reflash)
   - `sensor: wifi_signal` RSSI + `logger: level: DEBUG` for bring-up
2. **Grab the board MAC before flashing** — it's in the USB id:
   `ls /dev/serial/by-id/` → `...debug_unit_<MAC>` (S3 WiFi STA MAC =
   that base MAC).
3. **RUT DHCP reservation** — IP = `api_port − 6000` (`.7x`). The RUT is
   reachable only from the maze LAN; hop through the Pi (`sshpass` is
   installed there, creds in `maze-network-credentials.md`):
   ```
   ssh root@192.168.252.231 "sshpass -p '<RUT pw>' ssh root@192.168.252.1 \
     \"uci set dhcp.node_<room>=host; \
       uci set dhcp.node_<room>.mac='<MAC>'; \
       uci set dhcp.node_<room>.ip='192.168.252.<7x>'; \
       uci set dhcp.node_<room>.name='lohp-node-<room>'; \
       uci commit dhcp; /etc/init.d/dnsmasq restart\""
   ```
   **Board swap on an existing room** (RMA, wrong chip, dead board): update
   this reservation's `mac` AND purge the OLD board's line from the RUT's
   `/tmp/dhcp.leases` (stop dnsmasq, `sed -i` the MAC out, start) — dnsmasq
   won't hand the reserved IP to the new MAC while the old lease holds it,
   and the new board silently lands on a pool address (Guy Line 2026-08-20).
4. **`dmx_nodes.json`**: replace the room's `.local` host with the
   reserved IP + `"hardware": true`. NOT optional — the production
   container is bridge-networked and can never resolve mDNS; a `.local`
   entry means the room's fixtures silently get zero Art-Net.
5. **`node_audio_config.json`** (speaker rooms): add
   `"<Room>": {"host": "192.168.252.<7x>", "port": <api_port>}`.
6. New audio files in any pool since the last pass? Rerun
   `sim/esphome/make_node_audio.py` (cue WAVs are volume-baked).
7. **Deploy the server FIRST**: `tools/deploy-rpi.sh 192.168.252.231`
   (rsync + docker rebuild + health). Nodes POST the moment they boot;
   a trip that lands mid-rebuild is silently lost.
8. **Flash over USB**:
   `cd sim/esphome && .venv/bin/esphome compile rooms/<room>.yaml &&
   .venv/bin/esphome upload rooms/<room>.yaml --device /dev/ttyACM0`
   (`secrets.yaml` already carries the post-cutover creds; OTA works for
   later revs — OTA password = the WiFi password).

## Test

Drive everything from the Pi — the RUT blocks upstream→WLAN clients, and
the dev box's vmnet1 blackholes `192.168.252.0/24` (only `.231` has a
host route).

1. **Join**: the RUT lease table shows the MAC on the reserved IP, and the Pi
   can ping it. Example from the Pi:
   `ssh root@192.168.252.1 "cat /tmp/dhcp.leases | grep -i <MAC>"` then
   `ping -c 3 192.168.252.<node>`. If a reflashed node ever loops on
   association, kick that client from the RUT AP (`maze-network.md`), not from
   Pi `hostapd` (disabled in the current build).
2. **Audio attach** (speaker rooms): server log prints
   `Node audio connected: <Room> @ <ip>:<port>`, ambience bed starts on
   the Pebble.
3. **DMX**: serial shows `artnet_dmx: N ArtDMX frames received
   (+~940/min), signal=yes`; the room par plays the attract theme. An
   unmistakable check: POST `run_effect` `Lightning` at the room.
4. **Sensors/game — API first, then physical.** API:
   `ssh root@192.168.252.231 "docker exec lohp-server python \
   sim/esphome/harness.py call <ip>:<api_port> <action> [k=v]"` —
   actions: `trip` / `vacate` (occupancy pair), `press_button`,
   `press_moop n=1..4`, `press_bank bank=` (gate), `press_bike n=`,
   `press_shake n=`, `press_truck n=`. Then the physical version
   (walk-in, real button, piezo knock) while watching both ends.
5. **Watch both ends**:
   - node serial: `timeout 60 .venv/bin/esphome logs rooms/<room>.yaml
     --device /dev/ttyACM0` — when chasing lost POSTs do NOT grep-filter
     away `http`/`Code`/`failed` lines (that mistake cost an hour on
     VMM)
   - server truth = telemetry, not log grep (docker log greps race and
     `tail` truncates against Cuddle floor-show spam):
     ```
     ssh root@192.168.252.231 "docker exec lohp-server python -c \"
     import sqlite3
     db = sqlite3.connect('data/telemetry.sqlite3'); db.row_factory = sqlite3.Row
     for r in db.execute('SELECT ts_utc,event_type,effect_name FROM sensor_events \
       WHERE room=? ORDER BY id DESC LIMIT 15', ('<Room>',)): print(dict(r))\""
     ```
     What the node attempted (serial) minus what arrived (telemetry) =
     lost POSTs.
6. **Radar rooms at the bench**: expect occupancy weirdness — the cone
   sees the whole bench, and a fan/monitor inside gate 3 (~2.25 m) can
   hold a permanent still-lock so leave never fires (documented
   tripwire failure mode). Vacate test that always works: cover the
   radar with metal (pot/foil bowl) ~12 s → vacate; uncover + wave →
   entry effect. Real gate numbers are an on-site pass at the mount.
7. **After validation**: logger DEBUG→INFO via OTA; stamp the room
   yaml header REAL ROOM BOX + date + what was validated.
8. **Print the enclosure card**: `tools/box_labels.py "<Room>" --print` —
   QL-820NWB die-cut card for the enclosure (room/IP/server/Art-Net/
   fixtures/DMX range, read live from the configs) + a DB9-A wiring card
   for rooms with an external button/piezo box (POD_WIRING table in the
   script). One batched job; proof the PNGs before `--print`.
9. **Print the ammo-can parts label**:
   `tools/parts_can_label.py "<Room>" --print` — QL-820NWB 62x100 label for
   the room's parts can. It reads the room footprint and installed parts from
   the sim, draws a top-down map, and only labels parts that actually exist in
   the sim layout. Keep this legible: no footer note, no overlapping text.

## PENDING FLEET OTA — flat mix (2026-08-22)

Tim killed audio ducking — FLAT MIX: beds at `ambience_level`, effects
at `effect_level`, runtime-set from the Pi (`GET/POST /api/audio_levels`
→ `data/audio_levels.json`, deploy-protected; current 0.65 / 0.98; an
`effect_level` change also needs a `make_node_audio.py` rerun — cue
WAVs bake it). `packages/audio_s3.yaml` lost its 12dB duck — every audio box
still running pre-08-22 firmware dims the bed under cues until it gets one OTA.
At each box's next power-up: `esphome run rooms/<room>.yaml --device <ip>` (or
the Pi tunnel below). Done: **photo-bomb .68**, **guy-line-climb .64**,
**sparkle-pony .65**, **cuddle-cross .67**, and
**deep-playa-handshake .70** have been USB-flashed or re-flashed with the
flat-mix build and verified back on `LOHP-ESP`.
Still pending: cop-dodge .62, gate .63, porto .66, monkey .72,
vertical-moop-march .74.

## OTA updates after install (no USB — the field path)

Proven end-to-end on VMM 2026-08-17 (1.03 MB in ~5 s). Nodes are WLAN
clients: unreachable from upstream directly (RUT blocks upstream→WLAN,
and on the bench box VMware's vmnet1 squats 192.168.252.0/24 on top of
that). Two working routes:

- **From the bench box (upstream), tunneled through the Pi** — no need
  to join LOHP-ESP:
  ```
  ssh -f -N -o ExitOnForwardFailure=yes \
      -L 3232:192.168.252.<node>:3232 root@192.168.252.231
  cd sim/esphome && .venv/bin/esphome upload rooms/<room>.yaml --device 127.0.0.1
  pkill -f 'ssh -f -N.*3232'
  ```
  (`esphome run` works the same way when the config changed and needs a
  rebuild first. IP = api_port − 6000.)
- **On-site laptop joined to LOHP-ESP**: plain
  `esphome run rooms/<room>.yaml --device 192.168.252.<node>`.

The node reboots (~15 s: radar/buttons/audio out) and rejoins on its
own. Post-OTA smoke from the Pi:
`docker exec lohp-server python sim/esphome/harness.py call
<node-ip>:<api-port> press_moop n=1` (or `trip`/`press_button` per
room) — then read the POST + effect in `docker logs lohp-server`.
If it doesn't rejoin: check the RUT lease table and kick the stale client on
the RUT AP (maze-network.md). Pi `hostapd` must stay stopped.

## If triggers/audio go randomly flaky

30-second network check BEFORE debugging firmware: `iwinfo` on the RUT and
`systemctl is-active hostapd` on the Pi. The current as-built design is ONE AP:
the RUT broadcasting `LOHP-ESP`; Pi `hostapd` must be `inactive`. If both radios
ever advertise the same SSID, nodes roam and every roam is a seconds-scale TCP
blackout (POSTs vanish without telemetry rows, ambience streams die mid-flow,
Art-Net UDP can still look fine). Fix the extra AP, then retest.

## Done so far

| Room | Date | Notes |
|---|---|---|
| Cop Dodge | 2026-07-25 | first real box; pre-cutover — needs reflash (stale WiFi + bssid pin) |
| Monkey Room | 2026-08-16 | button + radar + ShrineGuard; first post-cutover |
| Vertical Moop March | 2026-08-17 | 4-button game + radar + MoopMarch; pod pending cut |
| Porto Room | 2026-08-20 | radar + 3-piezo knock game + audio; API + physical knocks validated (3 separate pads, ~0.3s knock→sound; hostapd-restart gotcha hit on the reflash); piezo thresholds recalibrate on-site behind the plywood; logger still DEBUG |
| Cuddle Cross | 2026-08-23 | first LD2450 box (sole radar: presence + projection tracks) + DMX + audio; API + PHYSICAL radar entry validated, target_1 x/y streaming, zone/multi-target boot programming; **LD2450 on D2/D3 as built** (D6/D7 dead — guide updated); OTA-tunnel proven. 2026-08-23 final pass: USB flashed latest flat-mix build, rejoined `LOHP-ESP` as `.67`, ping/API smoke good, parts-can label printed |
| Guy Line Climb | 2026-08-23 | radar + DMX + audio on the standard S3 recipe; gates widened for the 3.70 m top-down mount (move 5 / still 6, read back from the module); physical entries + vacate + re-trip in telemetry, ArtDMX signal=yes, node audio attached, Lightning fired, OTA-tunnel proven. 2026-08-23 final pass: USB flashed latest flat-mix build, rejoined `LOHP-ESP` as `.64`, ping/API smoke good, parts-can label printed. The first board was a distributor-substituted ESP32-C6; `hardware_c6.yaml` kept for reference |
| Sparkle Pony Room | 2026-08-23 | standard recipe (LD2410C + DMX + audio, genuine S3). Standard gates 2/3 + the room's prompt-vacate pair (module timeout 1 s / absence 0 s); physical radar entry/vacate/re-trip previously validated, ArtDMX + Lightning, bed + cue serial smoke. 2026-08-23 final pass: USB flashed latest flat-mix build, rejoined `LOHP-ESP` as `.65`, ping/API smoke good, parts-can label printed |
| Photo Bomb Room | 2026-08-23 | booth room on the standard S3 recipe (.68: LD2410C + shutter button on the D1 fleet contract / DB9-A pin 3 + DMX D5 + audio). Warm grabber production design: C930e supervised ffmpeg MJPEG passthrough to tmpfs, capture=file copy, frame ~0.25 s after press, flash 1.0 s, rolling window 5 shots/15 s, on-node snap WAV, server photo-landed cue lights-only. 2026-08-23 final pass: USB flashed latest build, rejoined `LOHP-ESP` as `.68`, ping/API smoke good, enclosure label + parts-can labels printed |
| Deep Playa Handshake | 2026-08-23 | 5-button handshake game on the standard S3 recipe (.70: LD2410C + buttons D0-D4 via `game_dph_hw.yaml`, DB9-A pins 3-7 low-numbered convention + DMX D5 + audio). Game validated via serial + API; physical button closures at the pod = Tim's hands. 2026-08-23 final pass: USB flashed latest flat-mix build, rejoined `LOHP-ESP` as `.70`, ping/API smoke good, parts-can label printed |
| Bike Lock Room | 2026-08-23 | quiz room on the standard S3 recipe (.73: LD2410C + 4 quiz buttons D0–D3 via **DB9-A pins 6–9** + DMX + audio; `game_bike_hw.yaml`). The box's first harness had a 5V short on 2026-08-21; bare-board self-test passed and Tim's rewire fixed it. 2026-08-23 final pass: USB flashed latest flat-mix build to MAC `68:EE:8F:50:B9:AC`, RUT lease/reservation `.73`, ping 3/3, node audio connected, DMX signal true, RSSI -46, API vacate/trip/wrong/correct smokes reached the server (`BikeLock-Entry`, `WrongAnswer`, `BikeLockRoom`), cue audio fetched, parts-can label printed |
