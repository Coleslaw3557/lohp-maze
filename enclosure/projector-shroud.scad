// LoHP maze — Cuddle projector SHROUD, laser-cut edition
// (2026-08-11 VIVO-mount rev; supersedes the 2026-08-01 beam/cradle arm)
// (2026-08-11b: CLOSED bottom w/ lens window + cable bay — Tim: open
//  bottom defeats the dust purpose; HDMI/power/serial need to plug in)
// ===========================================================================
// The LS625X hangs NOSE-DOWN at the hex NE corner throwing SW down the deck
// diagonal (optics + calibration in wiring-guides/cuddle-projector-mount.md).
//
// MOUNTING (2026-08-11): COTS VIVO MOUNT-VP01B universal projector mount
// (listing + vivo-us.com reviewed 2026-08-11): all-steel, 30 lb / 13.6 kg
// rated, +-15 deg tilt, +-15 deg swivel, 360 deg rotation, FIXED 6 in /
// 152 mm profile, spider feet fit boss spreads 5.25-12.5 in / 133-318 mm
// (LS625X 223 x 150 pattern = 268.8 diagonal — fits). Plate hose-clamped to
// the paired 43 mm corner legs on ~40 mm standoff blocks (see doc); the
// spider feet land OUTSIDE the REAR WALL and their M4 screws pass through
// the ply into the chassis bosses — wall SANDWICHED, shroud hangs on those
// four screws. 360 deg collar rolls the unit nose-down; tilt/swivel = fine
// trim. Nose-down the boss face is vertical facing the corner ("the bottom
// of the projector" IS the rear wall).
//
// ORIENTATION FACTS the box lives by (nose-down; airflow BENCH-MEASURED
// by Tim 2026-08-11):
//   lens/front face   -> DOWN  (bottom panel: EXACT 117 x 120 lens
//                               aperture — the ONLY front opening)
//   boss/bottom face  -> NE corner (rear wall = mount wall)
//   connector/rear    -> UP    (cable bay above the body; guide p.5 puts
//                               the connector panel on the chassis rear)
//   top face          -> SW    (front wall, throw side)
//   intake grille     -> flank, 9 x 3.5 in, viewer-LEFT facing the lens
//                       head-on = side R here, plenum side
//   exhaust grille    -> the OTHER flank (the one next to the off-center
//                       lens), same 9 x 3.5 = side L here, open vent
//
// CABLE BAY + THE ROOF TRADE: the old cavity left 4.5 mm over the body —
// no plug fits. cable_bay adds headroom for right-angle plugs BUT the
// shroud top is pinned ~6 mm under the 1760 soffit, so every mm of bay
// LOWERS the projection window 1 mm and costs ~2 mm of image width
// (TR 0.49). 35 is a right-angle-adapter BUDGET, not a measurement —
// bench-measure the plugged stack (HDMI + power + DB9, right-angle where
// possible) above the chassis rear face and shrink cable_bay to that.
// Cables gather to the 55 x 30 slot high in the rear wall (Tim covers it).
//
// BOTTOM = screw-on WINDOW PANEL (dust floor): flat plate under the rim on
// a glued 2-ply perimeter ring; 6 screws up into the ring. ONE opening —
// the lens aperture, BENCH-MEASURED by Tim 2026-08-11: EXACT 117 across x
// 120 high, starting 56 from the chassis edge on the side-L (exhaust)
// side. Vertical position on the 147.7 face assumed CENTERED — lay the
// unit on the panel and verify against the etched ruler before glue-up.
//
// Assemblies (3mm ply, t = 2.9 caliper-gated node-box stock; ply is
// STRUCTURAL — glue every joint, Titebond III; the box hangs on the wall):
//
//  SHROUD — 5-sided finger-jointed sleeve + screw-on bottom window panel:
//    vent windows both sides (filter cloth stapled OUTSIDE, staple ring
//    etched), rear wall = MOUNT WALL (etched 10 mm drill grid + nominal
//    223 x 150 boss rectangle — drill the real pattern FROM THE UNIT on
//    the bench) + cable slot. Top rides ~6 mm under the roof slab; service
//    = unscrew the spider feet or slack the hose clamps.
//
//  FILTERED INTAKE PLENUM — right-side bolt/gasket-on cartridge for the
//    on-hand 9.5 x 9.5 x 3/4 MERV filter and a 140 mm ARCTIC P14 Pro fan.
//    LS625X airflow with lens facing forward: RIGHT = intake, LEFT =
//    exhaust. Stack: room air -> MERV -> P14 -> shroud right vent ->
//    projector intake. Leave left shroud vent open exhaust. NOTE the
//    plenum hangs asymmetric off the right side — torque the VIVO's
//    rotation collar properly or the rig rolls toward the plenum.
//
// Field notes (also etched):
//  - VIVO's included M4s are sized for feet directly on bosses; through
//    2.9 ply they need ~3 mm more — verify boss depth, do NOT bottom out.
//  - Center the LENS on the string line, not the chassis (lens sits
//    off-center in the 383.7 width).
//  - Safety lanyard: from the VIVO pole/plate around the top rail.
//
// Export: python3 export-shroud.py   (black = CUT, red = SCORE/etch in XCS)

