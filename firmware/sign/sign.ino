// Camp-sign ArtDMX→WS2811 bridge — XIAO ESP32-S3 in the sign node box.
//
// The Pi stays the one show controller; this node renders universe channels
// 161-352 as the sign's 24 letter/logo zones (wiring-guides/camp-sign-plan.md).
// Deliberately dumb — no show logic, no brightness cap (wiring is sized for
// full white): receive ArtDMX on UDP :6454 exactly like the room nodes'
// component (sim/esphome/components/artnet_dmx), decode each zone exactly like
// the sim's decodeFixture (preview == wire), push pixels on 3 RMT outputs.
//
//   ./build.sh flash     first flash over USB (/dev/ttyACM0)
//   ./build.sh ota       reflash over WiFi once mounted behind the logo disc
//   ./build.sh monitor   serial console — '?' lists the bench commands
//
// The Dfi wired-DMX fallback (MAX485 RO on D4) is bench-populated in the box
// but NOT in this firmware — the plan pulls in esp_dmx only if the entrance-
// tower WiFi fails its on-site test.

#include <ArduinoOTA.h>
#include <ESPmDNS.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <WiFiUdp.h>

#include <FastLED.h>

#include "secrets.h"
#include "sign_config.h"

static const char *HOSTNAME = "lohp-sign-bridge";  // dmx_nodes.json unicasts to this .local name

static CRGB leds1[OUT1_PX], leds2[OUT2_PX], leds3[OUT3_PX];

struct OutDef {
  const ZoneRun *runs;
  uint8_t nruns;
  CRGB *px;
  uint16_t count;
};
static const OutDef OUTS[3] = {
    {OUT1_RUNS, sizeof(OUT1_RUNS) / sizeof(*OUT1_RUNS), leds1, OUT1_PX},
    {OUT2_RUNS, sizeof(OUT2_RUNS) / sizeof(*OUT2_RUNS), leds2, OUT2_PX},
    {OUT3_RUNS, sizeof(OUT3_RUNS) / sizeof(*OUT3_RUNS), leds3, OUT3_PX},
};

static uint8_t dmx[512];  // dmx[0] = DMX channel 1; sign zones live at [160..351]
static bool everRx = false;
static uint32_t framesRx = 0, framesLogged = 0;
static uint32_t lastFrameMs = 0, lastLogMs = 0;

static WiFiUDP udp;
static bool netUp = false, otaReady = false;
static uint32_t wifiDownSince = 0;

static char overrideMode = 0;  // bench override: 0 = DMX, r/g/b/w solid, '1'-'3' red-solo
static volatile bool stormBusy = false;
static uint32_t stormPresses = 0;

// ---------------------------------------------------------------- network --

static void netHousekeeping() {
  bool up = WiFi.status() == WL_CONNECTED;
  if (up && !netUp) {
    netUp = true;
    Serial.printf("[sign] wifi up: %s ip=%s rssi=%d\n", WIFI_SSID,
                  WiFi.localIP().toString().c_str(), WiFi.RSSI());
    udp.stop();
    udp.begin(ARTNET_PORT);
    if (!otaReady) {
      MDNS.begin(HOSTNAME);  // the A record the server's unicast resolves
      ArduinoOTA.setHostname(HOSTNAME);
      ArduinoOTA.setPassword(OTA_PASSWORD);
      ArduinoOTA.setMdnsEnabled(false);  // MDNS.begin above owns the record
      ArduinoOTA.begin();
      otaReady = true;
      Serial.printf("[sign] OTA + mDNS ready as %s.local\n", HOSTNAME);
    }
  } else if (!up && netUp) {
    netUp = false;
    wifiDownSince = millis();
    Serial.println("[sign] wifi DOWN");
  } else if (!up && millis() - wifiDownSince > 15000) {
    wifiDownSince = millis();
    WiFi.reconnect();
  }
}

// Mirror of sim/esphome/components/artnet_dmx drain_udp_(): a few packets per
// pass (the server bursts ~44 Hz while effects animate, 1 Hz heartbeat static).
static void drainUdp() {
  uint8_t buf[18 + 512];
  for (int i = 0; i < 8; i++) {
    int n = udp.parsePacket();
    if (n <= 0)
      break;
    int len = udp.read(buf, sizeof(buf));
    if (len < 18)
      continue;
    if (memcmp(buf, "Art-Net\0", 8) != 0 || buf[8] != 0x00 || buf[9] != 0x50)
      continue;  // not ArtDMX
    uint16_t universe = buf[14] | (buf[15] << 8);
    if (universe != ARTNET_UNIVERSE)
      continue;
    uint16_t dlen = (buf[16] << 8) | buf[17];
    if (dlen > (uint16_t)(len - 18))
      dlen = len - 18;
    if (dlen > 512)
      dlen = 512;
    memcpy(dmx, buf + 18, dlen);  // short packet = leading channels only
    lastFrameMs = millis();
    everRx = true;
    framesRx++;
  }
}

