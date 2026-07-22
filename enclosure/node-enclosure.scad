// LoHP maze — universal room-node enclosure, LASER-CUT edition
// ============================================================
// ONE design for all 15 room nodes, cut on the xTool from 3mm ply (walls)
// + 3mm acrylic (window panel). Six finger-jointed panels GLUE together
// (floor mortises through the wall bottoms, corner fingers interlock);
// the LID is the service hatch — it SLIDES in and out OVER the SHORT
// front wall (wall top = channel bottom; 07-22 rev3 — the old full-height
// wall + entry mouth could never pass the lid's tongues), riding side
// tongues in through-slot channels (no fasteners; finger-pull notch at
// the front edge).
//
// Holds the standard node build: XIAO ESP32-S3 + PCM5102A DAC + the room's
// ranging sensor(s) against the window (LD2410C, VL53L1X, Cuddle's
// 2410C+2450 pair — the pair needs the WIDER aperture: cuddle=true below;
// export.py emits both jobs). Boards fix at their ETCHED footprint marks
// however works on the bench (VHB/screws); no fastener holes are pre-drilled
// (the PORT openings are pre-cut since 07-22).
// Board footprints + ply thickness measured on the real parts 2026-07-21.
//
// IO — ALL port openings CUT in every box (07-22 rev; labels + footprint
// marks stay on the etch layer -> score in XCS, so nothing text-like cuts):
//   left wall: DB9 A (CUT window) — the field IO for the traveling maze
//     (rapid setup: one premade straight-through M-F serial extension
//     cable per wired room, screw-terminal breakout shells at both ends —
//     nothing crimped or soldered in the FIELD; the bench solders freely).
//     UNIVERSAL PINOUT on every box, used or not: 1 = 5V, 2 = GND,
//     3-9 = signals 1-7. Per-room map in wiring-guides/db9-field-wiring.md.
//     Populated in the 7 wired rooms; the other 8 blank the open window
//     (tape/cover) against dust — one universal cut file for every room.
//   left wall: DMX OUT (CUT in every box) — XLR3 FEMALE panel jack on the
//     Neutrik D-size footprint; MAX485 inside -> its solder cups (a one-
//     time bench solder: 1=GND 2=Data- 3=Data+) -> a standard DMX cable
//     to the room's fixtures (wiring-guides/dmx-over-wifi.md). Replaced
//     the one-day DB9 "port B" + DB9->XLR adapter 2026-07-22 — a DMX
//     port should be a DMX port. Wall-mounted because plugs insert
//     horizontally — the 34mm interior can't take a vertical connector.
//     Dust caps/covers on playa.
//   right wall: USB-C slot (CUT — the XIAO's USB end butts this wall so
//     the port reaches through the slot) + AUX hole (CUT) — the DAC's OWN
//     3.5mm jack barrel sits behind it (board butts the wall); no separate
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
Hw = slide_z + slide_w + cap_h;  // SIDE/BACK wall height = outer height
                         //  (43.8 at t=2.9). The FRONT wall is SHORT —
                         //  its top edge sits at slide_z and the lid
                         //  slides in over it (rev3)
lid_w   = W - 2*t + 4.4; // side tongues ride 2.2mm into each side channel
lid_d   = D - t;         // front edge flush outside; back edge stops
                         //  against the back wall's inner face
lid_notch = 14;          // finger pull, front edge
cap_bridge = 3;          // side channel stops this short of the back wall
                         //  so the cap rail stays attached to the panel;
                         //  lid back tongues relieved cap_bridge+0.2

// ---- measured boards (calipers on the real parts, 2026-07-21) ----------
dac_l = 31.93;  dac_w = 17.23;  // PCM5102A; 3.5mm jack on a LONG edge (Tim
dac_cy = 51;                    //  07-22 — the short-edge note was wrong),
                                //  barrel +2.44 past the PCB -> the LONG
                                //  edge butts the right wall, board reaches
                                //  only 17.23 into the box, barrel fills
                                //  the AUX hole at dac_cy. Jack offset
                                //  along that edge unmeasured -> footprint
                                //  assumes centered; the cut hole is the
                                //  datum (barrel-in-hole locates the board,
                                //  screw down where it lands).
