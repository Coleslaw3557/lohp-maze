# Maze network — RUT140 router **and AP** (radio-role swap 2026-08-21; original build 2026-08-10)

One flat LAN, `192.168.252.0/24`, for everything in the maze: the server Pi,
every ESP32 node, the orb, the sign bridge, and any laptop that joins
`LOHP-ESP`. The Teltonika RUT140 owns the network — **the `LOHP-ESP` AP**
(MT7628 radio, rated 50 clients — the Pi's Broadcom AP had a murky ~8–16
station ceiling, no good for the 15-node fleet + printer), DHCP, DNS, NAT.
The Pi is a wired LAN host that runs the server; its own radio is now the
**upstream internet client** (house/camp WiFi) so each radio has one job.

## Topology (since 2026-08-21)

```text
Upstream Wi-Fi (house/camp)
      │  (wlan0 STA, DHCP — internet for the Pi only)
Raspberry Pi  eth0(br0) ── ethernet ── RUT LAN port
                                        │ LAN 192.168.252.1/24
                              RUT140 radio = LOHP-ESP AP, ch 1 (ch 6 until 2026-08-31)
                                        │
                              ESP32 nodes, orb, sign bridge, laptops
```

Nodes and their DHCP reservations were untouched by the swap — same SSID,
same PSK (= the OTA password), same `.252` addresses; zero node reflashes.

## Credentials

All usernames, upstream SSIDs and passwords live in
`maze-network-credentials.md` next to this file — **gitignored, local only**
(this repo is public on GitHub). If that file is missing, re-copy it from the
bench box or the laminated cut sheet.

## Addresses + access

| Device | Address |
|---|---|
| RUT from LAN | `https://192.168.252.1` (from the Pi or any LOHP-ESP client) |
| Pi on the maze LAN (RUT DHCP reservation) | `192.168.252.231` — MAC `b8:27:eb:08:0c:24`, hostname `lohp-server` |
| Pi on the upstream network (its wlan0 client lease) | `192.168.253.187` (upstream DHCP — **may change**; if dead, scan `.253/24` for MAC `b8:27:eb:5d:59:71`) |

Since 2026-08-21 the RUT has **no upstream address** — its WiFi-WAN is
disabled (`wireless.multiap_radio0.disabled=1`); the old
`https://192.168.253.219` path is dead. Reach the RUT from the maze LAN
only, e.g. through the Pi: `ssh root@192.168.252.231` then
`sshpass ssh root@192.168.252.1`.

**Normal ops: join `LOHP-ESP`.** You're then on the flat LAN;
`tools/deploy-rpi.sh`, the sim's RPI dot, and the audio console all work.

