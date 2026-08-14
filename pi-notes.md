# Server Pi (DietPi) — provisioning + deploy

## Network (as built 2026-08-10) — RUT140 + Pi bridge AP

Full cut sheet: `wiring-guides/maze-network.md`. Short version: the RUT140
owns the maze LAN (`192.168.252.1/24` — DHCP, DNS, NAT, upstream WiFi
selection); the Pi no longer joins WiFi as a client — `br0` bridges `eth0`
(wired to the RUT LAN port) and `wlan0` (hostapd AP **LOHP-ESP**, 2.4 GHz
ch 6, WPA2), a transparent L2 bridge with a DHCP reservation:

- Pi: `dietpi@192.168.252.231` (`lohp-server.local` still works — mDNS
  crosses the bridge — so deploy/sim/console are unchanged **when you're on
  LOHP-ESP or the RUT LAN**)
- RUT: `https://192.168.252.1` (admin), `root@` for ssh
- From the upstream camp WiFi the Pi needs the RUT as a jump host:
  `ssh -J root@192.168.253.219 dietpi@192.168.252.231` (the `253.219` is the
  RUT's upstream DHCP lease — may change). The Pi's old upstream address
  `192.168.253.186` is dead.

## Automated path (2026-07-22)

The SD card is flashed from `DietPi_RPi234-ARMv8-Bookworm` (Raspberry Pi
2/3/4/Zero 2 image) with first-boot automation baked into the FAT partition
(`dietpi.txt`, `dietpi-wifi.txt`, `Automation_Custom_Script.sh`):

- joins the bench WiFi (credentials from `sim/esphome/secrets.yaml`, the same
  LAN the ESP32 nodes use), country `US`, DHCP, hostname `lohp-server`
  (mDNS `lohp-server.local` via avahi-daemon).
  **SUPERSEDED 2026-08-10**: the Pi is now a bridge AP behind the RUT140, not
  a WiFi client — after any reflash from this image, the `br0` + hostapd
  setup must be re-applied by hand (`wiring-guides/maze-network.md`); the
  first-boot automation has NOT been updated for it
- OpenSSH with the bench box's `~/.ssh/id_ed25519.pub` (tlister@rio) authorized
  for `root` and `dietpi`; password logins still allowed, login password is the
  DietPi default `dietpi`
- `AUTO_SETUP_AUTOMATED=1`: first boot self-updates, apt-installs
  `rsync git curl ca-certificates avahi-daemon iw`, then the custom script
  installs Docker (get.docker.com, includes the `docker compose` plugin),
  turns WiFi powersave off (the server unicasts Art-Net at 44 Hz — powersave
  adds latency spikes), pre-pulls `python:3.11-slim-bookworm`, and creates
  `/home/dietpi/lohp-server`
- timezone UTC, keyboard `us`, serial console left on

First boot needs internet and takes several minutes (dietpi-update + Docker
install); the green ACT LED settling down and `lohp-server.local` answering
ping are the "it's ready" signals.

### Deploy

```bash
tools/deploy-rpi.sh                  # target lohp-server.local (mDNS)
tools/deploy-rpi.sh 192.168.252.231  # or by IP (the RUT DHCP reservation)
```

Run it from a machine on the maze LAN (join **LOHP-ESP**); from the upstream
WiFi the Pi is behind the RUT's NAT (`wiring-guides/maze-network.md`).

Rsyncs the repo to `/home/dietpi/lohp-server` (deletes stale files; the Pi's
`photos/` is preserved), installs `tools/lohp-server.service`, runs
`docker compose build`, restarts the service, and waits for
`http://<pi>:5000/api/health` to answer.

### Watching it from the sim

The sim header has an `RPI` dot: green = server answering `/api/health`,
amber = Pi on the network but server not running (booted, not deployed),
red = unreachable. Default probe target is `lohp-server.local`; if mDNS
doesn't resolve on the sim box, launch with `RPI_HOST=<ip> sim/run.sh`.

### Floor projection (LS625X on HDMI)

`tools/rpi-projection-setup.sh` (run as root on the Pi, or via ssh) installs
the floor-projection renderer: configures the LEGACY display stack in
`/boot/firmware/config.txt` — vc4 KMS overlay commented out, a tiny
`framebuffer_width/height=192x144` firmware framebuffer that the VideoCore
scaler stretches to the projector's native mode, `gpu_mem` 64, HDMI blanking
off (first run exits 3 and asks for a reboot) — then builds
`/opt/lohp-projection-venv` (apt numpy + pip aioesphomeapi), installs and
starts `lohp-projection.service` — `projection_renderer.py --source demo
--theme jungle --grid 192 --fps 20` writing /dev/fb0 directly at grid
resolution (k=1, ~1 ms blit; the GPU does the whole upscale with smoothing).
History: no SDL/EGL — the vc4 EGL stack refused kmsdrm on the 3B+
(2026-07-22), and the KMS-sized fb cost ~60 ms/frame of numpy packing
(2026-07-23) — the firmware scaler is the free GPU on this box. The unit
unbinds fbcon while running; a `fps …` heartbeat prints to the journal once
a minute. Runs OUTSIDE docker. Theme switches live: `curl -X POST
http://lohp-server.local:5002/theme/<lava|jungle|temple>` (the sim Floor button
does this for you), and the renderer remembers its last theme in
`/home/dietpi/lohp-server/.floor_theme` — restarts and power cycles come back
showing whatever was last playing (`--theme` in the unit is first-boot only).
Flip `--source demo` to `--source esphome --node <cuddle-node>` in the unit
file once the LD2450 is wired (hardware day).
Content plans: `wiring-guides/cuddle-lava-plan.md`,
`wiring-guides/cuddle-jungle-plan.md`, `wiring-guides/cuddle-temple-plan.md`.

### Projector power (LS625X RS232 + DS3231, no internet needed)

The LS625X's USB service port has NO runtime control (probed 2026-07-23:
TI DDP442X HID, command dispatcher mute in ViewSonic's firmware — usbmon
shows every framing/transport ACKed and never answered; the port only talks
in firmware-download boot mode). Power control runs over the projector's
RS232 DE-9 instead: USB serial adapter (FTDI type, true RS232 levels — the
old DMX dongle is RS485, wrong PHY) + null-modem crossover per the manual's
page-71 pin table. Verified live 2026-08-11 (FTDI FT232R A700DQNX →
`/dev/ttyUSB0`, projector on the real cable): `--status` answers in
standby, and a full `--on` → warming → `--off` → standby round trip
works. Quirks seen live: warm-up takes >60 s to report `on`, and while
aborting a warm-up the projector ignores status reads for ~1 min
(`--status` prints `state=None`; harmless — the reconciler already holds
during warm/cool). Protocol: 115200 8N1, frames from the
ViewSonic LS625X user manual pages 70–82 (power on/off/status; status
distinguishes standby/warming/on/cooling, and the manual documenting a
"Power Down" status reply is why power-ON from standby works — the RS232
micro listens in standby).