xiao_l = 21.46; xiao_w = 17.78; // XIAO ESP32-S3; USB-C on the SHORT (17.78)
xiao_cy = (D - 2*t)/2 - 18;     //  end, +2 past the PCB -> that END butts the
                                //  right wall, long axis into the box, port
                                //  out the CUT slot (07-22 rotate — the old
                                //  long-edge-to-wall pointed the USB into
                                //  the box). cy = the front floor-mortise
                                //  tab center (short_cs[0] = -18): the
                                //  17.78 board sits inside the 20 tab, so
                                //  the tab seams at the joint line the
                                //  board up on the bench
ld2410_w = 22.14; ld2410_h = 16;   // radar, sensor side faces the window
ld2450_w = 44.12; ld2450_h = 15.4; // Cuddle's second radar

// ---- features ----------------------------------------------------------
win_w = cuddle ? 68 : 56;         // aperture (68 fits 2450+2410C side by side)
win_h = 24;  win_cz = t + 17;     // aperture center height
panel_w = cuddle ? 82 : 70;  panel_h = 32;   // acrylic window panel
// window screws: 2x M2 self-tap ON THE MIDLINE near the panel ends — never
// the corners (corner screws leave <1mm acrylic web -> CRACKS). No etched
// positions; drill 2mm pilots through acrylic + ply on the bench
usb_w = 10; usb_h = 4;       // XIAO USB-C slot — CUT (07-22, was etch+bench)
usb_z = 3.7;                 // floor -> shell center (VHB 1 + PCB + shell/2)
jack_z = 6;                  // floor -> DAC jack barrel center (PCB + barrel
                             //  + solder stubs) — still an ESTIMATE but now
                             //  a pre-CUT hole (07-22): caliper the real
                             //  barrel height before burning a sheet; Ø9
                             //  vs the ~Ø8 plug sleeve leaves only ±0.5
jack_hole = 7;               // frames the DAC jack's barrel (~Ø6.75 — Tim
                             //  07-22: the port is ~75% of the old Ø9,
                             //  which over-cut). The plug's Ø3.5 shank
                             //  goes INSIDE the barrel; its molded boot
                             //  stops on the wall face — the plug body
                             //  never needs to pass the hole
// ---- left-wall ports: DB9 A (field IO) + the XLR DMX out ---------------
// ANMBEST B09WD2V37T calipered 2026-07-22: socket opening 16.5x7.92 (outer
// D shell = standard ~19.3x10.9), screwlock posts protrude 6.3 past the
// front face -> they PASS THROUGH the 2.9 ply and stand 3.4 proud outside
// for the cable thumbscrews. 9 pins + shell-GND terminal. MOUNT = BARE PCB
// screwed to the floor at its corner holes (Tim's call after inspection —
// plastic case OFF; it has no floor-mount provision). The wall opening
// only frames the face: a loose window, not a registration fit.
db9_cut_w = 20.3; db9_cut_h = 11.7;  // CUT window, every box (07-22 — was
                                     //  etch + bench-cut) for the outer D
                                     //  shell (loose — floor screws locate
                                     //  the part, not this opening)
db9_screw = 24.99;                   // screwlock pitch, nominal DE-9 (Tim
                                     //  measured 24.26 — likely hex-corner
                                     //  artifact): drill the marks Ø6 so
                                     //  the hex posts clear at either value
db9_cx = 22;                         // port A center (toward the front)
db9_cz = 12.2;                       // center height. MEASURED
                                     //  2026-07-22: floor 2.9 + 3.89 (PCB
                                     //  bottom -> shell bottom) + 5.45
                                     //  (half a std 10.9 shell). If the
                                     //  case ever goes back ON, this rises
                                     //  ~2 (case bottom wall)
db9_zone = [34, 31.75];              // floor keep-out at port A: along wall
                                     //  x depth-into-box. Depth = the bare
                                     //  PCB, 1-1/4" MEASURED 2026-07-22,
                                     //  D-sub barrel excluded (it lives in
                                     //  the wall). The old 52 was oversized
                                     //  headroom for a re-cased part
