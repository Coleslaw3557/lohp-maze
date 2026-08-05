// CAMP SIGN PSU TERMINAL HOOD — laser-cut 6mm ply throughout (hood AND
// the DC board — one stock), xTool
// ========================================================================
// The ABI PA-WTHR-A (12V 500W rainproof, CL-500W class) keeps its own
// metal outdoor case — this part is NOT an enclosure around the PSU.
// It is a five-sided SLEEVE that slides over the TERMINAL END of the
// body and sticks out past the end face, making a connection chamber:
// every field cable lands on a connector in THIS hood's walls, short
// bench-made tails run from the connectors to the PSU's recessed screw
// terminals (9-pos strip: AC L/N/ground + 3x V+ / 3x V-, V-adjust pot
// beside it), and the four DC circuits fuse at a 4-way ATC blade block
// INSIDE the chamber (Tim 2026-08-02 — fuses live in the enclosure, not
// inline in the cables).
//
//   mouth (open)                                    end wall + DC BOARD
//     |  <- overlap: sleeve rides the body ->|<-- chamber -->|
//     |==== PSU body ====================[end face]  fuse    |[board]
//     |  (covered body vents breathe out the   block, AC dev |
//     |   open mouth + chamber -> side vents)      ≡ vents ≡ |
//
// THE DC CONNECTOR BOARD (2026-08-02, Tim): the sign connectors do NOT
// mount in the end wall itself — the end wall is a fixed MAIN FACEPLATE
// with per-connector cutouts + a pre-cut M3 grid, and a small separate
// BOARD carries the three connectors and screws onto the faceplate from
// outside. The board is expected to ITERATE (re-cut psu-hood-board.svg
// alone); the M3 grid in the faceplate is the fixed datum every revision
// re-registers against. (Deliberate exception to the no-fastener-holes
// house rule — iteration needs a repeatable pattern, same logic as the
// projector shroud's drill grids.)
//
// ONE CONNECTOR FAMILY, rev D (Tim 2026-08-02, parts ON HAND, his
// calipers): ALL FOUR DC circuits use the SAME part — SAE quick-connect
// flush-mount harness, integrated 10AWG pigtails. Body through the wood
// = 22.10 x 13.37; outer flange 50 x 21.62 with two screw holes (NO
// pre-cut screw holes — the flange is its own jig; the screws bite the
// 6mm board alone, the faceplate behind is open window). Flanges at 50
// wide don't fit the face side by side, so they mount ROTATED 90° — a
// row of FOUR vertical dominoes at 28 pitch (28, not 30: at 30 the
// outer flanges ride under the M3 heads). 10AWG pigtails mean the TRUNK
// keeps the plan's original 10AWG end-to-end.
//   LEGENDS @'L' 10A/14AWG · LOGO 5A/18AWG · TRUNK 20A/10AWG · BOX 2A
// BOX (rev D — was a BTF Ø8 in the left wall): the controller-box 2A
// feed rides the board like everything else; Tim converts SAE -> the
// box's existing BTF pigtail at the CONTROLLER-BOX end of that cable.
// The left wall is now bare except its vent slats.
// SAE POLARITY (minefield): wire hood V+ to each port's RECESSED
// terminal so nothing hot is exposed when unmated; verify every
// harness's molded polarity BEFORE landing tails.
//
// Orientation on the pillar (camp-sign-plan.md): PSU vertical, terminal
// end DOWN -> the hood is the bottom of the unit and the fan end + its
// louver stay fully in open air above. FLOOR = the back wall against
// the pillar plank; LID = the outward wide face (drop-in tray). The
// PSU's terminal-end mounting ear lands INSIDE the chamber flat on the
// floor: bolts through the ear's slots + the floor's matching cut slots
// + the pillar plank carry hood and PSU together. The fan-end ear gets
// the cut shim strip. A velcro one-wrap around the tube at the mouth
// holds lid + body (vertical drop-in lid — gravity doesn't).
//
// Joinery = node-enclosure.scad rev4 verbatim: 5-seg corner fingers
// (end wall owns segments 0,2,4), t-deep floor mortise tabs, drop-in
// lid into wall-top notches. The MOUTH has no wall — floor, lid and
// both side walls end flush and plain there (the PSU body is the
// fourth wall).
//
// CALIPER GATES before burning (Tim owns both PSUs — measure the real
// unit; numbers below are the Newegg listing + photo estimates):
//   psu_w / psu_t   body cross-section at the terminal end
//   overlap         slide-fit check (no pinch); the body's covered vent
//                   slots breathe via the open mouth + chamber side vents
//   ear_reach / ear_cs / ear_slot_*   the terminal-end ear's real slots
//   ac_* / sae_*    RESOLVED 2026-08-02 — both calipered by Tim (snap-in
//                   AC inlet 46.85 x 27.33; SAE body 22.10 x 13.37,
//                   flange 50 x 21.62)
//   fuse_zone_*     the purchased 4-way ATC block's footprint

