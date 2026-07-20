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
//   back wall: two vertical velcro-strap slots (CUT — the strap threads
//     through and wraps the scaffold leg) + two mounting ears.
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
strap_w = 5; strap_h = 24;                   // velcro-strap slots (back wall,
                                             //  vertical: a 20mm one-wrap
                                             //  passes horizontally around a
                                             //  scaffold leg and through both)
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
  for (px = [-10, 10], pz = [7, 33])                     // sensor zip-tie holes
    translate([W/2 + px, pz]) circle(d = 3.4);           //  (functional, not screws)
}

module front_etch() {                        // interior face marks
  translate([W/2, win_cz]) oline(64, 32);    // acrylic window panel sits here
  for (px = [-30, 30], pz = [-14, 14])       // its screw positions
    translate([W/2 + px, win_cz + pz]) cross();
  translate([W/2, win_cz]) oline(22, 16);    // LD2410C footprint in the aperture
  translate([10, win_cz]) label("SENSOR");
}

module panel_back() difference() {
  union() {
    square([W, Hw]);
    for (px = [-ear_w, W])                       // mounting ears
      translate([px, 14]) square([ear_w, ear_h]);
  }
  corner_notches(W);
  bottom_notches(W, long_cs);
  for (c = [-27, 27])                            // velcro-strap slots (CUT):
    translate([W/2 + c - strap_w/2, (Hw - strap_h)/2])  // strap threads both,
      square([strap_w, strap_h]);                //  wraps the scaffold leg
}

module back_etch() {
  for (px = [-ear_w/2, W + ear_w/2])             // ear screw positions
    translate([px, 14 + ear_h/2]) cross(5);
  translate([W/2, 19]) label("VELCRO", 2.8);     // strap between the slots
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

module panel_right() panel_side();               // identical cut to the left;
                                                 //  ports are etch marks only
module right_etch() {                            // x runs front->back
  translate([16, t + 2 + usb_h/2]) oline(usb_w, usb_h);      // XIAO USB-C
  translate([16, t + 10]) label("USB", 2.8);
  translate([48, t + 11]) oring(jack_d);                     // 3.5mm line-out
  translate([48, t + 19]) label("AUX", 2.8);
  translate([62, Hw - 8]) oring(ant_d);                      // antenna
  translate([62, Hw - 16]) label("ANT", 2.8);
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
  for (i = [0:2]) translate([38 + i*18, 14]) oring(gx12_d);
  translate([16, 25]) label("GX16");
  translate([56, 25]) label("GX12 x3");
  translate([dac_cx, dac_cy]) oline(30.5, 21);   // PCM5102A footprint
  for (px = [-dac_hx/2, dac_hx/2], py = [-dac_hy/2, dac_hy/2])
    translate([dac_cx + px, dac_cy + py]) cross(3.5);  // its screw corners
  translate([dac_cx, dac_cy + 15]) label("DAC");
  translate([90, 21]) oline(21.4, 17.8);         // XIAO footprint (VHB), USB
  translate([90, 21]) label("XIAO", 3);          //  toward the right wall
}

module panel_lid() square([W, D]);

module lid_etch()                                // screw down into the wall
  for (x = [12, W - 12], y = [t/2, D - t/2])     //  top edges as needed
    translate([x, y]) cross(3);                  // stays inside the outline

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
// One-bed nesting, 6mm gaps. sheet() = cut layer, sheet_etch() = the same
// placements' marks; they share coordinates so the merged SVG aligns.
module sheet() {
  translate([ear_w, 0])            panel_front();
  translate([ear_w, Hw + 6])       panel_back();
  translate([ear_w + t, 2*Hw + 12 + t]) panel_floor();
  translate([W + ear_w + 12, 0])   panel_left();
  translate([W + ear_w + 12, Hw + 6]) panel_right();
  translate([W + ear_w + 12, 2*Hw + 12]) panel_lid();
  translate([W + ear_w + 12 + panel_w/2, 2*Hw + D + 18 + panel_h/2]) panel_window();
}

module sheet_etch() {
  translate([ear_w, 0])            front_etch();
  translate([ear_w, Hw + 6])       back_etch();
  translate([ear_w + t, 2*Hw + 12 + t]) floor_etch();
  translate([W + ear_w + 12, Hw + 6]) right_etch();
  translate([W + ear_w + 12, 2*Hw + 12]) lid_etch();
  translate([W + ear_w + 12 + panel_w/2, 2*Hw + D + 18 + panel_h/2]) window_etch();
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
else if (part == "front_etch")  front_etch();
else if (part == "back_etch")   back_etch();
else if (part == "right_etch")  right_etch();
else if (part == "floor_etch")  floor_etch();
else if (part == "lid_etch")    lid_etch();
else if (part == "window_etch") window_etch();
else if (part == "sheet_etch")  sheet_etch();
else assembly();
