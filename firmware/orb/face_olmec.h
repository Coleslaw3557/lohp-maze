// Temple Oracle — a procedural homage to the monumental talking stone head
// from Legends of the Hidden Temple. A tall gray volcanic-stone mask sits in a
// red masonry shrine with round ear disks, a studded crown, narrow ember eyes,
// heavy lips, breathing nostrils, and an expressive sliding lower face.
//
// Pure procedural C++: no assets and no Arduino-only types. renderBase() and
// renderJawTile() run once at boot; only the declared eye, jaw, and nose dirty
// rectangles change per frame. The public FaceState contract is unchanged.
#pragma once
#include <math.h>
#include <stdint.h>
#include <string.h>

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
constexpr int EYEL_X0 = 101, EYEL_X1 = 178;
constexpr int EYER_X0 = 182, EYER_X1 = 259;
constexpr int EYE_Y0 = 112, EYE_Y1 = 177;
constexpr int JAW_X0 = 106, JAW_X1 = 254;
constexpr int JAW_Y0 = 214, JAW_Y1 = 326;
constexpr int NOSE_X0 = 145, NOSE_X1 = 215;
constexpr int NOSE_Y0 = 174, NOSE_Y1 = 226;

constexpr float EYE_CX = 0.245f, EYE_CY = -0.225f;
constexpr float EYE_AW = 27.5f, EYE_AH = 8.5f;

// The jaw is still a rigid prerendered tile, but its mask has a rounded simian
// chin and a central inlaid glyph. The open gap exposes teeth drawn by drawJaw.
constexpr float CAV_U = 0.37f, CAV_V0 = 0.285f, CAV_V1 = 0.70f;
constexpr int JAW_TILE_W = 122;
constexpr int JAW_TILE_H = 66;
constexpr int JAW_TILE_X = (W - JAW_TILE_W) / 2;
constexpr int JAW_TOP_CLOSED = 232;
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

// ---------- sculpted head height field ----------
struct Field {
  float h = 0, rec = 0;
};

