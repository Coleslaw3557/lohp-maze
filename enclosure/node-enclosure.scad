// LoHP maze — universal room-node enclosure, LASER-CUT edition
// ============================================================
// ONE design for all 15 room nodes, cut on the xTool from 3mm ply (walls;
// t below is the caliper-gated real value — 2.9 measured)
// + 3mm acrylic (window panel). Six finger-jointed panels GLUE together
// (floor mortises through the wall bottoms, corner fingers interlock);
// the LID is the service hatch — a DROP-IN TRAY (07-24 rev4; the rev3
// sliding tray wedged on the real kit and is gone): it drops straight
// down, edge tabs landing in TOP notches on all four full-height walls,
// finger notch at the front edge to lift it, velcro dabs against wind.
// No fasteners.
// ETCH SIDES (07-24, Tim's kit came out wrong): one sheet burns every
// mark on the face-up side, and the chiral side walls FORCE where that
// face ends up — as-drawn, the left wall's etch landed INSIDE. The flat
// outputs now PRE-MIRROR the left wall (labels re-drawn un-mirrored) so
// DMX/DB9 land OUTSIDE like the right wall's USB/AUX. Symmetric panels
// are placed by the assembler: floor etch UP, front etch IN (the window
// outline), back etch OUT. Burn the sheet as imported — etch face up.
//
// Holds the standard node build: XIAO ESP32-S3 + PCM5102A DAC + the room's
// ranging sensor(s) against the window (LD2410C in 12 rooms, TOF200C in
// Entrance/Exit, Cuddle's single LD2450 — the 2410C left that box
// 2026-08-20 (tracking radar does presence too), so the aperture is back
// to standard width and only the window ETCH differs: cuddle=true below;
// export.py emits both jobs). A THIRD variant (sign=true, 07-29) is the
// CAMP SIGN controller box: same shell, sign parts only — XIAO S3 +
// MAX485 (DMX IN fallback) + 74AHCT125 (3x pixel data) + 12->5V buck;
// ports = XLR + 12V in (left), D1-D3 data out (back), USB + the storm
// button's BTN pigtail (right). Boards fix at their ETCHED footprint marks
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
//     Neutrik D-size footprint (Ø24 — caliper gate resolved 07-23, insert
//     measured 23.55); MAX485 inside — cup pigtails soldered once at the
//     bench (1=GND 2=Data- 3=Data+) land in its A/B screw terminal -> a
//     standard DMX cable to the fixtures (wiring-guides/dmx-over-wifi.md).
//     The module's floor footprint is etched behind the barrel. Replaced
//     the one-day DB9 "port B" + DB9->XLR adapter 2026-07-22 — a DMX
//     port should be a DMX port. Wall-mounted because plugs insert
//     horizontally — the 34mm interior can't take a vertical connector.
//     Dust caps/covers on playa.
//   right wall: USB-C slot (CUT — the XIAO's USB end butts this wall so
//     the port reaches through the slot; boot-sized 07-24 since the port
//     face sits ~0.9 recessed — the cable plug's overmold passes the
//     wall to seat) + AUX hole (CUT) — the DAC's OWN
//     3.5mm jack barrel sits behind it (board butts the wall); no separate
//     panel-mount jack. Antenna stays INSIDE the box — no hole.
//   front wall: sensor aperture; the acrylic window panel screws over it
//     (2x M2 self-tap on the midline). Radar sees through plain acrylic, so
//     11 of the 13 radar panels are solid; Entrance and Exit cut the marked
//     16x16 aperture through the panel (940nm won't pass acrylic). Those two
//     are the ONLY openings in the whole fleet.
//   back wall: two vertical velcro-strap slots (CUT — a 20mm one-wrap
//     threads through and wraps the scaffold leg).
//
// Export (SVG for xTool; kerf compensate in XCS if you want tight joints):
//   python3 export.py    # standard + cuddle variants, ply + acrylic jobs
//   part="3d" is the glued-up assembly preview.

part = "3d";     // front|back|left|right|floor|lid|window|sheet|3d
cuddle = false;  // true = Cuddle's one-off: LD2450 alone since 2026-08-20
                 //  (was 2450+2410C wide-aperture; the 2410C is dropped —
                 //  presence now derives from the 2450). Same box as
                 //  standard; only the window-panel etch differs.
