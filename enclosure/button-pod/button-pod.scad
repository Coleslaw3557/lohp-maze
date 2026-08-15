// LoHP maze — BUTTON POD enclosure (the far end of the DB9 cable)
// ================================================================
// ONE universal pod for the 7 port-A rooms (Gate, DPH, Bike Lock, NFM,
// Photo Bomb, Monkey, Porto — wiring-guides/db9-field-wiring.md): the
// room-node box's DB9 A cable lands HERE, near the buttons, and fans out.
// Inside: the DB9 MALE screw-terminal breakout (same ANMBEST family as
// the box end, bare PCB, case off) and ONE dual-row terminal block
// (Tim's calipers 2026-08-15: 91 x 30, 17.60 tall cover-on, 6 CIRCUITS
// — one per pod, 10 on order for 7 pods + spares). Two parts, two jobs:
// SIGNALS land straight on the breakout's own pin screws (JST blue ->
// its DB9 pin, point to point — they never touch the block); the block
// is the POWER BUS only (6 pairs won't patch 9 conductors — the 08-15
// circuit count killed the patch-row idea): 2 circuits jumpered = 5V,
// 4 = GND. Only two jumpers cross the floor, the pin-1/pin-2 feeds.
// The WAGO 221s of the earlier draft are OUT of the standard build
// (redundant with the block-as-bus; they stay in the kit as splices). OUT:
// seven Ø7 pigtail holes, one per 4-pin JST-SM button lead (the BTF
// pigtail threads through bare-ends-first, connector half stays OUTSIDE,
// zip-tie knot inside = strain relief, ~10cm slack tail — the camp-sign
// box's proven pigtail grammar). Hole n = signal n = DB9 pin n+2; rooms
// use holes 1..n from the DB9 corner and tape over the rest (Gate 6,
// DPH 5, Bike 4, Porto 3, NFM 1, Photo Bomb 1, Monkey 1).
//
// SAME SHELL as the room-node box (node-enclosure.scad, cut 8+ times):
// 110 x 78 exterior, 3mm ply, 5-seg corner fingers, floor mortise tabs,
// full-height walls, rev4 DROP-IN LID — the pod lid and the room-box lid
// are the SAME PART (spares interchange). Back-wall mounting, two ways:
// the node-standard velcro slots (vertical leg / rail) PLUS four
// horizontal zip-tie slots for scaffolding cross members (see the
// zip_* params). Differences: no sensor
// window (solid front carries the JST row), no XLR, no USB/AUX (nothing
// powered lives here — the pod is passive copper), right wall blank.
//
// ETCH FACES — NOT the node-box habit, read this: the FRONT wall's etch
// (hole numerals + BTN POD id) faces OUTSIDE — the field wirer reads the
// wall when plugging buttons. (Node boxes etch their front INWARD; the
// pod has no window outline to hide.) Floor etch UP, back etch OUT
// (VELCRO), left wall ships PRE-MIRRORED in the flat output exactly like
// the node box so its DB9 label lands outside. Right wall has no cuts
// and no etch — it is non-chiral, orient it however it fits.
//
// CALIPER GATES:
//   * jst_cz vs block height: RESOLVED 2026-08-15 — the block calipers
//     17.60 tall (cover on); the hole row's bottom edge at 21.4 clears
//     it by 3.8. Burn as drawn.
//   * block screw-hole span: NOT pre-cut (parts are their own jigs) —
//     sit the block in its etched lane, mark, drive short screws (they
//     must not pass the 2.9 floor — grind or VHB instead if too long).
//   * Ø7 vs the 4-wire BTF SM bundle: 4x22AWG ≈ Ø4.5 threaded loose —
//     generous, same physics as the sign box's proven 3-pin Ø7.
//
// Export:  python3 export-button-pod.py   -> button-pod.svg + previews
// part="3d" is the glued-up assembly preview (ghost block/DB9).

part = "3d";   // front|back|left|right|floor|lid|sheet|3d (+ *_etch)

// ---- stock (node-box values verbatim — one family, one sheet) ----------
t  = 2.9;        // "3mm" ply, calipered 2026-07-21 — re-caliper new batches
kerf_note = "cut outlines are exact; add kerf offset in xTool XCS";

// ---- box (outer) — the node-box shell, unchanged ------------------------
W  = 110;        // width  (front/back length)
D  = 78;         // depth  (left/right length)
inner_h = 34;    // interior height (floor top -> lid underside)
Hw = 2*t + inner_h;        // wall height = outer height (39.8 at t=2.9)
lid_notch = 14;            // finger pull, front edge center
lid_front_cs = [-32, 32];  // front lid tabs skip the center for the notch

