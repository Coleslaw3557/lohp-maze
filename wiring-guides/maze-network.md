# Maze network — RUT140 router + Pi bridge AP (as built 2026-08-10)

One flat LAN, `192.168.252.0/24`, for everything in the maze: the server Pi,
every ESP32 node, the orb, the sign bridge, and any laptop that joins
`LOHP-ESP`. The Teltonika RUT140 owns the network — upstream selection,
routing, DHCP, DNS, NAT. The Pi is a **transparent Layer-2 wireless access
point** bridged onto the RUT's LAN; it does no DHCP and no NAT.

## Topology

```text
Upstream Wi-Fi (camp)
      │
RUT140 Wi-Fi WAN / Multi AP        ← picks the upstream by priority, NATs
      │ LAN 192.168.252.1/24
      │ RUT LAN port ── ethernet ── Pi eth0
Raspberry Pi  eth0 ↔ br0 ↔ wlan0   ← transparent L2 bridge, hostapd AP
      │
LOHP-ESP 2.4 GHz                   ← ESP32 nodes, orb, sign bridge, laptops
```

## Credentials

All usernames, upstream SSIDs and passwords live in
`maze-network-credentials.md` next to this file — **gitignored, local only**
(this repo is public on GitHub). If that file is missing, re-copy it from the
bench box or the laminated cut sheet.

## Addresses + access

| Device | Address |
|---|---|
| RUT from LAN | `https://192.168.252.1` |
| RUT from current upstream | `https://192.168.253.219` (upstream DHCP — **may change**) |
| Pi (RUT DHCP reservation) | `192.168.252.231` — MAC `b8:27:eb:08:0c:24`, hostname `lohp-server` |

**Normal ops: join `LOHP-ESP`.** You're then on the flat LAN — mDNS crosses
the Pi's L2 bridge, so `lohp-server.local`, `tools/deploy-rpi.sh`, the sim's
RPI dot, and the audio console all work unchanged.

**From the upstream network** the Pi is behind the RUT's NAT and needs the RUT
as a jump host:

```bash
ssh -J root@192.168.253.219 dietpi@192.168.252.231
```

or in `~/.ssh/config`:

```
Host lohp-pi
    HostName 192.168.252.231
    User dietpi
    ProxyJump root@192.168.253.219
```

The Pi's former upstream-WiFi address `192.168.253.186` is **dead** — the Pi
no longer joins any WiFi as a client.

Two upstream-side reachability quirks (learned on the 2026-08-16 Monkey Room
bring-up):

- The RUT's own admin surfaces (WebUI + ssh) answer from upstream **only at
  the WAN address** `192.168.253.219`. `192.168.252.1` pings from upstream
  but refuses admin — use it only from the maze LAN.
- Upstream traffic is forwarded to **wired** LAN hosts (the Pi) but **not to
  WLAN clients** — ESP nodes are unreachable from the upstream network. To
  drive a node from an upstream bench box, go through the Pi:
  `scp sim/esphome/harness.py root@192.168.252.231:/home/dietpi/lohp-server/`
  then `ssh root@192.168.252.231 "docker exec lohp-server python
  /app/harness.py call <node-ip>:<api_port> press_button"` (the container has
  aioesphomeapi; the copy is cleaned by the next deploy's rsync).

**Reflash gotcha — stale hostapd station entry.** Reflashing a node kills its
WiFi client without a deauth frame, and the Pi's brcmfmac AP then refuses the
node's re-association: the node loops `reason='Auth Expired'` at strong RSSI
while `iw dev wlan0 station dump` on the Pi still shows the old session's
`connected time` climbing. Fix: `systemctl restart hostapd` on the Pi (brief
AP blip for every WLAN client), then the node joins within ~30 s. Hit on the
Monkey Room radar reflash 2026-08-16 — expect it on every node reflash.
FIXED same day: `hostapd.conf` now carries `ctrl_interface=/run/hostapd`
(surgical kick: `hostapd_cli -p /run/hostapd deauthenticate <mac>`) and
`ap_max_inactivity=60`, so a dead session ages out and the reflashed node
re-associates on its own within ~1 min — the manual restart is only the
impatient path now. Backup of the pre-change conf:
`/etc/hostapd/hostapd.conf.bak-20260816` on the Pi (config is Pi-local,
not in this repo — re-apply by hand if the SD is ever re-imaged).

## RUT140 (FW `RUT14X_R_00.07.20.3`)

- LAN `192.168.252.1/24`; internal RUT AP **disabled** — the Pi is the AP
  - ⚠ **GOTCHA (hit 2026-08-17):** found silently re-enabled
    (`wireless.default_radio0`, same `LOHP-ESP`/psk2 as the Pi, cause
    unknown — possibly the 08-14 config session). TWO same-SSID APs a
    meter apart = nodes roam Pi↔RUT; every roam is a ~seconds TCP
    blackout that eats in-flight `run_effect`/`room_vacated` POSTs and
    kills the node's ambience stream mid-flow, while Art-Net UDP sails
    through — looks like "random lost triggers", VMM bench hit it twice
    in 10 min. Re-disabled via
    `uci set wireless.default_radio0.disabled=1; uci commit wireless;
    wifi`. If triggers ever go flaky again, `iwinfo` on the RUT and an
    empty `iw dev wlan0 station dump` on the Pi is the 30-second check.
- WiFi configured exclusively as **Multi AP station** (WiFi WAN), scan
  interval 60 s, priority order per the credentials file. Priority 1 tested
  live; priority 2 stored but untested (network was unavailable)
- WiFi WAN logical interface `wwan`, DHCP metric 10; wired WAN stays DHCP
  at metric 1
- IPv4 masquerading/NAT on; LAN→WAN and WAN→LAN forwarding enabled
- Current upstream lease: `192.168.253.219/24`, gateway `192.168.253.1`

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

- `br0` bridges `eth0` + `wlan0`; `br0` is a DHCP client of the RUT
  (reservation → always `192.168.252.231`), default gw `192.168.252.1`,
  route metric 100
- `hostapd`: SSID `LOHP-ESP`, 2.4 GHz, channel 6, WPA2-PSK CCMP/AES,
  country US — active and enabled at boot; `networking` enabled at boot
- Old WiFi-client processes removed; Docker networking untouched
- Pi→RUT and Pi→internet verified

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
  bakes the *old* WiFi-client config. After any reflash, the bridge AP setup
  (`br0` + hostapd, above) must be re-applied by hand — the automation has
  not been updated for it.
- No RUT rollback archive exists — the temporary rollback files were deleted.