sign = false;    // true = the CAMP SIGN controller box (one-off, 07-29):
                 //  same shell + joinery, sign port set — no sensor
                 //  window/acrylic, no DB9, no DAC/AUX, no strap slots
                 //  (it screws down inside the band cavity behind the
                 //  logo disc, not to a scaffold leg). XLR stays but is
                 //  DMX IN (the Dfi fallback), the left wall gains a 12V
                 //  feed hole, the back wall 4 pixel-data exits, the
                 //  floor a BUCK zone. cuddle + sign never both true.
                 //  wiring-guides/camp-sign-plan.md

// ---- stock -------------------------------------------------------------
t  = 2.9;        // ply thickness — back to 3mm stock (Tim 2026-07-24,
                 //  ending the one-day 6mm detour; the 07-24 dry-fit kit
                 //  was cut from this stock): 2.9 = the 07-21 caliper of
                 //  the "3mm" sheet. Re-caliper any NEW batch before
                 //  burning. Everything below derives from t —
                 //  db9_cx/db9_cz/xlr_cz/dac_cy stay t-relative (keep
                 //  them so; the 6mm episode proved why)
acrylic_t = 3;   // window stock, nominal (preview + screw length only)
kerf_note = "cut outlines are exact; add kerf offset in xTool XCS";

// ---- box (outer) -------------------------------------------------------
W  = 110;        // width  (front/back length)
D  = 78;         // depth  (left/right length)
inner_h = 34;    // interior height (floor top -> lid underside)

// ---- drop-in lid (rev4 2026-07-24) -------------------------------------
// The rev3 sliding tray is DEAD — it wedged on the real 07-24 kit.
// Post-mortem: 0.4mm channel clearance vs diode-kerf taper + 3mm-ply
// bow; a 108.6-wide lid guided by 2.2mm tongues racks and wedges under
// any off-center pull; and the cap rail above each through-slot channel
// was a 72mm stick anchored by one 3mm bridge — the first wedged lid
// pries it. rev4: every wall runs full height, the lid is a floor-twin
// that drops STRAIGHT DOWN, its edge tabs landing in matching top
// notches on all four walls. Nothing threads, nothing racks, nothing
// cantilevers. Velcro dabs (strap stash) on the front tab shelves hold
// it against wind; the finger notch lifts it out.
Hw = 2*t + inner_h;      // wall height = outer height (39.8 at t=2.9);
                         //  the lid sits IN the walls, top face flush,
                         //  underside at Hw-t = inner_h above the floor
lid_notch = 14;          // finger pull, front edge center
lid_front_cs = [-32, 32];  // front-edge lid tabs skip the center so the
                           //  finger notch owns it; the back edge keeps
                           //  all of long_cs, the sides keep short_cs

// ---- measured boards (calipers on the real parts, 2026-07-21) ----------
dac_l = 31.93;  dac_w = 17.23;  // PCM5102A; 3.5mm jack on a LONG edge
dac_cy = (D - 2*t)/2 + 15;      //  (confirmed at the 07-24 dry-fit) —
dac_jack_off = 10;              //  but NOT centered on it: the barrel
                                //  sits ~10mm off the board center toward
                                //  one end (Tim 07-24: the cut hole was
                                //  "about 10mm too far"; the old footprint
                                //  assumed centered). The AUX hole cuts at
                                //  dac_cy + dac_jack_off — MOUNT THE BOARD
                                //  JACK-END TOWARD THE BACK to match, and
                                //  CALIPER the exact offset before the
                                //  next burn. Footprint etch stays at
                                //  dac_cy (board center); the cut hole is
                                //  the datum (barrel-in-hole locates the
                                //  board, screw down where it lands).
                                //  Barrel +2.44 past the PCB -> the LONG
                                //  edge butts the right wall, board
                                //  reaches only 17.23 into the box.
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
ld2450_w = 44.12; ld2450_h = 15.4; // Cuddle's radar (tracking + presence;
                                   //  sole radar there since 2026-08-20)
rs485_l = 49.22; rs485_w = 14.05;  // MAX485 breakout — the room's DMX
                                   //  driver. RECEIVED batch 2026-07-23 =
                                   //  the screw-terminal variant: the A/B
                                   //  screw terminal sits ON TOP above the
                                   //  VCC/B/A/GND header end (07-24 photo
                                   //  fix — the first verbal note had the
                                   //  ends flipped); RO/RE/DE/DI at the
                                   //  far end. Both 4P headers come
                                   //  factory-soldered PINS DOWN — no flat
                                   //  belly to VHB until the bench pulls
                                   //  or flush-clips them (dmx-over-wifi.md)