// ----------------------------------------------------------------- render --

// Exactly sim decodeFixture (sim/web/app.js): W folds into RGB (0.92/0.92/0.85),
// total_dimming scales, strobe > 5 gates at 1 + (strobe/255)*11 Hz, 50% duty.
static CRGB zoneColor(uint8_t k, double tSec) {
  const uint8_t *z = dmx + (ZONE_DMX_FIRST - 1) + 8 * k;
  float m = z[0] / 255.0f;
  uint8_t strobe = z[5];
  if (strobe > 5) {
    double hz = 1.0 + (strobe / 255.0) * 11.0;
    if (fmod(tSec * hz, 1.0) > 0.5)
      return CRGB::Black;
  }
  float w = z[4];
  return CRGB((uint8_t)(fminf(255.0f, z[1] + w * 0.92f) * m + 0.5f),
              (uint8_t)(fminf(255.0f, z[2] + w * 0.92f) * m + 0.5f),
              (uint8_t)(fminf(255.0f, z[3] + w * 0.85f) * m + 0.5f));
}

static void fillAll(const CRGB &c) {
  for (const OutDef &o : OUTS)
    fill_solid(o.px, o.count, c);
}

// DMX gone (Pi reboot, AP drop): the camp sign must not go black. An all-zero
// frame is NOT loss — a deliberate blackout stays a blackout.
static void renderBreathe(uint32_t now) {
  float ph = (now % BREATHE_PERIOD_MS) / (float)BREATHE_PERIOD_MS;
  float lvl = 0.5f - 0.5f * cosf(ph * 6.2831853f);
  CRGB c(255, 110, 8);
  c.nscale8((uint8_t)(BREATHE_PEAK * lvl));
  fillAll(c);
}

static void renderOverride() {
  switch (overrideMode) {
    case 'r': fillAll(CRGB(255, 0, 0)); break;
    case 'g': fillAll(CRGB(0, 255, 0)); break;
    case 'b': fillAll(CRGB(0, 0, 255)); break;
    case 'w': fillAll(CRGB(255, 255, 255)); break;
    case '1':
    case '2':
    case '3': {  // red-only on ONE chain — build sequence step: each output alone
      int want = overrideMode - '1';
      for (int o = 0; o < 3; o++)
        fill_solid(OUTS[o].px, OUTS[o].count, o == want ? CRGB(255, 0, 0) : CRGB::Black);
      break;
    }
  }
}

static void render() {
  uint32_t now = millis();
  if (overrideMode) {
    renderOverride();
    return;
  }
  if (!everRx || now - lastFrameMs > SIGNAL_LOSS_MS) {
    renderBreathe(now);
    return;
  }
  double t = (now % 3600000UL) / 1000.0;  // strobe clock; hourly wrap keeps floats exact
  for (const OutDef &o : OUTS) {
    uint16_t at = 0;
    for (uint8_t r = 0; r < o.nruns; r++) {
      CRGB c = zoneColor(o.runs[r].zone, t);
      fill_solid(o.px + at, o.runs[r].px, c);
      at += o.runs[r].px;
    }
  }
}

// ------------------------------------------------------------------ storm --

static void stormTask(void *) {
  HTTPClient http;
  http.setConnectTimeout(1500);
  http.setTimeout(STORM_HTTP_TIMEOUT_MS);
  String url = String("http://") + SERVER_HOST + ":" + SERVER_PORT + "/api/sign_storm";
  int code = -100;
  if (http.begin(url)) {
    http.addHeader("Content-Type", "application/json");
    code = http.POST("{}");
    if (code > 0)
      Serial.printf("[sign] storm POST → %d %s\n", code, http.getString().c_str());
    http.end();
  }
  if (code <= 0)
    // Fire and forget: a late/lost response still means the strike is running
    // server-side (the room nodes' "http -1 = expected" precedent).
    Serial.printf("[sign] storm POST → err %d (strike may still fire)\n", code);
  stormBusy = false;
  vTaskDelete(nullptr);
}

static void fireStorm(const char *src) {
  stormPresses++;
  Serial.printf("[sign] storm press #%u (%s)\n", (unsigned)stormPresses, src);
  if (stormBusy) {
    Serial.println("[sign] storm POST already in flight — ignored");
    return;
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[sign] no wifi — press dropped");
    return;
  }
  stormBusy = true;
  // Off the render loop: the sign itself flashes Lightning during the strike,
  // and a blocking POST here would freeze the pixels mid-storm.
  xTaskCreate(stormTask, "storm", 8192, nullptr, 1, nullptr);
}

static void pollButton() {
  static bool stable = true, lastRead = true;
  static uint32_t edgeMs = 0;
  bool rd = digitalRead(PIN_BTN);
  if (rd != lastRead) {
    lastRead = rd;
    edgeMs = millis();
  } else if (rd != stable && millis() - edgeMs >= BTN_DEBOUNCE_MS) {
    stable = rd;
    if (!stable)
      fireStorm("button");  // NO shorts to GND on press; server owns the 30 s cooldown
  }
}

