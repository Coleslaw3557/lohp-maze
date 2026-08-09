// Photo Bomb room device enclosures — TWO laser-cut boxes from one file:
//   box = "camera"   Logitech C930e webcam box (strap to the back-plane scaffold,
//                    lens out the front aperture toward the poser/street face)
//   box = "printer"  Brother QL-820NWB label printer box (photo souvenir prints;
//                    open front frames the label slot + LCD + buttons)
//
// Same grammar as node-enclosure.scad: 6 finger-jointed ply panels glued up
// (walls corner-joined, floor tabs mortise through wall-bottom notches, flush
// outside), drop-in lid (floor-twin, tabs land in top notches on all four
// walls, Ø14 finger notch at the front edge), velcro strap slots in the back
// wall for 20mm one-wrap around scaffold tube, NO fastener holes anywhere —
// parts are their own jigs. Stock is 6mm ply (t below = nominal; CALIPER the
// real sheet and re-export before burning).
//
// Device sources (2026-08-08 lookups):
//   QL-820NWB: 125.3 W x 234 D x 145 H mm, 1.16 kg (Brother US spec page);
//     external AC adapter PA-AD-001A (25V DC in) — brick stays OUTSIDE the box;
//     LCD + buttons + label slot all on the sloped FRONT face, all connectors
//     (DC / USB-B / LAN / USB host) on the REAR face, roll cover lifts from the
//     front top (QL-810W/820NWB Quick Setup Guide "Parts Description").
//   C930e: body 94 x 29 x 24, ON FOLDED CLIP 94 W x 43.3 H x 71 D, 162 g,
//     fixed 1.5 m USB-A cable, 90 deg diagonal FOV (Logitech datasheet).
//     1/4-20 tripod thread in the clip foot: sit the camera in its etched
//     floor zone, mark the thread, drill Ø7, bolt from below (no pre-cut hole
//     — same drill-from-the-real-part rule as the DB9 screwlocks).
//
// part = "assembly" | "sheet" | "sheet_etch"
// Etch faces at glue-up (all panels are non-chiral — no pre-mirroring needed):
//   floor UP, front OUT, back OUT, lid UP. Label side out and up.

part = "assembly";
box  = "camera";           // "camera" | "printer"

t    = 6.0;                // ply thickness — caliper the real 6mm sheet
play = 0.3;                // lid drop-in clearance per side
tabslack = 0.4;            // lid tab length reduction vs its notch

// ---------------- device dims (measured/spec'd, see header) ----------------
cam_w = 94;    cam_d = 71;    cam_h = 43.3;   // C930e on folded clip
cam_lens_z = 28.8;                            // lens center above clip foot
prn_w = 125.3; prn_d = 234;   prn_h = 145;    // QL-820NWB
dev_gap_front = 4;                            // device face setback from wall

// ---------------- interiors ----------------
iw = box == "printer" ? 134 : 104;   // width  (device + side clearance)
id = box == "printer" ? 280 : 100;   // depth  (device + front gap + rear cable room:
                                     //  printer 42mm for the DC barrel plug + bend,
                                     //  camera 25mm for the fixed USB-A tail)
ih = box == "printer" ? 155 : 66;    // height (printer +10 headroom; camera clears
                                     //  the flipped-up privacy shade)

W  = iw + 2*t;                       // outer width
D  = id + 2*t;                       // outer depth
Hw = ih + 2*t;                       // wall height = outer height

// ---------------- corner joints ----------------
// nseg vertical segments per corner; front/back walls own the EVEN segs
// (material runs to the outer corner), side walls own the ODD segs.
nseg = box == "printer" ? 7 : 5;
seg  = Hw / nseg;

// ---------------- floor / lid tab positions (centers along the edge) ------
// Front and back edges use different centers on purpose: the floor and lid
// only seat one way (poka-yoke), and the back top edge keeps clear lanes for
// the cable notches between tabs.
tab_len   = 30;
ftab_cx   = box == "printer" ? [W/2-33, W/2+33]      : [W/2-26, W/2+26];
btab_cx   = box == "printer" ? [W/2-44, W/2+44]      : [W/2-28, W/2+10];
stab_cy   = box == "printer" ? [D/2-100, D/2, D/2+100] : [D/2-26, D/2+26];
stab_len  = box == "printer" ? 40 : 30;
finger_d  = 14;                      // lid finger-pull notch diameter

// ---------------- front opening ----------------
// camera: lens aperture. printer: LABEL MOUTH only — the wall stays solid over
// the LCD/buttons/cover (rev 2026-08-08, Tim: "doesn't need a window, it needs
// a spot for the print jobs to come out"). Mouth spans the output tray. Two
// independent measurements agree (product photos scaled to the 125.3 body
// width, AND Tim's photogrammetry scan in ~/printer-test — scale fixed by the
// 145 height, cross-validated by the tray width landing at 107.6 vs the photo
// band 106..109): cutter/slot shelf 74..87 above the feet, ramp bottom 42..48
// (photo only — the black ramp didn't scan), button row bottom ~100..109,
// tray 106..109 wide. Mouth 24..96 x 116 clears the tray on every band and
// keeps the buttons covered. Cut labels slide down the ramp, out the mouth.
ap_w = box == "printer" ? 116 : 84;
ap_z0 = box == "printer" ? t + 24  : t + cam_lens_z - 18;  // bottom (panel coords)
ap_z1 = box == "printer" ? t + 96  : t + cam_lens_z + 18;  // top