ahct_l = 21; ahct_w = 10;          // 74AHCT125, bare PDIP-14 over the legs
                                   //  (Tim 07-23) — NFM's dead-bug shifter;
                                   //  the SIGN box dead-bugs its own here
                                   //  (4 pixel-data buffers -> back holes)

// ---- camp-sign variant (sign = true; wiring-guides/camp-sign-plan.md) ---
buck_l = 47; buck_w = 27;    // DIANN 12->5V 3A buck — CONFIRMED by Tim
                             //  2026-07-29: body exactly 47 x 27. The
                             //  screw-terminal blocks OVERHANG the 47 at
                             //  BOTH ends (length unmeasured — this zone
                             //  marks the BODY only), wire entries low at
                             //  the ends. 12V IN pair on one end, 5V OUT
                             //  pair on the other: MOUNT THE 12V END
                             //  TOWARD THE LEFT WALL's hole, 5V end
                             //  toward the XIAO's 5V pin + AHCT VCC
buck_cx = 37.5; buck_cy = 17;// body center, front-left quarter: left
                             //  edge 14 off the wall = room for the
                             //  IN-end terminal overhang + a straight
                             //  wire shot from the Ø8 hole into the
                             //  screws (pre-confirmation cx=26 left only
                             //  2.5 — nothing for the overhang). Right
                             //  edge 61: OUT-end block ends ~14 clear of
                             //  the XIAO footprint at 82.7
pwr_hole = 8;                // 12V feed: a BTF 2-pin pigtail's bare ends
pwr_cx = 18; pwr_cz = t + 9; //  thread IN through this hole (connector
                             //  stays outside — the PSU run plugs into
                             //  it), zip-tie inside as strain relief.
                             //  Left wall, roughly where the DB9 window
                             //  would be; feeds the buck IN end
data_hole = 7;               // 3x pixel-data exits, BACK wall: a BTF
data_cs = [-24, 0, 24];      //  3-pin pigtail threads out each (its red
data_cz = t + 10;            //  +12V lead is DEAD inside the box — data +
                             //  GND only; group power comes from the
                             //  pillar fuse blocks, NEVER through this
                             //  box). Offsets about W/2, deliberately
                             //  SYMMETRIC: a flipped back wall lands the
                             //  same holes, only the label order mirrors
                             //  (cosmetic — pigtail-to-channel pairing
                             //  happens inside at the AHCT zone, which
                             //  sits right in front of these holes)
data_words = ["LEGENDS OF THE (e)", "LOGO",
              "HIDDEN PLAYA (H)"];
                             // 07-29 REGROUP v2 (Tim, superseding the
                             //  same-day 4-group split): THREE chains —
                             //  D1 = Legends+of+the (data enters at 'e',
                             //  the center end), D2 = the logo field
                             //  ALONE (the removable disc unplugs
                             //  without touching a letter chain), D3 =
                             //  Hidden+Playa (enters at 'H'). Power =
                             //  three matching runs landing ONLY at
                             //  word fronts/backs ('L' / the disc /
                             //  'a' — Tim: 12V is forgiving over these
                             //  lengths, no mid-word entries). Each word
                             //  etches UNDER its hole so the wirer
                             //  reads the wall; pitch 24 (16 collided —
                             //  render-MEASURE text, font-math lies).
                             //  LEGENDS OF THE (e) ~30 wide: gaps to
                             //  LOGO ~6, LOGO to HIDDEN PLAYA ~8, ok
btn_hole = 7;                // storm-button pigtail exit, RIGHT wall: a
btn_cx = 45; btn_cz = t + 10;//  BTF 3-pin threads out to the LIT arcade
                             //  button on the sign scaffolding; inside,
                             //  signal -> XIAO D3 (GPIO4, INPUT_PULLUP),
                             //  red +5V (buck) -> lamp always lit, white
                             //  -> shared GND (lamp- + switch COM). The
                             //  XIAO sits against this wall.
                             //  Press = POST /api/sign_storm (maze-wide
                             //  Lightning + thunder everywhere at once);
                             //  the SERVER owns the 30s cooldown
                             //  (main.py SIGN_STORM_COOLDOWN_S)

// ---- features ----------------------------------------------------------
win_w = 56;                       // aperture — standard for ALL rooms since
                                  //  2026-08-20: Cuddle's lone LD2450 (44.12
                                  //  wide) fits; the 68 was only for the
                                  //  retired 2450+2410C pair