// ---- joinery (node-box values verbatim) --------------------------------
nseg = 5;  seg = Hw / nseg;   // corner fingers: front/back own segs 0,2,4
ftab_w = 20;                  // floor mortise tab width
long_cs  = [-32, 0, 32];      // tab centers, W edges
short_cs = [-18, 18];         // tab centers, D edges
strap_w = 5; strap_h = 24;    // velcro slots, back wall (20mm one-wrap
                              //  around a VERTICAL leg; a standard 4.8
                              //  zip tie passes them too — heavy 7.6s
                              //  don't)
// zip-tie slots (Tim 2026-08-15): the pods zip-tie to scaffolding CROSS
// MEMBERS — horizontal tubes want a VERTICAL tie loop, which the
// vertical velcro slots can't make. Four HORIZONTAL slots, a high/low
// pair at each end of the back wall: tie enters the top slot, crosses
// the wall's inner face (same 3mm back-wall clearance the velcro strap
// uses — the DB9 zone already keeps off it), exits the bottom slot,
// wraps the tube, head cinches outside. Two ties per box kill rotation.
// 9 x 4 passes heavy 7.6 x 1.8 ties; 11" ties reach around a 48.3
// scaffold tube with slack.
zip_w = 9;  zip_h = 4;
zip_cxs = [-43, 43];          // about W/2 — outboard of the velcro
                              //  slots, symmetric so a flipped wall
                              //  lands the same cuts
zip_czs = [8, 31];            // low/high: 3.1 web above the floor-
                              //  mortise notches, 3.9 below the wall-
                              //  top lid notches

// ---- DB9 A, male breakout (ANMBEST B09WD2V37T — the box end's twin) ----
// Window/stack geometry copied from the node box (calipered 2026-07-22,
// cut + validated on the real kit). Only the ALONG-WALL position is new:
// the pod's breakout sits in the left wall's BACK half so the terminal
// block owns the front — the JST tails drop straight onto its front row.
db9_cut_w = 20.3; db9_cut_h = 11.7; // CUT window — loose frame, the floor
                                    //  screws locate the PCB, not this
db9_cz  = t + 9.34;                 // center height: 3.89 PCB->shell bottom
                                    //  + half a std 10.9 shell (measured)
db9_zone = [34, 31.75];             // floor zone: along-wall x into-box.
                                    //  31.75 = the bare PCB, 1-1/4"
db9_cx = t + (D - 2*t) - 3 - db9_zone[0]/2;
                                    // = 55.1: zone rear edge 3mm off the
                                    //  back wall's inner face — the velcro
                                    //  strap crosses that face between its
                                    //  slots and must not pinch on the PCB
db9_screw = 24.99;                  // screwlock pitch (nominal; the real
                                    //  part measured 24.26) — NOT pre-cut:
                                    //  posts touch the wall, mark, drill Ø6

// ---- terminal block (calipered by Tim 2026-08-15) ----------------------
// Dual-row, 6 circuits — the POWER BUS, flat on the floor along the
// front wall, screws up. Left 2 circuits jumpered = 5V, right 4 = GND
// (wire links or a comb); the pin-1/pin-2 feeds from the breakout land
// on the back row, JST reds/blacks/greens on the front. Gate (the
// worst case) fits without WAGOs because each pigtail's black + green
// are the SAME NET — land the pair under one GND screw: 6 pairs + feed
// across 8 screws, 7 reds across 4. Signals bypass the block entirely
// (breakout pin screws take the blues 1:1).
term_l = 91;  term_w = 30;          // the REAL part, calipers 2026-08-15
term_h = 17.6;                      //  — height cover-on, same session:
                                    //  closes the jst_cz gate (preview
                                    //  ghost only, no cut derives from it)
term_cx = (W - 2*t)/2;              // centered: 6.6 off each side wall
term_cy = 3 + term_w/2;            // front edge 3mm off the front wall's
                                    //  inner face (knot + wire-drop room)

// ---- JST pigtail exits (BTF-LIGHTING 4-pin JST-SM, on order) -----------
jst_hole = 7;                       // = the sign box's proven pigtail bore
jst_cs = [-36, -24, -12, 0, 12, 24, 36];  // 7 holes @ 12 pitch about W/2:
                                    //  hole 1 at drawn x 19 lands at the
                                    //  DB9 corner on the assembled box
                                    //  (etch OUT). Row symmetric — a
                                    //  flipped wall lands the same holes
jst_cz = t + 22;                    // row center 24.9 above the floor
                                    //  bottom: hole bottom edge 21.4
                                    //  clears the 17.60 block cover by
                                    //  3.8 (gate closed 08-15), under
                                    //  the wall-top lid notches at 36.9