part = "3d";     // end|left|right|floor|lid|board|shim|sheet|3d (+ *_etch)

t   = 6.0;       // 6mm stock for the HOOD (Tim 2026-08-02) — CALIPER THE
                 //  SHEET before burning: "6mm" ply runs 5.6-6.2 and
                 //  every joint, tab and wall position tracks t; set the
                 //  measured value and re-export (the node box's 07-21
                 //  lesson, and its 6mm detour's t-relative math is why
                 //  this is a one-line change). Cut the DC BOARD from
                 //  the SAME 6mm stock: the faceplate's big window means
                 //  the SAE flange screws bite the board ALONE, and 6mm
                 //  grips where 3mm wouldn't (the board's 2D file is
                 //  stock-agnostic — thickness is a bench choice)
eps = 0.01;
$fn = 48;

// ---- the PSU (CALIPER GATES) -------------------------------------------
psu_w   = 119.05;  // body width — CALIPERED (Tim 2026-08-02; the 5.0in
psu_t   = 54.03;   // body thickness — CALIPERED (listing said 127 x 58.4,
                   //  ~8mm oversize both ways — calipers win)
clr     = 3;       // slide clearance per side around the body
overlap = 65;      // sleeve length riding the body — GATE: dry slide-fit
chamber = 112;     // interior past the end face — grew 72->112 (08-02):
                   //  now holds the fuse block on the floor AND the AC
                   //  device's ~104mm yoke along the right wall
ear_reach = 28;    // ear plate protrusion past the end face — GATE
ear_slot_l = 14; ear_slot_w = 8;    // cut oversize; M4 + washers center
ear_cs  = [-47, 0, 47];             // slot centers across width — GATE

// ---- shell (derived — every position tracks t) -------------------------
Wi = psu_w + 2*clr;          // 133 interior width
W  = Wi + 2*t;               // 138.8 outer
Di = overlap + chamber;      // 177 interior length
D  = Di + t;                 // 179.9 outer — ONE end wall, mouth open
inner_h = psu_t + 3;         // 61.4 floor top -> lid underside
Hw = inner_h + 2*t;          // 67.2 wall height
ac_cz = Hw/2;                // shared mid-height for wall devices — MUST
                             //  precede m3_rows below: OpenSCAD resolves
                             //  top-level assignment RHS in file order,
                             //  and a forward ref = undef = silently
                             //  vanished M3 holes (caught by the zoomed
                             //  eyeball 08-02; sheet-scale looked "fine")

// ---- DC connector board on the end faceplate ----------------------------
// SAE flush-mounts, VERTICAL, row of three — on the BOARD only. The
// faceplate behind cuts ONE BIG WINDOW (Tim 2026-08-02: future boards may
// carry different ports — the faceplate never re-burns, the window passes
// whatever the next board mounts). Consequence: there is no faceplate
// wood behind the flanges anymore, so the flange screws bite the BOARD
// alone — cut the board from the same 6mm stock (the old 3mm rationale
// was SP21-specific and died with them), or use M3 machine screws + nuts
// through the flange holes. Board screws to the pre-cut M3 datum grid
// (4 corners); unscrew 4 M3s to swap the board.
sae_body_w = 22.10; sae_body_h = 13.37;  // pass-through body — CALIPERED
sae_flange_w = 50;  sae_flange_h = 21.62;// outer flange, 2 screw holes —
                                         //  part is its own jig, NO holes
