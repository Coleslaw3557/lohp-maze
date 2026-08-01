// LoHP maze — Cuddle projector SHROUD + MOUNT, laser-cut edition
// (2026-08-01 REAL-DIMS rev; supersedes 2026-07-29)
// ===========================================================================
// The LS625X hangs NOSE-DOWN at the hex NE corner throwing SW down the deck
// diagonal. 2026-08-01: chassis re-sized to the OFFICIAL ViewSonic figures
// (user guide p.56: 383.7 w x 291.5 d x 147.7 h, net 6.2 kg; ceiling bosses
// 4x M4 on a 223.0 x 150.0 pattern) — the earlier 293 x 221.5 x 114.6 body
// was a bad source, ~0.76x in every axis. The taller nose-down body forces
// the window DOWN: 1455 mm above deck (0.49 x 2969 mm image), body top
// 1746.5, shroud top 6 mm under the 1760 roof soffit. Lens plumb 250 mm
// from the corner ON the string line (coverage 90.2%, rear corners 25 mm
// clear of the rail tube worst-case). Numbers + on-site calibration in
// wiring-guides/cuddle-projector-mount.md; the sim's Mount button draws
// this hardware to scale.
//
// WHY THIS SHAPE (the corner is hostile to flat plates): the two frame
// planes meet at 120 deg, only 30 deg off any plate facing the corner, and
// each frame carries a TOP RAIL 75 mm below the leg tops plus a full-width
// HEADER 190 mm down. Anything wide that touches the leg pair crosses those
// members' ends within ~40 mm laterally. So the mount touches the legs ONLY
// at member-free heights, with horizontal CRADLE RIBS; everything vertical
// stays >= 65 mm inboard of the corner where no steel lives.
//
// Assemblies (3mm ply, t = 2.9 caliper-gated node-box stock; ply is
// STRUCTURAL here — glue every joint, Titebond III; the REAL unit is
// 6.2 kg, so no dry joints and all 4 hose clamps):
//
//  SHROUD — 5-sided finger-jointed sleeve around the nose-down chassis
//    (383.7 x 147.7 plan, 291.5 tall): OPEN BOTTOM (beam + dust exit; rim
//    flush with the projection window), vent windows both sides (filter
//    cloth stapled OUTSIDE, staple ring etched), rear wall = beam
//    pass-through + 16 mm cable exit. Top panel rides ~6 mm under the roof
//    slab — service by slacking the two M6 carriage bolts and lowering the
//    whole box.
//
//  BEAM — 100 x 45 box beam on the CORNER BISECTOR (60.0 deg to each frame
//    face), threading the 77 mm header-to-rail gap. Its SIDE PLATES extend
//    at the corner end into a tall back frame (245 mm) carrying the cradle
//    ribs; top/bottom plates carry the +-80 mm carriage slots (2026-08-01:
//    slots re-centered on the carriage's actual bolt line ~139 mm from the
//    corner — the 07-29 sheet had them at the far inboard end where the
//    carriage can never ride).
//
//  CRADLE RIBS x4 — horizontal plates at the four clamp heights (two bands:
//    ~1530-1560 above deck, below the legs' brace studs; ~1745-1775, above
//    the top-rail weld under the coupling collars). Each rib ends in two
//    open D44 cradles that seat the paired 43 mm legs, with a hose-clamp
//    slot inboard of each cradle: the clamp threads the slot, wraps the
//    tube, and pulls the cradle onto the leg. Ribs tenon through mortises
//    in the side-plate back frames (glued cross-lap).
//
//  CARRIAGE — vertical plate x3 laminations, 260 x 240 with a beam notch:
//    the real 223 x 150 boss pattern is WIDER than the beam and its top row
//    rides ABOVE the beam underside, so the plate ears rise beside the beam
//    (PI shape) and the notch floor sits at the beam bottom. Drill the boss
//    pattern ON THE BENCH from the unit (10 mm grid etched as drill guide;
//    4x M4x16 + fender washers into the chassis bosses — verify boss depth,
//    do NOT bottom out; center the LENS on the string line, not the
//    chassis — the lens sits off-center in the 383.7 width). Top flange
//    (x3, tongue into the mid lamination at the notch floor) bolting UP
//    into the beam slots: 2x M6, nuts + fender washers inside the open beam
//    end. Slack the bolts -> the carriage (plate + chassis + shroud) slides
//    +-80 mm along the beam = the on-site radial trim. Shroud rear wall
//    screws to the plate face (etched pilots).
//
// Load path: chassis bosses -> plate -> flange -> M6 -> beam -> side plates
// -> cradle ribs -> 4 hose clamps -> paired corner legs. Add a safety
// lanyard from the beam through the rail-header gap around the top rail.
//
// Export: python3 export-shroud.py   (black = CUT, red = SCORE/etch in XCS)

