#!/usr/bin/env python3
"""Ammo-can parts label with a sim-derived top-down room map."""
import argparse
import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
W, H = 1181, 732


def font(path, size):
    return ImageFont.truetype(path, size)


def fit_text(draw, text, path, size, max_w, min_size=24):
    while size > min_size:
        f = font(path, size)
        bb = draw.textbbox((0, 0), text, font=f)
        if bb[2] - bb[0] <= max_w:
            return f
        size -= 2
    return font(path, size)


def pos_xz(pos):
    if len(pos) >= 3:
        return float(pos[0]), float(pos[2])
    return float(pos[0]), float(pos[1])


def room_footprint(room, layout, r):
    hex_center = layout.get("hex_center") or {}
    if hex_center.get("rooms", {}).get("upper") == room:
        cx = float(hex_center["cx"])
        cz = float(hex_center["cz"])
        side = float(hex_center["side"])
        vertices = []
        for k in range(6):
            a = math.pi / 6 + k * math.pi / 3
            vertices.append((cx + side * math.cos(a), cz + side * math.sin(a)))
        wing_w = float(layout["rooms"][hex_center["rooms"]["ground_west"]]["x"])
        east = layout["rooms"][hex_center["rooms"]["ground_east"]]
        wing_e = float(east["x"]) + float(east["w"])
        return [
            vertices[1], vertices[2], (wing_w, vertices[2][1]), (wing_w, vertices[3][1]),
            vertices[3], vertices[4], vertices[5], (wing_e, vertices[5][1]),
            (wing_e, vertices[0][1]), vertices[0],
        ]
    x0, z0 = float(r["x"]), float(r["z"])
    x1, z1 = x0 + float(r["w"]), z0 + float(r["d"])
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


def room_sensor_names(room, sensors, room_box):
    names = []
    aliases = {
        "Photo Bomb Room": ["photo bomb", "photobomb"],
        "Deep Playa Handshake": ["deep playa handshake", "handshake"],
        "Guy Line Climb": ["guy line"],
        "Sparkle Pony Room": ["sparkle pony"],
        "Cuddle Cross": ["cuddle cross"],
        "Bike Lock Room": ["bike lock"],
        "Monkey Room": ["monkey"],
        "Vertical Moop March": ["vertical moop", "moop march"],
        "Porto Room": ["porto"],
        "Gate": ["gate"],
    }.get(room, [room.lower()])
    x0, x1, z0, z1 = room_box
    for name, sensor in sensors.items():
        p = sensor.get("pos")
        if not p:
            continue
        x, z = pos_xz(p)
        lname = name.lower()
        name_hit = any(a in lname for a in aliases)
        if name_hit:
            names.append(name)
    return names


def draw_centered(draw, xy, text, f, fill="black"):
    x, y = xy
    bb = draw.textbbox((0, 0), text, font=f)
    draw.text((x - (bb[2] - bb[0]) / 2 - bb[0], y - (bb[3] - bb[1]) / 2 - bb[1]),
              text, font=f, fill=fill)