sae_clr  = 0.6;                          // board cutout clearance
sae_pitch = 28;                          // FOUR vertical dominoes: span
                                         //  3x28+21.62 = 105.6 on the 130
                                         //  board -> 6.4 gaps, 1.2 clear
                                         //  of the M3 heads at the ends,
                                         //  outer bodies ±49 vs the
                                         //  window's ±52
board_w = 130; board_h = 64; // the removable board (own part + own SVG)
win_w = 104; win_h = 45;     // the faceplate's ONE window behind the
                             //  board — sized to the M3 grid, not to any
                             //  connector: grid at ±58/±28.5 keeps ≥4.3
                             //  of wood between each hole and the window
                             //  edge; the 130x64 board overlaps the
                             //  window ~10-13 per side. Move the grid ->
                             //  re-derive the window.
m3 = 3.4;                    // M3 clearance, board AND faceplate (datum)
m3_cols = [-58, 58];         // 4 screws at the board corners — the center
m3_rows = [ac_cz - 28.5,     //  column died with rev B (its heads would
           ac_cz + 28.5];    //  foul the middle flange); rows clear the
                             //  50-tall flanges, the notches and the
                             //  board edges at any t (t-derived)

// ---- AC on the RIGHT wall (moved off the end face for the board) --------
// "snapin" (default — RESOLVED 2026-08-02, Tim's calipers): the purchased
//   110V part is a SNAP-IN SINGLE panel-mount device — body
//   46.85 x 27.33 through the wall, outer screw lip landing on the
//   OUTSIDE face (lip holes = the part is its own jig, wood screws, no
//   pre-drill). Cutout passes the body with ~0.6 clearance.
//   THIS IS THE AC INPUT (Tim 2026-08-02 — the gland is deleted): the
//   generator cord plugs straight onto the face, its terminals tail
//   16AWG L/N/ground to the PSU's AC screws, and pulling the cord off
//   the face IS the accessible disconnect. (Sanity check at the bench:
//   the face must present BLADES, not slots, for the cord's female end
//   to mate — if it shows slots it's an outlet, shout before cutting.)
// "duplex"/"decora"/"inlet": kept for posterity (superseded readings of
//   the purchase; a NEMA yoke device or flanged inlet would cut here).
ac_style = "snapin";
ac_cut_w = 47.5; ac_cut_h = 28.0;             // 46.85 x 27.33 calipered
duplex_face_d = 35;  duplex_face_cc = 38.1;   // two outlet faces, hulled
yoke_cc  = 83.3;                              // 6-32 yoke screws c-c
decora_w = 67.3; decora_h = 33.5;
inlet_d  = 32;   inlet_screw_cc = 44;
ac_cx = 38;                  // device center along the wall — snapin
                             //  spans 14.25..61.75, near the front with
                             //  the other ports; side vents run behind it
                             //  (the left wall's BTF Ø8 died in rev D —
                             //  the BOX feed is SAE #4 on the board)

// ---- fuse block, floor of the chamber -----------------------------------
// 4-way ATC blade block + cover, fed from the PSU V+ screws (two 10AWG
// jumpers to a bussed block's stud, or one jumper per circuit into an
// independent block). Position clears the AC device's rear body (right
// wall, x>103) and the ear zone (y>84). GATE the real block's footprint.
fuse_zone_l = 88; fuse_zone_w = 46;
fuse_cx = 56; fuse_cy = 38;

// ---- side vents (Tim 2026-08-02: lid is SOLID; vents live on BOTH side
// walls in the chamber zone, behind the ports/receptacle). They ventilate
// the chamber (fuse block, terminal tails) and — via the ~3mm gap around
// the body — the PSU's covered terminal-end slots; the OPEN MOUTH is the
// other half of that path, so never foam/seal the mouth.
svent_n = 5; svent_l = 42; svent_h = 5; svent_pitch = 10;
svent_cx = 91;               // wall x center: behind the snapin/ports,
svent_z0 = 13;               //  short of the mouth-side tab band

// ---- joinery (node-enclosure.scad rev4) ---------------------------------
nseg = 5;  seg = Hw / nseg;  // end wall owns segments 0,2,4
ftab_w = 20;
long_T  = [25, Di/2, Di - 25];   // tab centers, ABSOLUTE from the end
                                 //  wall's inner face (the mouth edge has
                                 //  no wall, so node's shared-midline
                                 //  trick doesn't hold — one-wall offset)
