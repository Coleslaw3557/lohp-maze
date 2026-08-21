#!/usr/bin/env python3
"""The templated per-box print job — QL-820NWB die-cut DK-1202 62x100mm.

One DMX/network card per node enclosure (room name, IP, server, Art-Net,
fixtures, DMX range — pulled live from light_config.json + dmx_nodes.json)
and, for rooms with an external DB9-A box, one wiring card for it (pin map
from wiring-guides/room-node-wiring-guide.md, kept in POD_WIRING below).

Usage (from the repo root):
    tools/box_labels.py "Porto Room"            # render <room>-box.png/-pod.png
    tools/box_labels.py "Porto Room" --print    # render + ONE batched lp job

Printer rules live in ~/printer/PRINTING.md: 732x1181 @300dpi, bold, pure
black. Cards are designed landscape 1181x732 and rotated on save so the
printer maps pixels 1:1 (label reads sideways).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
W, H = 1181, 732

# DB9 port-A far-end boxes (room-node-wiring-guide.md table). Rooms not
# listed have no external box; extend as pods are built.
POD_WIRING = {
    "Porto Room": ("PIEZO KNOCK PADS ×3", [
        ("pin 3", "PAD 1 (piezo +)"),
        ("pin 4", "PAD 2 (piezo +)"),
        ("pin 5", "PAD 3 (piezo +)"),
        ("pin 2", "GND — all piezo −"),
        ("", "1MΩ bleeds live in the node box"),
    ]),
    "Vertical Moop March": ("MARCH BUTTONS ×4", [
        ("pin 3-6", "BTN 1-4 (close to GND)"),
        ("pin 2", "GND"),
        ("pin 1", "5V — button LEDs"),
    ]),
    "Bike Lock Room": ("QUIZ BUTTONS ×4 — PINS 6-9, NOT 3-6", [
        ("pin 6", "OPTION 1"),
        ("pin 7", "OPTION 2"),
        ("pin 8", "OPTION 3 — TRUE"),
        ("pin 9", "OPTION 4"),
        ("pin 2", "GND"),
        ("pin 1", "5V — button LEDs"),
    ]),
    "Gate": ("SERIES BANKS ×2 — PINS 8/9 (3 pads each, NO→COM chain)", [
        ("pin 8", "BANK A = PADS 1-3 in series"),
        ("pin 9", "BANK B = PADS 4-6 in series"),
        ("pin 2", "GND — both bank returns"),
        ("pin 1", "5V — all six pad LEDs"),
        ("", "bank conducts ONLY with all 3 held"),
    ]),
    "Monkey Room": ("PUZZLE BUTTON", [
        ("pin 3", "button (node D1)"),
        ("pin 2", "GND"),
        ("pin 1", "5V — button LED"),
    ]),
    "Photo Bomb Room": ("SHUTTER BUTTON", [
        ("pin 3", "button (node D1)"),
        ("pin 2", "GND"),
        ("pin 1", "5V — button LED"),
    ]),
}


def room_facts(room):
    lc = json.loads((REPO / "light_config.json").read_text())
    dn = json.loads((REPO / "dmx_nodes.json").read_text())
    na = json.loads((REPO / "node_audio_config.json").read_text())

    fixtures = lc["room_layout"].get(room)
    if fixtures is None:
        sys.exit(f"unknown room {room!r}; rooms: {sorted(lc['room_layout'])}")
    node = dn["nodes"][room]

    fixture_lines, ranges = [], []
    counts = {}
    for f in fixtures:
        model = f["model"]
        n_ch = len(lc["light_models"][model]["channels"])
        start = f["start_address"]
        ranges.append((start, start + n_ch - 1))
        short = model.replace("Light - Model ", "").replace("Light - ", "")
        counts.setdefault((short, n_ch), []).append(f"{start}-{start + n_ch - 1}")
    for (short, n_ch), rr in counts.items():
        fixture_lines.append(f"{len(rr)}× {short} ({n_ch}ch) @ {', '.join(rr)}")

    lo = min(a for a, _ in ranges)
    hi = max(b for _, b in ranges)
    return {
        "ip": node["host"],
        "server": f"{na['server_host']}:{na['server_port']}",
        "artnet": f"universe {dn['universe']} · unicast UDP {dn['port']}",
        "fixtures": fixture_lines,
        "dmx_range": f"{lo}-{hi}",
    }


def card(title, rows, out_path):
    """rows = [(field, value, font, size)]; field '' = full-width value line."""
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    size = 110
    while True:
        tfont = ImageFont.truetype(SANS, size)
        bb = draw.textbbox((0, 0), title, font=tfont)
        if bb[2] - bb[0] <= W - 120 or size <= 60:
            break
        size -= 6
    draw.text(((W - (bb[2] - bb[0])) / 2 - bb[0], 34 - bb[1]), title, font=tfont, fill="black")
    rule_y = 34 + (bb[3] - bb[1]) + 28
    draw.line((60, rule_y, W - 60, rule_y), fill="black", width=5)

    body_top, body_bot = rule_y + 18, H - 30
    heights, fitted = [], []
    for field, value, fpath, fsize in rows:
        # Shrink to the row's printable width (thermal clip = unreadable card).
        avail = (W - 40 - 330) if field else (W - 140)
        while True:
            vf = ImageFont.truetype(fpath, fsize)
            vb = draw.textbbox((0, 0), value, font=vf)
            if vb[2] - vb[0] <= avail or fsize <= 28:
                break
            fsize -= 2
        heights.append(vb[3] - vb[1])
        fitted.append(vf)
    gap = max(10, (body_bot - body_top - sum(heights)) / (len(rows) + 1))

    label_font = ImageFont.truetype(SANS, 34)
    y = body_top + gap
    for (field, value, fpath, fsize), h, vf in zip(rows, heights, fitted):
        vb = draw.textbbox((0, 0), value, font=vf)
        if field:
            draw.text((70, y + (h - 34) / 2), field.upper(), font=label_font, fill="black")
            draw.text((330 - vb[0], y - vb[1]), value, font=vf, fill="black")
        else:
            draw.text(((W - (vb[2] - vb[0])) / 2 - vb[0], y - vb[1]), value, font=vf, fill="black")
        y += h + gap

    img.rotate(90, expand=True).save(out_path, dpi=(300, 300))
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("room")
    ap.add_argument("--print", action="store_true", dest="do_print")
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args()

    facts = room_facts(args.room)
    out = Path(args.out_dir)
    slug = args.room.lower().replace(" ", "-")

    rows = [
        ("ip", facts["ip"], MONO, 58),
        ("server", facts["server"], MONO, 58),
        ("art-net", facts["artnet"], MONO, 46),
    ]
    for fl in facts["fixtures"]:
        rows.append(("fixtures" if fl is facts["fixtures"][0] else "", fl, MONO, 46))
    rows.append(("dmx range", facts["dmx_range"], MONO, 72))
    files = [card(args.room.upper(), rows, out / f"{slug}-box.png")]

    if args.room in POD_WIRING:
        subtitle, pins = POD_WIRING[args.room]
        rows = [("", subtitle, SANS, 60)]
        rows += [(("DB9-A " + p).strip() if p else "", v, MONO, 50) for p, v in pins]
        files.append(card(args.room.upper(), rows, out / f"{slug}-pod.png"))

    for f in files:
        print(f)
    if args.do_print:  # ONE batched job (PRINTING.md)
        cmd = ["lp", "-d", "Brother-QL-820NWB", "-o", "media=62x100mm",
               "-o", "PageSize=62x100mm", "-o", "MediaType=Labels",
               "-o", "fit-to-page", "-o", "PrintDensity=4Dark",
               *map(str, files)]
        sys.exit(subprocess.run(cmd).returncode)


if __name__ == "__main__":
    main()