win_h = 24;  win_cz = t + 17;     // aperture center height
panel_w = 70;  panel_h = 32;      // acrylic window panel (Cuddle rejoined
                                  //  the standard panel size 2026-08-20)
// window screws: 2x M2 self-tap ON THE MIDLINE near the panel ends — never
// the corners (corner screws leave <1mm acrylic web -> CRACKS). No etched
// positions; drill 2mm pilots through acrylic + ply on the bench
usb_w = 13; usb_h = 7;       // XIAO USB-C slot — CUT (07-22, was etch+bench).
                             //  07-24 upsize (was 10x4, shell-only): the
                             //  shell reaches just +2 into the 2.9 ply, so
                             //  the port face sits ~0.9 RECESSED and the
                             //  CABLE PLUG's overmold must enter the slot
                             //  to seat. Sized for a common boot (<=12 x
                             //  6.5 — caliper YOUR cable), centered on the
                             //  shell; the slot now runs INTO the floor-
                             //  mortise notch below (see panel_right)
usb_z = 3.7;                 // floor -> shell center (VHB 1 + PCB + shell/2)
jack_z = 6;                  // floor -> DAC jack barrel center (PCB + barrel
                             //  + solder stubs) — still an ESTIMATE but now
                             //  a pre-CUT hole (07-22): caliper the real
                             //  barrel height before burning a sheet; Ø9
                             //  vs the ~Ø8 plug sleeve leaves only ±0.5
jack_hole = 9;               // AUX opened 7->9 (Tim 2026-08-01): clears the
                             //  ~Ø8 molded plug sleeve instead of framing
                             //  the Ø6.75 barrel (the 07-22 Ø7 rev), so the
                             //  plug body may enter the wall. No longer a
                             //  snug barrel frame — the etched floor
                             //  footprint locates the board now. NB the fab
                             //  master for the BASE room box is
                             //  node-enclosure-jen.svg (Jen's Illustrator
                             //  redraw, already edited to Ø9); this file
                             //  still renders the -sign/-cuddle variants —
                             //  keep the two in sync
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
db9_cx = t + 18;                     // port A center (toward the front) —
                                     //  t-relative since the 6mm switch:
                                     //  centers the 34-long floor zone at
                                     //  interior y 18 so it keeps 1mm off
                                     //  the front wall's inner face (the
                                     //  old hardcoded 22 collided at t=6)
db9_cz = t + 9.34;                   // center height = floor top + the
                                     //  MEASURED 2026-07-22 stack: 3.89
                                     //  (PCB bottom -> shell bottom) +
                                     //  5.45 (half a std 10.9 shell). If
                                     //  the case ever goes back ON, this
                                     //  rises ~2 (case bottom wall)
db9_zone = [34, 31.75];              // floor keep-out at port A: along wall
                                     //  x depth-into-box. Depth = the bare
                                     //  PCB, 1-1/4" MEASURED 2026-07-22,
                                     //  D-sub barrel excluded (it lives in
                                     //  the wall). The old 52 was oversized
                                     //  headroom for a re-cased part
xlr_hole = 24.0;                     // XLR jack barrel hole. CALIPER GATE
                                     //  RESOLVED 2026-07-23: the received
                                     //  Devinal's circular insert measures
                                     //  Ø23.55 — true-D class (Neutrik's
                                     //  rear-mount drawing wants >Ø23.6),
                                     //  not the ~Ø21 economy nose the 07-22
                                     //  guess assumed; it would not pass
                                     //  the old Ø22 at all. Ø24 = the
                                     //  D-standard cutout, 0.45 diametral
                                     //  clearance before kerf; the flange
                                     //  (31x26, rests on the OUTSIDE face)
                                     //  still covers with >=1mm bearing on
                                     //  its narrow axis.
                                     //  Jacks = Devinal (amzn B07S6J8WVD),
                                     //  ship with NO screws — Tim drives
                                     //  short wood screws through the
                                     //  flange's own holes (the jack is
                                     //  its own jig, so the clone's hole
                                     //  diagonal doesn't matter). NO cut
                                     //  fastener holes, per the house rule.