short_cs = [-38, 38];            // end-edge tabs, about the width midline

module bottom_notches_abs(pos)               // wall coords: x=0 at end
  for (p = pos) translate([t + p - ftab_w/2, -eps])
    square([ftab_w, t + eps]);
module top_notches_abs(pos)
  for (p = pos) translate([t + p - ftab_w/2, Hw - t])
    square([ftab_w, t + eps]);
module oline(w, h, lw = 0.4)
  difference() { square([w, h], center = true);
                 square([w - 2*lw, h - 2*lw], center = true); }
module oring(d, lw = 0.4)
  difference() { circle(d = d); circle(d = d - 2*lw); }
module label(txt, size = 3.2)
  text(txt, size = size, halign = "center", valign = "center",
       font = "Liberation Sans:style=Bold");
module slot(l, w) hull()                      // stadium slot, l x w
  for (s = [-1, 1]) translate([s*(l - w)/2, 0]) circle(d = w);

// ---- end wall = the main faceplate ---------------------------------------
module panel_end() difference() {
  square([W, Hw]);
  for (s = [1, 3], x = [0, W - t])           // side walls' teeth land here
    translate([x - eps, s * seg]) square([t + 2*eps, seg]);
  for (c = short_cs) translate([W/2 + c - ftab_w/2, -eps])
    square([ftab_w, t + eps]);               // floor tabs
  for (c = short_cs) translate([W/2 + c - ftab_w/2, Hw - t])
    square([ftab_w, t + eps]);               // lid tabs
  translate([W/2, ac_cz])                    // ONE BIG WINDOW — the board
    square([win_w, win_h], center = true);   //  defines the ports, this
                                             //  wall just passes them
  for (cx = m3_cols, cz = m3_rows)           // the M3 datum grid (pre-CUT
    translate([W/2 + cx, cz]) circle(d = m3);//  on purpose — see header)
}

module end_etch() {                          // exterior face (symmetric
  translate([W/2, Hw - 6]) label("DC BOARD", 2.8);  // cut -> chirality-free)
}

// ---- the removable DC connector board (cut as its own job too) ----------
module panel_board() difference() {
  square([board_w, board_h]);
  for (i = [-1.5, -0.5, 0.5, 1.5])           // FOUR identical SAE ports,
    translate([board_w/2 + i*sae_pitch, board_h/2])    // vertical, snug
      square([sae_body_h + sae_clr, sae_body_w + sae_clr], center = true);
  for (cx = m3_cols, cz = m3_rows)           // matches the faceplate grid
    translate([board_w/2 + cx, cz - (ac_cz - board_h/2)]) circle(d = m3);
}

module board_etch() {                        // exterior face — words above
  words = ["LEGENDS", "LOGO", "TRUNK", "BOX"];   // the flanges, amps below
  amps  = ["@L 10A", "5A", "20A", "2A"];
  for (i = [0 : 3]) {
    translate([board_w/2 + (i - 1.5)*sae_pitch, board_h/2 + sae_flange_w/2 + 3.5])
      label(words[i], 2.5);
    translate([board_w/2 + (i - 1.5)*sae_pitch, board_h/2 - sae_flange_w/2 - 3.5])
      label(amps[i], 2.4);
  }
}

// ---- side walls ----------------------------------------------------------
// x = 0 at the END WALL'S OUTER FACE, x = D at the open mouth.
module panel_side() difference() {
  square([D, Hw]);
  for (s = [0, 2, 4])                        // end-wall edge only — the
    translate([-eps, s * seg])               //  mouth edge stays plain
      square([t + 2*eps, seg]);
  bottom_notches_abs(long_T);
  top_notches_abs(long_T);
  for (i = [0 : svent_n - 1])                // chamber vents, both walls
    translate([svent_cx, svent_z0 + i*svent_pitch + svent_h/2])
      square([svent_l, svent_h], center = true);
}

module panel_left() panel_side();            // bare wall — vents only.
                                             //  (The cord gland died with
                                             //  the snap-in AC inlet; the
                                             //  BOX BTF Ø8 died when the
                                             //  feed became SAE #4 on the
                                             //  board — both 08-02.)