xlr_hole = 22.0;                     // XLR jack barrel hole, sized to the
                                     //  PART not the D-standard cutout
                                     //  (Tim 07-22: 24 was too big).
                                     //  Looked up: male XLR body ~Ø19-19.5
                                     //  (EIZZ listing: 19); the female
                                     //  nose just wraps it -> ~Ø21 on
                                     //  economy jacks (Devinal's 31x26x21).
                                     //  Ø22 = nose + slop, flange covers.
                                     //  CAVEAT: a TRUE Neutrik D female
                                     //  needs >Ø23.6 (their rear-mount
                                     //  drawing, ST-NC3FD-LX) — caliper on
                                     //  arrival is a HARD GATE: if the
                                     //  Devinal nose measures like a real
                                     //  D front, put this back to 24.
                                     //  Jacks = Devinal (amzn B07S6J8WVD),
                                     //  flange 31x26x21 per reseller specs,
                                     //  ships with NO screws — Tim drives
                                     //  short wood screws through the
                                     //  flange's own holes (a 19x24-diag
                                     //  pattern on genuine Neutrik; the
                                     //  jack is its own jig, so the clone's
                                     //  diagonal doesn't matter). NO cut
                                     //  fastener holes, per the house rule.
                                     //  CALIPER-VERIFY barrel Ø on arrival
                                     //  before cutting 15
xlr_cx = 56;                         // same wall spot the one-day "port B"
xlr_cz = 19;                         //  had; raised so barrel + flange clear
                                     //  the floor mortise below and the lid
                                     //  channel above
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

module label(txt, size = 3.2)
  text(txt, size = size, halign = "center", valign = "center",
       font = "Liberation Sans:style=Bold");

// ---- panels (2D) -------------------------------------------------------
module panel_front() difference() {
  // SHORT wall — top edge AT the channel bottom, the lid slides in over it
  // (rev3, replacing the full-height wall + entry mouth). Why: the lid's
  // tongues make it 108.6 wide, but a mouth can only ever span 104.2
  // before the top strip severs — and the wall's seg-4 corner fingers sit
  // exactly at channel height, so anything wider than the mouth can NEVER
  // cross the wall plane. The lid could not be inserted at all (Tim
  // caught it 07-22; 3D previews don't collision-check a sliding part —
  // walk the insertion kinematics). Short wall = the classic laser-cut
  // sliding-lid form. Above the seg-3 notch a 1.86-tall stub finger
  // remains at each end, filling the side wall's stub notch just below
  // the channel.
  square([W, slide_z]);
  corner_notches(W);                   // segs 1,3 — both below slide_z
  bottom_notches(W, long_cs);
  translate([W/2 - win_w/2, win_cz - win_h/2]) square([win_w, win_h]); // aperture
}