xlr_cx = 56;                         // same wall spot the one-day "port B"
xlr_cz = t + 16;                     //  had; t-relative so the Ø24 hole
                                     //  keeps ~4mm of ply above the floor
                                     //  mortise notch below it (a fixed 19
                                     //  left a 1mm ligament at t=6) and
                                     //  sits well below the wall-top lid
                                     //  notches
// 07-24 dry-fit rearrange (Tim, from the photo): the MAX485 lane moves
// FORWARD off the jack's centerline — 2mm behind the DB9 floor zone —
// and its terminal end backs off to 7mm behind the jack's ~19mm rear
// reach, so the cup pigtails bend clear of the cups. Flat mounting holds
// (no on-its-side needed). The freed back-center gets the AHCT zone.
rs485_x0 = 26;                       // terminal-end x (from the left wall)
rs485_cy = db9_cx - t + db9_zone[0]/2 + 2 + rs485_w/2;  // = 44 at t=2.9
ahct_cx = 44.5; ahct_cy = 62;        // 74AHCT125 dead-bug zone (NFM only),
                                     //  back-center: 6mm behind the RS485
                                     //  lane, 5mm off the back wall, far
                                     //  from the DAC
strap_w = 5; strap_h = 24;   // velcro-strap slots (back wall, vertical: a
                             //  20mm one-wrap passes horizontally around a
                             //  scaffold leg and through both)
// ---- joinery -----------------------------------------------------------
nseg = 5;                    // corner finger segments over Hw
seg  = Hw / nseg;            // front/back own segments 0,2,4 at the corners
                             //  (the rev3 stub-finger special case died
                             //  with the sliding lid — all four joints
                             //  are plain 5-seg alternation again)
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

module top_notches(len, centers)             // the lid's tabs land here
  for (c = centers) translate([len/2 + c - ftab_w/2, Hw - t])
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
  // full height again (rev4): the drop-in lid needs no channel and no
  // short wall, so the rev3 mouth/stub gymnastics are gone. (Kept lesson:
  // walk the insertion kinematics of any moving part — 3D previews don't
  // collision-check them. The drop-in lid's kinematics are one straight
  // vertical translation, which cannot bind.)
  square([W, Hw]);
  corner_notches(W);                   // segs 1,3
  bottom_notches(W, long_cs);
  top_notches(W, lid_front_cs);        // lid tabs; center stays solid — the
                                       //  finger notch dips over it
  if (!sign)                           // sign box has no sensor: solid wall
    translate([W/2 - win_w/2, win_cz - win_h/2]) square([win_w, win_h]); // aperture
}

module front_etch() {                        // node: interior face marks
  if (sign)
    // sign: EXTERIOR face — the wall is solid (no window), so it carries
    // the box ID instead; 16 near-identical boxes want telling apart
    translate([W/2, Hw/2]) label("CAMP SIGN", 6);
  else {
    translate([W/2, win_cz]) oline(panel_w, panel_h);  // acrylic window panel
    translate([10, win_cz]) label("SENSOR");           //  sits here
    // no screw marks (M2s on the midline by eye — see the window comment);
    // sensor footprints are etched on the WINDOW PANEL (window_etch), not
    // here — anything drawn inside the aperture lands on the cutout scrap
    // (caught 2026-07-22; the sensors VHB to the acrylic's inner face)
  }
}

module panel_back() difference() {
  square([W, Hw]);
  corner_notches(W);
  bottom_notches(W, long_cs);
  top_notches(W, long_cs);                       // lid tabs, all three
  if (sign)                                      // 4x pixel-data pigtail
    for (c = data_cs)                            //  exits — right behind
      translate([W/2 + c, data_cz])              //  the AHCT zone inside
        circle(d = data_hole);
  else
    for (c = [-27, 27])                          // velcro strap slots
      translate([W/2 + c - strap_w/2, (34 - strap_h)/2 + t])
        square([strap_w, strap_h]);
}

module back_etch() {
  if (sign)                                      // labels face OUT (doc'd):
    for (i = [0 : len(data_cs) - 1]) {           //  D-number above each
      translate([W/2 + data_cs[i], data_cz + 9]) //  hole, its chain word +
        label(str("D", i + 1), 2.8);             //  connection letter
      translate([W/2 + data_cs[i], data_cz - 7]) //  below (07-29) — the
        label(data_words[i], 2);                 //  wirer reads the wall,
    }                                            //  not the docs
  else
    translate([W/2, 19]) label("VELCRO", 2.8);   // strap between the slots
}