static Field faceField(float u, float v) {
  Field f;
  float au = fabsf(u);
  float fm = faceMask(u, v), cm = crownMask(u, v), em = earMask(u, v), pm = portalMask(u, v);

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
  f.h += 0.07f * goldMask(u, v);
  for (int side = -1; side <= 1; side += 2) {
    f.h -= 0.075f * bell2(u - side * 0.43f, v + 0.82f, 0.070f, 0.060f);
    f.rec += 0.45f * bell2(u - side * 0.43f, v + 0.82f, 0.070f, 0.060f);
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
  f.h *= all;
  f.rec *= all;
  return f;
}

// ---------- weathered gray volcanic-stone shading ----------
static inline void shadePixel(int x, int y, float h0, float hx0, float hy0, float rec,
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

  float mask = stoneMask(u, v);
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

  // The shrine columns are red masonry; recesses gather brown-black patina.
  float pm = portalMask(u, v);
  ar = lerpf(ar, 132, 0.82f * pm);
  ag = lerpf(ag, 70, 0.82f * pm);
  ab = lerpf(ab, 49, 0.82f * pm);
  float dusk = clampf(0.34f * rec, 0, 0.70f);
  ar = lerpf(ar, 38, dusk);
  ag = lerpf(ag, 31, dusk);
  ab = lerpf(ab, 25, dusk);

  float tq = turquoiseMask(u, v);
  ar = lerpf(ar, 70, 0.46f * tq);
  ag = lerpf(ag, 91, 0.46f * tq);
  ab = lerpf(ab, 80, 0.46f * tq);
  float gd = goldMask(u, v);
  ar = lerpf(ar, 210, 0.88f * gd);
  ag = lerpf(ag, 163, 0.88f * gd);
  ab = lerpf(ab, 86, 0.88f * gd);

  float cav = cavityMask(u, v);
  ar = lerpf(ar, 17, cav);
  ag = lerpf(ag, 8, cav);
  ab = lerpf(ab, 5, cav);
  float crack = crackMask(u, v);
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

static void renderBase(uint16_t *fb) {
  float *hh = (float *)OLMEC_ALLOC((size_t)W * H * sizeof(float));
  float *rr = (float *)OLMEC_ALLOC((size_t)W * H * sizeof(float));
  if (!hh || !rr) {
    if (hh) free(hh);
    if (rr) free(rr);
    return;
  }
  for (int y = 0; y < H; y++)
    for (int x = 0; x < W; x++) {
      Field f = faceField((x - 180) / SCALE, (y - 180) / SCALE);
      hh[y * W + x] = f.h;
      rr[y * W + x] = f.rec;
    }
  for (int y = 0; y < H; y++)
    for (int x = 0; x < W; x++) {
      int i = y * W + x;
      float hx0 = x + 1 < W ? hh[i + 1] : hh[i];
      float hy0 = y + 1 < H ? hh[i + W] : hh[i];
      float r, g, b;
      shadePixel(x, y, hh[i], hx0, hy0, rr[i], r, g, b);
      fb[i] = pack565(r, g, b);
    }
  free(hh);
  free(rr);
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
  const float e = 2.0f / JAW_TILE_W;
  for (int ty = 0; ty < JAW_TILE_H; ty++)
    for (int tx = 0; tx < JAW_TILE_W; tx++) {
      float tu = (tx - JAW_TILE_W / 2) / (JAW_TILE_W / 2.0f);
      float tv = ty / (float)JAW_TILE_H;
      Field f0 = jawField(tu, tv), fx = jawField(tu + e, tv), fy = jawField(tu, tv + e);
      if (f0.h < 0.13f) {
        tile[ty * JAW_TILE_W + tx] = 0;
        continue;
      }
      float nx = -(fx.h - f0.h) / e * 0.88f, ny = -(fy.h - f0.h) / e * 0.88f, nz = 1;
      float il = 1.0f / sqrtf(nx * nx + ny * ny + nz * nz);
      nx *= il;
      ny *= il;
      nz *= il;
      float d = nx * -0.43f + ny * -0.61f + nz * 0.66f;
      float lum = 0.24f + 0.88f * (d > 0 ? d : 0);
      lum *= 0.58f + 0.42f / (1 + 1.2f * f0.rec);
      int ax = JAW_TILE_X + tx, ay = JAW_TOP_CLOSED + ty;
      float n = 0.58f * vnoise(ax / 27.0f, ay / 27.0f) + 0.42f * vnoise(ax / 9.0f, ay / 9.0f);
      float ar = 124 * (0.82f + 0.28f * n), ag = 121 * (0.81f + 0.30f * n), ab = 109 * (0.78f + 0.28f * n);
      float lip = bell2(tv - 0.105f, 0, 0.09f, 1);
      ar = lerpf(ar, 91, 0.42f * lip);
      ag = lerpf(ag, 84, 0.42f * lip);
      ab = lerpf(ab, 75, 0.42f * lip);
      float glyph = jawGlyph(tu, tv);
      ar = lerpf(ar, 64, 0.36f * glyph);
      ag = lerpf(ag, 61, 0.36f * glyph);
      ab = lerpf(ab, 55, 0.36f * glyph);
      uint16_t c = pack565(ar * lum, ag * lum, ab * lum);
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
  int gapBottom = slabTop < JAW_Y1 ? slabTop : JAW_Y1;
  float mood = clampf(s.mood, -1, 1), wild = clampf(s.wild, 0, 1);
  int jawShimmy = (int)(sinf(s.talkPhase * 1.7f) * (0.5f + 1.2f * wild) * s.talkGlow);

  // The upper lip curls by only a few pixels, preserving the monumental read.
  for (int x = 122; x < 238; x++) {
    float ex = fabsf((x - 180) / 58.0f);
    float lipY = JAW_TOP_CLOSED - 4.0f - 2.8f * fmaxf(mood, 0) * ex + 2.5f * fmaxf(-mood, 0) * ex;
    for (int y = JAW_Y0; y < JAW_TOP_CLOSED + 3; y++) {
      float d = fabsf(y - lipY);
      float body = clampf(1.0f - fabsf(y - (lipY - 2.6f)) / 4.7f, 0, 1) * (1 - sstep(0.78f, 1.0f, ex));
      if (body > 0.01f) blendPixel(fb[y * W + x], 128, 123, 111, body * 0.46f);
      if (d < 2.0f) blendPixel(fb[y * W + x], 43, 36, 31, (1 - d / 2.0f) * 0.82f);
      if (d >= 2.0f && d < 3.0f && y < lipY) blendPixel(fb[y * W + x], 151, 145, 130, 0.22f);
    }
  }

  for (int y = JAW_TOP_CLOSED - 3; y < gapBottom; y++) {
    float depth = clampf((float)(y - JAW_TOP_CLOSED + 3) / (gapBottom - JAW_TOP_CLOSED + 3.0f), 0, 1);
    for (int x = JAW_X0 + 9; x < JAW_X1 - 9; x++) {
      float u = (x - 180) / SCALE, v = (y - 180) / SCALE;
      if (cavityMask(u, v) < 0.45f) continue;
      uint16_t &px = fb[y * W + x];
      float flicker = 0.88f + 0.12f * sinf(x * 0.31f + y * 0.17f);
      float ember = s.talkGlow * flicker * (0.20f + 0.80f * depth);
      blendPixel(px, 185, 35, 12, 0.46f * ember);
      blendPixel(px, 255, 91, 25, 0.22f * ember * depth);
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

  // A separate lower-lip highlight keeps the closed mouth from reading as a
  // mechanical rectangle while remaining attached to the rigid jaw tile.
  for (int x = 124 + jawShimmy; x < 236 + jawShimmy; x++) {
    float ex = fabsf((x - (180 + jawShimmy)) / 56.0f);
    float lowerY = slabTop + 5.5f - 1.4f * fmaxf(mood, 0) * ex + 1.2f * fmaxf(-mood, 0) * ex;
    for (int y = slabTop; y < slabTop + 13 && y < JAW_Y1; y++) {
      float body = clampf(1.0f - fabsf(y - lowerY) / 5.0f, 0, 1) * (1 - sstep(0.78f, 1.0f, ex));
      if (body > 0.01f) blendPixel(fb[y * W + x], 137, 131, 118, body * 0.48f);
      if (fabsf((float)(x - (180 + jawShimmy))) < 1.2f && y < lowerY + 1.0f)
        blendPixel(fb[y * W + x], 56, 50, 44, body * 0.48f);
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
      float n = bell2(u - 0.095f, v - 0.205f, sx, sy) + bell2(u + 0.095f, v - 0.205f, sx, sy);
      uint16_t &px = fb[y * W + x];
      if (n > 0.01f) {
        float dr, dg, db;
        unpack565(px, dr, dg, db);
        float k = 1 - (0.18f + 0.22f * breath) * clampf(n, 0, 1);
        px = pack565(dr * k, dg * k, db * k);
      }
      float vapor = breath * (bell2(u - 0.095f, v - 0.235f, 0.072f, 0.038f) +
                               bell2(u + 0.095f, v - 0.235f, 0.072f, 0.038f)) * (1 - clampf(n, 0, 1));
      if (vapor > 0.02f) blendPixel(px, 175, 137, 91, 0.08f * vapor);
    }
  }
}

} // namespace olmec