// ------------------------------------------------------------------ bench --

static void help() {
  Serial.println("[sign] bench commands:");
  Serial.println("  z  zone dump (raw DMX + decoded RGB)   f  frame/wifi stats");
  Serial.println("  r/g/b/w  solid color, all chains       1/2/3  red on that chain only");
  Serial.println("  0  overrides off, back to DMX          s  simulate a storm press");
}

static void dumpStats() {
  bool live = everRx && millis() - lastFrameMs <= SIGNAL_LOSS_MS;
  Serial.printf("[sign] frames=%u last=%s wifi=%s rssi=%d ip=%s presses=%u override=%c\n",
                (unsigned)framesRx,
                everRx ? (String((millis() - lastFrameMs) / 1000.0, 1) + "s ago").c_str() : "never",
                WiFi.status() == WL_CONNECTED ? "up" : "DOWN", WiFi.RSSI(),
                WiFi.localIP().toString().c_str(), (unsigned)stormPresses,
                overrideMode ? overrideMode : '-');
  Serial.printf("[sign] signal=%s\n", live ? "live" : "LOST — amber breathe");
}

static void dumpZones() {
  dumpStats();
  double t = (millis() % 3600000UL) / 1000.0;
  for (uint8_t k = 0; k < ZONE_COUNT; k++) {
    const uint8_t *z = dmx + (ZONE_DMX_FIRST - 1) + 8 * k;
    CRGB c = zoneColor(k, t);
    Serial.printf("  z%-2u %-4s @%-3u  tot=%-3u r=%-3u g=%-3u b=%-3u w=%-3u strobe=%-3u  -> %3u,%3u,%3u\n",
                  k, ZONE_NAME[k], ZONE_DMX_FIRST + 8 * k, z[0], z[1], z[2], z[3], z[4],
                  z[5], c.r, c.g, c.b);
  }
}

static void pollSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    switch (c) {
      case 'z': dumpZones(); break;
      case 'f': dumpStats(); break;
      case 's': fireStorm("serial"); break;
      case 'r': case 'g': case 'b': case 'w':
      case '1': case '2': case '3':
        overrideMode = c;
        Serial.printf("[sign] override '%c' ('0' = back to DMX)\n", c);
        break;
      case '0':
        overrideMode = 0;
        Serial.println("[sign] override off — DMX");
        break;
      case '?': case 'h': help(); break;
      default: break;
    }
  }
}

// Once a minute, same shape as the room nodes' artnet_dmx log line.
static void statsLog() {
  uint32_t now = millis();
  if (now - lastLogMs < 60000)
    return;
  bool live = everRx && now - lastFrameMs <= SIGNAL_LOSS_MS;
  Serial.printf("[sign] %u ArtDMX frames received (+%u/min), signal=%s\n", (unsigned)framesRx,
                (unsigned)(framesRx - framesLogged), live ? "yes" : "AMBER FALLBACK");
  framesLogged = framesRx;
  lastLogMs = now;
}

// ------------------------------------------------------------------- main --

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BTN, INPUT_PULLUP);
  pinMode(PIN_DMX_RO, INPUT);  // MAX485 RO drives this pin (RE tied low) — don't fight it

  FastLED.addLeds<WS2811, PIN_DATA1, SIGN_COLOR_ORDER>(leds1, OUT1_PX);
  FastLED.addLeds<WS2811, PIN_DATA2, SIGN_COLOR_ORDER>(leds2, OUT2_PX);
  FastLED.addLeds<WS2811, PIN_DATA3, SIGN_COLOR_ORDER>(leds3, OUT3_PX);
  FastLED.clear(true);

  WiFi.mode(WIFI_STA);
  WiFi.setHostname(HOSTNAME);
  WiFi.setSleep(false);  // modem sleep would clump the 44 Hz effect bursts
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.printf("\n[sign] camp-sign bridge %s — %u zones @%u-%u, px %u+%u+%u on GPIO%u/%u/%u\n",
                HOSTNAME, ZONE_COUNT, ZONE_DMX_FIRST, ZONE_DMX_FIRST + 8 * ZONE_COUNT - 8,
                OUT1_PX, OUT2_PX, OUT3_PX, PIN_DATA1, PIN_DATA2, PIN_DATA3);
  Serial.printf("[sign] storm → http://%s:%u/api/sign_storm, btn GPIO%u\n", SERVER_HOST,
                SERVER_PORT, PIN_BTN);
  help();
}

void loop() {
  netHousekeeping();
  if (otaReady)
    ArduinoOTA.handle();
  if (netUp)
    drainUdp();
  pollButton();
  pollSerial();

  static uint32_t lastRender = 0;
  uint32_t now = millis();
  if (now - lastRender >= RENDER_MS) {
    lastRender = now;
    render();
    FastLED.show();
  }
  statsLog();
}
