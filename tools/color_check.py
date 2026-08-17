#!/usr/bin/env python3
"""Put a colour on a real par and decide, by eye, where orange becomes yellow.

The palette rule ("no yellow") has been argued from sRGB hue maths, and the
maths has been wrong twice in the room. On an RGBW par the green emitter is far
more visible per unit drive than the red one (the eye peaks near 555 nm, right
on top of green, and falls off hard toward 625 nm red), so a mix that plots as
"orange" on a monitor can read plainly YELLOW on the fixture. The only way to
settle the boundary is to look at it.

This drives one room's fixtures directly, holding each colour until you say
next, and records which ones you call yellow. The theme is stopped first so
nothing repaints over the colour, and attract is restored on the way out.

    tools/color_check.py                          # walk the palette, Vertical Moop March
    tools/color_check.py --room Gate
    tools/color_check.py --sweep                  # r=255, b=0, g climbing: find the line
    tools/color_check.py --rgb 255,95,10          # hold one colour
    tools/color_check.py --off                    # blackout + restore attract

Answer each prompt with ENTER (next), y (reads yellow), or q (quit).
"""
import argparse
import colorsys
import json
import sys
import urllib.error
import urllib.request

API = 'http://localhost:5000'

# What I claim each of these is. The bench decides who is right.
PALETTE = [
    ("torch deep",      (255,  60,   0), "deep orange, no yellow in it at all"),
    ("COPPER",          (230,  80,  20), "old-fitting copper — the maze's warm standard"),
    ("EMBER",           (255,  95,  10), "torch flame orange — the other warm standard"),
    ("entrance ember",  (255, 120,  20), "orange, but the green is climbing — SUSPECT"),
    ("backtrack amber", (255, 130,   0), "amber. My maths said orange; I expect this to read yellow"),
    ("monkey gold",     (255, 160,   0), "gold — I expect this to read yellow on the par"),
    ("photobomb gold",  (255, 190,  60), "warm gold — expect yellow"),
    ("plain yellow",    (255, 210,   0), "yellow, no argument"),
    ("pure yellow",     (255, 255,   0), "red + green at equal drive = yellow. The thing we ban"),
    ("chartreuse",      (176, 255,   0), "yellow-green — what the old clamp EMITTED as its 'safe' escape"),
    ("moop green",      ( 70, 195,  65), "the room's own green"),
    ("jade",            (  0, 255,  80), "victory green"),
    ("teal",            (  0, 190, 170), "temple teal"),
]


def post(path, payload):
    req = urllib.request.Request(API + path, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {'error': f'{e.code} {e.read()[:120].decode(errors="replace")}'}
    except Exception as e:
        return {'error': str(e)}


def show(room, rgb, total=255, w=0):
    r, g, b = rgb
    return post('/api/run_test', {
        'testType': 'channel',
        'rooms': [room],
        'channelValues': {'total_dimming': total, 'r_dimming': r, 'g_dimming': g,
                          'b_dimming': b, 'w_dimming': w, 'total_strobe': 0,
                          'function_selection': 0, 'function_speed': 0},
    })


def describe(rgb):
    r, g, b = rgb
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    ratio = f"{g / r:.2f}" if r else "-"
    return f"rgb=({r:3d},{g:3d},{b:3d})  hue={h * 360:5.1f}deg  sat={s:.2f}  g/r={ratio}"


def quiet_maze():
    post('/api/attract', {'on': False})
    post('/api/set_theme', {'theme_name': 'notheme'})


def restore():
    post('/api/stop_test', {})
    post('/api/attract', {'on': True})


def ask(label, detail, rgb):
    print(f"\n  {label:16} {describe(rgb)}")
    print(f"    I say: {detail}")
    try:
        answer = input("    [ENTER]=next  y=this reads YELLOW  q=quit > ").strip().lower()
    except EOFError:
        return 'q'
    return answer


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--room', default='Vertical Moop March')
    parser.add_argument('--rgb', help='hold one colour, e.g. 255,95,10')
    parser.add_argument('--sweep', action='store_true',
                        help='r=255, b=0, g in steps — find where orange turns yellow')
    parser.add_argument('--total', type=int, default=255, help='master dimmer (default 255)')
    parser.add_argument('--off', action='store_true', help='blackout and restore attract')
    args = parser.parse_args()

    if args.off:
        restore()
        print("blacked out; attract restored")
        return

    print(f"room: {args.room}   (theme stopped so the colour holds)")
    quiet_maze()

    called_yellow = []
    try:
        if args.rgb:
            rgb = tuple(int(x) for x in args.rgb.split(','))
            print(f"  holding {describe(rgb)}")
            show(args.room, rgb, args.total)
            input("  ENTER to release > ")
            return

        if args.sweep:
            print("  r=255, b=0. Say when it stops being orange and starts being yellow.")
            steps = [0, 40, 60, 80, 95, 110, 120, 130, 145, 160, 175, 190, 210, 230, 255]
            for g in steps:
                rgb = (255, g, 0)
                show(args.room, rgb, args.total)
                answer = ask(f"g={g}", f"hue {colorsys.rgb_to_hsv(1, g/255, 0)[0]*360:.0f}deg", rgb)
                if answer == 'q':
                    break
                if answer == 'y':
                    called_yellow.append((f"g={g}", rgb))
        else:
            for label, rgb, detail in PALETTE:
                show(args.room, rgb, args.total)
                answer = ask(label, detail, rgb)
                if answer == 'q':
                    break
                if answer == 'y':
                    called_yellow.append((label, rgb))
    finally:
        restore()

    if called_yellow:
        print("\n  YOU CALLED THESE YELLOW:")
        lowest = None
        for label, rgb in called_yellow:
            h = colorsys.rgb_to_hsv(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)[0] * 360
            print(f"    {label:16} {describe(rgb)}")
            if lowest is None or h < lowest[0]:
                lowest = (h, label, rgb)
        if lowest:
            h, label, rgb = lowest
            print(f"\n  Lowest one you called yellow: {label} at {h:.1f}deg "
                  f"(g/r {rgb[1]/rgb[0]:.2f}).")
            print(f"  So the ban has to start BELOW that — effect_utils.YELLOW_ARC "
                  f"low edge goes to about {max(h - 4, 1)/360:.3f} ({h - 4:.0f}deg), "
                  f"and warm tones get built at or under g/r {max(rgb[1]/rgb[0] - 0.08, 0.05):.2f}.")
    else:
        print("\n  nothing called yellow")


if __name__ == '__main__':
    main()