`projector_power.py` + `tools/rpi-projector-power-setup.sh` (run as root on
the Pi; safe to re-run, tolerates absent hardware):

- `lohp-projector-power.service` — reconciler: at boot and every 20 min,
  read light rule + projector status and converge: ON from civil dusk (sun
  6° below horizon) to sunrise, OFF in daytime. No action while warming/
  cooling (re-checks in 60 s). Day/night is computed locally (NOAA solar
  equations, Black Rock City lat/lon baked in, overridable via
  PROJ_LAT/PROJ_LON/PROJ_CHECK_SEC in the unit) — needs only a sane clock.
- `lohp-projector-shutdown.service` — oneshot whose ExecStop sends the
  graceful RS232 power-off at system shutdown/reboot. Deploys restart the
  reconciler but never this unit, so deploys don't power-cycle the
  projector.
- DS3231 RTC (Dorhea module on header pins 1-3-5-7-9, labeled 3V3 on
  pin 1, the corner pin nearest the SD slot) + `dtoverlay=i2c-rtc,ds3231`
  — the clock of record (no NTP on playa; the 3B+ has no RTC). INSTALLED
  + SET 2026-08-12: kernel binds it (rtc-ds1307 driver) ~7 s into boot
  and its hctosys sets system time at probe; a udev rule
  (`/etc/udev/rules.d/85-lohp-hwclock.rules`) runs `hwclock --hctosys` on
  device-add as backup. The original `lohp-hwclock.service` lost a probe
  race — sysinit evaluated its ConditionPathExists=/dev/rtc0 at 6.2 s,
  rtc0 registered at 7.7 s — so the setup script now installs the udev
  rule and removes that unit. One-time `hwclock -w` from RUT NTP done
  2026-08-12 21:52 UTC. ⚠ Cell: these boards ship with a LIR2032 charge
  circuit — before socketing a non-rechargeable CR2032, remove the charge
  resistor/diode (or fit a LIR2032). Power-pull test PASSED 2026-08-12,
  by an NTP-proof method (journal realtime−monotonic offset steps — immune
  to the kernel writing NTP time back into the RTC): at first NTP contact,
  boot+39 s, the RTC-carried clock needed only a +0.457 s correction; a
  stopped oscillator would have needed the full outage, +60 s or more. The
  cell holds. (DietPi runs timesyncd boot-only — one sync, then it stops —
  so the DS3231 is the clock of record even at the bench.)
  Gotcha: the factory oscillator-stop flag (OSF, status reg 0x0f bit 7)
  survives `hwclock -w` on this driver and kept dmesg nagging `SET TIME!`
  at every probe; cleared once via i2cset (i2c-tools installed; userspace
  access needs `modprobe i2c-dev`). From now on a `SET TIME!` line in
  dmesg is a REAL alarm: oscillator stopped = dead/loose cell. A clock
  pre-2026 makes the reconciler deliberately do nothing but log (guard
  against torching the schedule off a bogus clock).