$fn = 40;
eps = 0.01;

// ---- joinery helpers (2D — node-enclosure.scad verbatim) ---------------
module bottom_notches(len, centers)
  for (c = centers) translate([len/2 + c - ftab_w/2, -eps])
    square([ftab_w, t + eps]);

module top_notches(len, centers)
  for (c = centers) translate([len/2 + c - ftab_w/2, Hw - t])
    square([ftab_w, t + eps]);

module corner_notches(len)
  for (s = [1, 3], x = [0, len - t])
    translate([x - eps, s * seg]) square([t + 2*eps, seg]);

// ---- etch helpers (RED layer -> score in XCS) --------------------------
module oline(w, h, lw = 0.4)
  difference() { square([w, h], center = true);
                 square([w - 2*lw, h - 2*lw], center = true); }

module label(txt, size = 3.2)
  text(txt, size = size, halign = "center", valign = "center",
       font = "Liberation Sans:style=Bold");

// ---- panels (2D) -------------------------------------------------------
module panel_front() difference() {           // solid but for the JST row
  square([W, Hw]);
  corner_notches(W);
  bottom_notches(W, long_cs);
  top_notches(W, lid_front_cs);               // center stays solid — the
                                              //  lid's finger notch dips
  for (c = jst_cs)                            //  over it
    translate([W/2 + c, jst_cz]) circle(d = jst_hole);
}

module front_etch() {                         // EXTERIOR face (unlike the
  for (i = [0 : len(jst_cs) - 1])             //  node box): the wirer reads
    translate([W/2 + jst_cs[i], jst_cz + 8.5])//  the wall. Numeral above
      label(str(i + 1), 2.8);                 //  each hole; 1 = DB9 corner
  translate([W/2, 10]) label("BTN POD", 4);   //  = DB9 pin 3
}

module panel_back() difference() {
  square([W, Hw]);
  corner_notches(W);
  bottom_notches(W, long_cs);
  top_notches(W, long_cs);
  for (c = [-27, 27])                         // velcro strap slots — node
    translate([W/2 + c - strap_w/2, (inner_h - strap_h)/2 + t])
      square([strap_w, strap_h]);             //  box positions verbatim
  for (cx = zip_cxs, cz = zip_czs)            // zip-tie slots — cross-
    translate([W/2 + cx - zip_w/2, cz - zip_h/2])
      square([zip_w, zip_h]);                 //  member mounting
}

module back_etch() {
  translate([W/2, 19]) label("VELCRO", 2.8);
  for (cx = zip_cxs)
    translate([W/2 + cx, 19]) label("ZIP", 2.5);
}

module panel_side() difference() {            // x runs front->back
  square([D, Hw]);
  for (s = [0, 2, 4], x = [0, D - t])         // plain 5-seg corner joints
    translate([x - eps, s * seg]) square([t + 2*eps, seg]);
  bottom_notches(D, short_cs);
  top_notches(D, short_cs);
}

module panel_left() difference() {            // x runs front->back
  panel_side();
  // DB9 A window — the male breakout's D-sub face pokes through here
  // (loose frame; floor screws hold the PCB). Screwlock Ø6s stay a bench
  // drill from the real part's posts, exactly like the node box.
  translate([db9_cx, db9_cz]) square([db9_cut_w, db9_cut_h], center = true);
}

// The flat output pre-mirrors the left wall (the node box's 07-24 lesson,
// same chirality): cut mirrored, labels re-drawn UN-mirrored at mirrored
// positions, so the DB9 label lands OUTSIDE on the assembled box.
// (assembly() keeps the un-mirrored panel_left — the physical mirrored
// part, flipped over at glue-up, lands exactly there.)
module panel_left_cut() translate([D, 0]) mirror([1, 0]) panel_left();

module left_etch_cut()                        // x runs BACK->front
  translate([D - db9_cx, db9_cz + 12]) label("DB9", 3);

module panel_right() panel_side();            // no cuts, no etch: the ONLY
                                              //  non-chiral side wall in
                                              //  the family — orient at
                                              //  glue-up however it fits

module panel_floor() difference() {
  union() {
    square([W - 2*t, D - 2*t]);
    for (c = long_cs) {
      translate([(W - 2*t)/2 + c - ftab_w/2, -t]) square([ftab_w, t + eps]);
      translate([(W - 2*t)/2 + c - ftab_w/2, D - 2*t - eps]) square([ftab_w, t + eps]);
    }
    for (c = short_cs) {
      translate([-t, (D - 2*t)/2 + c - ftab_w/2]) square([t + eps, ftab_w]);
      translate([W - 2*t - eps, (D - 2*t)/2 + c - ftab_w/2]) square([t + eps, ftab_w]);
    }
  }
}