part = "3d";     // 3d | sheet | sheet_etch | front|rear|side|top|bottom|
                 //   ring_long|ring_short|
                 //   plenum_back|plenum_front|plenum_side|plenum_clip

t = 2.9;         // ply thickness, caliper-gated
finger = 18;     // finger/socket pitch — literal everywhere so mates align

// ---- chassis + clearances (LS625X official, guide p.56: 383.7 x 291.5 x
//      147.7 normal orientation; nose-down the DEPTH hangs vertical)
cw = 383.7;  cd = 147.7;  ch = 291.5;
gap = 4;
cable_bay = 35;         // headroom above the body top for right-angle
                        //  plugs — SEE ROOF TRADE in the header before
                        //  changing; bench-measure, then shrink
iw = cw + 2*gap;        // 391.7 inner width  (lateral)
id = cd + 2*gap + 0.4;  // 156.1 inner depth  (along the throw)
ih = ch + 4.5 + cable_bay;  // inner height: body + seat + cable bay
ow = iw + 2*t;
od = id + 2*t;
cz = 2 + ch/2;          // chassis CENTER above the rim — anchors bosses,
                        //  vents, grids, ghost (ih/2 is wrong once the
                        //  bay exists: the bay grows the box, not the body)

// ---- rear wall = mount wall
boss_w = 223.0;  boss_h = 150.0;    // LS625X ceiling bosses, 4x M4 (p.56);
                                    //  NOMINAL — etched for reference only,
                                    //  the real holes are drilled from the
                                    //  unit (pattern may sit off-center on
                                    //  the chassis; grid absorbs it)
grid_hw = 130;                      // drill-grid half-width around center
grid_y0 = 68;  grid_y1 = 228;       // drill-grid rows (cz = 147.75)
cable_slot_w = 55;                  // one pass for HDMI + molded C13 +
cable_slot_h = 30;                  //  DB9-with-backshell heads, one at a
cable_slot_x = 110;                 //  time; Tim covers the hole. Center
                                    //  +cable_slot_x from wall center-x,
                                    //  vertically mid-bay (above the body)

// ---- airflow openings (Tim BENCH-MEASURED 2026-08-11, corrected same
//      day: BOTH flanks carry a 9 x 3.5 in / 228.6 x 88.9 grille. Facing
//      the lens head-on: viewer-LEFT flank = INTAKE (= side R here, the
//      plenum side); the other flank — the one next to the off-center
//      lens — = EXHAUST (= side L here, open vent, coarse screen only,
//      never MERV). The FRONT face gets the lens aperture ONLY.)
vent_w = 95;  vent_h = 235;         // vent both flanks: grille + ~3 mm
                                    //  margin; vertical grille position
                                    //  assumed CENTERED — verify on unit

// ---- bottom window panel + perimeter ring
lens_w = 117;  lens_h = 120;        // lens aperture, EXACT (Tim bench):
lens_from_right = 56;               //  117 across x 120 high, starting
                                    //  56 from the chassis edge on the
                                    //  no-grille side (viewer-RIGHT
                                    //  facing head-on = side L here)
ring_w = 20;                        // 2-ply ring glued under the rim
panel_screw = 3.2;  ring_pilot = 2.4;   // #4 wood screws up into the ring
// panel screw points (shared by panel holes + ring pilots)
function bottom_pts() = [[70, 10], [ow - 70, 10],
                         [70, od - 10], [ow - 70, od - 10],
                         [10, od/2], [ow - 10, od/2]];
