// LoHP maze — universal room-node enclosure (ONE design fits every room)
// =======================================================================
// Holds the standard node build: XIAO ESP32-S3 + PCM5102A DAC + the room's
// ranging sensor(s) (LD2410C radar, VL53L1X ToF, Cuddle adds LD2450 beside
// the 2410). All field IO leaves through panel connectors — nothing is
// hard-wired through a wall:
//
//   floor (downward, dust/rain-smart):
//     1x GX16-8 aviation  -> up to 6 arcade buttons + common (Gate uses all 6;
//                            Cuddle hex station 4; Bike 4; DPH 5; others spare)
//     3x GX12-2 aviation  -> Porto piezos x3, single buttons, spares
//   right wall:
//     USB-C slot          -> XIAO power (bank/cube lead)
//     6.5mm jack hole     -> DAC 3.5mm line-out to the Creative Pebble
//     6.5mm antenna hole  -> XIAO external antenna pigtail
//   front wall:
//     sensor window       -> open aperture + recessed ledge for a laser-cut
//                            panel (acrylic for radar; ToF needs an open hole
//                            or IR-pass material — 940nm won't pass plain ply
//                            or most acrylic). Panel outline export below.
//   back wall:
//     2 mounting ears + 2 strap slots (SAE#24 hose clamp to scaffold tube —
//     the existing mounting standard)
//
// Render parts:
//   openscad -D 'part="box"'   -o box.stl   node-enclosure.scad
//   openscad -D 'part="lid"'   -o lid.stl   node-enclosure.scad
//   openscad -D 'part="panel"' -o panel.dxf node-enclosure.scad   (2D cut file)
//   openscad -D 'part="all"'   ...          assembly preview
//
// Print: PETG/ASA (playa heat), 0.2mm layers, 3-4 walls, no supports needed
// with the window face up... print box open-face-up as modeled.

part = "all";          // "box" | "lid" | "panel" | "all"

// ---- envelope ----------------------------------------------------------
wall   = 2.4;          // shell wall
floor_t= 2.4;          // floor thickness
lid_t  = 2.4;          // lid thickness
inner_w = 104;         // X — front/back wall length
inner_d = 72;          // Y — side wall length
inner_h = 34;          // Z — interior height
rf     = 3;            // outer corner fillet radius

// ---- sensor window (front wall, +Y face) -------------------------------
win_w  = 56;           // aperture width  (LD2410C alone, 2410+2450 side by
win_h  = 24;           // aperture height  side, or a ToF — all fit)
win_ledge = 4;         // recess border around aperture that seats the panel
panel_t   = 3;         // cut-panel thickness the recess accepts (acrylic)
win_z     = 17;        // aperture center height above interior floor

// ---- connectors --------------------------------------------------------
gx16_d = 16.2;         // GX16 panel hole
gx12_d = 12.2;         // GX12 panel hole
conn_row_y = 14;       // connector row distance from front interior wall
usb_w = 10;  usb_h = 4;      // USB-C slot
jack_d = 6.5;                // 3.5mm jack clearance hole
ant_d  = 6.5;                // antenna pigtail hole

// ---- boards ------------------------------------------------------------
xiao_w = 21.4; xiao_d = 18.2;   // XIAO cradle pocket (friction fit + tape)
dac_w  = 30.5; dac_d  = 21.0;   // PCM5102A purple board, 4x M2 posts
post_d = 5;  post_hole = 1.8;   // self-tap M2 pilot
standoff_h = 5;

// ---- lid / mounting ----------------------------------------------------
lid_screw_d = 2.8;     // M3 self-tap into corner posts
ear_hole = 5;          // mounting ear screw holes
strap_w  = 22; strap_h = 4;     // hose-clamp strap slots (back wall)

$fn = 48;
eps = 0.01;

ow = inner_w + 2*wall;          // outer dims
od = inner_d + 2*wall;
oh = inner_h + floor_t;         // box body height (open top; lid adds lid_t)

// ---- helpers -----------------------------------------------------------
module rbox(x, y, z, r) {       // rounded-corner slab (rounded in XY)
  hull() for (px = [r, x - r], py = [r, y - r])
    translate([px, py]) cylinder(h = z, r = r);
}

post_in = wall + 3.2;   // post centers 3.2mm inside the walls (0.8mm embed)

module corner_posts(hole_d, h) {
  for (px = [post_in, ow - post_in], py = [post_in, od - post_in])
    translate([px, py])
      difference() {
        cylinder(h = h, d = 8);
        translate([0, 0, h - 12]) cylinder(h = 12 + eps, d = hole_d);
      }
}

