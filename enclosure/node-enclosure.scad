// LoHP maze — universal room-node enclosure, LASER-CUT edition
// ============================================================
// ONE design for all 15 room nodes, cut on the xTool from 3mm ply (walls)
// + 3mm acrylic (window panel). Six finger-jointed panels GLUE together
// (floor mortises through the wall bottoms, corner fingers interlock);
// the LID is the service hatch — no glue, 4x M3 screws into T-slot nuts.
//
// Holds the standard node build: XIAO ESP32-S3 (VHB tape) + PCM5102A DAC
// (M2 screws through the floor) + the room's ranging sensor(s) zip-tied
// against the window (LD2410C, VL53L1X, Cuddle's 2410+2450 side by side).
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
//   back wall: hose-clamp strap slots + two mounting ears with 5mm holes.
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
Hw = 37;         // wall height; lid sits on top -> outer height Hw+t
                 // interior: 104 x 72 x 34

// ---- features ----------------------------------------------------------
win_w = 56;  win_h = 24;  win_cz = t + 17;   // aperture, center height
panel_w = 64; panel_h = 32;                  // acrylic window panel
gx16_d = 16.2;  gx12_d = 12.2;               // aviation connector holes
usb_w = 10; usb_h = 4;  jack_d = 6.5;  ant_d = 6.5;
strap_w = 22; strap_h = 4;                   // hose-clamp slots (back)
ear_w = 14; ear_h = 16; ear_hole = 5;        // mounting ears (back)
dac_hx = 25.4; dac_hy = 15.3;                // PCM5102A hole spacing — VERIFY
dac_cx = 84;  dac_cy = 51;                   //  on the real board before
                                             //  cutting all 15!
// ---- joinery -----------------------------------------------------------
nseg = 5;                    // corner finger segments over Hw
seg  = Hw / nseg;            // front/back own segments 0,2,4 at the corners
ftab_w = 20;                 // floor mortise tab width
long_cs  = [-32, 0, 32];     // tab centers on the W edges (about midline)
short_cs = [-18, 18];        // tab centers on the D edges
tslot_cs = [-38, 38];        // lid T-slot centers (about midline)
m3 = 3.4; m3_nut_w = 5.7; m3_nut_t = 2.7;

$fn = 40;
eps = 0.01;

// ---- joinery helpers (2D) ---------------------------------------------
module bottom_notches(len, centers)          // cut floor tabs into a wall
  for (c = centers) translate([len/2 + c - ftab_w/2, -eps])
    square([ftab_w, t + eps]);

module corner_notches(len)                   // notch a panel's vertical edges
  for (s = [1, 3], x = [0, len - t])         //  at segments 1 and 3
    translate([x - eps, s * seg]) square([t + 2*eps, seg]);

module tslot(cx, h)                          // lid screw T-slot from top edge
  translate([cx, 0]) {
    translate([-m3/2, h - 14]) square([m3, 14 + eps]);
    translate([-m3_nut_w/2, h - 9 - m3_nut_t]) square([m3_nut_w, m3_nut_t]);
  }

// ---- panels (2D) -------------------------------------------------------
module panel_front() difference() {
  square([W, Hw]);
  corner_notches(W);
  bottom_notches(W, long_cs);
  for (c = tslot_cs) tslot(W/2 + c, Hw);
  translate([W/2 - win_w/2, win_cz - win_h/2]) square([win_w, win_h]); // aperture
  for (px = [-30, 30], pz = [-14, 14])                                // window screws
    translate([W/2 + px, win_cz + pz]) circle(d = 2.2);               // M2.5 self-tap
  for (px = [-10, 10], pz = [7, 33])                                  // sensor zip holes
    translate([W/2 + px, pz]) circle(d = 3.4);
}

module panel_back() difference() {
  union() {
    square([W, Hw]);
    for (px = [-ear_w, W])                       // mounting ears, 5mm holes
      translate([px, 14]) square([ear_w, ear_h]);
  }
  corner_notches(W);
  bottom_notches(W, long_cs);
  for (c = tslot_cs) tslot(W/2 + c, Hw);
  for (px = [-ear_w/2, W + ear_w/2])
    translate([px, 14 + ear_h/2]) circle(d = ear_hole);
  for (c = [-27, 27])                            // hose-clamp strap slots
    translate([W/2 + c - strap_w/2, Hw - 9]) square([strap_w, strap_h]);
}

module panel_side() {          // common left/right: full-D, notched 0/2/4
  difference() {
    square([D, Hw]);
    for (s = [0, 2, 4], x = [0, D - t])
      translate([x - eps, s * seg]) square([t + 2*eps, seg]);
    bottom_notches(D, short_cs);
  }
}

module panel_left() panel_side();

module panel_right() difference() {
  panel_side();                                  // x runs front->back
  translate([16 - usb_w/2, t + 2]) square([usb_w, usb_h]);   // XIAO USB-C
  translate([48, t + 11]) circle(d = jack_d);                // 3.5mm line-out
  translate([62, Hw - 8]) circle(d = ant_d);                 // antenna
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
  translate([16, 14]) circle(d = gx16_d);        // connector row (faces down)
  for (i = [0:2]) translate([38 + i*18, 14]) circle(d = gx12_d);
  for (i = [0:4]) translate([58 + i*8, 38]) square([3, 24]);  // vents
  for (px = [-dac_hx/2, dac_hx/2], py = [-dac_hy/2, dac_hy/2])
    translate([dac_cx + px, dac_cy + py]) circle(d = 2.4);    // DAC M2
}

module panel_lid() difference() {
  square([W, D]);
  for (c = tslot_cs, y = [t/2, D - t/2])
    translate([W/2 + c, y]) circle(d = m3);
}

module panel_window() difference() {             // cut this one in acrylic
  translate([-panel_w/2, -panel_h/2]) square([panel_w, panel_h]);
  for (px = [-30, 30], pz = [-14, 14]) translate([px, pz]) circle(d = 2.8);
  // OPTIONAL ToF aperture — uncomment for Entrance/Exit/Guy Line/VMM
  // (940nm won't pass plain acrylic; radar rooms keep the panel solid)
  // square([16, 16], center = true);
}

// ---- layouts -----------------------------------------------------------
module sheet() {                                 // one-bed nesting, 6mm gaps
  translate([ear_w, 0])            panel_front();
  translate([ear_w, Hw + 6])       panel_back();
  translate([ear_w + t, 2*Hw + 12 + t]) panel_floor();
  translate([W + ear_w + 12, 0])   panel_left();
  translate([W + ear_w + 12, Hw + 6]) panel_right();
  translate([W + ear_w + 12, 2*Hw + 12]) panel_lid();
  translate([W + ear_w + 12 + panel_w/2, 2*Hw + D + 18 + panel_h/2]) panel_window();
}

module assembly() {
  color("BurlyWood") translate([t, t, 0]) linear_extrude(t) panel_floor();
  color("Peru")      translate([0, t, 0]) rotate([90, 0, 0]) linear_extrude(t) panel_front();
  color("Peru")      translate([0, D, 0]) rotate([90, 0, 0]) linear_extrude(t) panel_back();
  color("Sienna")    rotate([90, 0, 90]) linear_extrude(t) panel_left();
  color("Sienna")    translate([W - t, 0, 0]) rotate([90, 0, 90]) linear_extrude(t) panel_right();
  color("Tan", 0.85) translate([0, 0, Hw + 8]) linear_extrude(t) panel_lid();  // lifted
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
else assembly();