ch_x0 = (ow - cw)/2;                // chassis edge inset on the panel (6.9)

// ---- VIVO MOUNT-VP01B ghost dims (preview only, NOT cut: profile 152 is
//      the published number; plate/hub/pole are eyeballed from photos —
//      measure the real unit in hand before committing shim thickness)
vp_profile = 152;                   // plate face to boss face (6 in)
vp_plate = 130;  vp_plate_t = 4;
vp_pole_d = 35;  vp_hub_d = 70;
vp_shim = 42;                       // nominal leg standoff (see doc)
leg_dx = 22.5;  leg_d = 43;         // paired corner legs (nominal centers)

// ---- filtered intake plenum (right-side intake add-on, in this file)
pf_filter_w = 241.3;                // 9.5 in nominal
pf_filter_t = 19.1;                 // 3/4 in nominal
pf_filter_clear = 3.0;
pf_box = 265;
pf_filter_open = pf_filter_w + pf_filter_clear;
pf_depth = 72;                      // fan 27 + filter 19 + breathing room
pf_fan_frame = 140;
pf_fan_cut = 136;
pf_fan_pitch = 125;
pf_fan_screw = 4.5;
pf_mount_dx = 64;                   // pilots FLANK the vent now — the old
pf_mount_dy = 100;                  //  +-108 verticals would land inside
                                    //  the 235-tall intake opening
pf_mount_screw = 4.0;
pf_clip_w = 36;
pf_clip_h = 14;
pf_clip_hole = 4.2;

// =========================================================================
module teeth_x(len) for (x = [0 : 2*finger : len - finger])
  translate([x, 0]) square([finger, t]);
module teeth_y(len) for (y = [0 : 2*finger : len - finger])
  translate([0, y]) square([t, finger]);
module rounded_rect(w, h, r = 2) {
  hull() {
    translate([r, r]) circle(r = r, $fn = 16);
    translate([w - r, r]) circle(r = r, $fn = 16);
    translate([r, h - r]) circle(r = r, $fn = 16);
    translate([w - r, h - r]) circle(r = r, $fn = 16);
  }
}

// ---- SHROUD -------------------------------------------------------------
module shroud_face_blank() {
  union() {
    square([ow, ih]);
    translate([t, ih]) teeth_x(iw);
  }
}
module shroud_face() {
  difference() {
    shroud_face_blank();
    for (sx = [0, ow - t]) translate([sx, 0]) teeth_y(ih);
  }
}
module shroud_front() shroud_face();
module shroud_rear() {
  difference() {
    shroud_face();
    // cable slot mid-bay: bottom edge rides ~5 mm above the body top so
    // plugged right-angle heads clear the chassis edge on the way out
    translate([ow/2 + cable_slot_x - cable_slot_w/2,
               ih - cable_bay/2 - cable_slot_h/2])
      rounded_rect(cable_slot_w, cable_slot_h, 8);
  }
}
// identical vent both flanks: side R = intake (plenum gaskets over it),
// side L = exhaust (open, coarse screen at most)
module shroud_side() {
  difference() {
    union() {
      square([id, ih]);
      translate([t, ih]) teeth_x(id - 2*t);
      translate([-t, 0]) teeth_y(ih);
      translate([id, 0]) teeth_y(ih);
    }
    translate([id/2 - vent_w/2, cz - vent_h/2]) square([vent_w, vent_h]);
  }
}
module shroud_top() {
  difference() {
    square([ow, od]);
    translate([t, 0]) teeth_x(iw);
    translate([t, od - t]) teeth_x(iw);
    for (sx = [0, ow - t]) translate([sx, 2*t]) teeth_y(id - 2*t);
  }
}
// bottom window panel: hangs under the glued ring, 6 screws up into it.
// ONE opening — the EXACT lens aperture (Tim: nothing else on the front)
module shroud_bottom() {
  difference() {
    square([ow, od]);
    translate([ch_x0 + lens_from_right, od/2 - lens_h/2])
      rounded_rect(lens_w, lens_h, 2);
    for (p = bottom_pts()) translate(p) circle(d = panel_screw, $fn = 28);
  }
}
// perimeter ring strips (cut 2 of each = 2-ply stack, glued under the rim
// flush with the outer walls; pilots line up with the panel screws)
module ring_long() {
  difference() {
    square([ow, ring_w]);
    for (x = [70, ow - 70]) translate([x, 10]) circle(d = ring_pilot, $fn = 24);
  }
}
module ring_short() {
  difference() {
    square([od - 2*ring_w, ring_w]);
    translate([od/2 - ring_w, 10]) circle(d = ring_pilot, $fn = 24);
  }
}

