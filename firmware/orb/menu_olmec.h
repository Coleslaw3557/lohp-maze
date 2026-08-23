// Carved-stone action menu for the cuddle orb — same idiom as face_olmec.h
// (height field + material masks through the shared shadePixel stone lighting)
// so the menu reads as the back of the same idol, not a UI. Rendered once at
// boot into a PSRAM layer; orb.ino blits it whole on open and repaints one
// wedge for press/charge feedback.
//
// Wedge order (clockwise from the top), glyphs carved as gold inlay:
//   0 LIGHTS  sun          1 MODE twin masks    2 STORM  lightning bolt
//   3 FLOOR   serpent coil 4 CALM   closed eye
// Hub medallion = stepped pyramid (tap = close). orb.ino owns the action table.
#pragma once
#include "face_olmec.h"

namespace olmec {

constexpr int MENU_WEDGES = 5;
constexpr float MENU_HUB_R = 0.285f;   // inside = close
constexpr float MENU_OUT_R = 1.02f;    // slab edge (fades to the chamber)
constexpr float MENU_GLYPH_R = 0.645f; // glyph anchors sit on this ring

static inline float menuWedgeAngle(int w) { // radians, screen y-down: -pi/2 = top
  return -1.5707963f + w * 1.2566371f;
}
static inline float angDiff(float a, float b) {
  float d = a - b;
  while (d > 3.1415927f) d -= 6.2831853f;
  while (d < -3.1415927f) d += 6.2831853f;
  return d;
}

// distance to a line segment, for stroke-built glyphs
static inline float segDist(float px, float py, float ax, float ay, float bx, float by) {
  float dx = bx - ax, dy = by - ay;
  float len2 = dx * dx + dy * dy;
  float t = len2 > 0 ? clampf(((px - ax) * dx + (py - ay) * dy) / len2, 0, 1) : 0;
  float ex = px - (ax + t * dx), ey = py - (ay + t * dy);
  return sqrtf(ex * ex + ey * ey);
}
static inline float stroke(float d, float w) { return 1.0f - sstep(w, w + 0.016f, d); }

// ---------- glyphs (local coords, upright, ~±0.20 extent) ----------
static float glyphSun(float gu, float gv) {
  float r = sqrtf(gu * gu + gv * gv);
  float g = stroke(fabsf(r - 0.088f), 0.026f);          // disc ring
  g += bell2(gu, gv, 0.038f, 0.038f);                   // core
  float ang = atan2f(gv, gu);
  float ray = 0.5f + 0.5f * cosf(ang * 8.0f);           // 8 rays
  g += stroke(fabsf(r - 0.155f), 0.038f) * sstep(0.72f, 0.95f, ray);
  return clampf(g, 0, 1);
}
static float glyphMode(float gu, float gv) {
  // attended/unattended: paired masks, one alert and one sleeping
  float g = 0;
  g += stroke(fabsf(sqrtf((gu + 0.070f) * (gu + 0.070f) + (gv + 0.012f) * (gv + 0.012f)) - 0.086f), 0.024f);
  g += bell2(gu + 0.098f, gv + 0.030f, 0.012f, 0.012f);
  g += bell2(gu + 0.046f, gv + 0.030f, 0.012f, 0.012f);
  g += stroke(fabsf(gv + 0.018f - 0.72f * (gu + 0.072f) * (gu + 0.072f)), 0.012f)
       * (1.0f - sstep(0.048f, 0.070f, fabsf(gu + 0.072f)));
  g += stroke(fabsf(sqrtf((gu - 0.082f) * (gu - 0.082f) + (gv - 0.004f) * (gv - 0.004f)) - 0.078f), 0.022f);
  g += stroke(fabsf(gv + 0.018f + 0.70f * (gu - 0.082f) * (gu - 0.082f)), 0.012f)
       * (1.0f - sstep(0.044f, 0.064f, fabsf(gu - 0.082f)));
  g += stroke(segDist(gu, gv, 0.042f, 0.052f, 0.122f, 0.060f), 0.010f);
  return clampf(g, 0, 1);
}
static float glyphBolt(float gu, float gv) {
  float g = stroke(segDist(gu, gv, 0.055f, -0.165f, -0.045f, -0.015f), 0.030f);
  g += stroke(segDist(gu, gv, -0.045f, -0.015f, 0.045f, 0.005f), 0.030f);
  g += stroke(segDist(gu, gv, 0.045f, 0.005f, -0.055f, 0.165f), 0.030f);
  return clampf(g, 0, 1);
}
static float glyphSerpent(float gu, float gv) {
  // coiled snake: 2.3-turn archimedean spiral, head bead at the outer end
  float r = sqrtf(gu * gu + gv * gv);
  float ang = atan2f(gv, gu);
  float g = 0;
  for (int k = 0; k < 3; k++) {
    float th = ang + 1.5707963f + k * 6.2831853f; // unwrap candidates
    if (th < 0 || th > 14.45f) continue;
    g += stroke(fabsf(r - (0.020f + 0.0118f * th)), 0.021f);
  }
  float hx = 0.020f + 0.0118f * 14.45f; // spiral end -> head
  g += bell2(gu - hx * cosf(14.45f - 1.5707963f), gv - hx * sinf(14.45f - 1.5707963f),
             0.038f, 0.038f) * 1.2f;
  return clampf(g, 0, 1);
}
static float glyphClosedEye(float gu, float gv) {
  // sleeping eye: one clearly bowed lid arc, three separated lashes below it
  float lid = -0.045f + 1.55f * gu * gu; // bulges toward the top of the wedge
  float g = stroke(fabsf(gv - lid), 0.024f) * (1.0f - sstep(0.135f, 0.160f, fabsf(gu)));
  for (int i = -1; i <= 1; i++) {
    float x = 0.095f * i;
    float y0 = -0.045f + 1.55f * x * x + 0.035f;
    g += stroke(segDist(gu, gv, x, y0, x * 1.35f, y0 + 0.065f), 0.017f);
  }
  return clampf(g, 0, 1);
}
static float menuGlyph(int w, float gu, float gv) {
  switch (w) {
    case 0: return glyphSun(gu, gv);
    case 1: return glyphMode(gu, gv);
    case 2: return glyphBolt(gu, gv);
    case 3: return glyphSerpent(gu, gv);
    default: return glyphClosedEye(gu, gv);
  }
}

// ---------- height field ----------
static Field menuField(float u, float v) {
  Field f;
  float r = sqrtf(u * u + v * v);
  float slab = 1.0f - sstep(MENU_OUT_R - 0.02f, MENU_OUT_R + 0.025f, r);
  if (slab <= 0.001f) {
    f.mat = packMaterials(0, 0, 0, 0, 0, 0, 0, 0);
    return f;
  }
  float ang = atan2f(v, u);

  // gently domed slab with a raised hub medallion
  f.h += slab * (0.14f - 0.05f * r * r);
  float hub = 1.0f - sstep(MENU_HUB_R - 0.03f, MENU_HUB_R, r);
  f.h += 0.070f * hub;

  // hub carving: three-step pyramid (temple mark; tapping it closes the menu)
  float pyr = 0;
  const float sw[3] = {0.150f, 0.104f, 0.058f};
  for (int i = 0; i < 3; i++)
    pyr += boxMask(u, v, -sw[i], sw[i], 0.075f - 0.052f * (i + 1), 0.075f - 0.052f * i, 0.008f);
  pyr = clampf(pyr, 0, 1) * hub;
  f.h -= 0.030f * pyr;
  f.rec += 0.42f * pyr;

  // wedge plaque band, each wedge a hair different (hand-cut, not machined)
  float band = sstep(0.325f, 0.355f, r) * (1.0f - sstep(0.930f, 0.960f, r)) * slab;
  f.h += 0.052f * band;
  for (int w = 0; w < MENU_WEDGES; w++) {
    float in = 1.0f - sstep(0.55f, 0.63f, fabsf(angDiff(ang, menuWedgeAngle(w))));
    f.h += 0.010f * (hashf(w * 31 + 7, w * 13 + 3) - 0.5f) * band * in;
  }

  // carved separations: sector grooves + border rings
  float groove = 0;
  for (int w = 0; w < MENU_WEDGES; w++) {
    float bAng = menuWedgeAngle(w) + 0.6283185f; // boundary between w and w+1
    groove += stroke(fabsf(angDiff(ang, bAng)) * r, 0.020f) * band;
  }
  groove += stroke(fabsf(r - 0.325f), 0.014f) * slab;
  groove += stroke(fabsf(r - 0.960f), 0.014f) * slab;
  groove = clampf(groove, 0, 1);
  f.h -= 0.050f * groove;
  f.rec += 0.60f * groove;

  // gold-inlaid glyph per wedge, carved into the plaque
  float gold = 0;
  for (int w = 0; w < MENU_WEDGES; w++) {
    float aC = menuWedgeAngle(w);
    if (fabsf(angDiff(ang, aC)) > 0.75f) continue; // cheap sector cull
    float g = menuGlyph(w, u - MENU_GLYPH_R * cosf(aC), v - MENU_GLYPH_R * sinf(aC));
    gold += g * band;
  }
  gold = clampf(gold, 0, 1);
  f.h -= 0.028f * gold;
  f.rec += 0.30f * gold;

  // teal inlay rings echo the headdress
  float tq = stroke(fabsf(r - MENU_HUB_R + 0.012f), 0.011f) * slab +
             stroke(fabsf(r - 0.990f), 0.011f) * slab;

  f.mat = packMaterials(slab, 0, 0, 0, clampf(tq, 0, 1), gold, 0,
                        0.35f * groove);
  f.h *= slab;
  f.rec *= slab;
  return f;
}

// one-shot render, same two-pass structure as renderBase
static void renderMenu(uint16_t *out) {
  float *hh = (float *)OLMEC_ALLOC((size_t)W * H * sizeof(float));
  float *rr = (float *)OLMEC_ALLOC((size_t)W * H * sizeof(float));
  uint64_t *mm = (uint64_t *)OLMEC_ALLOC((size_t)W * H * sizeof(uint64_t));
  if (!hh || !rr || !mm) {
    if (hh) free(hh);
    if (rr) free(rr);
    if (mm) free(mm);
    return;
  }
  for (int y = 0; y < H; y++)
    for (int x = 0; x < W; x++) {
      Field f = menuField((x - 180) / SCALE, (y - 180) / SCALE);
      hh[y * W + x] = f.h;
      rr[y * W + x] = f.rec;
      mm[y * W + x] = f.mat;
    }
  for (int y = 0; y < H; y++)
    for (int x = 0; x < W; x++) {
      int i = y * W + x;
      float hx0 = x + 1 < W ? hh[i + 1] : hh[i];
      float hy0 = y + 1 < H ? hh[i + W] : hh[i];
      float r, g, b;
      shadePixel(x, y, hh[i], hx0, hy0, rr[i], mm[i], r, g, b);
      out[i] = pack565(r, g, b);
    }
  free(hh);
  free(rr);
  free(mm);
}

// ---------- runtime helpers ----------
// -1 = hub (close), 0..4 = wedge, -2 = dead zone
static inline int menuHit(int x, int y) {
  float u = (x - 180) / SCALE, v = (y - 180) / SCALE;
  float r = sqrtf(u * u + v * v);
  if (r < MENU_HUB_R + 0.02f) return -1;
  if (r > 1.10f) return -2;
  float ang = atan2f(v, u);
  for (int w = 0; w < MENU_WEDGES; w++)
    if (fabsf(angDiff(ang, menuWedgeAngle(w))) <= 0.6283185f) return w;
  return -2;
}

// conservative pixel bbox of a wedge (sampled arc), for feedback repaints
static inline void menuWedgeRect(int w, int &x0, int &y0, int &x1, int &y1) {
  float aC = menuWedgeAngle(w);
  float fx0 = 1e9f, fy0 = 1e9f, fx1 = -1e9f, fy1 = -1e9f;
  for (int i = 0; i <= 16; i++) {
    float a = aC + (-0.6283185f + 1.2566371f * i / 16.0f);
    for (int e = 0; e < 2; e++) {
      float rr = e ? 0.980f : 0.315f;
      float px = 180 + cosf(a) * rr * SCALE, py = 180 + sinf(a) * rr * SCALE;
      fx0 = fminf(fx0, px);
      fy0 = fminf(fy0, py);
      fx1 = fmaxf(fx1, px);
      fy1 = fmaxf(fy1, py);
    }
  }
  x0 = (int)fx0 - 3;
  y0 = (int)fy0 - 3;
  x1 = (int)fx1 + 4;
  y1 = (int)fy1 + 4;
  if (x0 < 0) x0 = 0;
  if (y0 < 0) y0 = 0;
  if (x1 > W) x1 = W;
  if (y1 > H) y1 = H;
}

// repaint one wedge from the pristine layer with an ember lift (amt 0 = as
// carved, 1 = fully lit — the storm charge sweeps this)
static void menuWedgeGlow(uint16_t *fb, const uint16_t *layer, int w, float amt) {
  int x0, y0, x1, y1;
  menuWedgeRect(w, x0, y0, x1, y1);
  for (int y = y0; y < y1; y++)
    for (int x = x0; x < x1; x++) {
      int i = y * W + x;
      if (menuHit(x, y) != w) {
        fb[i] = layer[i];
        continue;
      }
      float r, g, b;
      unpack565(layer[i], r, g, b);
      r = lerpf(r, 255, 0.50f * amt);
      g = lerpf(g, 196, 0.38f * amt);
      b = lerpf(b, 96, 0.22f * amt);
      fb[i] = pack565(r, g, b);
    }
}

} // namespace olmec