**From the upstream network** the jump host is now the **Pi itself** (root
carries the bench box's ed25519 key):

```bash
ssh -J root@192.168.253.187 dietpi@192.168.252.231   # or root@
```

or in `~/.ssh/config` (as installed on the bench box — makes plain
`ssh 192.168.252.231`, rsync, deploy-rpi.sh and the OTA tunnel all work
despite vmnet1 squatting `.252/24` locally):

```
Host 192.168.252.231
    ProxyCommand ssh -o StrictHostKeyChecking=accept-new -W %h:%p root@192.168.253.187
```

Reachability quirk that still holds after the swap:

- ESP nodes are **unreachable from the upstream network** (and from the
  bench box, whose vmnet1 also squats the subnet) — everything node-facing
  goes through the Pi. To drive a node from an upstream bench box:
  `scp sim/esphome/harness.py root@192.168.252.231:/home/dietpi/lohp-server/`
  then `ssh root@192.168.252.231 "docker exec lohp-server python
  /app/harness.py call <node-ip>:<api_port> press_button"` (the container has
  aioesphomeapi; the copy is cleaned by the next deploy's rsync).

**HISTORICAL (Pi-AP era, retired 2026-08-21) — stale hostapd station entry.**
Reflashing a node used to hit `Auth Expired` loops on the Pi's brcmfmac AP;
the fix was `ap_max_inactivity=60` + `hostapd_cli deauthenticate`. hostapd
is now stopped and disabled (config kept at `/etc/hostapd/` for rollback).
On the RUT AP the first post-swap OTA reflash re-associated clean; if a
reflashed node ever loops on auth, kick it on the RUT:
`ubus call hostapd.wlan0-1 del_client '{"addr":"<mac>","deauth":true}'`
(or WebUI → Wireless → clients).

## RUT140 (FW `RUT14X_R_00.07.24.1`)

FW self-updated from 07.20.3 and broke the radio (2026-08-31 incident,
bottom of this doc) — treat any future firmware jump as a config audit.

- LAN `192.168.252.1/24`; internal AP `wireless.default_radio0` **ENABLED
  since 2026-08-21** — SSID `LOHP-ESP`, psk2/CCMP, **channel 1 since
  2026-08-31** (ch 6 carried three camp APs + splatter from networks parked
  on ch 8/9; playa band census + survey math in the incident section),
  network=lan, MT7628 radio (rated 50 clients). This is THE maze AP now.
  - ⚠ The 2026-08-17 dual-AP gotcha is **inverted**: two same-SSID APs a
    meter apart = node roam blackouts that eat POSTs and kill ambience
    streams. The AP that must stay OFF is now the **Pi's hostapd**
    (stopped + disabled 2026-08-21). If triggers ever go flaky:
    `systemctl is-active hostapd` on the Pi must say `inactive`, and
    `iwinfo` on the RUT should be the only `LOHP-ESP`.
- WiFi-WAN (**`wireless.multiap_radio0`**, Multi AP station to the
  upstream) **disabled 2026-08-21, re-disabled 2026-08-31** — upstream
  internet moved to the Pi's own radio; the RUT radio is a pure AP.
  ⚠ **The 07.24.1 firmware update silently re-enabled this.** With no
  matching upstream SSID in range, wpa_supplicant scan-storms (1/s,
  `SCAN-FAILED ret=-16`) and drags the single radio off-channel — LOHP-ESP
  effectively stops beaconing and the whole node fleet flaps. **After any
  RUT firmware update, check `uci get wireless.multiap_radio0.disabled`
  is `1` before debugging anything else.** Re-enable it only if the maze
  LAN itself ever needs internet again (`uci set
  wireless.multiap_radio0.disabled=0; uci commit wireless; wifi`) — and
  expect the AP to hop to the upstream's channel while both roles share
  the radio.
- IPv4 masquerading/NAT config remains (harmless with no active WAN);
  wired WAN port unused

### DHCP

- Dynamic range `192.168.252.100–249`, 150 leases, 12 h, authoritative;
  leases in `/tmp/dhcp.leases`; IPv6 DHCP + RA enabled
- Persistent reservations: `lohp-server` → `192.168.252.231`;
  `lohp-node-monkey` → `192.168.252.72` (uci section `dhcp.node_monkey`,
  first room node, 2026-08-16). ESP32-S3 WiFi MAC = the board's USB-JTAG
  serial id (`ls /dev/serial/by-id/`), so a node's reservation can be staged
  before its first boot
- No automatic dynamic→static conversion — **add a reservation per ESP node
  at flash time** (needed anyway: the dockerized server can't resolve
  `.local`, so `dmx_nodes.json` wants IPs — see `dmx-over-wifi.md`).
  Node scheme: `192.168.252.(api_port − 6000)` — e.g. `lohp-node-monkey`
  api 6072 → `.72` (added 2026-08-16, first node reservation)

### Firewall

Packet filtering is effectively **disabled** (service runs only for NAT):
input/output/forward ACCEPT on all zones, attack prevention off, HTTP/HTTPS/SSH
listening on all addresses. Anyone on the upstream network can reach the RUT's
management UI and SSH — fine for bench; consider tightening WAN input before
running on shared camp WiFi.

## Pi (DietPi / Debian 12, hostname `lohp-server`)

- `br0` (ports: `eth0` only) is a DHCP client of the RUT (reservation →
  always `192.168.252.231`), gw `192.168.252.1` at route metric 100 —
  the maze-LAN leg, wire only
- `wlan0` = **upstream WiFi client** since 2026-08-21 (wpa_supplicant in
  `/etc/wpa_supplicant/wpa_supplicant.conf`: upstream priority 1 then 2,
  same list/order the RUT's WiFi-WAN used — SSIDs + passwords in the
  gitignored credentials file), DHCP at route metric 50, so the default
  route goes out the house WiFi while `.252/24` stays on the wire.
  Current lease `192.168.253.187`
- `hostapd` **stopped + disabled** (2026-08-21) — config kept in
  `/etc/hostapd/` only as rollback; it must never run alongside the RUT AP
- `/etc/dhcp/dhclient.conf` carries `supersede domain-name-servers
  1.1.1.1, 8.8.8.8;` so the RUT's (internet-less) DNS can't shadow the
  upstream's
- Reboot-tested 2026-08-21 (both boxes): AP, reservations, wlan0 rejoin,
  docker server autostart, node re-association all came back unaided

## Migration gotchas (2026-08-10 cutover)

- **ESP credentials moved**: `sim/esphome/secrets.yaml` (and the generated
  `firmware/{orb,sign}/secrets.h`) now hold the `LOHP-ESP` credentials.
  Anything flashed before 2026-08-10 still holds the upstream-WiFi
  credentials and keeps working there until reflashed.
- **Orb/sign OTA auth**: `gen_secrets.sh` sets `OTA_PASSWORD` = WiFi
  password, and `build.sh ota` reads the auth from the *new* `secrets.h` —
  but the device checks against its *running* firmware. For the first push
  after the cutover, OTA with the old password (temporarily set the old
  value in `secrets.h`) or flash over USB; subsequent OTAs use the new WiFi
  password.
- **SD reflash caveat**: the DietPi first-boot automation (pi-notes.md) still
  bakes the old pre-field assumptions. After any reflash, re-apply this current
  RUT-as-AP / Pi-as-upstream-client setup by hand — especially: RUT radio is
  the only `LOHP-ESP`, Pi `hostapd` is stopped+disabled, Pi `wlan0` is the
  upstream client, and Pi `eth0`/`br0` has the `192.168.252.231` reservation.
- No RUT rollback archive exists — the temporary rollback files were deleted.

## On-playa incident + retune, 2026-08-30/31

Symptom: fleet-wide node flapping ("rooms going up/down"), beds staggering,
boxes unreachable — while every box was powered. Two stacked RUT faults plus
a congested channel, all diagnosed over the reverse tunnel:

1. **WiFi-WAN scan storm** (root cause): the 07.20.3→07.24.1 firmware
   update re-enabled `wireless.multiap_radio0`; with the home upstream SSID
   absent, wpa_supplicant scanned once per second (`SCAN-FAILED ret=-16`)
   and the AP stopped beaconing — LOHP-ESP was absent from a band scan taken
   from the Pi at the same rack. Fix: disable + commit + reboot (see the
   WiFi-WAN bullet above).
2. **`logread -f` CPU spin**: this build busy-loops the log follower at
   ~90% CPU (0% idle) on every boot, even with zero log traffic. Syslog is
   now **disabled persistently** (`/etc/init.d/log disable`). Re-enable only
   while actively debugging, and expect the spin while it runs.
3. **Channel 6 → 1** (`uci set wireless.radio0.channel=1`): ch 6 carried
   three camp APs co-channel plus edge splatter from networks parked on
   ch 8/9; ch 11 holds the camp uplink and 7 APs. Settled-window survey on
   ch 1: ~55% airtime busy = our own TX 21% (Art-Net + beds) + foreign 34%.
   Nodes follow the SSID across channels on their own within ~95 s.
   The AP **cannot scan while serving** (`iwinfo scan` → "Scanning not
   possible") — census from the Pi: `iw dev wlan0 scan flush`. The honest
   congestion number is a survey DELTA over a timed window
   (`iw dev wlan0-1 survey dump`, busy−transmit), not the boot-cumulative
   counters.

Also changed on-playa:

- Pi sshd: `GatewayPorts clientspecified` (2026-08-30) so the dev box can
  publish the calibration phone page on `192.168.252.231:5001` through the
  reverse tunnel (`tools/calibrate/run-calibrate.sh`).
- Field access: the Pi reverse-tunnels to the dev box —
  `ssh -p 2222 dietpi@localhost` from there; deploys via
  `SSH_PORT=2222 tools/deploy-rpi.sh localhost`. RUT admin from the Pi:
  `sshpass -p '<see maze-network-credentials.md>' ssh root@192.168.252.1`.
- Node keepalive timeouts relaxed for playa RTTs (node_audio_manager:
  probe 8 s, connect 10 s) — 300–500 ms lossy RTTs are normal here and the
  old 3 s probe turned them into constant connection flapping.