// ---- FILTERED INTAKE PLENUM -------------------------------------------
module plenum_fan_holes() {
  circle(d = pf_fan_cut, $fn = 96);
  for (sx = [-1, 1], sy = [-1, 1])
    translate([sx * pf_fan_pitch / 2, sy * pf_fan_pitch / 2])
      circle(d = pf_fan_screw, $fn = 32);
}
module plenum_mount_holes() {
  for (sx = [-1, 1], sy = [-1, 1])
    translate([sx * pf_mount_dx, sy * pf_mount_dy])
      circle(d = pf_mount_screw, $fn = 28);
}
module plenum_back() {
  difference() {
    square([pf_box, pf_box], center = true);
    plenum_fan_holes();
    plenum_mount_holes();
  }
}
module plenum_front() {
  difference() {
    square([pf_box, pf_box], center = true);
    square([pf_filter_open, pf_filter_open], center = true);
    for (p = [[0, pf_box/2 - 9], [0, -pf_box/2 + 9],
              [pf_box/2 - 9, 0], [-pf_box/2 + 9, 0]])
      translate(p) circle(d = 3.2, $fn = 24);
  }
}
module plenum_side() square([pf_box, pf_depth]);
module plenum_clip() {
  difference() {
    rounded_rect(pf_clip_w, pf_clip_h, 2);
    translate([pf_clip_w / 2, pf_clip_h / 2]) circle(d = pf_clip_hole, $fn = 28);
  }
}

// ---- sheet nesting ------------------------------------------------------
P_front  = [   0,   0];
P_rear   = [ 420,   0];
P_sideL  = [ 850,   0];
P_sideR  = [1040,   0];
P_top    = [   0, 375];
P_bottom = [   0, 555];
P_pf_back  = [420 + pf_box/2, 375 + pf_box/2];
P_pf_front = [420 + pf_box + 25 + pf_box/2, 375 + pf_box/2];
P_pf_side  = [[1000, 375], [1000, 462], [1000, 549], [1000, 636]];
P_pf_clip0 = [1000, 723];
P_ringL  = [[0, 730], [0, 755], [0, 780], [0, 805]];
P_ringS  = [[420, 660], [560, 660], [420, 685], [560, 685]];

module sheet_cut() {
  translate(P_front) shroud_front();
  translate(P_rear)  shroud_rear();
  translate(P_sideL) shroud_side();
  translate(P_sideR) shroud_side();
  translate(P_top)   shroud_top();
  translate(P_bottom) shroud_bottom();
  translate(P_pf_back) plenum_back();
  translate(P_pf_front) plenum_front();
  for (p = P_pf_side) translate(p) plenum_side();
  for (i = [0 : 3])
    translate([P_pf_clip0[0] + (i % 2) * (pf_clip_w + 10),
               P_pf_clip0[1] + floor(i / 2) * (pf_clip_h + 10)])
      plenum_clip();
  for (p = P_ringL) translate(p) ring_long();
  for (p = P_ringS) translate(p) ring_short();
}

