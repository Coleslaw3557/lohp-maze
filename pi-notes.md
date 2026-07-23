# Server Pi (DietPi) — provisioning + deploy

## Automated path (2026-07-22)

The SD card is flashed from `DietPi_RPi234-ARMv8-Bookworm` (Raspberry Pi
2/3/4/Zero 2 image) with first-boot automation baked into the FAT partition
(`dietpi.txt`, `dietpi-wifi.txt`, `Automation_Custom_Script.sh`):

- joins the bench WiFi (credentials from `sim/esphome/secrets.yaml`, the same
  LAN the ESP32 nodes use), country `US`, DHCP, hostname `lohp-server`
  (mDNS `lohp-server.local` via avahi-daemon)
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
tools/deploy-rpi.sh              # target lohp-server.local (mDNS)
tools/deploy-rpi.sh 192.168.1.42 # or by IP
```

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
does this for you). Flip `--source demo` to `--source esphome --node
<cuddle-node>` in the unit file once the LD2450 is wired (hardware day).
Content plans: `wiring-guides/cuddle-lava-plan.md`,
`wiring-guides/cuddle-jungle-plan.md`, `wiring-guides/cuddle-temple-plan.md`.

### Reflash note

Reflashing the card changes the Pi's SSH host key — clear the old one before
the next deploy:

```bash
ssh-keygen -R lohp-server.local   # and/or the IP
```

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