module panel_side() {          // common left/right: full-D, full height —
  difference() {               //  rev4 deleted the channel, the cap rail
    square([D, Hw]);           //  and the stub special case; both vertical
    // front + back edges: plain 5-seg joints, front/back walls own 0,2,4
    for (s = [0, 2, 4], x = [0, D - t])
      translate([x - eps, s * seg]) square([t + 2*eps, seg]);
    bottom_notches(D, short_cs);
    top_notches(D, short_cs);  // lid tabs
  }
}

module panel_left() difference() {               // x runs front->back
  panel_side();
  // the DMX port is a CUT in every box (dmx-over-wifi.md): XLR3 female
  // panel jack, D-size footprint — BARREL HOLE ONLY. No fastener holes
  // (house rule): the jack is its own jig — hold it in the hole, drive
  // wood screws through whichever flange diagonal the part has.
  // Room boxes: DMX OUT (MAX485 drives the fixtures). Sign box: DMX IN —
  // the Dfi RX's male stick (or the packed fallback cable, via adapter)
  // plugs in; same jack, same A/B screw landing, module just receives
  translate([xlr_cx, xlr_cz]) circle(d = xlr_hole);
  if (sign)
    // 12V feed hole — the BTF 2-pin pigtail threads in to the buck's IN
    // end (zone right behind this wall); connector half stays outside
    translate([pwr_cx, pwr_cz]) circle(d = pwr_hole);
  else
    // DB9 A window — CUT in every box since 07-22 (was etched, opened on the
    // bench in the wired rooms). A loose frame only; the floor screws locate
    // the PCB. The screwlock Ø6s stay a bench drill from the real part's posts
    translate([db9_cx, db9_cz]) square([db9_cut_w, db9_cut_h], center = true);
}

// FLAT outputs pre-mirror the left wall (07-24 label-side fix): the two
// side walls are chiral twins cut from one same-side-up sheet, so one of
// them must show its etch face inward once assembled — and as-drawn that
// was the LEFT wall, hiding DMX/DB9 inside the box. Mirroring the cut
// flips its etch face to the EXTERIOR; the labels are then re-drawn
// UN-mirrored at mirrored positions so the text reads correctly outside.
// (assembly() keeps the un-mirrored panel_left: the physical mirrored
// part, flipped over during glue-up, lands exactly there.)
module panel_left_cut() translate([D, 0]) mirror([1, 0]) panel_left();

module left_etch_cut() {                         // x runs BACK->front
  if (sign)                                               // holes = CUT;
    translate([D - pwr_cx, pwr_cz + 10]) label("12V", 2.8); //  labels score
  else
    translate([D - db9_cx, db9_cz + 12]) label("DB9", 3);
  translate([D - xlr_cx, xlr_cz + 14]) label("DMX", 2.8);
  // no screwlock marks: sit the breakout PCB in its floor zone, let the
  // posts touch the wall, mark the contact points, drill those Ø6 — the
  // real part beats the nominal 24.99 spacing (measured 24.26-ish)
}

