// Camp-sign bridge — hardware + zone configuration.
// Pin truth: ../../wiring-guides/camp-sign-wiring-guide.md ("Controller cavity");
// zone map + decode spec: ../../wiring-guides/camp-sign-plan.md (the zone map's
// production source is light_config.json room "Camp Sign" — verified 24 × 8-ch
// slots @161..345 against this table).
#pragma once
#include <stdint.h>
#include <stddef.h>

// ---- XIAO ESP32-S3 pins ----
#define PIN_DATA1 1   // D0 → AHCT 1A→1Y → chain 1 "Legends of the", enters at 'e'
#define PIN_DATA2 2   // D1 → AHCT 2A→2Y → chain 2 logo field (disc)
#define PIN_DATA3 3   // D2 → AHCT 3A→3Y → chain 3 "Hidden Playa", enters at 'H'
#define PIN_BTN 4     // D3 ← storm button microswitch NO shorts to GND (INPUT_PULLUP)
#define PIN_DMX_RO 5  // D4 ← MAX485 RO. Dfi wired-DMX fallback — deliberately NOT
                      // in this build (plan: esp_dmx only if the tower WiFi fails)

// ---- ArtDMX in (dmx_nodes.json: universe 0, UDP :6454) ----
#define ARTNET_PORT 6454
#define ARTNET_UNIVERSE 0

// ---- DMX slotting (light_config.json "Camp Sign": 24 × 8-ch zones @161) ----
#define ZONE_COUNT 24
#define ZONE_DMX_FIRST 161  // 1-indexed DMX address of zone 0; zone k = 161+8k
// Per-zone byte layout (matches the ZQ01424 par, camp-sign-plan.md):
//   +0 total_dimming  +1 R  +2 G  +3 B  +4 W  +5 strobe  +6..7 unused

// ---- Behavior ----
#define RENDER_MS 10              // LED update tick (strobe tops out ~12 Hz)
#define SIGNAL_LOSS_MS 3000       // no ArtDMX for this long -> amber breathe
                                  // (server heartbeats each node at 1 Hz while static,
                                  // so 3 s = three missed heartbeats, not a quiet show)
#define BREATHE_PERIOD_MS 5000    // loss-fallback breathe cycle
#define BREATHE_PEAK 140          // loss-fallback peak brightness (0-255)
#define BTN_DEBOUNCE_MS 50
#define STORM_HTTP_TIMEOUT_MS 5000  // long enough to SEE the 200/429 — the ~3.5 s
                                    // strike answers late; the server owns the cooldown

// ---- Strip ----
// BTF 12V WS2811 60 LED/m: 1 pixel = one 3-LED group ≈ 2 in.
// VERIFY ORDER on the first strip test: serial 'r' must light RED (12V WS2811
// reels ship RGB or BRG depending on batch) — if not, change here + reflash.
#define SIGN_COLOR_ORDER RGB

// A letter (or the logo): its zone id + how many pixels it got on the strip.
struct ZoneRun {
  uint8_t zone;
  uint16_t px;
};

// Pixel counts below are the PLAN ESTIMATES (big letter ~14 px, small ~6 px,
// logo ~56 px). Count real pixels per letter AS INSTALLED and correct these
// (build sequence step 2) — letter = zone = contiguous pixel range.
// Order = physical strip order leaving the box (pixel 0 at band center).

// Chain 1: e h t · f o · s d n e g e L (the/of/Legends, all reversed)
constexpr ZoneRun OUT1_RUNS[] = {
    {11, 6}, {10, 6}, {9, 6},                                  // e h t  (@249,241,233)
    {8, 6},  {7, 6},                                           // f o    (@225,217)
    {6, 14}, {5, 14}, {4, 14}, {3, 14}, {2, 14}, {1, 14}, {0, 14},  // s d n e g e L (@209..161)
};
// Chain 2: logo field behind the disc
constexpr ZoneRun OUT2_RUNS[] = {
    {12, 56},                                                  // logo (@257)
};
// Chain 3: H i d d e n · P l a y a
constexpr ZoneRun OUT3_RUNS[] = {
    {13, 14}, {14, 14}, {15, 14}, {16, 14}, {17, 14}, {18, 14},  // Hidden (@265..305)
    {19, 14}, {20, 14}, {21, 14}, {22, 14}, {23, 14},            // Playa  (@313..345)
};

constexpr uint16_t runTotal(const ZoneRun *r, size_t n) {
  return n == 0 ? 0 : r->px + runTotal(r + 1, n - 1);
}
constexpr uint16_t OUT1_PX = runTotal(OUT1_RUNS, sizeof(OUT1_RUNS) / sizeof(*OUT1_RUNS));
constexpr uint16_t OUT2_PX = runTotal(OUT2_RUNS, sizeof(OUT2_RUNS) / sizeof(*OUT2_RUNS));
constexpr uint16_t OUT3_PX = runTotal(OUT3_RUNS, sizeof(OUT3_RUNS) / sizeof(*OUT3_RUNS));

// Reading-order names for the serial 'z' dump.
static const char *const ZONE_NAME[ZONE_COUNT] = {
    "L", "e", "g", "e", "n", "d", "s", "o", "f", "t", "h", "e",
    "LOGO", "H", "i", "d", "d", "e", "n", "P", "l", "a", "y", "a",
};
