// LoHP maze — universal room-node enclosure, LASER-CUT edition
// ============================================================
// ONE design for all 15 room nodes, cut on the xTool from 3mm ply (walls)
// + 3mm acrylic (window panel). Six finger-jointed panels GLUE together
// (floor mortises through the wall bottoms, corner fingers interlock);
// the LID is the service hatch — it SLIDES in and out through a mouth in
// the front wall, riding side tongues in through-slot channels (no
// fasteners; finger-pull notch at the front edge).
//
// Holds the standard node build: XIAO ESP32-S3 + PCM5102A DAC + the room's
// ranging sensor(s) against the window (LD2410C, VL53L1X, Cuddle's
// 2410C+2450 pair — the pair needs the WIDER aperture: cuddle=true below;
// export.py emits both jobs). Boards fix at their ETCHED footprint marks
// however works on the bench (VHB/screws); nothing is pre-drilled.
// Board footprints + ply thickness measured on the real parts 2026-07-21.
//
// IO — port B cut, everything else etched + opened per room on the bench:
//   left wall: 2x DB9 positions — the field IO for the traveling maze
//     (rapid setup: one premade straight-through M-F serial extension
//     cable per wired room, screw-terminal breakout shells at both ends —
//     no crimping or soldering anywhere). UNIVERSAL PINOUT on every box,
//     used or not: 1 = 5V, 2 = GND, 3-9 = signals 1-7. Per-room map in
//     wiring-guides/db9-field-wiring.md. Port A = etched, opened in the
//     7 wired rooms. Port B = CUT in every box: it is the room's DMX OUT
//     (MAX485 inside -> DB9->XLR adapter -> the room's fixtures, pinout
//     2=GND 3=Data+ 4=Data-, wiring-guides/dmx-over-wifi.md); a future
//     MCP23017's extra signals may share its shell. Wall-mounted because
//     plugs insert horizontally — the 34mm interior can't take a vertical
//     connector. Dust caps on playa.
//   floor (faces DOWN when mounted): 1x ~10mm SPARE grommet hole — the
//     wildcard for anything that isn't a DB9 someday.
//   right wall: USB-C slot (XIAO power) + AUX hole — the DAC's OWN 3.5mm
//     jack barrel sits behind it (board butts the wall); no separate
//     panel-mount jack. Antenna stays INSIDE the box — no hole.
//   front wall: sensor aperture; the acrylic window panel screws over it
//     (2x M2 self-tap on the midline). Radar sees through plain acrylic;
//     the 4 ToF rooms cut the marked aperture through the panel (940nm
//     won't pass acrylic).
//   back wall: two vertical velcro-strap slots (CUT — a 20mm one-wrap
//     threads through and wraps the scaffold leg).
//
// Export (SVG for xTool; kerf compensate in XCS if you want tight joints):
//   python3 export.py    # standard + cuddle variants, ply + acrylic jobs
//   part="3d" is the glued-up assembly preview.

part = "3d";     // front|back|left|right|floor|lid|window|sheet|3d
cuddle = false;  // true = Cuddle's wide-aperture one-off (2450 + 2410C)

// ---- stock -------------------------------------------------------------
t  = 2.9;        // ply thickness — MEASURED on the sheet 2026-07-21
acrylic_t = 3;   // window stock, nominal (preview + screw length only)
kerf_note = "cut outlines are exact; add kerf offset in xTool XCS";

// ---- box (outer) -------------------------------------------------------
W  = 110;        // width  (front/back length)
D  = 78;         // depth  (left/right length)
inner_h = 34;    // interior height (floor top -> lid underside)

// ---- sliding lid -------------------------------------------------------
slide_w = t + 0.4;       // channel width (lid thickness + play)
slide_z = t + inner_h;   // channel bottom
cap_h   = 3.6;           // rail above the channel
Hw = slide_z + slide_w + cap_h;  // wall height = outer height (43.8 at t=2.9)
lid_w   = W - 2*t + 4.4; // side tongues ride 2.2mm into each side channel
lid_d   = D - t;         // front edge flush outside; back edge stops
                         //  against the back wall's inner face
lid_notch = 14;          // finger pull, front edge

// ---- measured boards (calipers on the real parts, 2026-07-21) ----------
dac_l = 31.93;  dac_w = 17.23;  // PCM5102A; 3.5mm jack on a short edge, its
dac_cy = 51;                    //  barrel +2.44 past the PCB -> butt that
                                //  edge to the right wall, barrel lands in
                                //  the AUX hole. Screwed down where it sits.