part = "3d";     // 3d | sheet | sheet_etch | front|rear|side|top|
                 //   side_plate|rib|beam_plate|beam_rib|plate|plate_mid|flange

t = 2.9;         // ply thickness, caliper-gated
finger = 18;     // finger/socket pitch — literal everywhere so mates align

// ---- chassis + clearances (LS625X official, guide p.56: 383.7 x 291.5 x
//      147.7 normal orientation; nose-down the DEPTH hangs vertical)
cw = 383.7;  cd = 147.7;  ch = 291.5;
gap = 4;
iw = cw + 2*gap;        // 391.7 inner width  (lateral)
id = cd + 2*gap + 0.4;  // 156.1 inner depth  (along the throw)
ih = ch + 4.5;          // 296 inner height
ow = iw + 2*t;
od = id + 2*t;

// ---- rear-wall openings
beam_w = 100; beam_h = 45;
pass_w = beam_w + 4;  pass_h = beam_h + 4;
pass_cy = 203;                      // pass center above the bottom rim
                                    //  (beam axis 1658 - window 1455)
cable_d = 16;
vent_w = 90; vent_h = 160;          // sized to the real side fan grilles

// ---- beam + back frame + ribs (heights in mm ABOVE THE DECK for sanity;
//      beam axis 1658 = mid rail-header gap; window 1455)
beam_len = 320;                     // beam FRONT end lands 40 mm shy of the
                                    //  corner (scad x = beam_len end);
                                    //  x = 0 is the inboard/deck end
adj = 80;  m6 = 6.5;
adj_slot_len = 2*adj + m6;
slot_x0 = 136;                      // slot start from the inboard end —
                                    //  centers the +-80 travel on the
                                    //  carriage bolt line ~139 mm from the
                                    //  corner (nominal plumb 250)
bolt_dx = 28;
web_h = beam_h - 2*t;               // 39.2 — the beam-band web height
ext_d = 80;                         // back-frame depth (along the bisector)
ext_off = 25;                       // back frame ends this far shy of the
                                    //  beam end -> outboard edge corner-65,
                                    //  clear of the rail/header ends
ext_up = 94;                        // above the web bottom -> 1775 top
ext_dn = 111;                       // below the web bottom -> 1530 bottom
rib_ys = [-111, -97, 104, 118];     // rib undersides above web bottom:
                                    //  bands 1530/1544 and 1745/1759
mort_len = 45;                      // rib wing crossing in the back frame
// cradle rib plan (local y: 0 = inboard tip = corner-102)
rib_w = 150;  rib_d = 124;          // wings reach corner+9
wing_y0 = 5;                        // wing leading shoulder
tube_z = 102; tube_dx = 22.5;       // nominal leg centers (pair varies —
tube_d = 44;                        //  cradles are open, clamps close them)
cslot_w = 16; cslot_h = 5;          // hose-clamp slots (1/2" band)
cslot_z = 82;
// carriage (2026-08-01: sized to the real 223 x 150 boss pattern)
plate_w = 260; plate_h = 240;
notch_w = pass_w;                   // beam notch through all 3 laminations
notch_y0 = 175.5;                   // notch floor = beam underside
                                    //  (plate bottom rides 3 mm above the
                                    //  window rim: 178.5 - 3)
flange_d = 60;

// =========================================================================
module teeth_x(len) for (x = [0 : 2*finger : len - finger])
  translate([x, 0]) square([finger, t]);