module panel_right() difference() {              // x runs front->back
  panel_side();
  // USB + AUX are CUTS (07-22, was etch + bench-drill). The boards behind
  // register themselves: the XIAO's USB-C noses into the slot (PCB flush
  // on the wall), the DAC's jack barrel centers in AUX. Both sit over a
  // floor-mortise notch. The 07-24 boot-sized USB slot would leave a
  // 0.2mm bridge over its notch — kerf dust — so it deliberately merges
  // with the notch instead: one keyhole opening, and the glued floor
  // tab's top edge becomes the slot's bottom sill (13 wide inside the
  // 20 tab, so the sill is solid tab). AUX keeps a ~1.5 bridge at Ø9
  // (was ~2.5 at Ø7) — handle that one gently until the floor glues in
  translate([t + xiao_cy - usb_w/2, t - 0.5])
    square([usb_w, usb_z + usb_h/2 + 0.5]);
  if (!sign)                                     // no DAC on the sign box
    translate([t + dac_cy + dac_jack_off, t + jack_z]) circle(d = jack_hole);
  else                                           // storm-button pigtail exit
    translate([btn_cx, btn_cz]) circle(d = btn_hole);
}
module right_etch() {                            // x runs front->back
  translate([t + xiao_cy, t + 9]) label("USB", 2.8);   // holes = CUT layer;
  if (!sign)                                           //  labels score only
    translate([t + dac_cy + dac_jack_off, t + 13]) label("AUX", 2.8);
  else {
    translate([btn_cx, btn_cz + 9]) label("BTN", 2.8);
    translate([btn_cx, btn_cz - 7]) label("STORM", 2);
  }
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
  if (!sign) {
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
  } else {
    // DIANN buck in the freed front-left quarter (dims confirmed 07-29):
    // zone = the 47x27 BODY — the end terminal blocks overhang the line
    // both sides. 12V end toward the left wall's hole, 5V end dresses
    // along the front wall to the XIAO's 5V pin + AHCT VCC
    translate([buck_cx, buck_cy]) oline(buck_l, buck_w);
    translate([buck_cx, buck_cy]) label("BUCK", 2.8);
  }
  translate([W - 2*t - xiao_l/2, xiao_cy]) oline(xiao_l, xiao_w);  // XIAO
  translate([W - 2*t - xiao_l/2, xiao_cy]) label("ESP32", 3);      //  (VHB),
                                                 //  USB END to the wall, the
                                                 //  port out the cut slot
  // MAX485 (every room — the DMX driver): long axis INTO the box, lane
  // 2mm behind the DB9 zone, terminal END toward the jack at rs485_x0
  // (the A/B label marks it) — 7mm clear of the XLR's ~19mm rear reach so
  // the cup pigtails bend without fouling the cups (07-24 dry-fit).
  // Photo-corrected ends: VCC/B/A/GND header AT the terminal end (5V/GND
  // dress back along the wall), RO/RE/DE/DI at the far end (DI + the
  // DE/RE tie head toward the XIAO). Pins-DOWN headers: pull or
  // flush-clip at the bench, then VHB flat here — dmx-over-wifi.md
  translate([rs485_x0 + rs485_l/2, rs485_cy]) oline(rs485_l, rs485_w);
  translate([rs485_x0 + rs485_l/2, rs485_cy]) label("RS485", 2.8);
  translate([rs485_x0 - 6, rs485_cy]) label("A/B", 2.2);
  // 74AHCT125: dead-bug legs-up in this zone. NFM's truck-lamp shifter
  // (recipe in wiring-guides/room-games-plan.md) — and the SIGN box's
  // pixel-data buffer (3 channels + series resistors at the chip,
  // straight out the D1-D3 back holes behind it; the unused input ties
  // to GND); other rooms leave empty
  translate([ahct_cx, ahct_cy]) oline(ahct_l, ahct_w);
  translate([ahct_cx, ahct_cy]) label("AHCT", 2.5);
}

module panel_lid() difference() {
  union() {                                      // a floor-twin: drops in
    square([W - 2*t, D - 2*t]);                  //  from above, tabs on all
    for (c = lid_front_cs)                       //  four edges landing in
      translate([(W - 2*t)/2 + c - ftab_w/2, -t]) square([ftab_w, t + eps]);
    for (c = long_cs)                            //  the walls' top notches
      translate([(W - 2*t)/2 + c - ftab_w/2, D - 2*t - eps]) square([ftab_w, t + eps]);
    for (c = short_cs) {
      translate([-t, (D - 2*t)/2 + c - ftab_w/2]) square([t + eps, ftab_w]);
      translate([W - 2*t - eps, (D - 2*t)/2 + c - ftab_w/2]) square([t + eps, ftab_w]);
    }
  }
  translate([(W - 2*t)/2, 0]) circle(d = lid_notch); // finger pull — dips
}                                                //  over the front wall's
                                                 //  solid top-edge center

module panel_window() difference() {             // cut this one in acrylic
  translate([-panel_w/2, -panel_h/2]) square([panel_w, panel_h]);
  // ToF aperture — uncomment for ENTRANCE and EXIT only (940nm won't pass
  // plain acrylic). The other 13 rooms are radar and keep the panel solid.
  // Guy Line/VMM are radar too as of 2026-07-30 — they do NOT need this.
  // square([16, 16], center = true);
}

module window_etch() {
  // sensor footprints: the sensor VHBs to THIS panel's inner face (tape at
  // the board edges, clear of the antennas), looking out the wall aperture
  if (cuddle) {                                  // LD2450 alone (2026-08-20)
    oline(ld2450_w, ld2450_h);
  } else {
    oline(ld2410_w, ld2410_h);                   // LD2410C footprint (12 rooms)
    oline(16, 16);                               // ToF aperture — Entrance +
  }                                              //  Exit cut this through
}