// printer status-LED peep: LED ~43 left of center; height band 106..118
// across both measurements -> Ø12 centered 112 covers it (green/red shows
// through; box stays closed to check health)
led_peep_d = 12;
led_x = W/2 - 43;
led_z = t + 112;

// ---------------- back wall features ----------------
vs_w = 5; vs_h = 24; vs_dx = 24;     // velcro slots: 5x24, pair spans a 43mm tube
// cable notches down from the top edge (cables leave over the top-back, the
// lid caps the channel): [center x, width, depth]
notches = box == "printer"
  ? [[60, 13, 20], [86, 13, 20]]     // PWR (DC barrel) | DATA (USB-B / LAN)
  : [[W/2+38.5, 13, 16]];            // USB (12mm USB-A plug head passes)
notch_lbl = box == "printer" ? ["PWR", "DATA"] : ["USB"];

// ---------------- side vents (printer only) ----------------
vent_n = 5; vent_l = 60; vent_h = 5; vent_pitch = 10;
vent_z0 = 110;                       // first slat bottom (panel coords)

// ---------------- 2D helpers ----------------
module corner_notches(width, even) {
  // notch the vertical edges of a panel at the segs it does NOT own
  for (i = [0:nseg-1])
    for (x0 = [0, width - t])
      if (even ? i % 2 == 1 : i % 2 == 0)
        translate([x0 - 0.01, i*seg - 0.01])
          square([t + 0.02, seg + 0.02]);
}

module edge_slots(centers, len, y0, deep) {
  // rectangular cuts of size len x deep with bottom edge at y0
  for (cx = centers)
    translate([cx - len/2, y0 - 0.01]) square([len, deep + 0.02]);
}

// ---------------- wall panels (2D) ----------------
module panel_front_2d() {
  difference() {
    square([W, Hw]);
    corner_notches(W, true);
    edge_slots(ftab_cx, tab_len, 0, t);          // floor mortises
    edge_slots(ftab_cx, tab_len, Hw - t, t);     // lid notches
    translate([(W - ap_w)/2, ap_z0]) square([ap_w, ap_z1 - ap_z0]);
    if (box == "printer") translate([led_x, led_z]) circle(d = led_peep_d, $fn = 40);
  }
}

module panel_back_2d() {
  difference() {
    square([W, Hw]);
    corner_notches(W, true);
    edge_slots(btab_cx, tab_len, 0, t);
    edge_slots(btab_cx, tab_len, Hw - t, t);
    // velcro strap slots
    if (box == "printer") {
      for (zc = [49, 118]) for (s = [-1, 1])
        translate([W/2 + s*vs_dx - vs_w/2, zc - vs_h/2]) square([vs_w, vs_h]);
    } else {
      for (s = [-1, 1])
        translate([W/2 + s*vs_dx - vs_w/2, Hw/2 - vs_h/2]) square([vs_w, vs_h]);
    }
    // cable notches from the top edge
    for (n = notches)
      translate([n[0] - n[1]/2, Hw - n[2]]) square([n[1], n[2] + 0.02]);
  }
}

module panel_side_2d() {                     // left/right: own ODD segs
  difference() {
    square([D, Hw]);
    corner_notches(D, false);
    edge_slots(stab_cy, stab_len, 0, t);
    edge_slots(stab_cy, stab_len, Hw - t, t);
    if (box == "printer")
      for (i = [0:vent_n-1])
        translate([D/2 - vent_l/2, vent_z0 + i*vent_pitch])
          square([vent_l, vent_h]);
  }
}

// ---------------- floor + lid (2D) ----------------
module plate_2d(shrink, tabshrink) {
  // core (iw x id) minus shrink per side, plus edge tabs reaching the outer
  // face through the wall notches
  union() {
    translate([t + shrink, t + shrink])
      square([iw - 2*shrink, id - 2*shrink]);
    for (cx = ftab_cx)                                     // front edge (y=0)
      translate([cx - (tab_len - tabshrink)/2, 0])
        square([tab_len - tabshrink, t + shrink + 0.02]);
    for (cx = btab_cx)                                     // back edge
      translate([cx - (tab_len - tabshrink)/2, D - t - shrink])
        square([tab_len - tabshrink, t + shrink + 0.02]);
    for (cy = stab_cy) for (x0 = [0, W - t - shrink])      // side edges
      translate([x0, cy - (stab_len - tabshrink)/2])
        square([t + shrink + 0.02, stab_len - tabshrink]);
  }
}

module panel_floor_2d() { plate_2d(0, 0); }

module panel_lid_2d() {
  difference() {
    plate_2d(play, tabslack);
    // finger-pull: half-moon into the lid's front core edge, over the front
    // wall's solid top center — reach in and lift
    translate([W/2, t + play]) circle(d = finger_d, $fn = 48);
  }
}

