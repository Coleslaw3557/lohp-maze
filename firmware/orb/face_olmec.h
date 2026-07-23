// Temple Oracle — a painted Olmec/Maya-inspired animatronic stone guardian.
// The display-sized face is a palette-indexed RGB565 bitmap; ember eyes,
// breathing nostrils, and the sliding lower face remain live procedural layers.
//
// renderBase() and renderJawTile() expand the flash-resident art once at boot.
// Only the declared eye, jaw, and nose dirty rectangles change per frame. The
// public FaceState contract is unchanged, and the procedural material helpers
// below are retained for menu_olmec.h.
#pragma once
#include <math.h>
#include <stdint.h>
#include <string.h>
#include "face_bitmap.h"

#ifdef ESP32
#include <esp32-hal-psram.h>
#define OLMEC_ALLOC ps_malloc
#else
#include <stdlib.h>
#define OLMEC_ALLOC malloc
#endif

namespace olmec {

constexpr int W = 360, H = 360;
constexpr float SCALE = 165.0f;

// Dirty rects (inclusive-exclusive). The eyes include their animated lids and
// brows; the jaw rect includes the open mouth throughout its full travel.
constexpr int EYEL_X0 = 96, EYEL_X1 = 174;
constexpr int EYER_X0 = 186, EYER_X1 = 264;
constexpr int EYE_Y0 = 119, EYE_Y1 = 179;
constexpr int JAW_X0 = 102, JAW_X1 = 258;
constexpr int JAW_Y0 = 211, JAW_Y1 = 336;
constexpr int NOSE_X0 = 146, NOSE_X1 = 214;
constexpr int NOSE_Y0 = 178, NOSE_Y1 = 225;

constexpr float EYE_CX = 0.285f, EYE_CY = -0.188f;
constexpr float EYE_AW = 27.0f, EYE_AH = 9.0f;

// The jaw is still a rigid prerendered tile, but its mask has a rounded simian
// chin and a central inlaid glyph. The open gap exposes teeth drawn by drawJaw.
constexpr float CAV_U = 0.40f, CAV_V0 = 0.29f, CAV_V1 = 0.80f;
constexpr int JAW_TILE_W = 136;
constexpr int JAW_TILE_H = 64;
constexpr int JAW_TILE_X = (W - JAW_TILE_W) / 2;
constexpr int JAW_TOP_CLOSED = 233;
constexpr int JAW_TRAVEL = 27;

struct FaceState {
  float gx = 0, gy = 0; // gaze -1..1
  float dil = 0.4f;     // pupil dilation 0..1
  float glow = 0;       // eye wake/glow 0..1
  float jaw = 0;        // 0 closed .. 1 open
  float talkGlow = 0;   // ember light in the mouth
  float mood = 0;       // -1 suspicious/grumpy .. +1 delighted
  float blink = 0;      // 0 open .. 1 fully closed
  float wild = 0;       // 0 stone-faced .. 1 surprised/manic
  float talkPhase = 0;  // free-running radians for jaw shimmy/ember flicker
};

// ---------- compact math ----------
static inline float clampf(float x, float a, float b) { return x < a ? a : (x > b ? b : x); }
static inline float lerpf(float a, float b, float t) { return a + (b - a) * t; }
static inline float sstep(float e0, float e1, float x) {
  if (e0 == e1) return x < e0 ? 0.0f : 1.0f;
  x = clampf((x - e0) / (e1 - e0), 0, 1);
  return x * x * (3 - 2 * x);
}
static inline float bell(float q) {
  float t = 1.0f - 0.25f * q;
  if (t <= 0) return 0;
  t *= t;
  return t * t;
}
static inline float bell2(float du, float dv, float sx, float sy) {
  float qx = du / sx, qy = dv / sy;
  return bell(qx * qx + qy * qy);
}
static inline float boxMask(float u, float v, float x0, float x1, float y0, float y1, float feather) {
  return sstep(x0 - feather, x0 + feather, u) * (1 - sstep(x1 - feather, x1 + feather, u)) *
         sstep(y0 - feather, y0 + feather, v) * (1 - sstep(y1 - feather, y1 + feather, v));
}
static inline float roundedBoxMask(float u, float v, float hx, float hy, float radius, float feather) {
  float qx = fabsf(u) - (hx - radius), qy = fabsf(v) - (hy - radius);
  float ox = qx > 0 ? qx : 0, oy = qy > 0 ? qy : 0;
  float d = sqrtf(ox * ox + oy * oy) + fminf(fmaxf(qx, qy), 0.0f) - radius;
  return 1 - sstep(-feather, feather, d);
}
static inline uint32_t hash2(int x, int y) {
  uint32_t h = (uint32_t)x * 374761393u + (uint32_t)y * 668265263u;
  h = (h ^ (h >> 13)) * 1274126177u;
  return h ^ (h >> 16);
}
static inline float hashf(int x, int y) { return (hash2(x, y) & 0xFFFF) / 65535.0f; }
static inline float vnoise(float x, float y) {
  int xi = (int)floorf(x), yi = (int)floorf(y);
  float fx = x - xi, fy = y - yi;
  fx = fx * fx * (3 - 2 * fx);
  fy = fy * fy * (3 - 2 * fy);
  float a = hashf(xi, yi), b = hashf(xi + 1, yi), c = hashf(xi, yi + 1), d = hashf(xi + 1, yi + 1);
  return lerpf(lerpf(a, b, fx), lerpf(c, d, fx), fy);
}
static inline uint16_t pack565(float r, float g, float b) {
  int ri = (int)clampf(r, 0, 255), gi = (int)clampf(g, 0, 255), bi = (int)clampf(b, 0, 255);
  return (uint16_t)(((ri & 0xF8) << 8) | ((gi & 0xFC) << 3) | (bi >> 3));
}
static inline void unpack565(uint16_t c, float &r, float &g, float &b) {
  r = ((c >> 11) & 31) * (255.0f / 31.0f);
  g = ((c >> 5) & 63) * (255.0f / 63.0f);
  b = (c & 31) * (255.0f / 31.0f);
}

// ---------- silhouette and carved material masks ----------
static inline float faceMask(float u, float v) {
  float mask = roundedBoxMask(u, v + 0.015f, 0.625f, 0.79f, 0.15f, 0.026f);
  float chin = bell2(u, v - 0.69f, 0.52f, 0.23f);
  return clampf(mask + 0.52f * chin, 0, 1);
}
static inline float crownMask(float u, float v) {
  float band = boxMask(u, v, -0.68f, 0.68f, -0.69f, -0.49f, 0.024f);
  float top = boxMask(u, v, -0.53f, 0.53f, -0.80f, -0.68f, 0.025f);
  float lobes = bell2(u - 0.43f, v + 0.82f, 0.15f, 0.13f) +
                bell2(u + 0.43f, v + 0.82f, 0.15f, 0.13f) +
                bell2(u - 0.15f, v + 0.85f, 0.13f, 0.15f) +
                bell2(u + 0.15f, v + 0.85f, 0.13f, 0.15f);
  float holes = bell2(u - 0.43f, v + 0.82f, 0.065f, 0.055f) +
                bell2(u + 0.43f, v + 0.82f, 0.065f, 0.055f);
  float wings = boxMask(u, v, -0.78f, -0.55f, -0.76f, -0.54f, 0.04f) +
                boxMask(u, v, 0.55f, 0.78f, -0.76f, -0.54f, 0.04f);
  return clampf((band + top + 0.72f * lobes + wings) * (1 - clampf(1.15f * holes, 0, 1)), 0, 1);
}
static inline float earMask(float u, float v) {
  return clampf(bell2(u - 0.735f, v + 0.02f, 0.215f, 0.225f) +
                    bell2(u + 0.735f, v + 0.02f, 0.215f, 0.225f),
                0, 1);
}
static inline float earCoreMask(float u, float v) {
  return clampf(bell2(u - 0.735f, v + 0.02f, 0.105f, 0.118f) +
                    bell2(u + 0.735f, v + 0.02f, 0.105f, 0.118f),
                0, 1);
}
static inline float collarMaterialMask(float u, float v) {
  float slab = boxMask(u, v, -0.54f, 0.54f, 0.72f, 0.92f, 0.025f);
  float beads = 0;
  for (int i = 0; i < 7; i++) {
    float cx = -0.42f + 0.14f * i;
    beads += bell2(u - cx, v - 0.78f, 0.065f, 0.055f);
  }
  return clampf(slab + beads, 0, 1);
}
static inline float portalMask(float u, float v) {
  float r = sqrtf(u * u + v * v);
  float left = boxMask(u, v, -1.04f, -0.54f, -0.69f, 0.83f, 0.035f);
  float right = boxMask(u, v, 0.54f, 1.04f, -0.69f, 0.83f, 0.035f);
  float lower = boxMask(u, v, -0.80f, 0.80f, 0.66f, 1.04f, 0.04f);
  return clampf(left + right + lower, 0, 1) * (1 - sstep(1.03f, 1.09f, r));
}
static inline float stoneMask(float u, float v) {
  return clampf(faceMask(u, v) + crownMask(u, v) + earMask(u, v) + portalMask(u, v), 0, 1);
}
static inline float cavityMask(float u, float v) {
  float taper = 0.045f * sstep(CAV_V0, CAV_V1, v);
  float cu = CAV_U - taper;
  return sstep(-cu - 0.025f, -cu + 0.025f, u) * (1 - sstep(cu - 0.025f, cu + 0.025f, u)) *
         sstep(CAV_V0 - 0.018f, CAV_V0 + 0.018f, v) * (1 - sstep(CAV_V1 - 0.025f, CAV_V1 + 0.04f, v));
}
static inline float turquoiseMask(float u, float v) {
  float earRing = 0;
  for (int side = -1; side <= 1; side += 2) {
    float du = u - side * 0.735f, dv = v + 0.02f;
    float rr = sqrtf(du * du + dv * dv);
    earRing += sstep(0.105f, 0.125f, rr) * (1 - sstep(0.155f, 0.178f, rr));
  }
  float collar = boxMask(u, v, -0.43f, 0.43f, 0.75f, 0.84f, 0.02f);
  return clampf(earRing + 0.32f * collar, 0, 1);
}
static inline float goldMask(float u, float v) {
  float studs = 0;
  for (int i = 0; i < 7; i++) {
    float cx = -0.45f + 0.15f * i;
    studs += bell2(u - cx, v + 0.585f, 0.027f, 0.027f);
  }
  return clampf(studs, 0, 1);
}
static inline float crackMask(float u, float v) {
  // Two hairline faults. They alter recess/albedo, not silhouette.
  float l1 = fabsf(u + 0.39f + 0.18f * (v + 0.10f) - 0.018f * sinf(v * 31.0f));
  float c1 = (1 - sstep(0.006f, 0.014f, l1)) * sstep(-0.30f, -0.20f, v) * (1 - sstep(0.24f, 0.36f, v));
  float l2 = fabsf(u - 0.34f + 0.12f * (v + 0.45f));
  float c2 = (1 - sstep(0.005f, 0.012f, l2)) * sstep(-0.52f, -0.44f, v) * (1 - sstep(-0.08f, 0.02f, v));
  return clampf(c1 + c2, 0, 1);
}

// Cache eight 0..1 material masks at byte precision. The temporary buffer is
// freed after boot; this avoids recomputing every procedural mask in both the
// geometry and shading passes while retaining soft silhouette edges.
static inline uint64_t qmask8(float x) { return (uint64_t)(clampf(x, 0, 1) * 255.0f + 0.5f); }
static inline uint64_t packMaterials(float stone, float shrine, float earCore, float collar,
                                     float patina, float gold, float cavity, float crack) {
  return qmask8(stone) | (qmask8(shrine) << 8) | (qmask8(earCore) << 16) | (qmask8(collar) << 24) |
         (qmask8(patina) << 32) | (qmask8(gold) << 40) | (qmask8(cavity) << 48) | (qmask8(crack) << 56);
}
static inline float unpackMask8(uint64_t word, int shift) { return ((word >> shift) & 255u) * (1.0f / 255.0f); }

// ---------- sculpted head height field ----------
struct Field {
  float h = 0, rec = 0;
  uint64_t mat = 0;
};

static Field faceField(float u, float v) {
  Field f;
  float au = fabsf(u);
  float fm = faceMask(u, v), cm = crownMask(u, v), em = earMask(u, v), pm = portalMask(u, v);
  float gd = goldMask(u, v);

  // Red temple masonry behind the mask, broken into uneven blocks.
  f.h += 0.105f * pm;
  for (int row = 0; row < 5; row++) {
    float y0 = -0.66f + row * 0.29f;
    f.h += 0.035f * boxMask(u, v, -1.00f, -0.57f, y0 + 0.018f, y0 + 0.25f, 0.018f);
    f.h += 0.028f * boxMask(u, v, 0.57f, 1.00f, y0 + 0.018f, y0 + 0.25f, 0.018f);
    float seam = bell2(v - (y0 + 0.27f), 0, 0.012f, 1) * pm;
    f.h -= 0.025f * seam;
    f.rec += 0.30f * seam;
  }

  // Tall, slightly convex volcanic-stone face.
  float sq = fmaxf(fabsf(u) / 0.625f, fabsf(v + 0.015f) / 0.79f);
  if (sq < 1) f.h += fm * (0.39f + 0.31f * sqrtf(1 - sq * sq));
  f.h += fm * 0.026f * (vnoise(u * 5.0f + 8.0f, v * 5.0f + 13.0f) - 0.5f);
  f.h += 0.085f * (bell2(u - 0.43f, v + 0.01f, 0.22f, 0.31f) +
                    bell2(u + 0.43f, v + 0.01f, 0.22f, 0.31f));

  // Crown: slab band, gold studs, and four pierced scroll-like lobes.
  f.h += 0.18f * cm;
  f.h += 0.055f * boxMask(u, v, -0.68f, 0.68f, -0.69f, -0.49f, 0.018f);
  f.h += 0.07f * gd;
  for (int side = -1; side <= 1; side += 2) {
    float du = u - side * 0.43f, dv = v + 0.82f;
    float sr = sqrtf(du * du + dv * dv);
    f.h -= 0.075f * bell2(du, dv, 0.070f, 0.060f);
    f.rec += 0.45f * bell2(du, dv, 0.070f, 0.060f);
    float scrollRidge = sstep(0.060f, 0.078f, sr) * (1 - sstep(0.105f, 0.125f, sr));
    f.h += 0.038f * scrollRidge;
  }

  // Narrow eye sockets under straight brow shelves.
  for (int side = -1; side <= 1; side += 2) {
    float eu = u - side * EYE_CX;
    f.h += 0.075f * boxMask(eu, v, -0.19f, 0.19f, -0.335f, -0.285f, 0.026f);
    float socket = roundedBoxMask(eu, v - EYE_CY, 0.19f, 0.085f, 0.035f, 0.018f);
    f.h -= 0.11f * socket;
    f.rec += 1.05f * socket;
  }

  // Long triangular nose wedge, hooked tip, and deep nostrils.
  float noseT = sstep(-0.27f, 0.16f, v);
  float noseW = 0.052f + 0.078f * noseT;
  float nosePlane = sstep(-noseW - 0.022f, -noseW + 0.018f, u) *
                    (1 - sstep(noseW - 0.018f, noseW + 0.022f, u)) *
                    sstep(-0.31f, -0.27f, v) * (1 - sstep(0.16f, 0.21f, v));
  f.h += 0.18f * nosePlane;
  f.h += 0.145f * bell2(u, v - 0.16f, 0.17f, 0.13f);
  f.h += 0.07f * (bell2(u - 0.135f, v - 0.19f, 0.085f, 0.065f) +
                   bell2(u + 0.135f, v - 0.19f, 0.085f, 0.065f));
  float nost = bell2(u - 0.095f, v - 0.205f, 0.038f, 0.029f) +
               bell2(u + 0.095f, v - 0.205f, 0.038f, 0.029f);
  f.h -= 0.09f * nost;
  f.rec += 1.65f * nost;

  // Full sculpted upper lip; the lower lip lives on the jaw tile.
  f.h += 0.135f * (bell2(u - 0.145f, v - 0.255f, 0.18f, 0.060f) +
                    bell2(u + 0.145f, v - 0.255f, 0.18f, 0.060f));
  f.h -= 0.018f * bell2(u, v - 0.275f, 0.035f, 0.06f);
  for (int side = -1; side <= 1; side += 2) {
    float fold = bell2(u - side * 0.365f, v - 0.315f, 0.030f, 0.115f);
    f.h -= 0.023f * fold;
    f.rec += 0.34f * fold;
  }

  // Mouth cavity and carved rails for the sliding chin.
  float cav = cavityMask(u, v);
  f.h -= 0.20f * cav;
  f.rec += 2.6f * cav;
  float groove = bell2(au - (CAV_U + 0.018f), 0, 0.014f, 1) *
                 sstep(CAV_V0 - 0.04f, CAV_V0 + 0.03f, v) * (1 - sstep(0.73f, 0.80f, v));
  f.h -= 0.032f * groove;
  f.rec += 0.55f * groove;
  f.h -= 0.045f * sstep(0.67f, 0.81f, v) * (1 - sstep(0.39f, 0.48f, au));

  // Large circular ear medallions set into the red brick columns.
  for (int side = -1; side <= 1; side += 2) {
    float du = u - side * 0.735f, dv = v + 0.02f;
    float er = sqrtf(du * du + dv * dv);
    f.h += 0.18f * bell2(du, dv, 0.195f, 0.205f);
    f.h -= 0.065f * bell2(du, dv, 0.128f, 0.14f);
    f.h += 0.095f * bell2(du, dv, 0.083f, 0.09f);
    float ring = sstep(0.105f, 0.122f, er) * (1 - sstep(0.155f, 0.178f, er));
    f.h += 0.025f * ring;
  }

  // Beaded collar and central scroll at the base of the idol.
  float collar = boxMask(u, v, -0.53f, 0.53f, 0.73f, 0.90f, 0.025f);
  f.h += 0.065f * collar;
  for (int i = 0; i < 7; i++) {
    float cx = -0.42f + 0.14f * i;
    f.h += 0.065f * bell2(u - cx, v - 0.78f, 0.055f, 0.045f);
  }
  f.h += 0.055f * bell2(u, v - 0.865f, 0.16f, 0.075f);

  // Hairline archaeological damage makes the symmetry feel hand-carved.
  float crack = crackMask(u, v);
  f.h -= 0.020f * crack;
  f.rec += 0.72f * crack;

  // Keep field edges crisp against the dark chamber.
  float all = clampf(fm + cm + em + pm, 0, 1);
  float earCore = earCoreMask(u, v), collarMat = collarMaterialMask(u, v);
  float shrine = pm * (1 - 0.94f * fm) * (1 - 0.92f * earCore) * (1 - 0.90f * collarMat);
  f.mat = packMaterials(all, shrine, earCore, collarMat, turquoiseMask(u, v), gd, cav, crack);
  f.h *= all;
  f.rec *= all;
  return f;
}

// ---------- weathered gray volcanic-stone shading ----------
static inline void shadePixel(int x, int y, float h0, float hx0, float hy0, float rec, uint64_t mat,
                              float &r, float &g, float &b) {
  float u = (x - 180) / SCALE, v = (y - 180) / SCALE;
  float e = 1.0f / SCALE;
  float nx = -(hx0 - h0) / e * 1.28f, ny = -(hy0 - h0) / e * 1.28f, nz = 1;
  float il = 1.0f / sqrtf(nx * nx + ny * ny + nz * nz);
  nx *= il;
  ny *= il;
  nz *= il;

  float key = nx * -0.43f + ny * -0.61f + nz * 0.66f;
  float fill = nx * 0.63f + ny * 0.12f + nz * 0.77f;
  float lum = 0.23f + 0.82f * (key > 0 ? key : 0) + 0.14f * (fill > 0 ? fill : 0);
  float hv = nx * -0.25f + ny * -0.38f + nz * 0.89f;
  float sp = hv > 0 ? hv : 0;
  sp *= sp;
  sp *= sp;
  sp *= sp;
  lum += 0.13f * sp;
  lum *= 0.52f + 0.48f / (1.0f + 1.25f * rec);

  float mask = unpackMask8(mat, 0);
  float rad = sqrtf(u * u + v * v);
  // The chamber behind the idol is not flat black: faint warm stone and dust
  // motes help the round portal edge remain visible at 47 mm.
  float bgN = vnoise(x / 34.0f, y / 34.0f);
  float br = 7 + 7 * bgN, bg = 5 + 5 * bgN, bb = 4 + 4 * bgN;
  if (rad > 1.09f) br = bg = bb = 1;
  if (mask < 0.01f) {
    float mote = hashf(x * 11 + 3, y * 7 + 19);
    if (mote > 0.9985f && rad < 1.05f) {
      br += 36;
      bg += 28;
      bb += 16;
    }
    r = br;
    g = bg;
    b = bb;
    return;
  }

  float n1 = vnoise(x / 31.0f, y / 31.0f);
  float n2 = vnoise(x / 10.5f, y / 10.5f);
  float n3 = vnoise(x / 3.7f, y / 3.7f);
  float ar = 126, ag = 124, ab = 113; // cool gray volcanic stone under warm stage light
  float mineral = 0.55f * n1 + 0.35f * n2 + 0.10f * n3;
  ar *= 0.82f + 0.28f * mineral;
  ag *= 0.81f + 0.30f * mineral;
  ab *= 0.78f + 0.28f * mineral;

  // The shrine columns are irregular red masonry. Central collar stones and
  // ear plugs remain pale even where their geometry overlaps the brick mask.
  float shrine = unpackMask8(mat, 8);
  float earCore = unpackMask8(mat, 16), collarMat = unpackMask8(mat, 24);
  int brickRow = (int)floorf((v + 0.69f) / 0.29f);
  int brickSide = u < 0 ? -1 : 1;
  float brickVar = hashf(brickSide * 17 + brickRow * 5, brickRow * 13 + 9) - 0.5f;
  ar = lerpf(ar, 132 + 28 * brickVar, 0.86f * shrine);
  ag = lerpf(ag, 70 + 18 * brickVar, 0.86f * shrine);
  ab = lerpf(ab, 49 + 12 * brickVar, 0.86f * shrine);
  ar = lerpf(ar, 151, 0.78f * earCore);
  ag = lerpf(ag, 145, 0.78f * earCore);
  ab = lerpf(ab, 127, 0.78f * earCore);
  ar = lerpf(ar, 137, 0.72f * collarMat);
  ag = lerpf(ag, 132, 0.72f * collarMat);
  ab = lerpf(ab, 116, 0.72f * collarMat);
  float dusk = clampf(0.34f * rec, 0, 0.70f);
  ar = lerpf(ar, 38, dusk);
  ag = lerpf(ag, 31, dusk);
  ab = lerpf(ab, 25, dusk);

  float tq = unpackMask8(mat, 32);
  ar = lerpf(ar, 70, 0.46f * tq);
  ag = lerpf(ag, 91, 0.46f * tq);
  ab = lerpf(ab, 80, 0.46f * tq);
  float gd = unpackMask8(mat, 40);
  ar = lerpf(ar, 210, 0.88f * gd);
  ag = lerpf(ag, 163, 0.88f * gd);
  ab = lerpf(ab, 86, 0.88f * gd);

  float cav = unpackMask8(mat, 48);
  ar = lerpf(ar, 17, cav);
  ag = lerpf(ag, 8, cav);
  ab = lerpf(ab, 5, cav);
  float crack = unpackMask8(mat, 56);
  ar *= 1 - 0.48f * crack;
  ag *= 1 - 0.48f * crack;
  ab *= 1 - 0.45f * crack;

  // Moss collects mostly on upper-left horizontal shelves.
  float mossNoise = 0.62f * vnoise(x / 18.0f, y / 18.0f) + 0.38f * vnoise(x / 6.0f, y / 6.0f);
  float moss = sstep(0.61f, 0.78f, mossNoise) * sstep(-0.76f, -0.12f, -v) *
               clampf(0.55f + 0.55f * (-ny), 0, 1) * (1 - tq) * (1 - gd);
  ar = lerpf(ar, 58, 0.34f * moss);
  ag = lerpf(ag, 72, 0.34f * moss);
  ab = lerpf(ab, 43, 0.34f * moss);

  if (hashf(x * 3 + 7, y * 3 + 11) < 0.010f) lum *= 0.68f;
  float edge = sstep(0.0f, 0.12f, mask);
  r = lerpf(br, ar * lum, edge);
  g = lerpf(bg, ag * lum, edge);
  b = lerpf(bb, ab * lum, edge);
}

static inline uint16_t bitmapPixel(int x, int y) {
  return olmec_bitmap::PALETTE[olmec_bitmap::PIXELS[y * W + x]];
}

// Rounded slab cut from the painted neutral portrait. At jaw=0 the tile
// reconstructs the source art pixel-for-pixel; opening it reveals the dark
// cavity prepared underneath.
static inline float jawTileMask(int tx, int ty) {
  float tu = (tx + 0.5f - JAW_TILE_W * 0.5f) / (JAW_TILE_W * 0.5f);
  float tv = (ty + 0.5f) / JAW_TILE_H;
  float lipTop = 1.5f + 6.5f * (1 - fabsf(tu));
  float lip = roundedBoxMask(tu, tv - 0.135f, 0.96f, 0.17f, 0.11f, 0.012f);
  float chin = roundedBoxMask(tu, tv - 0.555f, 0.82f, 0.47f, 0.25f, 0.012f);
  return fmaxf(lip, chin) * sstep(lipTop - 1.0f, lipTop + 1.0f, ty);
}

static inline float jawCavityMask(int x, int y) {
  float tu = (x + 0.5f - 180.0f) / (JAW_TILE_W * 0.5f);
  float lipTop = 1.5f + 6.5f * (1 - fabsf(tu));
  float relY = y - JAW_TOP_CLOSED - lipTop;
  float t = clampf(relY / (JAW_TRAVEL + 6.0f), 0, 1);
  float endRound = 1 - sinf(t * 3.1415927f);
  float halfW = 0.90f - 0.08f * t - 0.045f * endRound;
  float horiz = 1 - sstep(halfW - 0.035f, halfW + 0.015f, fabsf(tu));
  float vert = sstep(-1.5f, 1.5f, relY) *
               (1 - sstep(JAW_TRAVEL + 1.0f, JAW_TRAVEL + 6.0f, relY));
  return horiz * vert;
}

static void renderBase(uint16_t *fb) {
  static_assert(olmec_bitmap::WIDTH == W && olmec_bitmap::HEIGHT == H, "face bitmap dimensions");
  for (int i = 0; i < W * H; i++)
    fb[i] = olmec_bitmap::PALETTE[olmec_bitmap::PIXELS[i]];

  // The source painting contains the fully awake ember slits. Turn those
  // interiors into unlit recesses so drawEyes owns every glow/blink state.
  for (int side = -1; side <= 1; side += 2) {
    float cx = 180 + side * EYE_CX * SCALE;
    float cy = 180 + EYE_CY * SCALE;
    for (int y = EYE_Y0; y < EYE_Y1; y++)
      for (int x = side < 0 ? EYEL_X0 : EYER_X0; x < (side < 0 ? EYEL_X1 : EYER_X1); x++) {
        float dx = (x - cx) / 30.0f, dy = (y - cy) / 10.2f;
        float d = dx * dx + dy * dy;
        if (d >= 1.0f) continue;
        float r, g, b;
        unpack565(fb[y * W + x], r, g, b);
        float ember = clampf((r - fmaxf(g, b) * 1.18f) / 120.0f, 0, 1);
        float a = clampf((1 - sstep(0.74f, 1.0f, d)) * 0.72f + ember * 0.55f, 0, 0.96f);
        fb[y * W + x] = pack565(lerpf(r, 13, a), lerpf(g, 6, a), lerpf(b, 4, a));
      }
  }

  // Hollow only the band that the jaw can uncover. Keeping the painted chin
  // below it prevents a black rectangular silhouette around the shifted tile.
  for (int y = JAW_TOP_CLOSED - 3; y < JAW_TOP_CLOSED + JAW_TRAVEL + 15; y++)
    for (int x = JAW_TILE_X; x < JAW_TILE_X + JAW_TILE_W; x++) {
      float m = jawCavityMask(x, y);
      if (m <= 0) continue;
      float side = fabsf((x + 0.5f - 180.0f) / (JAW_TILE_W * 0.5f));
      float warm = (1 - side) * (1 - clampf((y - JAW_TOP_CLOSED) / 38.0f, 0, 1));
      float r, g, b;
      unpack565(fb[y * W + x], r, g, b);
      fb[y * W + x] = pack565(lerpf(r, 11 + 10 * warm, m), lerpf(g, 5 + 4 * warm, m),
                                lerpf(b, 3 + 2 * warm, m));
    }
}

// ---------- expressive sliding lower face ----------
static Field jawField(float tu, float tv) {
  Field f;
  float side = fabsf(tu);
  f.h += 0.30f * (1 - 0.18f * tv);
  float edgeStart = 0.84f - 0.16f * tv;
  f.h -= 0.28f * sstep(edgeStart, 1.0f, side);            // chin tapers toward the neck
  f.h -= 0.12f * sstep(0.84f, 1.0f, tv) * (0.35f + 0.65f * side * side);
  f.h += 0.20f * bell2(tv - 0.10f, 0, 0.095f, 1);        // heavy lower lip
  f.h += 0.12f * bell2(tu, tv - 0.58f, 0.60f, 0.40f);    // rounded chin
  f.h += 0.045f * (bell2(tu - 0.38f, tv - 0.42f, 0.23f, 0.31f) +
                    bell2(tu + 0.38f, tv - 0.42f, 0.23f, 0.31f));
  f.h -= 0.028f * bell2(tv - 0.31f, 0, 0.060f, 1);       // lip/chin crease
  f.h -= 0.018f * bell2(tu, tv - 0.16f, 0.045f, 0.16f);  // lower-lip cleft
  f.rec += 0.38f * bell2(tv - 0.31f, 0, 0.078f, 1);
  return f;
}

static inline float jawGlyph(float tu, float tv) {
  float crease = bell2(tu, tv - 0.69f, 0.055f, 0.20f);
  return clampf(crease, 0, 1);
}

static void renderJawTile(uint16_t *tile) {
  for (int ty = 0; ty < JAW_TILE_H; ty++)
    for (int tx = 0; tx < JAW_TILE_W; tx++) {
      if (jawTileMask(tx, ty) < 0.5f) {
        tile[ty * JAW_TILE_W + tx] = 0;
        continue;
      }
      uint16_t c = bitmapPixel(JAW_TILE_X + tx, JAW_TOP_CLOSED + ty);
      tile[ty * JAW_TILE_W + tx] = c ? c : 1;
    }
}

// ---------- per-frame layers ----------
static inline void restoreRect(uint16_t *fb, const uint16_t *base, int x0, int y0, int x1, int y1) {
  for (int y = y0; y < y1; y++)
    memcpy(fb + y * W + x0, base + y * W + x0, (size_t)(x1 - x0) * 2);
}

static inline void blendPixel(uint16_t &dst, float r, float g, float b, float a) {
  if (a <= 0) return;
  float dr, dg, db;
  unpack565(dst, dr, dg, db);
  dst = pack565(lerpf(dr, r, clampf(a, 0, 1)), lerpf(dg, g, clampf(a, 0, 1)), lerpf(db, b, clampf(a, 0, 1)));
}

static void drawOneEye(uint16_t *fb, int side, const FaceState &s) {
  float ecx = 180 + side * EYE_CX * SCALE;
  float ecy = 180 + EYE_CY * SCALE;
  int x0 = side < 0 ? EYEL_X0 : EYER_X0;
  int x1 = side < 0 ? EYEL_X1 : EYER_X1;

  float gazeX = clampf(s.gx, -1, 1), gazeY = clampf(s.gy, -1, 1);
  float mood = clampf(s.mood, -1, 1), wild = clampf(s.wild, 0, 1), blink = clampf(s.blink, 0, 1);
  float happy = clampf(mood, 0, 1), angry = clampf(-mood, 0, 1);
  float sideSquint = clampf(side * gazeX, 0, 1);
  float asym = 1.0f + side * 0.07f * mood;
  float aw = EYE_AW * (1 + 0.06f * wild);
  float ah = (4.2f + 2.2f * s.glow + 3.4f * wild - 1.2f * happy - 0.8f * sideSquint) * asym;
  ah = fmaxf(0.45f, ah * (1 - 0.94f * blink));
  float lidTilt = side * (1.5f * gazeX + 2.4f * angry) - 0.7f * gazeY;
  float hotX = gazeX * 5.5f, hotY = gazeY * fminf(2.4f, ah * 0.35f);
  float glow = 0.23f + 0.77f * clampf(s.glow, 0, 1);
  float flicker = 0.92f + 0.08f * sinf(s.talkPhase * 0.71f + side * 1.4f);

  // Work only around the illuminated slit. Computing its vertical edge once
  // per column (instead of a sqrt for every dirty-rect pixel) is the critical
  // 240 MHz hot-path optimization.
  int ex0 = (int)(ecx - aw * 1.52f - 2), ex1 = (int)(ecx + aw * 1.52f + 3);
  if (ex0 < x0) ex0 = x0;
  if (ex1 > x1) ex1 = x1;
  for (int x = ex0; x < ex1; x++) {
    float dx = x - ecx;
    float ndx = dx / aw;
    float root = sqrtf(clampf(1 - ndx * ndx, 0, 1));
    float eyeCenterY = ecy + lidTilt * ndx;
    float eyeEdgeY = ah * root;
    float outerY = ah * 1.49f * root + 2.0f;
    int ey0 = (int)(eyeCenterY - outerY - 1), ey1 = (int)(eyeCenterY + outerY + 2);
    if (ey0 < EYE_Y0) ey0 = EYE_Y0;
    if (ey1 > EYE_Y1) ey1 = EYE_Y1;
    for (int y = ey0; y < ey1; y++) {
      float dy = y - eyeCenterY;
      float ed = ndx * ndx + (dy / ah) * (dy / ah);
      uint16_t &px = fb[y * W + x];

      // Soft red-orange spill catches the stone immediately around the slit.
      if (ed >= 1.0f && ed < 2.2f) {
        float halo = glow * (0.7f + 0.3f * wild) * (1 - (ed - 1.0f) / 1.2f) * 0.30f;
        blendPixel(px, 235, 63, 19, halo);
      }
      if (ed < 1.0f) {
        float edge = sstep(0.62f, 1.0f, ed);
        float coreDx = (dx - hotX) / 9.0f, coreDy = (dy - hotY) / fmaxf(1.2f, ah * 0.75f);
        float core = bell(coreDx * coreDx + coreDy * coreDy);
        float rr = lerpf(103, 255, core) * glow * flicker;
        float gg = lerpf(16, 83, core) * glow * flicker;
        float bb = lerpf(6, 24, core) * glow;
        rr = lerpf(rr, 25, 0.55f * edge);
        gg = lerpf(gg, 8, 0.65f * edge);
        bb = lerpf(bb, 4, 0.65f * edge);
        // A tiny travelling coal preserves gaze without turning into a pupil.
        float coalDx = dx - hotX, coalDy = dy - hotY;
        if (coalDx * coalDx + coalDy * coalDy < 2.3f + 2.0f * s.dil) {
          rr *= 0.28f;
          gg *= 0.22f;
          bb *= 0.18f;
        }
        px = pack565(rr, gg, bb);
      }

      // Dark stone rims clamp the light into the characteristic rectangular slit.
      float lidLine = fabsf(fabsf(dy) - eyeEdgeY);
      if (fabsf(dx) < aw && lidLine < 1.35f) blendPixel(px, 48, 42, 36, 0.86f);
    }
  }

  // The brow is a separate narrow pass rather than another full-rect scan.
  int bx0 = (int)(ecx - aw - 5), bx1 = (int)(ecx + aw + 6);
  if (bx0 < x0) bx0 = x0;
  if (bx1 > x1) bx1 = x1;
  float browBase = ecy - 18.0f - 3.0f * wild - 1.5f * happy + 1.5f * angry;
  float browSlope = -side * angry * 5.5f + side * gazeX * 1.5f;
  for (int x = bx0; x < bx1; x++) {
    float ndx = (x - ecx) / (aw + 1.0f);
    float browY = browBase + browSlope * ndx + happy * 1.8f * fabsf(ndx);
    int by0 = (int)(browY - 3.5f), by1 = (int)(browY + 4.5f);
    if (by0 < EYE_Y0) by0 = EYE_Y0;
    if (by1 > EYE_Y1) by1 = EYE_Y1;
    for (int y = by0; y < by1; y++) {
      float bd = fabsf(y - browY);
      if (bd >= 2.8f) continue;
      float ba = (1 - bd / 2.8f) * 0.62f;
      uint16_t &px = fb[y * W + x];
      if (y > browY) blendPixel(px, 55, 49, 42, ba);
      else blendPixel(px, 145, 142, 128, ba * 0.72f);
    }
  }
}

static void drawEyes(uint16_t *fb, const uint16_t *base, const FaceState &s) {
  restoreRect(fb, base, EYEL_X0, EYE_Y0, EYEL_X1, EYE_Y1);
  restoreRect(fb, base, EYER_X0, EYE_Y0, EYER_X1, EYE_Y1);
  drawOneEye(fb, -1, s);
  drawOneEye(fb, +1, s);
}

// Restore the mouth, curl the upper lip, light its depth, then drop the lower
// lip/chin tile. This stays close to the heavy animatronic mouth in the show.
static void drawJaw(uint16_t *fb, const uint16_t *base, const uint16_t *tile, const FaceState &s) {
  restoreRect(fb, base, JAW_X0, JAW_Y0, JAW_X1, JAW_Y1);
  int slabTop = JAW_TOP_CLOSED + (int)(clampf(s.jaw, 0, 1) * JAW_TRAVEL + 0.5f);
  float mood = clampf(s.mood, -1, 1), wild = clampf(s.wild, 0, 1);
  int jawShimmy = (int)(sinf(s.talkPhase * 1.7f) * (0.5f + 1.2f * wild) * s.talkGlow);

  // Reinforce the source painting's bowed upper lip while mood pulls its
  // corners up or down by only a few pixels.
  for (int x = 122; x < 238; x++) {
    float ex = fabsf((x - 180) / 58.0f);
    float lipY = JAW_TOP_CLOSED - 4.0f + 6.0f * (1 - ex) -
                 2.8f * fmaxf(mood, 0) * ex + 2.5f * fmaxf(-mood, 0) * ex;
    for (int y = JAW_Y0; y < JAW_TOP_CLOSED + 9; y++) {
      float d = fabsf(y - lipY);
      float body = clampf(1.0f - fabsf(y - (lipY - 2.6f)) / 4.7f, 0, 1) * (1 - sstep(0.78f, 1.0f, ex));
      if (body > 0.01f) blendPixel(fb[y * W + x], 121, 105, 84, body * 0.25f);
      if (d < 1.8f) blendPixel(fb[y * W + x], 31, 23, 18, (1 - d / 1.8f) * 0.88f);
      if (d >= 1.8f && d < 2.8f && y < lipY) blendPixel(fb[y * W + x], 166, 141, 108, 0.15f);
    }
  }

  int cavityBottom = slabTop + 10;
  if (cavityBottom > JAW_TOP_CLOSED + JAW_TRAVEL + 15)
    cavityBottom = JAW_TOP_CLOSED + JAW_TRAVEL + 15;
  for (int y = JAW_TOP_CLOSED - 1; y < cavityBottom; y++) {
    for (int x = JAW_TILE_X; x < JAW_TILE_X + JAW_TILE_W; x++) {
      float tu = (x + 0.5f - 180.0f) / (JAW_TILE_W * 0.5f);
      float movingLip = slabTop + 1.5f + 6.5f * (1 - fabsf(tu));
      float cav = jawCavityMask(x, y);
      if (cav < 0.02f || y >= movingLip) continue;
      float depth = clampf((y - (JAW_TOP_CLOSED + 1.5f)) / (JAW_TRAVEL + 8.0f), 0, 1);
      uint16_t &px = fb[y * W + x];
      float flicker = 0.88f + 0.12f * sinf(x * 0.31f + y * 0.17f);
      float ember = s.talkGlow * flicker * (0.18f + 0.82f * depth) * cav;
      blendPixel(px, 185, 35, 12, 0.46f * ember);
      blendPixel(px, 255, 91, 25, 0.22f * ember * depth);
    }
  }

  // A dark, broad tongue rises into the lower half of the opening. It is
  // clipped against the moving lower lip, so it peeks in naturally rather
  // than appearing as a sticker floating in front of the mouth.
  float mouthOpen = clampf(s.jaw, 0, 1);
  float tongueReveal = sstep(0.28f, 0.62f, mouthOpen);
  if (tongueReveal > 0.01f) {
    float tongueCy = JAW_TOP_CLOSED + 24.0f;
    for (int y = JAW_TOP_CLOSED + 12; y < JAW_TOP_CLOSED + 34; y++)
      for (int x = 137; x <= 223; x++) {
        float tu = (x + 0.5f - 180.0f) / (JAW_TILE_W * 0.5f);
        float movingLip = slabTop + 1.5f + 6.5f * (1 - fabsf(tu));
        if (y >= movingLip) continue;
        float dx = (x - 180.0f) / 43.0f, dy = (y - tongueCy) / 11.0f;
        float q = dx * dx + dy * dy;
        float shape = 1 - sstep(0.72f, 1.02f, q);
        if (shape <= 0) continue;
        float centerLift = (1 - fabsf(dx)) * (1 - fabsf(dy));
        blendPixel(fb[y * W + x], 104 + 28 * centerLift, 38 + 14 * centerLift,
                   42 + 12 * centerLift, tongueReveal * shape * 0.82f);
        if (fabsf(y - (tongueCy - 2.0f)) < 1.2f)
          blendPixel(fb[y * W + x], 169, 64, 66, tongueReveal * shape * 0.20f);
      }
  }

  // Four blunt, uneven temple-idol teeth appear only once the jaw has opened
  // far enough to expose them. Their short height keeps speech from becoming
  // a cartoon mouth.
  float toothReveal = sstep(0.18f, 0.62f, clampf(s.jaw, 0, 1));
  if (toothReveal > 0.01f) {
    static const int toothCx[4] = {153, 171, 189, 207};
    static const int toothH[4] = {9, 11, 10, 8};
    for (int n = 0; n < 4; n++) {
      for (int y = JAW_TOP_CLOSED + 5; y < JAW_TOP_CLOSED + 5 + toothH[n]; y++)
        for (int x = toothCx[n] - 8; x <= toothCx[n] + 8; x++) {
          float tu = (x + 0.5f - 180.0f) / (JAW_TILE_W * 0.5f);
          float movingLip = slabTop + 1.5f + 6.5f * (1 - fabsf(tu));
          if (y >= movingLip) continue;
          float dx = fabsf((x - toothCx[n]) / 8.5f);
          float dy = (y - (JAW_TOP_CLOSED + 5)) / (float)toothH[n];
          float shape = (1 - sstep(0.78f, 1.02f, dx)) * (1 - sstep(0.80f, 1.02f, dy));
          if (shape <= 0) continue;
          float edge = sstep(0.62f, 0.96f, dx) + sstep(0.64f, 0.96f, dy);
          blendPixel(fb[y * W + x], 171 - 36 * edge, 147 - 34 * edge, 105 - 24 * edge,
                     toothReveal * shape * 0.78f);
        }
    }
  }

  // Tiny patterned blotter tab, physically resting on the tongue. The 11 px
  // square is about 1.4 mm on the 47 mm display: readable, but still a gag
  // discovered only when the idol opens wide.
  float tabReveal = sstep(0.44f, 0.78f, mouthOpen);
  if (tabReveal > 0.01f) {
    int tabCx = 180 + (int)(sinf(s.talkPhase * 0.41f) * 0.8f * s.talkGlow);
    int tabCy = JAW_TOP_CLOSED + 19;
    for (int dy = -5; dy <= 5; dy++)
      for (int dx = -5; dx <= 5; dx++) {
        int x = tabCx + dx, y = tabCy + dy;
        float tu = (x + 0.5f - 180.0f) / (JAW_TILE_W * 0.5f);
        float movingLip = slabTop + 1.5f + 6.5f * (1 - fabsf(tu));
        if (y >= movingLip) continue;
        int ax = dx < 0 ? -dx : dx, ay = dy < 0 ? -dy : dy;
        bool shadow = ax == 5 || ay == 5;
        bool paperEdge = ax == 4 || ay == 4;
        float r = 232, g = 218, b = 171;
        if (shadow) {
          r = 49, g = 38, b = 30;
        } else if (!paperEdge) {
          if (dx < 0 && dy < 0) r = 218, g = 67, b = 126;
          else if (dx >= 0 && dy < 0) r = 55, g = 174, b = 184;
          else if (dx < 0) r = 232, g = 179, b = 48;
          else r = 111, g = 76, b = 160;
        }
        blendPixel(fb[y * W + x], r, g, b, tabReveal);
      }
  }

  int tx0 = JAW_TILE_X + jawShimmy;
  for (int ty = 0; ty < JAW_TILE_H; ty++) {
    int y = slabTop + ty;
    if (y < JAW_Y0 || y >= JAW_Y1) continue;
    const uint16_t *src = tile + ty * JAW_TILE_W;
    uint16_t *dst = fb + y * W + tx0;
    for (int tx = 0; tx < JAW_TILE_W; tx++)
      if (src[tx]) dst[tx] = src[tx];
  }

  // A restrained lower-lip lift follows the painted lip rather than replacing
  // it with a procedural slab.
  for (int x = 124 + jawShimmy; x < 236 + jawShimmy; x++) {
    float ex = fabsf((x - (180 + jawShimmy)) / 56.0f);
    float lowerY = slabTop + 9.5f + 3.5f * (1 - ex) -
                   1.4f * fmaxf(mood, 0) * ex + 1.2f * fmaxf(-mood, 0) * ex;
    for (int y = slabTop + 4; y < slabTop + 19 && y < JAW_Y1; y++) {
      float body = clampf(1.0f - fabsf(y - lowerY) / 5.5f, 0, 1) * (1 - sstep(0.78f, 1.0f, ex));
      if (body > 0.01f) blendPixel(fb[y * W + x], 145, 124, 96, body * 0.18f);
      if (fabsf((float)(x - (180 + jawShimmy))) < 1.2f && y < lowerY + 1.0f)
        blendPixel(fb[y * W + x], 47, 38, 30, body * 0.30f);
    }
  }
}

// Nostrils flare and acquire a dusty amber vapor-rim over the five-second breath
// cycle. It reads as breathing without drawing outside the tiny nose strip.
static void nostrilBreath(uint16_t *fb, const uint16_t *base, float breath) {
  restoreRect(fb, base, NOSE_X0, NOSE_Y0, NOSE_X1, NOSE_Y1);
  breath = clampf(breath, 0, 1);
  float sx = 0.040f + 0.012f * breath;
  float sy = 0.030f + 0.007f * breath;
  for (int y = NOSE_Y0; y < NOSE_Y1; y++) {
    float v = (y - 180) / SCALE;
    for (int x = NOSE_X0; x < NOSE_X1; x++) {
      float u = (x - 180) / SCALE;
      float n = bell2(u - 0.095f, v - 0.155f, sx, sy) + bell2(u + 0.095f, v - 0.155f, sx, sy);
      uint16_t &px = fb[y * W + x];
      if (n > 0.01f) {
        float dr, dg, db;
        unpack565(px, dr, dg, db);
        float k = 1 - (0.18f + 0.22f * breath) * clampf(n, 0, 1);
        px = pack565(dr * k, dg * k, db * k);
      }
      float vapor = breath * (bell2(u - 0.095f, v - 0.185f, 0.072f, 0.038f) +
                               bell2(u + 0.095f, v - 0.185f, 0.072f, 0.038f)) * (1 - clampf(n, 0, 1));
      if (vapor > 0.02f) blendPixel(px, 175, 137, 91, 0.08f * vapor);
    }
  }
}

} // namespace olmec
