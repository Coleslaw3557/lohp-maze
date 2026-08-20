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

1. **Join**: Pi `iw dev wlan0 station dump` shows the MAC; ping the
   reserved IP. REflash of a known box + endless `Auth Expired` = the
   stale-hostapd-STA gotcha (`maze-network.md`) — restart hostapd on the
   Pi. Fresh MACs join clean.
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
   `press_moop n=1..4`, `press_pad pad=`, `press_bike n=`,
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
If it doesn't rejoin: stale hostapd association — `systemctl restart
hostapd` on the Pi (maze-network.md reflash gotcha).

## If triggers/audio go randomly flaky

30-second network check BEFORE debugging firmware (cost VMM an evening,
2026-08-17): `iwinfo` on the RUT — if a second `LOHP-ESP` AP is
broadcasting, nodes roam Pi↔RUT and every roam is a ~seconds TCP
blackout (POSTs vanish without telemetry rows, ambience streams die
mid-flow and only recover on the next cue, Art-Net UDP keeps flowing so
lights look fine). Fix: `uci set wireless.default_radio0.disabled=1;
uci commit wireless; wifi` on the RUT. The as-built design is ONE AP —
the Pi.

## Done so far

| Room | Date | Notes |
|---|---|---|
| Cop Dodge | 2026-07-25 | first real box; pre-cutover — needs reflash (stale WiFi + bssid pin) |
| Monkey Room | 2026-08-16 | button + radar + ShrineGuard; first post-cutover |
| Vertical Moop March | 2026-08-17 | 4-button game + radar + MoopMarch; pod pending cut |
| Porto Room | 2026-08-20 | radar + 3-piezo knock game + audio; API-validated end-to-end; physical knock test pending (piezo pod not plugged in), logger still DEBUG |