// ---- etch layer ---------------------------------------------------------
// hairline hollow frame (a FILLED etch square would union with grid strips
// in OpenSCAD 2D and erase every line inside it)
module etch_frame(w, h) {
  difference() {
    translate([-0.4, -0.4]) square([w + 0.8, h + 0.8]);
    translate([0.4, 0.4]) square([w - 0.8, h - 0.8]);
  }
}
// rear-wall drill guide: 10 mm grid over the whole plausible boss zone +
// the NOMINAL 223 x 150 rectangle for reference — the four real holes are
// transferred from the unit on the bench (lens off-center, pattern maybe
// too), then the VIVO spider feet screw through into the bosses
module mount_wall_guide() {
  translate([ow/2 - boss_w/2, cz - boss_h/2]) etch_frame(boss_w, boss_h);
  translate([ow/2 - 12, cz - 0.2]) square([24, 0.4]);
  translate([ow/2 - 0.2, cz - 12]) square([0.4, 24]);
  for (gy = [grid_y0 : 10 : grid_y1])
    translate([ow/2 - grid_hw, gy - 0.2]) square([2*grid_hw, 0.4]);
  for (gx = [ow/2 - grid_hw : 10 : ow/2 + grid_hw])
    translate([gx - 0.2, grid_y0]) square([0.4, grid_y1 - grid_y0]);
}
// bottom-panel guide: hairline frame around the exact lens aperture +
// 10 mm ruler ticks clipped clear of both cutouts (transfer/verify aid)
module bottom_guide() {
  translate([ch_x0 + lens_from_right - 2.5, od/2 - lens_h/2 - 2.5])
    etch_frame(lens_w + 5, lens_h + 5);
  difference() {
    union() {
      for (gy = [od/2 - 60 : 10 : od/2 + 60])
        translate([30, gy - 0.2]) square([ow - 60, 0.4]);
      for (gx = [40 : 10 : ow - 40])
        translate([gx - 0.2, od/2 - 70]) square([0.4, 140]);
    }
    translate([ch_x0 + lens_from_right - 6, od/2 - lens_h/2 - 6])
      square([lens_w + 12, lens_h + 12]);
  }
}
module etch_sheet() {
  translate(P_front) translate([10, ih - 16]) text("FRONT (throw side)", size = 7);
  translate(P_rear) {
    translate([10, ih - 16]) text("REAR = MOUNT WALL", size = 7);
    mount_wall_guide();
    translate([ow/2 + cable_slot_x - 18, ih - cable_bay/2 - cable_slot_h/2 - 10])
      text("cables", size = 5);
    translate([40, 30])
      text("VIVO VP01B feet OUTSIDE - M4 thru wall into bosses", size = 5);
    translate([40, 18])
      text("223 x 150 NOMINAL - drill from the unit, do NOT bottom out", size = 5);
  }
  for (i = [0, 1]) translate(i ? P_sideR : P_sideL) {
    translate([10, ih - 16]) text(i ? "SIDE R  INTAKE - plenum gaskets here"
      : "SIDE L  EXHAUST - open, coarse screen only", size = 6);
    for (a = [0 : 30 : 359])
      translate([id/2 + cos(a)*(vent_w/2 + 8), cz + sin(a)*(vent_h/2 + 8)])
        circle(d = 1.5, $fn = 12);
  }
  translate(P_top) translate([10, od/2]) text("TOP  (roof slab ~6mm above)", size = 6);
  translate(P_bottom) {
    bottom_guide();
    translate([12, 3])
      text("BOTTOM - LENS 117 x 120 @ 56 off side-L chassis edge - the ONLY front opening", size = 4.5);
    translate([12, 11])
      text("lay the unit on this panel to verify before glue-up (bench 8-11)", size = 4.5);
  }
  translate(P_pf_back) {
    translate([-pf_box/2 + 10, pf_box/2 - 16])
      text("PLENUM BACK - gasket to RIGHT shroud side", size = 6);
    square([id, ih], center = true);
    square([vent_w, vent_h], center = true);
    circle(d = pf_fan_frame, $fn = 96);
    translate([-44, -4]) text("AIR TO SHROUD", size = 7);
  }
  translate(P_pf_front) {
    translate([-pf_box/2 + 10, pf_box/2 - 16])
      text("PLENUM FRONT - 9.5 x 9.5 x 0.75 MERV", size = 6);
    square([pf_filter_w, pf_filter_w], center = true);
  }
  for (p = P_pf_side)
    translate([p[0] + 8, p[1] + pf_depth/2 - 3])
      text("PLENUM SIDE x4 - glue/tape airtight", size = 5);
  for (i = [0 : 3])
    translate([P_pf_clip0[0] + (i % 2) * (pf_clip_w + 10) + 2,
               P_pf_clip0[1] + floor(i / 2) * (pf_clip_h + 10) + 4])
      text("clip", size = 4);
  translate([P_ringL[0][0] + 130, P_ringL[0][1] + 6])
    text("RING x2 layers - glue under rim, pilots up", size = 4.5);
  translate([P_ringS[0][0] + 8, P_ringS[0][1] + 6])
    text("RING short x2 layers", size = 4.5);
}