xiao_l = 21.46; xiao_w = 17.78; // XIAO ESP32-S3; USB-C on a LONG edge, +2
xiao_cy = 13;                   //  past the PCB -> that edge to the wall
ld2410_w = 22.14; ld2410_h = 16;   // radar, sensor side faces the window
ld2450_w = 44.12; ld2450_h = 15.4; // Cuddle's second radar

// ---- features ----------------------------------------------------------
win_w = cuddle ? 68 : 56;         // aperture (68 fits 2450+2410C side by side)
win_h = 24;  win_cz = t + 17;     // aperture center height
panel_w = cuddle ? 82 : 70;  panel_h = 32;   // acrylic window panel
wscrew_x = panel_w/2 - 3.5;  // 2 window screws on the midline: M2 self-tap
                             //  (~4 head). Corner screws would leave <1mm
                             //  acrylic web at these margins -> cracks.
usb_w = 10; usb_h = 4;       // XIAO USB-C slot
usb_z = 3.7;                 // floor -> shell center (VHB 1 + PCB + shell/2)
jack_z = 6;                  // floor -> DAC jack barrel center (PCB + barrel
                             //  + solder stubs) — ESTIMATE; drill after the
                             //  DAC is screwed down
jack_hole = 9;               // must swallow the aux PLUG's sleeve (~8)
grom_main = 10;              // floor SPARE pass-through (rubber grommet)
// ---- DB9 field ports (left wall) ---------------------------------------
db9_cut_w = 19.7; db9_cut_h = 11.1;  // D-sub 9 panel cutout (rect; file the
                                     //  D corners) — standard DE-9 geometry;
                                     //  part on order = ANMBEST B09WD2V37T
                                     //  (52x34x21.5 cased, bolts incl) —
                                     //  CALIPER-VERIFY flange + screws on
                                     //  arrival before cutting 15
db9_screw = 24.99;                   // jackscrew hole spacing (Ø3.2)
db9_cx = [22, 56];                   // port A (front, etched) / port B (CUT
db9_cz = 14;                         //  = DMX out, every box); center height
strap_w = 5; strap_h = 24;   // velcro-strap slots (back wall, vertical: a
                             //  20mm one-wrap passes horizontally around a
                             //  scaffold leg and through both)
// ---- joinery -----------------------------------------------------------
nseg = 5;                    // corner finger segments over Hw
seg  = Hw / nseg;            // front/back own segments 0,2,4 at the corners
ftab_w = 20;                 // floor mortise tab width
long_cs  = [-32, 0, 32];     // tab centers on the W edges (about midline)
short_cs = [-18, 18];        // tab centers on the D edges
// No fastener holes anywhere — screws go in as needed on the bench; all
// mounting positions live on the ETCH layer (part="*_etch", red in the
// merged SVGs -> set to score/engrave in xTool XCS).

$fn = 40;
eps = 0.01;

// ---- joinery helpers (2D) ---------------------------------------------
module bottom_notches(len, centers)          // cut floor tabs into a wall
  for (c = centers) translate([len/2 + c - ftab_w/2, -eps])
    square([ftab_w, t + eps]);

module corner_notches(len)                   // notch a panel's vertical edges
  for (s = [1, 3], x = [0, len - t])         //  at segments 1 and 3
    translate([x - eps, s * seg]) square([t + 2*eps, seg]);

// ---- etch helpers (2D marks — the RED layer, score/engrave in XCS) -----
module oline(w, h, lw = 0.4)                 // rectangle outline
  difference() { square([w, h], center = true);
                 square([w - 2*lw, h - 2*lw], center = true); }

module oring(d, lw = 0.4)                    // circle outline (hole position)
  difference() { circle(d = d); circle(d = d - 2*lw); }

module cross(s = 4, lw = 0.5) {              // screw-position mark
  square([s, lw], center = true);
  square([lw, s], center = true);
}

module label(txt, size = 3.2)
  text(txt, size = size, halign = "center", valign = "center",
       font = "Liberation Sans:style=Bold");