def label_for_room(room, out_path):
    layout = json.loads((REPO / "sim" / "maze_layout.json").read_text())
    dmx = json.loads((REPO / "dmx_nodes.json").read_text())

    if room not in layout["rooms"]:
        raise SystemExit(f"room not in sim layout: {room}")

    r = layout["rooms"][room]
    ip = dmx["nodes"].get(room, {}).get("host", "?")
    mac = {
        "Photo Bomb Room": "68:EE:8F:50:AF:C4",
        "Deep Playa Handshake": "68:EE:8F:50:B9:50",
        "Guy Line Climb": "68:EE:8F:50:B2:A8",
        "Sparkle Pony Room": "68:EE:8F:50:B2:EC",
        "Cuddle Cross": "68:EE:8F:50:B0:18",
        "Bike Lock Room": "68:EE:8F:50:B9:AC",
        "Monkey Room": "68:EE:8F:50:07:54",
        "Vertical Moop March": "A4:CB:8F:DF:52:80",
        "Porto Room": "68:EE:8F:50:AF:C0",
        "Gate": "68:EE:8F:50:B2:F4",
    }.get(room)

    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle((36, 36, W - 36, H - 36), outline="black", width=5)

    title_f = fit_text(draw, room.upper(), SANS, 96, W - 110, 54)
    draw_centered(draw, (W / 2, 88), room.upper(), title_f)
    info_x, info_y = 70, 166
    label_f = font(SANS, 30)
    value_f = font(MONO, 42)
    rows = [("IP", ip)]
    if mac:
        rows.append(("MAC", mac))
    rows.append(("LEVEL", f"{r.get('floor', '?')}"))
    for i, (k, v) in enumerate(rows):
        y = info_y + i * 58
        draw.text((info_x, y), k, font=label_f, fill="black")
        draw.text((info_x + 118, y - 7), v, font=value_f, fill="black")

    map_box = (560, 166, 1110, 674)
    draw.rectangle(map_box, outline="black", width=4)
    draw.text((map_box[0] + 16, map_box[1] + 12), "TOP-DOWN FROM SIM", font=font(SANS, 30), fill="black")

    footprint = room_footprint(room, layout, r)
    rx0, rx1 = min(p[0] for p in footprint), max(p[0] for p in footprint)
    rz0, rz1 = min(p[1] for p in footprint), max(p[1] for p in footprint)
    room_box = (rx0, rx1, rz0, rz1)

    items = []
    enc = r.get("enclosure")
    if enc and enc.get("pos"):
        items.append(("ENCLOSURE", pos_xz(enc["pos"]), enc))
    cam = r.get("camera_mount")
    if cam and cam.get("pos"):
        items.append(("CAMERA", pos_xz(cam["pos"]), cam))
    projection = layout.get("projection") or {}
    if projection.get("room") == room and projection.get("projector", {}).get("pos"):
        items.append(("PROJECTOR", pos_xz(projection["projector"]["pos"]), projection["projector"]))
    eye = layout.get("eye") or {}
    if eye.get("room") == room and eye.get("mount"):
        items.append(("ORB", pos_xz(eye["mount"]), eye))
    for tb in layout.get("audio_power", {}).get("terminal_blocks", []):
        if tb.get("room") == room and tb.get("pos"):
            items.append(("12V TB", pos_xz(tb["pos"]), tb))
    for ladder in layout.get("ladders", []):
        if ladder.get("room") == room and ladder.get("pos"):
            items.append(("CLIMB", pos_xz(ladder["pos"]), ladder))
    for sname in room_sensor_names(room, layout.get("sensors", {}), room_box):
        s = layout["sensors"][sname]
        label = "SENSOR" if ("yaw_deg" in s or "fov_deg" in s) else sname.replace(room, "").strip() or "PART"
        if "Shutter" in sname:
            label = "SHUTTER"
        if "Handshake Button" in sname:
            label = "BTN" + sname.rsplit(" ", 1)[-1]
        items.append((label.upper(), pos_xz(s["pos"]), s))

    combined = []
    used = set()
    for i, (label, p, meta) in enumerate(items):
        if i in used:
            continue
        if label == "ENCLOSURE":
            merged = dict(meta)
            has_sensor = False
            has_climb = False
            has_orb = False
            for j, (label2, p2, meta2) in enumerate(items):
                if j == i or j in used:
                    continue
                same_point = abs(p2[0] - p[0]) < 0.03 and abs(p2[1] - p[1]) < 0.03
                if same_point and label2 in {"SENSOR", "CLIMB", "ORB"}:
                    merged.update(meta2)
                    if label2 == "SENSOR":
                        has_sensor = True
                    elif label2 == "ORB":
                        has_orb = True
                    else:
                        has_climb = True
                    used.add(j)
            if has_climb:
                merged_label = "ENC/SENSOR/CLIMB"
            elif has_sensor and has_orb:
                merged_label = "ENC/SENSOR/ORB"
            elif has_sensor:
                merged_label = "ENC/SENSOR"
            elif has_orb:
                merged_label = "ENC/ORB"
            else:
                merged_label = label
            combined.append((merged_label, p, merged))
            used.add(i)
        else:
            combined.append((label, p, meta))
            used.add(i)
    items = combined

    xs = [p[0] for p in footprint] + [p[0] for _, p, _ in items]
    zs = [p[1] for p in footprint] + [p[1] for _, p, _ in items]
    pad = 0.28
    min_x, max_x = min(xs) - pad, max(xs) + pad
    min_z, max_z = min(zs) - pad, max(zs) + pad
    mx0, my0, mx1, my1 = map_box
    inner = (mx0 + 48, my0 + 70, mx1 - 42, my1 - 118)
    iw, ih = inner[2] - inner[0], inner[3] - inner[1]
    scale = min(iw / (max_x - min_x), ih / (max_z - min_z))

    def sx(x):
        return inner[0] + (x - min_x) * scale

    def sy(z):
        return inner[3] - (z - min_z) * scale

    # Room footprint.
    draw.line(
        [(sx(x), sy(z)) for x, z in footprint] + [(sx(footprint[0][0]), sy(footprint[0][1]))],
        fill="black",
        width=5,
    )
    # Direction convention from sim: yaw 0 faces +z. Draw sensor rays and FOV.
    for label, (x, z), meta in items:
        if "yaw_deg" not in meta:
            continue
        yaw = math.radians(float(meta.get("yaw_deg", 0)))
        rng = min(float(meta.get("range_m", 1.2)), 1.4)
        fov = math.radians(float(meta.get("fov_deg", 35)))
        px, py = sx(x), sy(z)
        if float(meta.get("fov_deg", 35)) >= 359:
            draw.ellipse((px - 24, py - 24, px + 24, py + 24), outline="black", width=3)
            draw.line((px - 30, py, px + 30, py), fill="black", width=2)
            draw.line((px, py - 30, px, py + 30), fill="black", width=2)
            continue
        for a in (yaw - fov / 2, yaw + fov / 2, yaw):
            ex = sx(x + math.sin(a) * rng)
            ey = sy(z + math.cos(a) * rng)
            draw.line((px, py, ex, ey), fill="black", width=3)

    codes = {
        "ENC/SENSOR": "E",
        "ENC/SENSOR/CLIMB": "E",
        "ENC/SENSOR/ORB": "E",
        "ENC/ORB": "E",
        "ENCLOSURE": "E",
        "SENSOR": "S",
        "CAMERA": "C",
        "PROJECTOR": "P",
        "ORB": "O",
        "SHUTTER": "B",
        "BTN1": "1",
        "BTN2": "2",
        "BTN3": "3",
        "BTN4": "4",
        "BTN5": "5",
        "12V TB": "T",
        "CLIMB": "L",
    }
    legend_text = {
        "E": "box+sensor",
        "C": "camera",
        "B": "shutter",
        "1": "button 1",
        "2": "button 2",
        "3": "button 3",
        "4": "button 4",
        "5": "button 5",
        "T": "12V terminal",
        "L": "climb point",
        "S": "sensor",
        "P": "projector",
        "O": "orb",
    }
    if any(label == "ENC/SENSOR/ORB" for label, _, _ in items):
        legend_text["E"] = "box+sensor+orb"

    for label, (x, z), meta in items:
        px, py = sx(x), sy(z)
        code = codes.get(label, label[:1])
        dark = label in {"ENCLOSURE", "ENC/SENSOR", "ENC/SENSOR/CLIMB", "ENC/SENSOR/ORB", "ENC/ORB", "SENSOR"}
        if label in {"ENCLOSURE", "ENC/SENSOR", "ENC/SENSOR/CLIMB", "ENC/SENSOR/ORB", "ENC/ORB"}:
            draw.rectangle((px - 12, py - 12, px + 12, py + 12), fill="black")
        elif label == "SENSOR":
            draw.ellipse((px - 10, py - 10, px + 10, py + 10), fill="black")
        else:
            draw.ellipse((px - 13, py - 13, px + 13, py + 13), outline="black", width=4)
        cf = font(SANS, 20)
        cb = draw.textbbox((0, 0), code, font=cf)
        draw.text((px - (cb[2] - cb[0]) / 2 - cb[0], py - (cb[3] - cb[1]) / 2 - cb[1]),
                  code, font=cf, fill=("white" if dark else "black"))

    used_codes = []
    for label, _, _ in items:
        code = codes.get(label, label[:1])
        if code not in used_codes:
            used_codes.append(code)
    legend_x, legend_y = map_box[0] + 22, map_box[3] - 92
    lf = font(MONO, 21)
    for i, code in enumerate(used_codes[:5]):
        col = i // 3
        row = i % 3
        draw.text((legend_x + col * 265, legend_y + row * 28),
                  f"{code}={legend_text.get(code, code)}", font=lf, fill="black")

    img.rotate(90, expand=True).save(out_path, dpi=(300, 300))
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("room")
    ap.add_argument("--print", action="store_true", dest="do_print")
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args()

    out = Path(args.out_dir) / f"{args.room.lower().replace(' ', '-')}-parts-can.png"
    label_for_room(args.room, out)
    print(out)
    if args.do_print:
        cmd = [
            "lp", "-d", "Brother-QL-820NWB",
            "-o", "media=62x100mm",
            "-o", "PageSize=62x100mm",
            "-o", "MediaType=Labels",
            "-o", "fit-to-page",
            "-o", "PrintDensity=4Dark",
            str(out),
        ]
        raise SystemExit(subprocess.run(cmd).returncode)


if __name__ == "__main__":
    main()