// ---- the box -----------------------------------------------------------
module box() {
  difference() {
    union() {
      // shell
      difference() {
        rbox(ow, od, oh, rf);
        translate([wall, wall, floor_t]) cube([inner_w, inner_d, inner_h + eps]);
      }
      // lid screw posts
      corner_posts(lid_screw_d, oh);
      // window panel recess frame is part of the wall (made by the two-depth
      // cut below), nothing to add
      // DAC standoffs (right-rear area)
      for (px = [0, dac_w - 4], py = [0, dac_d - 4])
        translate([wall + 66 + px + 2, wall + 40 + py + 2, floor_t - eps])
          difference() {
            cylinder(h = standoff_h, d = post_d);
            cylinder(h = standoff_h + eps, d = post_hole);
          }
      // XIAO cradle (right-front, USB toward right wall)
      translate([wall + inner_w - xiao_w - 1.5, wall + 12, floor_t - eps])
        difference() {
          cube([xiao_w + 3, xiao_d + 3, 4]);
          translate([1.5, 1.5, 1.2]) cube([xiao_w, xiao_d, 4]);
          translate([1.5 + 2, -eps, -eps]) cube([xiao_w - 4, xiao_d + 3 + 2*eps, 6]); // wire/USB clear
        }
      // sensor shelf behind the window: ledge + zip-tie slots
      translate([wall + (inner_w - win_w)/2 - 6, od - wall - 8, floor_t - eps])
        difference() {
          cube([win_w + 12, 8, win_z - win_h/2 - floor_t]);
          for (sx = [8, (win_w + 12)/2, win_w + 4])
            translate([sx, -eps, 3]) cube([3, 8 + 2*eps, 4]);   // zip slots
        }
      // mounting ears: vertical tabs flush with the BACK outer face (y=0),
      // so the box screws flat against wood/plate; back straps do scaffold tube
      for (px = [-10, ow])
        translate([px, 0, floor_t + 6])
          difference() {
            cube([10, 6, 16]);
            translate([5, -eps, 8]) rotate([-90, 0, 0]) cylinder(h = 7, d = ear_hole);
          }
    }

    // ---- window: aperture + panel recess (front = +Y outer face) ----
    translate([(ow - win_w)/2, od - wall - eps, floor_t + win_z - win_h/2])
      cube([win_w, wall + 2*eps, win_h]);                        // aperture
    translate([(ow - (win_w + 2*win_ledge))/2, od - panel_t,
               floor_t + win_z - win_h/2 - win_ledge])
      cube([win_w + 2*win_ledge, panel_t + eps, win_h + 2*win_ledge]); // recess
    // panel screw pilots (into the recess floor, M2.5 self-tap)
    for (px = [-1, 1], pz = [-1, 1])
      translate([ow/2 + px*(win_w/2 + win_ledge/2),
                 od - panel_t - 4, floor_t + win_z + pz*(win_h/2 + win_ledge/2)])
        rotate([-90, 0, 0]) cylinder(h = panel_t + 4 + eps, d = 2.2);

    // ---- floor connector row (downward): GX16 + 3x GX12 ----
    translate([wall + 16, wall + conn_row_y, -eps]) cylinder(h = floor_t + 2*eps, d = gx16_d);
    for (i = [0:2])
      translate([wall + 38 + i*18, wall + conn_row_y, -eps])
        cylinder(h = floor_t + 2*eps, d = gx12_d);

    // ---- right wall: USB-C slot, 3.5mm jack, antenna ----
    translate([ow - wall - eps, wall + 12 + 1.5 + (xiao_d + 3)/2 - usb_w/2, floor_t + 2])
      cube([wall + 2*eps, usb_w, usb_h]);                        // USB-C at cradle
    translate([ow - wall - eps, wall + 52, floor_t + 8])
      rotate([0, 90, 0]) cylinder(h = wall + 2*eps, d = jack_d); // 3.5mm line-out
    translate([ow - wall - eps, wall + 64, floor_t + inner_h - 6])
      rotate([0, 90, 0]) cylinder(h = wall + 2*eps, d = ant_d);  // antenna

    // ---- back wall: hose-clamp strap slots ----
    for (px = [ow*0.28, ow*0.72])
      translate([px - strap_w/2, -eps, floor_t + inner_h - strap_h - 3])
        cube([strap_w, wall + 2*eps, strap_h]);

    // ---- floor vents (right half, away from connectors) ----
    for (i = [0:4])
      translate([wall + 62 + i*7, wall + 26, -eps]) cube([3, 24, floor_t + 2*eps]);
  }
}

// ---- the lid -----------------------------------------------------------
module lid() {
  difference() {
    union() {
      rbox(ow, od, lid_t, rf);
      translate([wall + 0.3, wall + 0.3, lid_t - eps])
        difference() {                                   // registration lip
          rbox(inner_w - 0.6, inner_d - 0.6, 3, 2);
          translate([2, 2, -eps]) rbox(inner_w - 4.6, inner_d - 4.6, 3.2, 2);
        }
    }
    for (px = [post_in, ow - post_in], py = [post_in, od - post_in])
      translate([px, py, -eps]) {
        cylinder(h = lid_t + 4, d = 3.4);
        cylinder(h = 2, d2 = 3.4, d1 = 6.4);             // countersink
      }
  }
}

// ---- laser-cut window panel outline (2D) -------------------------------
// Cut per room: 3mm acrylic for radar rooms (LD2410C/LD2450 see through it);
// ToF rooms cut the marked aperture through the panel (940nm needs open air
// or IR-pass material). Export: -D 'part="panel"' -o panel.dxf
module panel_2d() {
  difference() {
    square([win_w + 2*win_ledge - 0.6, win_h + 2*win_ledge - 0.6]);  // fits recess
    for (px = [-1, 1], py = [-1, 1])
      translate([(win_w + 2*win_ledge - 0.6)/2 + px*(win_w/2 + win_ledge/2),
                 (win_h + 2*win_ledge - 0.6)/2 + py*(win_h/2 + win_ledge/2)])
        circle(d = 2.8);                                 // M2.5 clearance
    // OPTIONAL ToF aperture — uncomment for the 4 ToF rooms
    // translate([(win_w + 2*win_ledge)/2 - 8, (win_h + 2*win_ledge)/2 - 8]) square([16, 16]);
  }
}

// ---- part selection ----------------------------------------------------
if (part == "box") box();
else if (part == "lid") lid();
else if (part == "panel") panel_2d();
else {                                                    // assembly preview
  box();
  translate([0, 0, oh + 12]) lid();
  color("lightblue", 0.5)
    translate([(ow - (win_w + 2*win_ledge) + 0.6)/2, od - panel_t + 0.4,
               floor_t + win_z - win_h/2 - win_ledge + 0.3])
      rotate([90, 0, 0]) linear_extrude(panel_t - 0.5) panel_2d();
}
