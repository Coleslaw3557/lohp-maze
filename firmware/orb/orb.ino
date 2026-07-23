// LoHP Cuddle Orb — Olmec talking-head firmware for the Guition JC3636W518C
// round display (see board.h for the hardware map, cuddle-orb-plan.md for the
// plan). The face is a Legends of the Hidden Temple-style Olmec homage
// (face_olmec.h, shared verbatim with tools/preview_face.cpp for host preview).
//
// Render architecture: the terracotta head shades once at boot into a PSRAM
// base layer + one full flush; the sliding jaw slab prerenders once into a
// small tile. Per frame only the eye rects repaint (glow pulses + pupils
// track); the jaw region repaints only while the jaw is moving or the void
// glow changes, the nostril rect only on breath steps.
//
// Movement: pupils track gaze (synthetic attention until the LD2450 relay
// lands) with saccades; the idol blinks, cycles through suspicious/delighted/
// startled moods, throws its stone brows around, glows when a target is
// present, breathes, and TALKS — idle chatter episodes every ~20-35 s, a
// "notices you" drop when someone appears, and it holds open through each
// gesture POST (he's mid-sentence while the blocking HTTP call runs).
//
// Gestures (no IMU / no dock detect on this hardware — see plan doc). The orb
// is the whole Cuddle control surface — these replace wall buttons there:
//   tap        -> POST /api/set_theme {"next_theme": true}   (next lighting theme)
//   swipe      -> POST /api/toggle_music {}                  (music on/off)
//   long-press -> POST /api/run_effect_all_rooms {"effect_name":"LightningStorm"}

#include <Arduino_GFX_Library.h>
#include <ArduinoOTA.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <Wire.h>
#include <esp_ota_ops.h>
#include <math.h>

#include "board.h"
#include "face_olmec.h"
#include "secrets.h"

Arduino_DataBus *bus = new Arduino_ESP32QSPI(
    LCD_QSPI_CS, LCD_QSPI_CLK, LCD_QSPI_D0, LCD_QSPI_D1, LCD_QSPI_D2, LCD_QSPI_D3);
Arduino_GFX *panel = new Arduino_ST77916(bus, LCD_RST, 0, true, LCD_W, LCD_H);
Arduino_Canvas *gfx = new Arduino_Canvas(LCD_W, LCD_H, panel);

uint16_t *baseLayer = nullptr; // pristine head, PSRAM
uint16_t *jawTile = nullptr;   // prerendered jaw slab, PSRAM
bool havePanel = false, haveTouch = false;

// declared before the first function: the .ino preprocessor hoists auto
// prototypes above everything below this point
struct TouchState {
  bool down = false;
  int x = 0, y = 0;
};

// ---------- CST816 ----------
static void touchReset() {
  pinMode(TOUCH_RST, OUTPUT);
  digitalWrite(TOUCH_RST, LOW);
  delay(8);
  digitalWrite(TOUCH_RST, HIGH);
  delay(120); // chip ACKs in the window right after reset
}