module front_etch() {                        // interior face marks
  translate([W/2, win_cz]) oline(panel_w, panel_h);  // acrylic window panel
  translate([10, win_cz]) label("SENSOR");           //  sits here
  // no screw marks (M2s on the midline by eye — see the window comment);
  // sensor footprints are etched on the WINDOW PANEL (window_etch), not
  // here — anything drawn inside the aperture lands on the cutout scrap
  // (caught 2026-07-22; the sensors VHB to the acrylic's inner face)
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

module panel_side() {          // common left/right: full-D
  difference() {
    square([D, Hw]);
    // back edge: full segs 0,2,4 — the back wall keeps full height
    for (s = [0, 2, 4])
      translate([D - t - eps, s * seg]) square([t + 2*eps, seg]);
    // front edge: segs 0,2 + only a STUB of seg 4 below the channel (the
    // front wall is short, rev3). The channel slot below cuts the
    // 36.9-40.2 band open to the front edge for the tongues; ABOVE it the
    // cap rail now runs clear to the front edge (this also closes the old
    // top-front corner void the full seg-4 notch used to leave)
    for (s = [0, 2])
      translate([-eps, s * seg]) square([t + 2*eps, seg]);
    translate([-eps, 4 * seg]) square([t + 2*eps, slide_z - 4*seg + eps]);
    bottom_notches(D, short_cs);
    // lid channel: open at the front edge (x=0, where the lid enters),
    // STOPS cap_bridge short of the back wall's inner face. That bridge
    // is what keeps the cap rail above the channel attached — the seg-4
    // corner notches sever the channel band at both ends, so a full-
    // length slot turns the rail into a loose stick (Tim caught it on
    // the 2D sheet 2026-07-22; the 3D preview renders islands in place).
    // The lid's back tongue corners are relieved to match.
    translate([-eps, slide_z]) square([D - t - cap_bridge + eps, slide_w]);
  }
}

module panel_left() difference() {               // x runs front->back
  panel_side();
  // the DMX out is a CUT in every box (dmx-over-wifi.md): XLR3 female
  // panel jack, D-size footprint — BARREL HOLE ONLY. No fastener holes
  // (house rule): the jack is its own jig — hold it in the hole, drive
  // wood screws through whichever flange diagonal the part has
  translate([xlr_cx, xlr_cz]) circle(d = xlr_hole);
  // DB9 A window — CUT in every box since 07-22 (was etched, opened on the
  // bench in the wired rooms). A loose frame only; the floor screws locate
  // the PCB. The screwlock Ø6s stay a bench drill from the real part's posts
  translate([db9_cx, db9_cz]) square([db9_cut_w, db9_cut_h], center = true);
}

module left_etch() {                             // x runs front->back
  translate([db9_cx, db9_cz + 12]) label("DB9", 3);   // the window = CUT now;
  translate([xlr_cx, xlr_cz + 14]) label("DMX", 2.8); //  labels score only
  // no screwlock marks: sit the breakout PCB in its floor zone, let the
  // posts touch the wall, mark the contact points, drill those Ø6 — the
  // real part beats the nominal 24.99 spacing (measured 24.26-ish)
}

module panel_right() difference() {              // x runs front->back
  panel_side();
  // USB + AUX are CUTS (07-22, was etch + bench-drill). The boards behind
  // register themselves: the XIAO's USB-C noses into the slot (PCB flush
  // on the wall), the DAC's own jack barrel fills AUX. Both sit over a
  // floor-mortise notch — the USB slot leaves only a ~1.7mm ply bridge
  // (AUX ~2.5 at Ø7) until the floor tab glues in behind — handle gently
  translate([t + xiao_cy, t + usb_z]) square([usb_w, usb_h], center = true);
  translate([t + dac_cy, t + jack_z]) circle(d = jack_hole);
}
module right_etch() {                            // x runs front->back
  translate([t + xiao_cy, t + 9]) label("USB", 2.8);   // holes = CUT layer;
  translate([t + dac_cy, t + 13]) label("AUX", 2.8);   //  labels score only
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
  // DB9-A breakout: bare PCB screwed to the floor in this zone (7 wired
  // rooms), face through the wall window; screw positions per the real
  // part (nothing pre-drilled, house rule)
  translate([db9_zone[1]/2, db9_cx - t]) oline(db9_zone[1], db9_zone[0]);
  translate([db9_zone[1]/2, db9_cx - t]) label("DB9 PCB", 2.8);
  translate([W - 2*t - dac_w/2, dac_cy]) oline(dac_w, dac_l);   // PCM5102A —
  translate([W - 2*t - dac_w/2, dac_cy]) label("DAC");          //  the LONG
                                                 //  jack edge butts the
                                                 //  right wall so the
                                                 //  barrel meets AUX
  translate([W - 2*t - xiao_l/2, xiao_cy]) oline(xiao_l, xiao_w);  // XIAO
  translate([W - 2*t - xiao_l/2, xiao_cy]) label("ESP32", 3);      //  (VHB),
}                                                //  USB END to the wall, the
                                                 //  port out the cut slot

module panel_lid() difference() {
  square([lid_w, lid_d]);
  // no front corner notches since rev3 — with the short front wall there
  // is no mouth to squeeze through, and the full-width front corners plug
  // the top-front corner columns against dust
  // back corner relief: the side channels stop cap_bridge short of the
  // back wall — clear the tongues past that, so the lid's center span
  // still seats against the back wall's inner face
  for (x = [-eps, lid_w - 2.4])
    translate([x, lid_d - cap_bridge - 0.2])
      square([2.4 + eps, cap_bridge + 0.2 + eps]);
  translate([lid_w/2, 0]) circle(d = lid_notch); // finger pull
}

module panel_window() difference() {             // cut this one in acrylic
  translate([-panel_w/2, -panel_h/2]) square([panel_w, panel_h]);
  // OPTIONAL ToF aperture — uncomment for Entrance/Exit/Guy Line/VMM
  // (940nm won't pass plain acrylic; radar rooms keep the panel solid)
  // square([16, 16], center = true);
}

module window_etch() {
  // sensor footprints: the sensor VHBs to THIS panel's inner face (tape at
  // the board edges, clear of the antennas), looking out the wall aperture
  if (cuddle) {                                  // the radar pair, side by side
    cud_t = ld2450_w + 1 + ld2410_w;
    translate([(ld2450_w - cud_t)/2, 0]) oline(ld2450_w, ld2450_h);
    translate([(cud_t - ld2410_w)/2, 0]) oline(ld2410_w, ld2410_h);
  } else {
    oline(ld2410_w, ld2410_h);                   // LD2410C footprint (11 rooms)
    oline(16, 16);                               // ToF aperture — the 4 ToF
  }                                              //  rooms cut this through
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