- `touch /home/dietpi/lohp-server/.projector-manual` suspends reconciling
  (bench/maintenance); deploy-rpi.sh protects that flag and `.floor_theme`
  from rsync --delete. Remove the file to resume.
- Handy: `python3 projector_power.py --status | --on | --off |
  --test-solar` (the last prints the current verdict and next dusk/sunrise
  in UTC and PDT). Journal heartbeat per pass:
  `projector: sun=-16.6deg night state=on usb=present action=none`
  (`usb=` is the DDP442X on the USB bus — free projector-power telemetry).
- The serial port exposes far more than power: temperature and
  light-source-hours telemetry, error-status block, source/volume/mute/
  blank/freeze/picture reads+writes, laser dimming (Custom 20–100 %),
  and full OSD navigation via remote-key injection. Cut sheet with
  frames, live-probed values, and gotchas:
  `wiring-guides/ls625x-rs232.md`; guide PDF mirrored at
  `~/lohp/LS625X_User_Guide.pdf`.

### Reflash note

Reflashing the card changes the Pi's SSH host key — clear the old one before
the next deploy:

```bash
ssh-keygen -R lohp-server.local
ssh-keygen -R 192.168.252.231
```

And remember the network caveat above: a fresh flash comes up as a WiFi
*client* (old config) — re-apply the bridge AP setup before the nodes can
see it.

## Manual recipe (original)

Here are the directions for auto-starting lohp-server Docker Compose on DietPi
(this is what `tools/rpi-setup.sh` now automates — the unit file lives at
`tools/lohp-server.service`):

    Create the systemd service file:

sudo nano /etc/systemd/system/lohp-server.service

    Add this content to the file:

[Unit]
Description=LOHP Server Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/dietpi/lohp-server
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target

    Save and exit the editor.

    Reload systemd:

sudo systemctl daemon-reload

    Enable the service:

sudo systemctl enable lohp-server.service

    Start the service:

sudo systemctl start lohp-server.service

    Check status:

sudo systemctl status lohp-server.service

    Reboot to test:

sudo reboot