// ---- panels (2D) -------------------------------------------------------
module panel_front() difference() {
  square([W, Hw]);
  corner_notches(W);
  bottom_notches(W, long_cs);
  translate([W/2 - win_w/2, win_cz - win_h/2]) square([win_w, win_h]); // aperture
  translate([t, slide_z]) square([W - 2*t, slide_w]);  // lid entry mouth
}

module front_etch() {                        // interior face marks
  translate([W/2, win_cz]) oline(panel_w, panel_h);  // acrylic window panel
  for (px = [-wscrew_x, wscrew_x])                   //  sits here; 2 screws
    translate([W/2 + px, win_cz]) cross();
  if (cuddle) {                              // the radar pair, side by side
    cud_t = ld2450_w + 1 + ld2410_w;
    translate([W/2 + (ld2450_w - cud_t)/2, win_cz]) oline(ld2450_w, ld2450_h);
    translate([W/2 + (cud_t - ld2410_w)/2, win_cz]) oline(ld2410_w, ld2410_h);
  } else {
    translate([W/2, win_cz]) oline(ld2410_w, ld2410_h);  // LD2410C footprint
    translate([10, win_cz]) label("SENSOR");
  }
}

module panel_back() difference() {
  square([W, Hw]);                               // SOLID at lid height — the
  corner_notches(W);                             //  lid STOPS against this
  bottom_notches(W, long_cs);                    //  wall's inner face (a
  for (c = [-27, 27])                            //  through-slot here would
    translate([W/2 + c - strap_w/2, (34 - strap_h)/2 + t])  // be open to the
      square([strap_w, strap_h]);                //  outside when closed)
}

module back_etch()
  translate([W/2, 19]) label("VELCRO", 2.8);     // strap between the slots

module panel_side() {          // common left/right: full-D, notched 0/2/4
  difference() {
    square([D, Hw]);
    for (s = [0, 2, 4], x = [0, D - t])
      translate([x - eps, s * seg]) square([t + 2*eps, seg]);
    bottom_notches(D, short_cs);
    // lid channel: open at the front edge (x=0, where the lid enters),
    // ends at the back wall's inner face
    translate([-eps, slide_z]) square([D - t + eps, slide_w]);
  }
}

module panel_left() difference() {               // x runs front->back
  panel_side();
  // port B is a CUT in every box — the room's DMX out (dmx-over-wifi.md):
  // D-sub opening + its two jackscrew holes, breakout bolts straight in
  translate([db9_cx[1] - db9_cut_w/2, db9_cz - db9_cut_h/2])
    square([db9_cut_w, db9_cut_h]);
  for (s = [-1, 1])
    translate([db9_cx[1] + s*db9_screw/2, db9_cz]) circle(d = 3.2);
}

module left_etch() {                             // x runs front->back
  translate([db9_cx[0], db9_cz]) oline(db9_cut_w, db9_cut_h);
  for (s = [-1, 1])                              // jackscrew positions
    translate([db9_cx[0] + s*db9_screw/2, db9_cz]) cross();
  translate([db9_cx[0], db9_cz + 12]) label("DB9 A", 3);
  translate([db9_cx[1], db9_cz + 12]) label("DB9 B DMX", 3);
}                                                // A etched = 7 wired rooms
                                                 //  open it; B cut = DMX out

module panel_right() panel_side();               // identical cut to the left;
                                                 //  ports are etch marks only
module right_etch() {                            // x runs front->back
  translate([t + xiao_cy, t + usb_z]) oline(usb_w, usb_h);   // XIAO USB-C
  translate([t + xiao_cy, t + 11]) label("USB", 2.8);
  translate([t + dac_cy, t + jack_z]) oring(jack_hole);      // the DAC's own
  translate([t + dac_cy, t + 15]) label("AUX", 2.8);         //  jack barrel
}                                                            //  behind this

module panel_floor() difference() {
  union() {
    square([W - 2*t, D - 2*t]);
    for (c = long_cs) {                          // mortise tabs, W edges
      translate([(W - 2*t)/2 + c - ftab_w/2, -t]) square([ftab_w, t + eps]);
      translate([(W - 2*t)/2 + c - ftab_w/2, D - 2*t - eps]) square([ftab_w, t + eps]);
    }
    for (c = short_cs) {                         // mortise tabs, D edges
      translate([-t, (D - 2*t)/2 + c - ftab_w/2]) square([t + eps, ftab_w]);
      translate([W - 2*t - eps, (D - 2*t)/2 + c - ftab_w/2]) square([t + eps, ftab_w]);
    }
  }
}