module floor_etch() {
  // terminal block lane along the front wall, screws up: the power bus
  // (left 2 circuits = 5V, right 4 = GND). Signals bypass it — the JST
  // blues land straight on the DB9 breakout's own pin screws
  translate([term_cx, term_cy]) oline(term_l, term_w);
  translate([term_cx, term_cy]) label("TERM BLOCK", 3);
  translate([13, term_cy + 9]) label("5V", 2.2);
  translate([90, term_cy + 9]) label("GND", 2.2);
  // DB9 male breakout: bare PCB screwed down here, face out the wall
  // window behind it. Same zone as the node box, back-left instead of
  // front-left
  translate([db9_zone[1]/2, db9_cx - t]) oline(db9_zone[1], db9_zone[0]);
  translate([db9_zone[1]/2, db9_cx - t]) label("DB9 PCB", 2.8);
}

module panel_lid() difference() {             // IDENTICAL to the node-box
  union() {                                   //  lid — spares interchange
    square([W - 2*t, D - 2*t]);
    for (c = lid_front_cs)
      translate([(W - 2*t)/2 + c - ftab_w/2, -t]) square([ftab_w, t + eps]);
    for (c = long_cs)
      translate([(W - 2*t)/2 + c - ftab_w/2, D - 2*t - eps]) square([ftab_w, t + eps]);
    for (c = short_cs) {
      translate([-t, (D - 2*t)/2 + c - ftab_w/2]) square([t + eps, ftab_w]);
      translate([W - 2*t - eps, (D - 2*t)/2 + c - ftab_w/2]) square([t + eps, ftab_w]);
    }
  }
  translate([(W - 2*t)/2, 0]) circle(d = lid_notch);
}

// ---- layouts -----------------------------------------------------------
// Same nesting as the node-box sheet: ~232 x 170, one S1 bed load.
module sheet() {
  panel_front();
  translate([0, Hw + 6])        panel_back();
  translate([t, 2*Hw + 12 + t]) panel_floor();
  translate([W + 12, 0])        panel_left_cut();
  translate([W + 12, Hw + 6])   panel_right();
  translate([W + 12 + t, 2*Hw + 12 + t]) panel_lid();
}

module sheet_etch() {
  front_etch();
  translate([0, Hw + 6])        back_etch();
  translate([t, 2*Hw + 12 + t]) floor_etch();
  translate([W + 12, 0])        left_etch_cut();
}

module assembly() {
  color("BurlyWood") translate([t, t, 0]) linear_extrude(t) panel_floor();
  color("Peru")      translate([0, t, 0]) rotate([90, 0, 0]) linear_extrude(t) panel_front();
  color("Peru")      translate([0, D, 0]) rotate([90, 0, 0]) linear_extrude(t) panel_back();
  color("Sienna")    rotate([90, 0, 90]) linear_extrude(t) panel_left();
  color("Sienna")    translate([W - t, 0, 0]) rotate([90, 0, 90]) linear_extrude(t) panel_right();
  color("Tan", 0.85) translate([t, t, Hw - t + 14]) linear_extrude(t) panel_lid();
  // fit-check ghosts (preview only — never exported)
  color("Gold", 0.55)                         // the terminal block, as
    translate([t + term_cx - term_l/2, t + term_cy - term_w/2, t])
      cube([term_l, term_w, term_h]);         //  calipered 91x30x17.60
  color("SeaGreen", 0.6)                      // DB9 breakout PCB + shell
    translate([t, db9_cx - db9_zone[0]/2, t]) //  nub out the left window
      cube([db9_zone[1], db9_zone[0], 1.6]);
  color("Silver", 0.8)
    translate([-4, db9_cx - 19.3/2, db9_cz - 10.9/2]) cube([4 + t + eps, 19.3, 10.9]);
}

// ---- part selection ----------------------------------------------------
if (part == "front")            panel_front();
else if (part == "back")        panel_back();
else if (part == "left")        panel_left_cut();
else if (part == "right")       panel_right();
else if (part == "floor")       panel_floor();
else if (part == "lid")         panel_lid();
else if (part == "sheet")       sheet();
else if (part == "front_etch")  front_etch();
else if (part == "back_etch")   back_etch();
else if (part == "left_etch")   left_etch_cut();
else if (part == "floor_etch")  floor_etch();
else if (part == "sheet_etch")  sheet_etch();
else assembly();