// same one-sheet chirality fix as the node box: pre-mirror the left
// wall (moot while it carries no ports, kept for when one returns)
module panel_left_cut() translate([D, 0]) mirror([1, 0]) panel_left();
module left_etch_cut() {}                    // nothing to label

module panel_right() difference() {          // x runs end -> mouth
  panel_side();
  if (ac_style == "snapin")                  // body through, lip outside
    translate([ac_cx, ac_cz]) square([ac_cut_w, ac_cut_h], center = true);
  else if (ac_style == "duplex")
    translate([ac_cx, ac_cz]) hull()
      for (s = [-1, 1]) translate([s*duplex_face_cc/2, 0])
        circle(d = duplex_face_d);
  else if (ac_style == "decora")
    translate([ac_cx, ac_cz]) square([decora_w, decora_h], center = true);
  else                                       // flanged male inlet
    translate([ac_cx, ac_cz]) circle(d = inlet_d);
}
module right_etch() {
  if (ac_style != "snapin") {                // NEMA yoke / inlet marks;
    cc = ac_style == "inlet" ? inlet_screw_cc : yoke_cc;   // the snapin's
    for (s = [-1, 1])                        //  lip holes are unknown —
      translate([ac_cx + s*cc/2, ac_cz]) oring(4);  // part is its own jig
  }
  translate([ac_cx, 14]) label("120V IN", 3);
}

// ---- floor (the back wall, against the pillar plank) --------------------
// y = 0 at the end wall's INNER face, y = Di at the mouth.
module panel_floor() difference() {
  union() {
    square([Wi, Di]);
    for (p = long_T) {                       // side-wall mortise tabs
      translate([-t, p - ftab_w/2]) square([t + eps, ftab_w]);
      translate([Wi - eps, p - ftab_w/2]) square([t + eps, ftab_w]);
    }
    for (c = short_cs)                       // end-wall tabs; mouth: none
      translate([Wi/2 + c - ftab_w/2, -t]) square([ftab_w, t + eps]);
  }
  for (c = ear_cs)                           // terminal-end ear slots —
    translate([Wi/2 + c, chamber - ear_reach/2])   // bolts through ear +
      slot(ear_slot_l, ear_slot_w);          //  floor + pillar plank in
}                                            //  one go (GATE: real ear)

module floor_etch() {                        // interior face marks
  translate([Wi/2, chamber + (Di - chamber)/2])
    oline(psu_w, Di - chamber);              // body footprint to the mouth
  translate([Wi/2, chamber + 32]) label("ABI 500W BODY", 3);
  translate([Wi/2, chamber + 42]) label("TERMINAL END DOWN HERE", 2.2);
  translate([Wi/2 - 0.15, chamber - 1]) square([0.3, 2]); // end-face tick
  translate([Wi/2, chamber - ear_reach - 6]) label("EAR BOLTS", 2.5);
  translate([fuse_cx, fuse_cy]) oline(fuse_zone_l, fuse_zone_w);
  translate([fuse_cx, fuse_cy]) label("FUSES 4-WAY ATC", 2.8);
  translate([fuse_cx, fuse_cy - 8]) label("10 · 5 · 20 · spare", 2.2);
  translate([Wi/2, 8]) label("AC RIGHT WALL · DC OUT THE END BOARD", 2.2);
}

// ---- lid (drop-in tray, outward face; vent relief over the body) --------
module panel_lid() difference() {
  union() {
    square([Wi, Di]);
    for (p = long_T) {
      translate([-t, p - ftab_w/2]) square([t + eps, ftab_w]);
      translate([Wi - eps, p - ftab_w/2]) square([t + eps, ftab_w]);
    }
    for (c = short_cs)
      translate([Wi/2 + c - ftab_w/2, -t]) square([ftab_w, t + eps]);
  }
}                                            // lid is a PLAIN solid tray
                                             //  (08-02): vents live in the
                                             //  side walls, and the finger
                                             //  pull died too — the mouth
                                             //  edge is free, lift there

module lid_etch() {                          // exterior warning face
  translate([Wi/2, 16]) label("CAMP SIGN PSU", 4.5);
  translate([Wi/2, 26]) label("120V + 12V INSIDE", 3.2);
  translate([Wi/2, 34]) label("UNPLUG CORD — FUSES INSIDE", 2.5);
}