module floor_etch() {                            // component-side marks
  translate([16, 14]) oring(grom_main);          // wildcard pass-through —
  translate([16, 25]) label("SPARE", 3);         //  field IO rides the DB9s
  translate([W - 2*t - dac_l/2, dac_cy]) oline(dac_l, dac_w);   // PCM5102A —
  translate([W - 2*t - dac_l/2, dac_cy + 13]) label("DAC");     //  jack edge
                                                 //  butts the right wall so
                                                 //  the barrel meets AUX
  translate([W - 2*t - xiao_w/2, xiao_cy]) oline(xiao_w, xiao_l);  // XIAO
  translate([W - 2*t - xiao_w/2, xiao_cy]) label("XIAO", 3);       //  (VHB),
}                                                //  USB edge to the wall too

module panel_lid() difference() {
  square([lid_w, lid_d]);
  // front corner notches: the tongues start behind the front wall, so the
  // central width passes through the front mouth while the tongues enter
  // the side channels' open ends
  for (x = [-eps, lid_w - 2.4])
    translate([x, -eps]) square([2.4 + eps, t + 0.2 + eps]);
  translate([lid_w/2, 0]) circle(d = lid_notch); // finger pull
}

module panel_window() difference() {             // cut this one in acrylic
  translate([-panel_w/2, -panel_h/2]) square([panel_w, panel_h]);
  // OPTIONAL ToF aperture — uncomment for Entrance/Exit/Guy Line/VMM
  // (940nm won't pass plain acrylic; radar rooms keep the panel solid)
  // square([16, 16], center = true);
}

module window_etch() {
  for (px = [-wscrew_x, wscrew_x]) translate([px, 0]) cross();  // M2 screws
  if (!cuddle) oline(16, 16);                    // ToF aperture, if this room
}

// ---- layouts -----------------------------------------------------------
// PLY job: the six wall panels nested with 6mm gaps. sheet() = cut layer,
// sheet_etch() = the same placements' marks — shared coordinates, so the
// merged SVG aligns. The ACRYLIC job is the separate window part
// (part="window"/"window_etch" -> window-acrylic.svg).
module sheet() {
  panel_front();
  translate([0, Hw + 6])       panel_back();
  translate([t, 2*Hw + 12 + t]) panel_floor();
  translate([W + 12, 0])   panel_left();
  translate([W + 12, Hw + 6]) panel_right();
  translate([W + 12, 2*Hw + 12]) panel_lid();
}

module sheet_etch() {
  front_etch();
  translate([0, Hw + 6])       back_etch();
  translate([t, 2*Hw + 12 + t]) floor_etch();
  translate([W + 12, 0])   left_etch();
  translate([W + 12, Hw + 6]) right_etch();
}

module assembly() {
  color("BurlyWood") translate([t, t, 0]) linear_extrude(t) panel_floor();
  color("Peru")      translate([0, t, 0]) rotate([90, 0, 0]) linear_extrude(t) panel_front();
  color("Peru")      translate([0, D, 0]) rotate([90, 0, 0]) linear_extrude(t) panel_back();
  color("Sienna")    rotate([90, 0, 90]) linear_extrude(t) panel_left();
  color("Sienna")    translate([W - t, 0, 0]) rotate([90, 0, 90]) linear_extrude(t) panel_right();
  color("Tan", 0.85)                              // lid shown half-slid-out
    translate([(W - lid_w)/2, -22, slide_z]) linear_extrude(t) panel_lid();
  color("LightBlue", 0.6)
    translate([W/2, t + 4 + eps, win_cz]) rotate([90, 0, 0]) linear_extrude(acrylic_t) panel_window();
}

// ---- part selection ----------------------------------------------------
if (part == "front")  panel_front();
else if (part == "back")   panel_back();
else if (part == "left")   panel_left();
else if (part == "right")  panel_right();
else if (part == "floor")  panel_floor();
else if (part == "lid")    panel_lid();
else if (part == "window") panel_window();
else if (part == "sheet")  sheet();
else if (part == "front_etch")  front_etch();
else if (part == "back_etch")   back_etch();
else if (part == "left_etch")   left_etch();
else if (part == "right_etch")  right_etch();
else if (part == "floor_etch")  floor_etch();
else if (part == "window_etch") window_etch();
else if (part == "sheet_etch")  sheet_etch();
else assembly();