// ---- paper test-fit net (PRINT 1:1 — not a cut job) --------------------
// Floor body flanked by both side walls, unfolded flat at their fold
// lines (the red etch lines). Print on paper, cut the outline, fold each
// wall UP at its red line: every port cut then stands at its TRUE height
// above the floor top and TRUE front-back position — sit the real boards
// on their etched footprints and check the DAC barrel meets AUX, the DB9
// face meets its window, the XIAO's USB-C meets the slot.
// Geometry notes that make the fold honest:
//   * the wall strip below the floor-top line (bottom mortise notches,
//     y < t) is clipped off, and the floor's tabs are omitted — the fold
//     line IS the floor plane, so heights need no mental +t
//   * folding puts the printed face INWARD, so each wall appears as its
//     interior view: panel_left as-drawn already is (that's the whole
//     07-24 mirror saga); panel_right (drawn = exterior) gets mirrored
module wall_above_floor()                      // drop the sub-floor strip
  intersection() { children(); translate([-1, t]) square([D + 2, Hw]); }

module testfit() {                             // shared edges union away —
  square([W - 2*t, D - 2*t]);                  //  the fold lines live on
  translate([t, -t]) rotate(90)                //  the etch layer instead
    wall_above_floor() panel_left();
  translate([W - 3*t, -t]) rotate(90) mirror([0, 1])
    wall_above_floor() panel_right();
}

module testfit_etch() {
  floor_etch();
  for (x = [0, W - 2*t])                       // the fold lines
    translate([x - 0.15, -t]) square([0.3, D]);
  translate([(W - 2*t)/2, 6]) label("FRONT", 3);
  // wall labels re-drawn upright in page coords (the panel transforms
  // would rotate/mirror the originals): page X = t - y_wall on the left,
  // W - 3t + y_wall on the right; page Y = x_wall - t on both
  translate([t - db9_cz - 12, db9_cx - t]) label("DB9", 3);
  translate([t - xlr_cz - 14, xlr_cx - t]) label("DMX", 2.8);
  translate([W - 2*t + 9, xiao_cy]) label("USB", 2.8);
  translate([W - 2*t + 13, dac_cy + dac_jack_off]) label("AUX", 2.8);
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
  translate([W + 12, 0])   panel_left_cut();
  translate([W + 12, Hw + 6]) panel_right();
  translate([W + 12 + t, 2*Hw + 12 + t]) panel_lid();
}

module sheet_etch() {
  front_etch();
  translate([0, Hw + 6])       back_etch();
  translate([t, 2*Hw + 12 + t]) floor_etch();
  translate([W + 12, 0])   left_etch_cut();
  translate([W + 12, Hw + 6]) right_etch();
}

module assembly() {
  color("BurlyWood") translate([t, t, 0]) linear_extrude(t) panel_floor();
  color("Peru")      translate([0, t, 0]) rotate([90, 0, 0]) linear_extrude(t) panel_front();
  color("Peru")      translate([0, D, 0]) rotate([90, 0, 0]) linear_extrude(t) panel_back();
  color("Sienna")    rotate([90, 0, 90]) linear_extrude(t) panel_left();
  color("Sienna")    translate([W - t, 0, 0]) rotate([90, 0, 90]) linear_extrude(t) panel_right();
  color("Tan", 0.85)                              // lid hovering above its
    translate([t, t, Hw - t + 14]) linear_extrude(t) panel_lid();  // seat
  if (!sign)                                      // sign box: no window
    color("LightBlue", 0.6)
      translate([W/2, t + 4 + eps, win_cz]) rotate([90, 0, 0]) linear_extrude(acrylic_t) panel_window();
}

// ---- part selection ----------------------------------------------------
if (part == "front")  panel_front();
else if (part == "back")   panel_back();
else if (part == "left")   panel_left_cut();
else if (part == "right")  panel_right();
else if (part == "floor")  panel_floor();
else if (part == "lid")    panel_lid();
else if (part == "window") panel_window();
else if (part == "sheet")  sheet();
else if (part == "testfit") testfit();
else if (part == "testfit_etch") testfit_etch();
else if (part == "front_etch")  front_etch();
else if (part == "back_etch")   back_etch();
else if (part == "left_etch")   left_etch_cut();
else if (part == "right_etch")  right_etch();
else if (part == "floor_etch")  floor_etch();
else if (part == "window_etch") window_etch();
else if (part == "sheet_etch")  sheet_etch();
else assembly();