// ---- fan-end ear shim (same ply — keeps the body parallel to the plank)
module panel_shim() square([psu_w - 20, 36]);
module shim_etch() translate([(psu_w - 20)/2, 18]) label("FAN-END EAR SHIM", 2.8);

// ---- sheet ----------------------------------------------------------------
// ~372 x 316: fits the D1/S1 class beds; on a shorter bed (P2's 308mm)
// slide the shim beside the board in XCS — paths are loose objects.
module sheet() {
  panel_end();
  translate([0, Hw + 6]) panel_left_cut();
  translate([0, 2*Hw + 12]) panel_right();
  translate([0, 3*Hw + 18]) panel_board();
  translate([0, 3*Hw + board_h + 24]) panel_shim();
  translate([196, W + t]) rotate(-90) panel_floor();   // the two big plates
  translate([196, 2*W + t + 12]) rotate(-90) panel_lid();  // lie sideways
}
module sheet_etch() {
  end_etch();
  translate([0, Hw + 6]) left_etch_cut();
  translate([0, 2*Hw + 12]) right_etch();
  translate([0, 3*Hw + 18]) board_etch();
  translate([0, 3*Hw + board_h + 24]) shim_etch();
  translate([196, W + t]) rotate(-90) floor_etch();
  translate([196, 2*W + t + 12]) rotate(-90) lid_etch();
}

// ---- 3D preview ----------------------------------------------------------
// Same transform grammar as node-enclosure.scad's assembly(): end wall at
// y 0..t, mouth open toward +y, floor plane z 0..t. The DC board hovers
// off the faceplate with its three SP21 ghosts.
module assembly() {
  color("BurlyWood") translate([t, t, 0]) linear_extrude(t) panel_floor();
  color("Peru")      translate([0, t, 0]) rotate([90, 0, 0])
                       linear_extrude(t) panel_end();
  color("Sienna")    rotate([90, 0, 90]) linear_extrude(t) panel_left();
  color("Sienna")    translate([W - t, 0, 0]) rotate([90, 0, 90])
                       linear_extrude(t) panel_right();
  color("Tan", 0.85) translate([t, t, Hw - t + 14])          // hover = seat
                       linear_extrude(t) panel_lid();
  color("Chocolate") translate([W/2 - board_w/2, -14, ac_cz - board_h/2])
    rotate([90, 0, 0]) linear_extrude(t) panel_board();      // hover = seat
  color("Silver", 0.9) for (i = [-1, 0, 1])                  // SAE flange
    translate([W/2 + i*sae_pitch - sae_flange_h/2, -14 - t - 2,   // ghosts
               ac_cz - sae_flange_w/2])
      cube([sae_flange_h, 2, sae_flange_w]);
  // PSU ghost: body enters the mouth, end face at the chamber line, ear
  // plate lying on the floor over its slots, terminal recess dark
  color("Silver", 0.5) translate([t + clr, t + chamber, t])
    cube([psu_w, Di - chamber + 80, psu_t]);
  color("Gray", 0.6) translate([t + clr + 12, t + chamber - ear_reach, t])
    cube([psu_w - 24, ear_reach, 2]);
  color("DimGray", 0.9) translate([t + clr + 8, t + chamber + eps, t + 12])
    cube([psu_w - 16, 15, 24]);
  color("DarkSlateGray", 0.8)                                // fuse block
    translate([t + fuse_cx - fuse_zone_l/2, t + fuse_cy - fuse_zone_w/2, t])
      cube([fuse_zone_l, fuse_zone_w, 30]);
}

// ---- part selection -------------------------------------------------------
if      (part == "end")    panel_end();
else if (part == "left")   panel_left_cut();
else if (part == "right")  panel_right();
else if (part == "floor")  panel_floor();
else if (part == "lid")    panel_lid();
else if (part == "board")  panel_board();
else if (part == "shim")   panel_shim();
else if (part == "sheet")  sheet();
else if (part == "end_etch")   end_etch();
else if (part == "left_etch")  left_etch_cut();
else if (part == "right_etch") right_etch();
else if (part == "floor_etch") floor_etch();
else if (part == "lid_etch")   lid_etch();
else if (part == "board_etch") board_etch();
else if (part == "shim_etch")  shim_etch();
else if (part == "sheet_etch") sheet_etch();
else assembly();
