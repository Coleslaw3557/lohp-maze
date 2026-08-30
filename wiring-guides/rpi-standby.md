# Server Pi cold standby — SD card (baked 2026-08-24)

One microSD card (SanDisk-class 64 GB, labeled **LOHP STANDBY**) that turns a
spare Raspberry Pi into the maze server. Cold standby: if the primary dies,
power it off, move the card + peripherals to the spare, done. First boot needs
**zero internet** — everything is pre-baked (the playa has none).

Built on rio 2026-08-24 from repo `main` and `DietPi_RPi234-ARMv8-Bookworm`
(Pi 2/3/4/Zero 2 image — matches the 3B+ primary; **not a Pi 5 image**).
The build was fully offline-provisioned in an ARM chroot; it has **never
booted on real hardware** — do the bench validation below before packing it.

## Swap procedure (the 3 a.m. version)

1. Power off the primary Pi (pull power if it's already dead).
2. Move to the spare Pi:
   - this SD card
   - **DS3231 RTC module** — header pins 1‑3‑5‑7‑9, 3V3 corner pin nearest
     the SD slot (it carries the real time on its cell; without it the clock
     is wrong and the projector reconciler deliberately does nothing but log)
   - FTDI RS232 USB adapter (projector power)
   - C930e webcam USB (Photo Bomb)
   - HDMI to the projector, ethernet to the RUT LAN port, power last
3. First boot: ~5 extra minutes while a one-shot unit loads the pre-baked
   docker image (`lohp-image-load.service`), then the server comes up on its
   own. Later boots are normal speed.
4. Check: `http://192.168.252.231:5000/api/health` from anything on LOHP-ESP
   (mDNS `lohp-server.local` also works on the maze LAN).
5. The card's SSH host keys differ from the primary's — on any box that has
   talked to the primary: `ssh-keygen -R lohp-server.local` and
   `ssh-keygen -R 192.168.252.231`.

## Deliberate differences from the primary

| | Primary | Standby card |
|---|---|---|
| `br0` (eth0) maze-LAN address | DHCP + RUT reservation (keyed to the primary's MAC) | **Static 192.168.252.231** — a spare Pi's MAC won't match the reservation, and the reservation keeps `.231` out of the dynamic pool while the primary is off |
| hostapd | installed, stopped+disabled (rollback config) | **not installed at all** — can't ever fight the RUT AP |
| `photos/`, `data/` | live data | **empty** — Photo Bomb photos to date stay on the primary's card (recover them from it later); audio levels / sound mode restart at defaults |
| DietPi first-run | completed online 2026-07 | neutered in the bake (`.install_stage=2`, firstboot disabled, update checks + NTP mode 0 — the DS3231 is the clock of record) |
| Docker server image | built on-Pi by deploys | pre-built on rio (buildx arm64), loaded by `lohp-image-load.service` on first boot |

Everything else matches the as-built primary: wlan0 upstream WiFi client
(all three upstream SSIDs, powersave off), DNS supersede in `dhclient.conf`,
avahi mDNS, rio's ed25519 key for `root` + `dietpi`, root/dietpi passwords
per the credentials sheet, projection venv + legacy-framebuffer `config.txt`
(192×144 fb, `gpu_mem_1024=64`, `hdmi_blanking=0`), I2C + DS3231 overlay,
the `85-lohp-hwclock.rules` udev rule, 1 GB swapfile, and all four LOHP
systemd units enabled. Deploy tree at `/home/dietpi/lohp-server` is repo
`main` as of the bake (`tools/deploy-rpi.sh` works on it unchanged — first
deploy just rebuilds the docker image as usual).

## Bench validation (do once before packing)

Boot it in a spare Pi at the bench with ethernet into the RUT LAN:

1. First boot, wait ~5 min → `curl http://192.168.252.231:5000/api/health`
2. `ssh root@192.168.252.231 docker ps` — container `lohp-server` up
3. wlan0 joined the house WiFi (`ip -4 addr show wlan0`) — proves the radio
   stack; on playa this leg simply stays down
4. Reboot once more — second boot should be fast and clean
5. Shut down (`poweroff`), pull the card, label it, pack it with the spares

If the spare Pi is a **Pi 5**, stop: this image won't boot on it — tell
Claude, the bake needs the RPi5 base image (and the legacy-framebuffer
projection path needs rethinking there).

## Rebaking / provenance

Build artifacts live in `~/lohp/rpi-standby/` on rio — **local only, never
commit** (the provisioning script embeds WiFi credentials):

- `rpi-standby-20260824.img` — the finished image (dd it to any ≥10 GB card,
  then grow partition 2: `sfdisk -N 2` with `, +` then `resize2fs`)
- `provision-standby.sh` — the full bake script (base DietPi image →
  finished standby); rerun after major server changes, or just re-dd and
  let the next `deploy-rpi.sh` refresh the tree
- `lohp-server-image.tar` + `.sha256` — the arm64 docker image as preloaded

The card does NOT self-refresh: after significant repo/server changes before
departure, either rebake or boot it once on the bench and run a normal
`tools/deploy-rpi.sh 192.168.252.231` against it.