static bool cstWrite(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(CST816_ADDR);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

static int cstRead(uint8_t reg, uint8_t *buf, size_t n) {
  Wire.beginTransmission(CST816_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return -1;
  size_t got = Wire.requestFrom((int)CST816_ADDR, (int)n);
  for (size_t i = 0; i < got; i++) buf[i] = Wire.read();
  return (int)got;
}

static bool touchPoll(TouchState &t) {
  uint8_t d[6];
  if (cstRead(0x01, d, 6) != 6) { // asleep chips NACK until first touch
    t.down = false;               // never leave a stale press latched
    return false;
  }
  uint8_t fingers = d[1];
  t.down = fingers > 0;
  if (t.down) {
    t.x = ((d[2] & 0x0F) << 8) | d[3];
    t.y = ((d[4] & 0x0F) << 8) | d[5];
  }
  return true;
}

// ---------- dirty-rect blit ----------
// contiguous scratch for the largest rect (jaw: 136x90)
static uint16_t blitScratch[(olmec::JAW_X1 - olmec::JAW_X0) * (olmec::JAW_Y1 - olmec::JAW_Y0)];

static void blitRect(int x0, int y0, int x1, int y1) {
  int w = x1 - x0, h = y1 - y0;
  uint16_t *fb = gfx->getFramebuffer();
  for (int y = 0; y < h; y++)
    memcpy(blitScratch + y * w, fb + (y0 + y) * LCD_W + x0, (size_t)w * 2);
  panel->draw16bitRGBBitmap(x0, y0, blitScratch, w, h);
}

static void blitEyes() {
  blitRect(olmec::EYEL_X0, olmec::EYE_Y0, olmec::EYEL_X1, olmec::EYE_Y1);
  blitRect(olmec::EYER_X0, olmec::EYE_Y0, olmec::EYER_X1, olmec::EYE_Y1);
}

// ---------- server calls ----------
static int postJson(const char *path, const char *body) {
  if (WiFi.status() != WL_CONNECTED) return -1;
  HTTPClient http;
  http.setConnectTimeout(800);
  http.setTimeout(1500);
  String url = String("http://") + SERVER_HOST + ":" + SERVER_PORT + path;
  if (!http.begin(url)) return -2;
  http.addHeader("Content-Type", "application/json");
  int code = http.POST((uint8_t *)body, strlen(body));
  http.end();
  Serial.printf("[orb] POST %s -> %d\n", path, code);
  return code;
}

// Drop the jaw open with a glowing void, blit, run the blocking call: the
// stone head is mid-sentence for the freeze instead of visibly hanging.
static void speakingCall(const char *path, const char *body) {
  olmec::FaceState s;
  s.jaw = 1.0f;
  s.talkGlow = 1.0f;
  s.glow = 1.0f;
  s.mood = 0.55f;
  s.wild = 0.90f;
  s.talkPhase = millis() * 0.0132f;
  uint16_t *fb = gfx->getFramebuffer();
  olmec::drawEyes(fb, baseLayer, s);
  olmec::drawJaw(fb, baseLayer, jawTile, s);
  blitEyes();
  blitRect(olmec::JAW_X0, olmec::JAW_Y0, olmec::JAW_X1, olmec::JAW_Y1);
  postJson(path, body);
}

// ---------- state ----------
uint32_t lastFrame = 0, bootMs = 0, lastBeat = 0;
uint32_t frames = 0, frameMsAcc = 0;
uint32_t eyesUs = 0, jawUs = 0, blitUs = 0; // per-stage budget telemetry
float gxS = 0, gyS = 0;                     // smoothed gaze
float sacX = 0, sacY = 0, sacT = 3;         // saccade offset + next-jump timer
float glowS = 0;                            // eased eye glow
float moodS = -0.15f, wildS = 0.05f;        // expression morph channels
float blinkT = 2.4f, blinkLeft = 0, blinkLen = 0.16f, blinkValue = 0;
bool blinkAgain = false, blinkSecondPending = false;
float jawPos = 0, lastJawDrawn = -1, lastTalkGlowDrawn = -1;
float lastMoodJawDrawn = 9, lastWildJawDrawn = 9;
float talkT = 12;                           // seconds until the next idle chatter
float talkLeft = 0, talkLen = 0;            // active episode countdown/length
float lastBreathDrawn = -1;
float wasAwake = 0;
TouchState touch;
bool wasDown = false;
uint32_t downAt = 0, lastGestureAt = 0;
int downX = 0, downY = 0; // where the press started
bool movedFar = false;    // finger crossed swipe distance since press
bool longFired = false;
bool otaReady = false;

void setup() {
  Serial.begin(115200);
  delay(300);
  bootMs = millis();
  Serial.println("\n[orb] LoHP cuddle orb — JC3636W518C build " __DATE__ " " __TIME__);
  // USB flash always boots app0; OTA writes the inactive slot — the label here
  // is the ground truth for "did my OTA land"
  const esp_partition_t *part = esp_ota_get_running_partition();
  Serial.printf("[orb] running from %s @0x%06lx\n", part->label, (unsigned long)part->address);

  Wire.begin(I2C_SDA, I2C_SCL, 400000);
  touchReset(); // wake the CST816 first or the scan sees a silent bus

  // Bus fingerprint — on this wiring only the CST816 (0x15) should appear
  Serial.print("[orb] i2c scan:");
  for (uint8_t a = 8; a <= 0x77; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) Serial.printf(" 0x%02X", a);
  }
  Serial.println();

  pinMode(BL_GPIO, OUTPUT); // backlight off until the first real frame is up
  digitalWrite(BL_GPIO, LOW);

  touchReset();
  uint8_t chipId = 0;
  haveTouch = cstRead(0xA7, &chipId, 1) == 1;
  if (haveTouch) cstWrite(0xFE, 0x01); // disable auto-sleep so polling works
  Serial.printf("[orb] cst816 @0x15: %s (chip id 0x%02X)\n",
                haveTouch ? "OK, auto-sleep off" : "no response", chipId);

  havePanel = gfx->begin(LCD_QSPI_HZ);
  Serial.printf("[orb] st77916 qspi begin: %s\n", havePanel ? "OK" : "FAILED");

  if (havePanel) { // RGB sweep: proves panel end-to-end before the face starts
    gfx->fillScreen(RGB565_RED);
    gfx->flush();
    digitalWrite(BL_GPIO, HIGH); // reveal only after the first frame: no boot garbage
    delay(250);
    gfx->fillScreen(RGB565_GREEN);
    gfx->flush();
    delay(250);
    gfx->fillScreen(RGB565_BLUE);
    gfx->flush();
    delay(250);
    gfx->fillScreen(RGB565_BLACK);
    gfx->flush();
  }

  baseLayer = (uint16_t *)ps_malloc(LCD_W * LCD_H * 2);
  jawTile = (uint16_t *)ps_malloc(olmec::JAW_TILE_W * olmec::JAW_TILE_H * 2);
  if (!baseLayer || !jawTile) Serial.println("[orb] FATAL: no PSRAM for face layers");
  if (havePanel && baseLayer && jawTile) {
    uint32_t t0 = millis();
    olmec::renderBase(gfx->getFramebuffer()); // carve the head
    olmec::renderJawTile(jawTile);
    memcpy(baseLayer, gfx->getFramebuffer(), LCD_W * LCD_H * 2);
    // first frame: eyes open, jaw closed
    olmec::FaceState s;
    olmec::drawEyes(gfx->getFramebuffer(), baseLayer, s);
    olmec::drawJaw(gfx->getFramebuffer(), baseLayer, jawTile, s);
    gfx->flush();
    Serial.printf("[orb] olmec carved in %lums, heap=%u psram=%u\n",
                  (unsigned long)(millis() - t0), ESP.getFreeHeap(), ESP.getFreePsram());
  }

  WiFi.mode(WIFI_STA);
  WiFi.setHostname("lohp-orb");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("[orb] wifi: connecting to %s\n", WIFI_SSID);
}

void loop() {
  uint32_t now = millis();
  if (now - lastFrame < 20) {
    delay(2);
    return;
  }
  uint32_t frameStart = now;
  float dt = (now - lastFrame) / 1000.0f;
  lastFrame = now;
  float t = (now - bootMs) / 1000.0f;

  static wl_status_t lastWifi = WL_IDLE_STATUS;
  wl_status_t ws = WiFi.status();
  if (ws != lastWifi) {
    lastWifi = ws;
    if (ws == WL_CONNECTED) {
      Serial.printf("[orb] wifi: connected, ip=%s\n", WiFi.localIP().toString().c_str());
      if (!otaReady) {
        ArduinoOTA.setHostname("lohp-orb");
        ArduinoOTA.setPassword(OTA_PASSWORD);
        ArduinoOTA.begin();
        otaReady = true;
      }
    } else {
      Serial.printf("[orb] wifi: status %d\n", ws);
    }
  }
  if (otaReady) ArduinoOTA.handle();

  // -- touch gestures --
  if (touchPoll(touch) && !haveTouch) {
    haveTouch = true; // chip finally ACKed (CST816 sleeps until first touch)
    cstWrite(0xFE, 0x01);
    Serial.println("[orb] cst816 awake, auto-sleep disabled");
  }
  bool cooled = now - lastGestureAt > 1000;
  bool spoke = false;
  if (touch.down && !wasDown) {
    downAt = now;
    downX = touch.x;
    downY = touch.y;
    movedFar = false;
    longFired = false;
  }
  if (touch.down) {
    int dx = touch.x - downX, dy = touch.y - downY;
    if (dx * dx + dy * dy >= 60 * 60) movedFar = true; // ~1/6 of the panel
  }
  // movedFar gates the long-press: a swipe that ends in a rest must stay a
  // swipe, not ripen into the storm
  if (touch.down && !longFired && !movedFar && now - downAt >= 1200 && cooled) {
    longFired = true;
    lastGestureAt = now;
    Serial.println("[orb] gesture: LONG-PRESS -> storm all rooms");
    speakingCall("/api/run_effect_all_rooms", "{\"effect_name\":\"LightningStorm\"}");
    spoke = true;
  }
  if (!touch.down && wasDown && !longFired && cooled) {
    if (movedFar) { // any direction, any speed — the most forgiving playa gesture
      lastGestureAt = now;
      Serial.println("[orb] gesture: SWIPE -> toggle music");
      speakingCall("/api/toggle_music", "{}");
      spoke = true;
    } else if (now - downAt < 600) {
      lastGestureAt = now;
      Serial.println("[orb] gesture: TAP -> next theme");
      speakingCall("/api/set_theme", "{\"next_theme\":true}");
      spoke = true;
    }
  }
  wasDown = touch.down;
  if (spoke) { // finish the sentence after the call returns
    jawPos = 1.0f;
    talkLen = 1.5f;
    talkLeft = 1.5f;
  }

  // -- synthetic attention until the LD2450 feed lands (plan: server relays
  // the same radar the floor projection reads) --
  float phase = fmodf(t, 12.0f);
  float nearT = (phase < 6.0f) ? fmaxf(0.0f, 1.0f - fabsf(phase - 3.0f) / 2.5f) : 0.0f;
  float awake = nearT > 0.05f ? 1.0f : 0.0f;
  float gx = sinf(t * 0.9f) * (nearT > 0.1f ? 0.8f : 0.35f);
  float gy = sinf(t * 0.7f + 1.3f) * (nearT > 0.1f ? 0.6f : 0.2f);
#if GAZE_FLIP_X
  gx = -gx;
#endif

  // saccades: quick small jumps layered on the smooth pursuit
  sacT -= dt;
  if (sacT <= 0) {
    sacX = (awake ? 0.14f : 0.06f) * sinf(t * 37.7f);
    sacY = (awake ? 0.10f : 0.04f) * cosf(t * 29.3f);
    sacT = 1.2f + 2.8f * (0.5f + 0.5f * sinf(t * 1.7f));
  }
  float lag = fminf(1.0f, dt * 7.0f);
  gxS += (gx + sacX - gxS) * lag;
  gyS += (gy + sacY - gyS) * lag;

  // eye glow: lights up while watching, gentle pulse
  float glowTarget = awake * (0.80f + 0.20f * sinf(t * 2.9f));
  glowS += (glowTarget - glowS) * fminf(1.0f, dt * 3.0f);

  // Uneven organic blinks, including an occasional quick double-blink. Wild
  // surprise holds the eyes open longer; relaxed stone-face blinks slowly.
  if (blinkLeft > 0) {
    blinkLeft -= dt;
    float bp = 1.0f - olmec::clampf(blinkLeft / blinkLen, 0, 1);
    blinkValue = sinf(3.1416f * bp);
    if (blinkLeft <= 0) {
      blinkValue = 0;
      blinkT = blinkAgain ? 0.11f : 2.1f + 3.8f * (0.5f + 0.5f * sinf(t * 0.73f + 1.2f));
      blinkSecondPending = blinkAgain;
      blinkAgain = false;
    }
  } else {
    blinkT -= dt;
    blinkValue = 0;
    if (blinkT <= 0) {
      bool secondBlink = blinkSecondPending;
      blinkSecondPending = false;
      blinkLen = 0.13f + 0.06f * (0.5f + 0.5f * sinf(t * 1.91f));
      blinkLeft = blinkLen;
      blinkAgain = !secondBlink && ((now / 1000) % 7) == 3 && wildS < 0.55f;
    }
  }

  // -- jaw talk scheduler --
  if (awake > 0.5f && wasAwake <= 0.5f && talkLeft <= 0) {
    talkLen = 0.9f; // notices someone: a short greeting chatter
    talkLeft = 0.9f;
  }
  wasAwake = awake;
  talkT -= dt;
  if (talkT <= 0 && talkLeft <= 0) {
    talkLen = 1.6f + (now % 1000) / 1000.0f;   // idle chatter episode
    talkLeft = talkLen;
    talkT = 20.0f + (now % 15000) / 1000.0f;   // next one in 20-35 s
  }
  float jawTarget = 0, talkGlow = 0;
  if (talkLeft > 0) {
    talkLeft -= dt;
    float prog = 1.0f - talkLeft / talkLen;
    float env = sinf(3.1416f * fminf(prog * 1.15f, 1.0f)); // ease in/out
    float syll = fabsf(sinf(t * 13.2f)) * (0.7f + 0.3f * sinf(t * 5.1f));
    jawTarget = env * (0.25f + 0.75f * syll);
    talkGlow = env;
  }
  jawPos += (jawTarget - jawPos) * fminf(1.0f, dt / 0.06f);

  // Slow expression weather with sharper reactions to attention and speech.
  // mood: negative carves a suspicious scowl, positive lifts a broad grin.
  float moodTarget = -0.12f + 0.55f * sinf(t * 0.31f) + 0.23f * sinf(t * 0.83f + 1.4f);
  if (awake > 0.5f) moodTarget += 0.20f;
  if (talkGlow > 0.05f) moodTarget = 0.28f + 0.62f * sinf(t * 2.7f);
  moodTarget = olmec::clampf(moodTarget, -1, 1);
  float wildTarget = 0.05f + 0.22f * awake + 0.73f * talkGlow;
  wildTarget += 0.20f * olmec::clampf((fabsf(sacX) + fabsf(sacY)) * 4.0f, 0, 1);
  if (nearT > 0.88f) wildTarget += 0.22f;
  wildTarget = olmec::clampf(wildTarget, 0, 1);
  moodS += (moodTarget - moodS) * fminf(1.0f, dt * (talkGlow > 0.05f ? 5.0f : 1.25f));
  wildS += (wildTarget - wildS) * fminf(1.0f, dt * (talkGlow > 0.05f ? 7.0f : 2.0f));

  float breath = 0.5f + 0.5f * sinf(t * 6.2832f / 5.2f);

  if (havePanel && baseLayer && jawTile) {
    olmec::FaceState s;
    s.gx = gxS;
    s.gy = gyS;
    s.dil = 0.35f + 0.5f * nearT;
    s.glow = glowS;
    s.jaw = jawPos;
    s.talkGlow = talkGlow;
    s.mood = moodS;
    s.blink = blinkValue;
    s.wild = wildS;
    s.talkPhase = t * 13.2f;
    uint16_t *fb = gfx->getFramebuffer();
    bool jawChanged = fabsf(jawPos - lastJawDrawn) > 0.02f ||
                      fabsf(talkGlow - lastTalkGlowDrawn) > 0.05f ||
                      fabsf(moodS - lastMoodJawDrawn) > 0.07f ||
                      fabsf(wildS - lastWildJawDrawn) > 0.07f || talkGlow > 0.08f;
    bool breathStep = fabsf(breath - lastBreathDrawn) > 0.05f;
    uint32_t t0 = micros();
    olmec::drawEyes(fb, baseLayer, s);
    uint32_t t1 = micros();
    if (jawChanged) {
      olmec::drawJaw(fb, baseLayer, jawTile, s);
      lastJawDrawn = jawPos;
      lastTalkGlowDrawn = talkGlow;
      lastMoodJawDrawn = moodS;
      lastWildJawDrawn = wildS;
    }
    if (breathStep) {
      olmec::nostrilBreath(fb, baseLayer, breath);
      lastBreathDrawn = breath;
    }
    uint32_t t2 = micros();
    blitEyes();
    if (jawChanged) blitRect(olmec::JAW_X0, olmec::JAW_Y0, olmec::JAW_X1, olmec::JAW_Y1);
    if (breathStep) blitRect(olmec::NOSE_X0, olmec::NOSE_Y0, olmec::NOSE_X1, olmec::NOSE_Y1);
    eyesUs += t1 - t0;
    jawUs += t2 - t1;
    blitUs += micros() - t2;
  }

  frames++;
  frameMsAcc += millis() - frameStart;
  if (now - lastBeat > 5000) {
    uint32_t n = frames ? frames : 1;
    Serial.printf("[orb] alive %lus fps=%.1f frame=%lums (eyes=%lu jaw=%lu blit=%lu us) heap=%u wifi=%d touch=%d,%d,%d\n",
                  (unsigned long)((now - bootMs) / 1000), frames / 5.0f,
                  frames ? (unsigned long)(frameMsAcc / frames) : 0, (unsigned long)(eyesUs / n),
                  (unsigned long)(jawUs / n), (unsigned long)(blitUs / n), ESP.getFreeHeap(),
                  ws == WL_CONNECTED, touch.down, touch.x, touch.y);
    frames = 0;
    frameMsAcc = 0;
    eyesUs = jawUs = blitUs = 0;
    lastBeat = now;
  }
}