module teeth_y(len) for (y = [0 : 2*finger : len - finger])
  translate([0, y]) square([t, finger]);

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
    translate([ow/2 - pass_w/2, pass_cy - pass_h/2]) square([pass_w, pass_h]);
    translate([ow/2 + 90, 55]) circle(d = cable_d, $fn = 40);
  }
}
module shroud_side() {
  difference() {
    union() {
      square([id, ih]);
      translate([t, ih]) teeth_x(id - 2*t);
      translate([-t, 0]) teeth_y(ih);
      translate([id, 0]) teeth_y(ih);
    }
    translate([id/2 - vent_w/2, ih/2 - vent_h/2]) square([vent_w, vent_h]);
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

// ---- BEAM side plate (web + back frame), 2D in the vertical bisector
// plane: x = along the beam toward the corner, y = up from the web bottom
module side_plate() {
  difference() {
    union() {
      square([beam_len, web_h]);                                  // web
      translate([beam_len - ext_off - ext_d, -ext_dn])
        square([ext_d, ext_up + ext_dn]);                         // back frame
    }
    // rib mortises: the rib tongues cross the back frame's outboard zone
    for (ry = [rib_ys[0], rib_ys[1], rib_ys[2], rib_ys[3]])
      translate([beam_len - ext_off - mort_len, ry]) square([mort_len, t]);
  }
}

// ---- beam top/bottom plates + internal ribs ----------------------------
module adj_slots() for (sy = [-1, 1])
  translate([slot_x0 + m6/2, beam_w/2 + sy*bolt_dx])
    hull() { circle(d = m6, $fn = 30);
             translate([adj_slot_len - m6, 0]) circle(d = m6, $fn = 30); }
module beam_plate() difference() { square([beam_len, beam_w]); adj_slots(); }
module beam_rib() square([beam_w - 2*t, web_h]);

// ---- CRADLE RIB ---------------------------------------------------------
// horizontal; slides in from the corner side — the WINGS (full +-75 span,
// 45 deep) enter the side-plate mortises while the central block (92 wide)
// threads between the plates — then the open cradles seat on the leg pair
// and the clamps close them
module cradle_rib() {
  difference() {
    union() {
      translate([-rib_w/2, wing_y0]) square([rib_w, mort_len]);        // wings
      translate([-46, 0]) square([92, rib_d]);                          // core
    }
    for (sx = [-1, 1]) {
      // open cradle: D44 slot from the tube seat out the far edge
      hull() {
        translate([sx*tube_dx, tube_z]) circle(d = tube_d, $fn = 48);
        translate([sx*tube_dx, rib_d + tube_d]) circle(d = tube_d, $fn = 48);
      }
      // hose-clamp slot inboard of the cradle
      translate([sx*tube_dx - cslot_w/2, cslot_z - cslot_h/2])
        square([cslot_w, cslot_h]);
    }
  }
}

// ---- CARRIAGE -----------------------------------------------------------
// PI-shaped plate: full width below the beam underside, ears rising beside
// the beam so the 223 x 150 boss pattern's top row (which sits above the
// beam bottom on the 291.5 mm boss face) still lands on ply
module plate_vert() {
  difference() {
    square([plate_w, plate_h]);
    translate([plate_w/2 - notch_w/2, notch_y0])
      square([notch_w, plate_h - notch_y0]);
  }
}
module plate_mid() {
  difference() {
    plate_vert();
    // flange tongue slot at the notch floor
    translate([plate_w/2 - beam_w/2, notch_y0 - t]) square([beam_w, t]);
  }
}
module flange() {
  difference() {
    union() {
      square([beam_w, flange_d]);
      translate([0, -t]) square([beam_w, t]);
    }
    for (sy = [-1, 1]) translate([beam_w/2 + sy*bolt_dx, flange_d/2])
      circle(d = m6, $fn = 30);
  }
}

// ---- sheet nesting ------------------------------------------------------
P_front  = [   0,   0];
P_rear   = [ 420,   0];
P_sideL  = [ 850,   0];
P_sideR  = [1040,   0];
P_top    = [   0, 320];
P_sp     = [[420, 320], [420, 545]];      // side plates
P_ribsC  = [[760, 320], [930, 320], [760, 460], [930, 460]];
P_beamT  = [   0, 500];
P_beamB  = [   0, 620];
P_beamR  = [[0, 740], [110, 740]];
P_plateM = [ 760, 600];
P_plateV = [[1040, 600], [1090, 320]];
P_flange = [[420, 780], [530, 780], [640, 780]];

module sheet_cut() {
  translate(P_front) shroud_front();
  translate(P_rear)  shroud_rear();
  translate(P_sideL) shroud_side();
  translate(P_sideR) shroud_side();
  translate(P_top)   shroud_top();
  for (p = P_sp) translate([p[0], p[1] + ext_dn]) side_plate();
  for (p = P_ribsC) translate([p[0] + rib_w/2, p[1]]) cradle_rib();
  translate(P_beamT) beam_plate();
  translate(P_beamB) beam_plate();
  for (p = P_beamR) translate(p) beam_rib();
  translate(P_plateM) plate_mid();
  for (p = P_plateV) translate(p) plate_vert();
  for (p = P_flange) translate(p) flange();
}

// ---- etch layer ---------------------------------------------------------
// carriage drill grid: full-width rows below the notch floor, ear columns
// beside the notch above it — covers the whole 223 x 150 boss-pattern zone
module plate_grid() {
  for (gy = [20 : 10 : notch_y0 - 8])
    translate([15, gy - 0.2]) square([plate_w - 30, 0.4]);
  for (gx = [15 : 10 : plate_w - 15]) {
    ear = (gx < plate_w/2 - notch_w/2 - 4) || (gx > plate_w/2 + notch_w/2 + 4);
    translate([gx - 0.2, 20]) square([0.4, (ear ? plate_h - 10 : notch_y0 - 8) - 20]);
  }
}
module etch_sheet() {
  translate(P_front) translate([10, ih - 16]) text("FRONT (throw side)", size = 7);
  translate(P_rear) {
    translate([10, ih - 16]) text("REAR  beam pass  cable", size = 7);
    for (sx = [-1, 1]) translate([ow/2 + sx*70, pass_cy]) circle(d = 2, $fn = 16);
  }
  for (i = [0, 1]) translate(i ? P_sideR : P_sideL) {
    translate([10, ih - 16]) text(str("SIDE ", i ? "R" : "L", "  cloth OUTSIDE"), size = 6);
    for (a = [0 : 30 : 359])
      translate([id/2 + cos(a)*(vent_w/2 + 8), ih/2 + sin(a)*(vent_h/2 + 8)])
        circle(d = 1.5, $fn = 12);
  }
  translate(P_top) translate([10, od/2]) text("TOP  (roof slab ~6mm above)", size = 6);
  translate([P_sp[0][0] + 20, P_sp[0][1] + ext_dn + 8])
    text("SIDE PLATE  corner end ->", size = 6);
  translate([P_ribsC[0][0] + rib_w/2 - 55, P_ribsC[0][1] + 12])
    text("CRADLE RIB x4  clamps thread slots", size = 5);
  translate(P_beamT) translate([30, beam_w/2 - 3])
    text("BEAM TOP   <- -80 to corner    +80 to deck ->", size = 5);
  translate(P_plateV[0]) {
    plate_grid();
    translate([8, 12]) text("LS625X bosses 223 x 150 - drill from the unit", size = 5);
    translate([8, 4]) text("4x M4x16 +washers (don't bottom) - LENS on the line", size = 5);
  }
  translate(P_plateV[1]) plate_grid();
  translate(P_plateM) plate_grid();
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
  %translate([-cw/2, -cd/2, 2]) cube([cw, cd, ch]);
  yb = pass_cy - beam_h/2 + t;                 // web bottom, shroud coords
  for (sx = [-1, 1]) color("tan")
    translate([sx*(beam_w/2 - (sx > 0 ? t : 0)), id/2 - 30, yb])
      rotate([90, 0, 90]) linear_extrude(t) side_plate();
  color("tan") {
    translate([-beam_w/2, id/2 - 30, yb - t]) cube([beam_w, beam_len, t]);
    translate([-beam_w/2, id/2 - 30, yb + web_h]) cube([beam_w, beam_len, t]);
  }
  for (ry = rib_ys) color("peru")
    translate([0, id/2 - 30 + beam_len - ext_off - mort_len - wing_y0, yb + ry])
      linear_extrude(t) cradle_rib();
  // leg pair ghost
  for (sx = [-1, 1]) %translate([sx*tube_dx, id/2 - 30 + beam_len - ext_off - mort_len - wing_y0 + tube_z, yb - ext_dn - 30])
    cylinder(h = ext_up + ext_dn + 60, d = 43, $fn = 24);
  color("sienna") translate([-plate_w/2, id/2 + t + 1 + 3*t, 3])
    rotate([90, 0, 0]) linear_extrude(3*t) plate_vert();
}

// ---- part switch --------------------------------------------------------
if (part == "sheet") sheet_cut();
else if (part == "sheet_etch") etch_sheet();
else if (part == "front") shroud_front();
else if (part == "rear") shroud_rear();
else if (part == "side") shroud_side();
else if (part == "top") shroud_top();
else if (part == "side_plate") side_plate();
else if (part == "rib") cradle_rib();
else if (part == "beam_plate") beam_plate();
else if (part == "beam_rib") beam_rib();
else if (part == "plate") plate_vert();
else if (part == "plate_mid") plate_mid();
else if (part == "flange") flange();
else preview3d();