// ---- 3D preview ---------------------------------------------------------
module preview3d() {
  color("burlywood") {
    translate([-ow/2, -od/2 + t, 0]) rotate([90, 0, 0]) linear_extrude(t) shroud_front();
    translate([-ow/2, od/2 + t, 0]) rotate([90, 0, 0]) linear_extrude(t) shroud_rear();
    translate([-iw/2 - t, -id/2, 0]) rotate([90, 0, 90]) linear_extrude(t) shroud_side();
    translate([iw/2, -id/2, 0]) rotate([90, 0, 90]) linear_extrude(t) shroud_side();
    translate([-ow/2, -od/2, ih]) linear_extrude(t) square([ow, od]);
  }
  // bottom: 2-ply ring under the rim + the window panel under that
  color("peru") translate([-ow/2, -od/2, -2*t]) linear_extrude(2*t)
    difference() {
      square([ow, od]);
      translate([ring_w, ring_w]) square([ow - 2*ring_w, od - 2*ring_w]);
    }
  color("sienna") translate([-ow/2, -od/2, -3*t]) linear_extrude(t) shroud_bottom();
  %translate([-cw/2, -cd/2, 2]) cube([cw, cd, ch]);
  // ---- VIVO MOUNT-VP01B ghost (approx; +y = toward the corner) ----------
  wall_y = od/2 + t;                 // rear wall outer face
  boss_y = cd/2;                     // chassis boss face
  plate_y = boss_y + vp_profile;     // VIVO fixed 6in profile
  %union() {
    // spider feet on the wall at the nominal boss corners
    for (sx = [-1, 1], sz = [-1, 1])
      translate([sx*boss_w/2 - 12, wall_y, cz + sz*boss_h/2 - 6])
        cube([24, 6, 12]);
    // arms: feet up to the hub
    for (sx = [-1, 1], sz = [-1, 1]) hull() {
      translate([sx*boss_w/2, wall_y + 8, cz + sz*boss_h/2]) cube(10, center = true);
      translate([0, plate_y - 60, cz]) cube(12, center = true);
    }
    // hub + ball/pole stem + plate
    translate([0, plate_y - 62, cz]) rotate([-90, 0, 0]) cylinder(h = 20, d = vp_hub_d, $fn = 40);
    translate([0, plate_y - 46, cz]) rotate([-90, 0, 0]) cylinder(h = 46, d = vp_pole_d, $fn = 32);
    translate([-vp_plate/2, plate_y, cz - vp_plate/2])
      cube([vp_plate, vp_plate_t, vp_plate]);
    // shim blocks plate->legs (thickness set on site) + the leg pair
    for (bz = [cz - 65, cz + 25]) translate([-30, plate_y + vp_plate_t, bz])
      cube([60, vp_shim, 40]);
    for (sx = [-1, 1])
      translate([sx*leg_dx, plate_y + vp_plate_t + vp_shim + leg_d/2, -60])
        cylinder(h = ih + 110, d = leg_d, $fn = 28);
  }
  // Right-side filtered intake plenum, centered on the shroud side vent.
  color("sandybrown") translate([iw/2 + t, -pf_box/2, cz - pf_box/2])
    cube([pf_depth, pf_box, pf_box]);
  color("burlywood") translate([iw/2 + t - 0.1, -id/2, 0])
    cube([t, id, ih]);
  %translate([iw/2 + t + 8, -pf_fan_frame/2, cz - pf_fan_frame/2])
    cube([27, pf_fan_frame, pf_fan_frame]);
  %translate([iw/2 + t + pf_depth + t + 1, -pf_filter_w/2, cz - pf_filter_w/2])
    cube([pf_filter_t, pf_filter_w, pf_filter_w]);
}

// ---- part switch --------------------------------------------------------
if (part == "sheet") sheet_cut();
else if (part == "sheet_etch") etch_sheet();
else if (part == "front") shroud_front();
else if (part == "rear") shroud_rear();
else if (part == "side") shroud_side();
else if (part == "top") shroud_top();
else if (part == "bottom") shroud_bottom();
else if (part == "ring_long") ring_long();
else if (part == "ring_short") ring_short();
else if (part == "plenum_back") plenum_back();
else if (part == "plenum_front") plenum_front();
else if (part == "plenum_side") plenum_side();
else if (part == "plenum_clip") plenum_clip();
else preview3d();