// ---------------- etch layers (2D, same frames as the cut panels) ----------
lbl = 5;          // label text size
fnt = "DejaVu Sans:style=Bold";

module etch_front_2d() {
  txt = box == "printer" ? "PHOTO BOMB PRINTER" : "PHOTO BOMB CAM";
  tz = box == "printer" ? 138 : ap_z1 + 4;   // printer: on the solid upper field
  translate([W/2, tz]) text(txt, size = lbl, halign = "center", font = fnt);
  if (box == "printer")
    translate([led_x, led_z + led_peep_d/2 + 2])
      text("LED", size = lbl - 1, halign = "center", font = fnt);
}

module etch_back_2d() {
  vz = box == "printer" ? 84 : Hw/2;   // between the slot pair(s)
  translate([W/2, vz - lbl/2]) text("VELCRO", size = lbl, halign = "center", font = fnt);
  for (i = [0:len(notches)-1])
    translate([notches[i][0], Hw - notches[i][2] - lbl - 2])
      text(notch_lbl[i], size = lbl - 1, halign = "center", font = fnt);
}

module etch_floor_2d() {
  // device footprint zone, front edge dev_gap_front behind the front wall's
  // inner face; drawn as a 1mm band so it scores as a visible outline
  zw = box == "printer" ? prn_w : cam_w;
  zd = box == "printer" ? prn_d : cam_d;
  translate([W/2 - zw/2, t + dev_gap_front]) difference() {
    square([zw, zd]);
    translate([1, 1]) square([zw - 2, zd - 2]);
  }
  translate([W/2, t + dev_gap_front + zd/2])
    text(box == "printer" ? "QL-820NWB" : "C930e", size = lbl,
         halign = "center", valign = "center", font = fnt);
  translate([W/2, t + dev_gap_front + 4])
    text("FRONT", size = 3, halign = "center", font = fnt);
}

// ---------------- flat sheet ----------------
// Rows are grouped so each row fits a ~430x390 bed load on its own:
//   camera:  one load (~236 x 276 total)
//   printer: row 1 floor+lid (296x292), rows 2+3 left+right (292x338),
//            row 4 front+back (296x167) — select per-row in XCS if the whole
//            sheet exceeds the bed.
gap = 4;
module sheet_cut() {
  if (box == "printer") {
    translate([0, 0])                        panel_floor_2d();
    translate([W + gap, 0])                  panel_lid_2d();
    translate([0, D + gap])                  panel_side_2d();       // left
    translate([0, D + gap + Hw + gap])       panel_side_2d();       // right
    translate([0, D + 2*(Hw + gap) + gap])       panel_front_2d();
    translate([W + gap, D + 2*(Hw + gap) + gap]) panel_back_2d();
  } else {
    translate([0, 0])                        panel_floor_2d();
    translate([W + gap, 0])                  panel_lid_2d();
    translate([0, D + gap])                  panel_front_2d();
    translate([W + gap, D + gap])            panel_back_2d();
    translate([0, D + gap + Hw + gap])       panel_side_2d();       // left
    translate([D + gap, D + gap + Hw + gap]) panel_side_2d();       // right
  }
}

module sheet_etch() {
  if (box == "printer") {
    translate([0, 0])                            etch_floor_2d();
    translate([0, D + 2*(Hw + gap) + gap])       etch_front_2d();
    translate([W + gap, D + 2*(Hw + gap) + gap]) etch_back_2d();
  } else {
    translate([0, 0])                        etch_floor_2d();
    translate([0, D + gap])                  etch_front_2d();
    translate([W + gap, D + gap])            etch_back_2d();
  }
}

// ---------------- assembly preview ----------------
module assembly() {
  color("BurlyWood") linear_extrude(t) panel_floor_2d();
  // front wall: panel x -> world x, panel y -> world z, occupies y 0..t
  color("Peru") rotate([90, 0, 0]) translate([0, 0, -t])
    linear_extrude(t) panel_front_2d();
  // back wall: occupies y D-t..D
  color("Peru") translate([0, D, 0]) rotate([90, 0, 0])
    linear_extrude(t) panel_back_2d();
  // side walls: extrusion maps to +X; left needs no x-translate
  color("Tan") rotate([90, 0, 90]) linear_extrude(t) panel_side_2d();
  color("Tan") translate([W - t, 0, 0]) rotate([90, 0, 90])
    linear_extrude(t) panel_side_2d();
  color("BurlyWood") translate([0, 0, Hw - t]) linear_extrude(t) panel_lid_2d();
  // ghost device for the eyeball fit-check
  %if (box == "printer")
    translate([W/2 - prn_w/2, t + dev_gap_front, t]) cube([prn_w, prn_d, prn_h]);
  else
    translate([W/2 - cam_w/2, t + dev_gap_front, t]) cube([cam_w, cam_d, cam_h]);
}

// ---------------- part switch ----------------
if (part == "sheet")           sheet_cut();
else if (part == "sheet_etch") sheet_etch();
else                           assembly();
