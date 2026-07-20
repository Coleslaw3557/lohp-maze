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
// 2410+2450 side by side) — all fixed at their ETCHED footprint marks
// however works on the bench (VHB/screws/glue); nothing is pre-drilled.
//
// IO — everything leaves through a panel connector:
//   floor (faces DOWN when mounted — dust/rain smart):
//     1x GX16-8  -> up to 6 arcade buttons + common
//     3x GX12-2  -> piezos / single buttons / spares
//   right wall: USB-C slot (XIAO power), 6.5mm jack hole (3.5mm line-out
//     to the Pebble), 6.5mm antenna hole
//   front wall: 56x24 sensor aperture; the acrylic window panel screws
//     over it (M2.5). Radar sees through plain acrylic; the 4 ToF rooms
//     cut the marked aperture through the panel (940nm won't pass acrylic).
//   back wall: two vertical velcro-strap slots (CUT — the strap threads
//     through and wraps the scaffold leg).
//
// Export (SVG for xTool; kerf compensate in XCS if you want tight joints):
//   for p in front back left right floor lid window sheet; do
//     openscad -D "part=\"$p\"" -o panel-$p.svg node-enclosure.scad; done
//   part="3d" is the glued-up assembly preview.

part = "3d";     // front|back|left|right|floor|lid|window|sheet|3d

// ---- stock -------------------------------------------------------------
t  = 3;          // material thickness (ply/acrylic)
kerf_note = "cut outlines are exact; add kerf offset in xTool XCS";

// ---- box (outer) -------------------------------------------------------
W  = 110;        // width  (front/back length)
D  = 78;         // depth  (left/right length)
Hw = 44;         // wall height = outer height. Interior stays 104 x 72 x 34;
                 // above it: 3.4mm lid slide channel + 3.2mm cap.

// ---- sliding lid -------------------------------------------------------
slide_z = 37;            // channel bottom (floor_t + 34 interior)
slide_w = 3.4;           // channel width (t + play)
lid_w   = W - 2*t + 4.4; // side tongues ride 2.2mm into each side channel
lid_d   = D - t + 2.4;   // front edge flush outside; back edge 2.4 into
                         //  the back channel
lid_notch = 14;          // finger pull, front edge

// ---- features ----------------------------------------------------------
win_w = 56;  win_h = 24;  win_cz = t + 17;   // aperture, center height
panel_w = 64; panel_h = 32;                  // acrylic window panel
gx16_d = 16.2;  gx12_d = 12.2;               // aviation connector holes
usb_w = 10; usb_h = 4;  jack_d = 6.5;  ant_d = 6.5;
strap_w = 5; strap_h = 24;                   // velcro-strap slots (back wall,
                                             //  vertical: a 20mm one-wrap
                                             //  passes horizontally around a
                                             //  scaffold leg and through both)
dac_hx = 25.4; dac_hy = 15.3;                // PCM5102A hole spacing — VERIFY
dac_cx = 84;  dac_cy = 51;                   //  on the real board before
                                             //  cutting all 15!
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
  translate([W/2, win_cz]) oline(64, 32);    // acrylic window panel sits here
  for (px = [-30, 30], pz = [-14, 14])       // its screw positions
    translate([W/2 + px, win_cz + pz]) cross();
  translate([W/2, win_cz]) oline(22, 16);    // LD2410C footprint in the aperture
  translate([10, win_cz]) label("SENSOR");
}

module panel_back() difference() {
  square([W, Hw]);
  corner_notches(W);
  bottom_notches(W, long_cs);
  translate([t, slide_z]) square([W - 2*t, slide_w]);  // lid channel (back)
  for (c = [-27, 27])                            // velcro-strap slots (CUT):
    translate([W/2 + c - strap_w/2, (34 - strap_h)/2 + t])  // strap threads
      square([strap_w, strap_h]);                //  both, wraps the leg
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

module panel_left() panel_side();

module panel_right() panel_side();               // identical cut to the left;
                                                 //  ports are etch marks only
module right_etch() {                            // x runs front->back
  translate([16, t + 2 + usb_h/2]) oline(usb_w, usb_h);      // XIAO USB-C
  translate([16, t + 10]) label("USB", 2.8);
  translate([48, t + 11]) oring(jack_d);                     // 3.5mm line-out
  translate([48, t + 19]) label("AUX", 2.8);
  translate([62, 30]) oring(ant_d);                          // antenna (below
  translate([62, 22]) label("ANT", 2.8);                     //  the lid channel)
}

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
  translate([16, 14]) oring(gx16_d);             // connector positions
  for (i = [0:2]) translate([38 + i*16, 14]) oring(gx12_d);  // 16mm pitch:
  translate([16, 25]) label("GX16");             //  GX12 nuts (15mm) clear
  translate([54, 25]) label("GX12 x3");          //  each other AND the XIAO
  translate([dac_cx, dac_cy]) oline(30.5, 21);   // PCM5102A footprint
  for (px = [-dac_hx/2, dac_hx/2], py = [-dac_hy/2, dac_hy/2])
    translate([dac_cx + px, dac_cy + py]) cross(3.5);  // its screw corners
  translate([dac_cx, dac_cy + 15]) label("DAC");
  translate([91, 13]) oline(21.4, 17.8);         // XIAO footprint (VHB): USB
  translate([91, 13]) label("XIAO", 3);          //  faces the right-wall USB
}                                                //  mark (x2d 16 -> y 13)

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
  for (px = [-30, 30], pz = [-14, 14]) translate([px, pz]) cross();  // screws
  oline(16, 16);                                 // ToF aperture, if this room
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
    translate([W/2, t + 4 + eps, win_cz]) rotate([90, 0, 0]) linear_extrude(t) panel_window();
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
else if (part == "right_etch")  right_etch();
else if (part == "floor_etch")  floor_etch();
else if (part == "window_etch") window_etch();
else if (part == "sheet_etch")  sheet_etch();
else assembly();
