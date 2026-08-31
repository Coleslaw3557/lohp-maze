// Fastcon BLE flood bridge — the orb's second job (Exterior room).
//
// The server treats the 3 ILC 80W BLE floods as room "Exterior" (fixtures at
// DMX 353/361/369, dmx_nodes host = this orb at .77) and unicasts the same
// ArtDMX universe every node gets. This header receives it (sign.ino's
// drainUdp pattern), decodes each 8ch slot exactly like the sign zones / sim
// decodeFixture (W folds 0.92/0.92/0.85, total_dimming scales, strobe > 5
// gates), and re-broadcasts changes as Broadlink Fastcon BLE advertisements.
// Byte math ported from the field-proven dsclee1/BRmesh-esp32-mqtt (which ran
// this exact ILC/BLFL flood family) — protocol credit mooody.me. DO NOT
// "clean up" the packing; the numbers are load-bearing.
//
// DOUBLE DUTY: advertising runs as a millis()-driven IDLE/ADV/GAP state
// machine off floodsLoop() — no blocking delay, the Olmec face keeps its
// 48fps. BLE coexists with the orb's WiFi. Never touches the panel or
// GPIO19/20. Fire-and-forget: no readback, so sends are change-detected
// (deadband) + rate-limited, and every flood is repainted every few seconds
// regardless, so a generator power cut self-heals within one refresh.
//
// PAIRING (app-free, the maze owns the mesh): floodsStartPairing() wakes the
// mesh and adopts factory-fresh lights (default key 5e367bc4) onto OUR mesh
// key (secrets.h FASTCON_MESH_KEY_HEX) with light ids 1..FLOOD_COUNT; they
// flash to confirm and remember it across power cuts. Capped at FLOOD_COUNT so
// a window can't adopt a neighbor camp's light. A light that ever belonged to
// a phone app must be factory reset first (power-cycle 5x). This one call
// blocks ~5s (rare, manual via K1 or auto once/boot) — the only time the face
// pauses; control never blocks.
#pragma once

#include <Arduino.h>
#include <esp_coexist.h>
#include <NimBLEDevice.h>
#include <WiFi.h>
#include <WiFiUdp.h>

namespace fastcon {

// ---- exterior room config (matches light_config.json / dmx_nodes.json) ----
static const int FLOOD_COUNT = 3;
static const uint16_t FLOOD_DMX_FIRST = 353;  // 8ch per flood: 353/361/369
static const uint16_t ARTNET_UNIVERSE_F = 0;
static const uint16_t ARTNET_PORT_F = 6454;

// BLE budget: one command ~= ADV_MS + GAP_MS on the wire; each change is sent
// REDUNDANCY times because a single non-connectable advert is ~80% received.
static const uint32_t ADV_MS = 26;
static const uint32_t GAP_MS = 260;
static const int REDUNDANCY = 1;
static const uint32_t SEND_MIN_MS = 2500;     // per-flood send floor
static const uint32_t REFRESH_MS = 15000;     // unchanged-state repaint
static const uint32_t REFRESH_STAGGER_MS = 1500;
static const float STROBE_MAX_HZ = 2.0f;      // wire spec 1-12Hz; BLE can't
static const uint8_t DEADBAND = 3;

static const uint8_t DEFAULT_KEY[4] = {0x5e, 0x36, 0x7b, 0xc4};
static const uint8_t FASTCON_ADDR[3] = {0xC1, 0xC2, 0xC3};

static uint8_t meshKey[4] = {0, 0, 0, 0};
static uint8_t safeKey = 0xff;
static uint8_t sendSeq = 0;

// ------------------------------------------------------ protocol primitives --
static uint8_t reverse8(uint8_t d) {
  uint8_t r = 0;
  for (int i = 0; i < 8; i++) r |= ((d >> i) & 1) << (7 - i);
  return r;
}
static uint16_t reverse16(uint16_t d) {
  uint16_t r = 0;
  for (int i = 0; i < 16; i++) r |= ((d >> i) & 1) << (15 - i);
  return r;
}
static uint16_t crc16f(const uint8_t *addr, const uint8_t *data, uint8_t dataLen) {
  uint16_t crc = 0xffff;
  for (int8_t i = 2; i >= 0; i--) {
    crc ^= (uint16_t)addr[i] << 8;
    for (uint8_t j = 0; j < 4; j++) {
      uint16_t tmp = crc << 1;
      if (crc & 0x8000) tmp ^= 0x1021;
      crc = tmp << 1;
      if (tmp & 0x8000) crc ^= 0x1021;
    }
  }
  for (uint8_t i = 0; i < dataLen; i++) {
    crc ^= (uint16_t)reverse8(data[i]) << 8;
    for (uint8_t j = 0; j < 4; j++) {
      uint16_t tmp = crc << 1;
      if (crc & 0x8000) tmp ^= 0x1021;
      crc = tmp << 1;
      if (tmp & 0x8000) crc ^= 0x1021;
    }
  }
  return ~reverse16(crc) & 0xffff;
}

struct Whitening {
  uint8_t c[7];
};
static void whitenInit(uint8_t val, Whitening &w) {
  w.c[0] = 1;
  w.c[1] = (val >> 5) & 1;
  w.c[2] = (val >> 4) & 1;
  w.c[3] = (val >> 3) & 1;
  w.c[4] = (val >> 2) & 1;
  w.c[5] = (val >> 1) & 1;
  w.c[6] = val & 1;
}
static void whitenEncode(uint8_t *data, int len, Whitening &w) {
  for (int i = 0; i < len; i++) {
    int c3 = w.c[3], c5 = w.c[5], c6 = w.c[6], c4 = w.c[4];
    int c52 = c5 ^ w.c[2], c41 = c4 ^ w.c[1], c63 = c6 ^ c3;
    int c630 = c63 ^ w.c[0];
    uint8_t b = data[i];
    data[i] = ((b & 0x80) ^ ((c52 ^ c6) << 7)) + ((b & 0x40) ^ (c630 << 6)) +
              ((b & 0x20) ^ (c41 << 5)) + ((b & 0x10) ^ (c52 << 4)) +
              ((b & 0x08) ^ (c63 << 3)) + ((b & 0x04) ^ (c4 << 2)) +
              ((b & 0x02) ^ (c5 << 1)) + ((b & 0x01) ^ (c6 << 0));
    w.c[2] = c41;
    w.c[3] = c52;
    w.c[4] = c52 ^ c3;
    w.c[5] = c630 ^ c4;
    w.c[6] = c41 ^ c5;
    w.c[0] = c52 ^ c6;
    w.c[1] = c630;
  }
}

// body: 4-byte header (xor DEFAULT_KEY) + 12-byte data area (xor key). n selects
// the command class (5 control, 0 wake, 2 keyset). Mirrors dsclee1
// package_ble_fastcon_body + get_payload_with_inner_retry.
static void packBody(uint8_t n, uint8_t seq, uint8_t sk, bool forward,
                     const uint8_t *data, int len, const uint8_t *key,
                     bool zeroKey, uint8_t out[16]) {
  out[0] = (0 & 0x0f) | ((n & 0x07) << 4) | ((forward ? 1 : 0) << 7);
  out[1] = seq;
  out[2] = sk;
  out[3] = 0;  // checksum, filled below
  for (int i = 4; i < 16; i++) out[i] = 0;
  memcpy(out + 4, data, len > 12 ? 12 : len);
  uint8_t chk = 0;
  for (int i = 0; i < len + 4; i++)
    if (i != 3) chk = (chk + out[i]) & 0xff;
  out[3] = chk;
  for (int i = 0; i < 4; i++) out[i] = DEFAULT_KEY[i & 3] ^ out[i];
  for (int i = 0; i < 12; i++) out[4 + i] = key[i & 3] ^ out[4 + i];
  if (zeroKey)  // wake probe: the data area is the factory key pattern in clear
    for (int i = 4; i < 16; i++) out[i] = DEFAULT_KEY[i & 3];
}

// RF framing + CRC + whitening (dsclee1 get_rf_payload + do_generate_command
// tail). Fills adv[] with the whitened payload; returns its length.
static int rfPayload(const uint8_t *body, int bodyLen, uint8_t adv[24]) {
  const uint8_t dataOffset = 0x12, addrLen = 3;
  uint8_t buf[0x12 + 3 + 16 + 2];
  int sz = dataOffset + addrLen + bodyLen + 2;
  memset(buf, 0, sz);
  buf[0x0f] = 0x71;
  buf[0x10] = 0x0f;
  buf[0x11] = 0x55;
  for (int j = 0; j < addrLen; j++) buf[dataOffset + addrLen - j - 1] = FASTCON_ADDR[j];
  for (int j = 0; j < bodyLen; j++) buf[dataOffset + addrLen + j] = body[j];
  for (int i = 0x0f; i < 0x0f + addrLen + 3; i++) buf[i] = reverse8(buf[i]);
  uint16_t crc = crc16f(FASTCON_ADDR, body, bodyLen);
  buf[sz - 2] = crc & 0xff;
  buf[sz - 1] = (crc >> 8) & 0xff;
  Whitening w;
  whitenInit(0x25, w);
  whitenEncode(buf, sz, w);
  memcpy(adv, buf + 15, sz - 15);  // drop the 15-byte preamble
  return sz - 15;
}

// One full advert as a BLE AD payload string: flags are added by the caller;
// this returns the manufacturer-data AD [len][0xFF][0xF0 0xFF][rf...].
static String buildAdvAD(uint8_t n, bool forward, const uint8_t *data, int len,
                         const uint8_t *key, bool zeroKey) {
  uint8_t body[16];
  int dataArea = (n == 0 || n == 2) ? 12 : len;
  if (len > dataArea) dataArea = len;
  int bodyLen = dataArea + 4;
  sendSeq++;
  if (sendSeq == 0) sendSeq = 1;
  uint8_t sk = (zeroKey || key == DEFAULT_KEY) ? 0xff : safeKey;
  packBody(n, sendSeq, sk, forward, data, len, key, zeroKey, body);
  uint8_t rf[24];
  int rlen = rfPayload(body, bodyLen, rf);
  String ad;
  ad += (char)(rlen + 3);
  ad += (char)0xFF;
  ad += (char)0xF0;
  ad += (char)0xFF;
  for (int i = 0; i < rlen; i++) ad += (char)rf[i];
  return ad;
}

// BRmesh 5.x sendStartScan() uses package_ble_fastcon_body_nor_encryp:
// command 0, 12 zero bytes, safe key 0xff, header still default-xored, but the
// data area is not phone-key/default-key encrypted. Broadcast it alongside the
// older wake probe so reset/app-paired lights have a chance to announce.
static String buildDiscoveryAD() {
  uint8_t body[16];
  memset(body, 0, sizeof(body));
  sendSeq++;
  if (sendSeq == 0) sendSeq = 1;
  body[0] = (0 & 0x0f) | ((0 & 0x07) << 4);
  body[1] = sendSeq;
  body[2] = 0xff;
  body[3] = 0;
  uint8_t chk = 0;
  for (int i = 0; i < 16; i++)
    if (i != 3) chk = (chk + body[i]) & 0xff;
  body[3] = chk;
  for (int i = 0; i < 4; i++) body[i] = DEFAULT_KEY[i & 3] ^ body[i];
  uint8_t rf[24];
  int rlen = rfPayload(body, 16, rf);
  String ad;
  ad += (char)(rlen + 3);
  ad += (char)0xFF;
  ad += (char)0xF0;
  ad += (char)0xFF;
  for (int i = 0; i < rlen; i++) ad += (char)rf[i];
  return ad;
}

// ------------------------------------------------------------ advertising ---
static NimBLEAdvertising *pAdv = nullptr;
static const int QN = 32;
static String advQ[QN];
static int qHead = 0, qTail = 0;
enum AdvState { A_IDLE, A_ADV, A_GAP };
static AdvState advState = A_IDLE;
static uint32_t advT0 = 0;
static bool paused = false;  // true during a blocking pairing pass
static bool wifiRadioOk = true;

static void enqueue(const String &ad, int times) {
  for (int t = 0; t < times; t++) {
    int nn = (qTail + 1) % QN;
    if (nn == qHead) return;  // full: newest change wins next pass, drop rest
    advQ[qTail] = ad;
    qTail = nn;
  }
}

static void advStartAD(const String &ad) {
  NimBLEAdvertisementData d;
  d.setFlags(0x06);  // general discoverable + BR/EDR not supported (app capture)
  d.addData((const uint8_t *)ad.c_str(), ad.length());
  pAdv->setAdvertisementData(d);
  pAdv->start();
}

static void advService(uint32_t now) {
  if (paused) return;
  switch (advState) {
    case A_IDLE:
      if (qHead == qTail) return;
      advStartAD(advQ[qHead]);
      qHead = (qHead + 1) % QN;
      advState = A_ADV;
      advT0 = now;
      break;
    case A_ADV:
      if (now - advT0 >= ADV_MS) {
        pAdv->stop();
        advState = A_GAP;
        advT0 = now;
      }
      break;
    case A_GAP:
      if (now - advT0 >= GAP_MS) advState = A_IDLE;
      break;
  }
}

static void stopBleAirtime() {
  if (pAdv && advState == A_ADV) pAdv->stop();
  advState = A_IDLE;
  qHead = qTail = 0;
}

// BRmesh/BLSBleLight wraps genSingleLightCommand([on|bri,B,R,G,W,C])
// through package_device_control(addr, ...): [0x72,id,on|bri,B,R,G,warm,cold].
static void sendColorKey(uint8_t id, uint8_t bri, uint8_t r, uint8_t g, uint8_t b, const uint8_t *key) {
  uint8_t data[8] = {0x72, id, (uint8_t)(0x80 | (bri & 0x7f)), b, r, g, 0x00, 0x00};
  enqueue(buildAdvAD(5, true, data, 8, key, false), REDUNDANCY);
}
static void sendColor(uint8_t id, uint8_t bri, uint8_t r, uint8_t g, uint8_t b) {
  sendColorKey(id, bri, r, g, b, meshKey);
}
static void sendOffKey(uint8_t id, const uint8_t *key) {
  uint8_t data[3] = {0x22, id, 0x00};
  enqueue(buildAdvAD(5, true, data, 3, key, false), REDUNDANCY);
}
static void sendOff(uint8_t id) {
  sendOffKey(id, meshKey);
}

// --------------------------------------------------------- Art-Net + decode --
static WiFiUDP udp;
static uint8_t dmx[512];
static uint32_t lastFrameMs = 0;
static bool everRx = false;
static uint32_t framesRx = 0;
static uint32_t framesLogged = 0;
static uint32_t sendsQueued = 0;
static uint32_t lastStatsLog = 0;
static uint32_t manualTestUntil = 0;

struct FloodOut {
  uint8_t r, g, b;
  bool off;
  bool ever;
  uint32_t lastSend;
};
static FloodOut fout[FLOOD_COUNT];

static void drainUdp() {
  uint8_t buf[18 + 512];
  for (int i = 0; i < 8; i++) {
    int n = udp.parsePacket();
    if (n <= 0) break;
    int len = udp.read(buf, sizeof(buf));
    if (len < 18) continue;
    if (memcmp(buf, "Art-Net\0", 8) != 0 || buf[8] != 0x00 || buf[9] != 0x50) continue;
    uint16_t universe = buf[14] | (buf[15] << 8);
    if (universe != ARTNET_UNIVERSE_F) continue;
    uint16_t dlen = (buf[16] << 8) | buf[17];
    if (dlen > (uint16_t)(len - 18)) dlen = len - 18;
    if (dlen > 512) dlen = 512;
    memcpy(dmx, buf + 18, dlen);
    lastFrameMs = millis();
    framesRx++;
    if (!everRx) {
      Serial.printf("[flood] ArtDMX first frame len=%u ch353=%u,%u,%u,%u,%u,%u\n",
                    dlen, dmx[352], dmx[353], dmx[354], dmx[355], dmx[356], dmx[357]);
    }
    everRx = true;
  }
}

static void serviceFlood(int idx, uint32_t now) {
  FloodOut &f = fout[idx];
  if (now - f.lastSend < SEND_MIN_MS) return;
  const uint8_t *z = dmx + (FLOOD_DMX_FIRST - 1) + 8 * idx;
  uint8_t total = z[0];
  uint8_t strobe = z[5];
  bool strobeOff = false;
  if (strobe > 5) {
    float hz = 1.0f + (strobe / 255.0f) * 11.0f;
    if (hz > STROBE_MAX_HZ) hz = STROBE_MAX_HZ;
    if (fmodf((now / 1000.0f) * hz, 1.0f) > 0.5f) strobeOff = true;
  }
  uint8_t w = z[4];
  uint8_t r = (uint8_t)fminf(255.0f, z[1] + w * 0.92f);
  uint8_t g = (uint8_t)fminf(255.0f, z[2] + w * 0.92f);
  uint8_t b = (uint8_t)fminf(255.0f, z[3] + w * 0.92f);
  uint8_t bri = total >> 1;
  bool off = strobeOff || (total == 0) || ((r | g | b) == 0);

  bool changed = !f.ever || (off != f.off);
  if (!off && !changed) {
    changed = abs((int)r - f.r) >= DEADBAND || abs((int)g - f.g) >= DEADBAND ||
              abs((int)b - f.b) >= DEADBAND;
  }
  uint32_t refreshDue = REFRESH_MS + (uint32_t)idx * REFRESH_STAGGER_MS;
  if (!changed && (now - f.lastSend) < refreshDue) return;

  if (off) sendOff(idx + 1);
  else sendColor(idx + 1, bri, r, g, b);
  sendsQueued++;
  if (sendsQueued <= 12 || sendsQueued % 50 == 0) {
    Serial.printf("[flood] send #%u id=%d bri=%u rgb=%u,%u,%u off=%d q=%d\n",
                  (unsigned)sendsQueued, idx + 1, bri, r, g, b, off,
                  (qTail - qHead + QN) % QN);
  }
  f.r = r; f.g = g; f.b = b;
  f.off = off; f.ever = true; f.lastSend = now;
}

// ------------------------------------------------------------- pairing ------
// dsclee1 wake + keyset, adapted. Blocking (~5s), rare, one-time. Adopts every
// factory-key light in range (capped) onto meshKey with sequential ids.
static int pairedCount = 0;
static uint32_t pairedAt = 0;

struct Candidate {
  uint8_t mac[6];
  bool used;
  bool confirmed;
};

static void advOnce(const String &ad, uint32_t ms) {
  advStartAD(ad);
  delay(ms);
  pAdv->stop();
}

static void keysetCandidate(Candidate &cand, int id) {
  uint8_t data[12];
  memcpy(data, cand.mac, 6);
  data[6] = (uint8_t)id;
  data[7] = 0x01;              // group
  data[8] = meshKey[0];
  data[9] = meshKey[1];
  data[10] = meshKey[2];
  data[11] = meshKey[3];
  String ks = buildAdvAD(2, false, data, 12, DEFAULT_KEY, false);
  for (int rpt = 0; rpt < 6; rpt++) advOnce(ks, 60);
  Serial.printf("[flood] pairing: assigned id %d to %02X%02X%02X%02X%02X%02X\n",
                id, cand.mac[0], cand.mac[1], cand.mac[2], cand.mac[3], cand.mac[4], cand.mac[5]);
}

static int floodsStartPairing() {
  paused = true;  // hand the radio to the blocking pass
  advState = A_IDLE;
  Serial.println("[flood] pairing: wake + scan 25s");

  // 1) wake probes, interleaved with short scans so NimBLE does not have to
  // advertise and scan at the same instant.
  uint8_t zero[6] = {0, 0, 0, 0, 0, 0};
  uint8_t zk[4] = {0, 0, 0, 0};
  String wake = buildAdvAD(0, false, zero, 6, zk, true);
  String discover = buildDiscoveryAD();

  NimBLEScan *scan = NimBLEDevice::getScan();
  scan->setActiveScan(true);
  scan->setInterval(160);
  scan->setWindow(40);
  scan->start(25000, false, true);

  Candidate cand[FLOOD_COUNT];
  int nc = 0;
  int scans = 0, advSeen = 0, factorySeen = 0, ourSeen = 0, foreignSeen = 0;
  uint32_t lastWake = 0;
  uint32_t lastScanRead = 0;
  uint32_t deadline = millis() + 25000;
  while ((int32_t)(millis() - deadline) < 0) {
    uint32_t now = millis();
    if (now - lastWake >= 700) {
      lastWake = now;
      advOnce(wake, 80);
      delay(40);
      advOnce(discover, 80);
    }
    if (now - lastScanRead < 250) {
      delay(20);
      continue;
    }
    lastScanRead = now;
    NimBLEScanResults res = scan->getResults();
    scans++;
    for (int i = 0; i < res.getCount(); i++) {
      const NimBLEAdvertisedDevice *dev = res.getDevice(i);
      if (!dev || !dev->haveManufacturerData()) continue;
      std::string md = dev->getManufacturerData();
      const uint8_t *raw = (const uint8_t *)md.data();
      int off = -1;
      if (md.length() == 16) off = 0;
      else if (md.length() == 18) off = 2;  // tolerate APIs that include company id
      if (off < 0) continue;
      const uint8_t *p = raw + off;
      advSeen++;
      const uint8_t *advKey = p + 12;
      bool factoryKey = advKey[0] == DEFAULT_KEY[0] && advKey[1] == DEFAULT_KEY[1] &&
                        advKey[2] == DEFAULT_KEY[2] && advKey[3] == DEFAULT_KEY[3];
      bool ourKey = advKey[0] == meshKey[0] && advKey[1] == meshKey[1] &&
                    advKey[2] == meshKey[2] && advKey[3] == meshKey[3];
      if (factoryKey) factorySeen++;
      else if (ourKey) ourSeen++;
      else foreignSeen++;
      bool dup = false;
      for (int k = 0; k < nc; k++)
        if (memcmp(cand[k].mac, p + 4, 6) == 0) {
          dup = true;
          if (ourKey && !cand[k].confirmed) {
            cand[k].confirmed = true;
            Serial.printf("[flood] pairing: id %d confirmed on our key\n", k + 1);
          }
        }
      if (dup || !factoryKey || nc >= FLOOD_COUNT) continue;
      memcpy(cand[nc].mac, p + 4, 6);
      cand[nc].used = true;
      cand[nc].confirmed = false;
      keysetCandidate(cand[nc], nc + 1);
      nc++;
    }
  }
  scan->stop();
  pAdv->stop();
  scan->clearResults();
  Serial.printf("[flood] pairing: %d factory light(s) found (scans=%d fastcon=%d factory=%d ours=%d foreign=%d)\n",
                nc, scans, advSeen, factorySeen, ourSeen, foreignSeen);

  pairedCount = nc;
  pairedAt = millis();
  for (int i = 0; i < FLOOD_COUNT; i++) fout[i].ever = false;  // force a repaint
  esp_coex_preference_set(ESP_COEX_PREFER_WIFI);
  paused = false;
  return nc;
}

// --------------------------------------------------------------- lifecycle --
static bool started = false;
static bool bleHostInited = false;

static void ensureBleHost() {
  if (bleHostInited) return;
  NimBLEDevice::init("");         // brings up the controller + NimBLE host
  esp_coex_preference_set(ESP_COEX_PREFER_WIFI);
  NimBLEDevice::setPower(9);      // floods are outdoors; keep adv duty low for WiFi
  bleHostInited = true;
}

static void floodsSetup(const char *meshKeyHex) {
  // parse 8-hex-char key
  auto hexNib = [](char c) -> uint8_t {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return 0;
  };
  for (int i = 0; i < 4; i++)
    meshKey[i] = (hexNib(meshKeyHex[i * 2]) << 4) | hexNib(meshKeyHex[i * 2 + 1]);
  safeKey = meshKey[3];

  ensureBleHost();
  pAdv = NimBLEDevice::getAdvertising();
  pAdv->setConnectableMode(BLE_GAP_CONN_MODE_UND);
  pAdv->enableScanResponse(false);
  pAdv->setMinInterval(0x20);
  pAdv->setMaxInterval(0x30);

  udp.begin(ARTNET_PORT_F);
  for (int i = 0; i < FLOOD_COUNT; i++) { fout[i].ever = false; fout[i].off = true; }
  started = true;
  Serial.printf("[flood] bridge up: key %02X%02X%02X%02X, %d floods, ArtDMX :%u\n",
                meshKey[0], meshKey[1], meshKey[2], meshKey[3], FLOOD_COUNT, ARTNET_PORT_F);
}

// Called every loop iteration, before the frame-pacing gate — always cheap.
static void floodsLoop(uint32_t now) {
  if (!started) return;
  bool wifiOk = WiFi.status() == WL_CONNECTED;
  if (!wifiOk) {
    if (wifiRadioOk) {
      stopBleAirtime();
      Serial.println("[flood] WiFi down: BLE advertising paused");
    }
    wifiRadioOk = false;
    return;
  }
  if (!wifiRadioOk) {
    wifiRadioOk = true;
    for (int i = 0; i < FLOOD_COUNT; i++) fout[i].ever = false;
    esp_coex_preference_set(ESP_COEX_PREFER_WIFI);
    Serial.println("[flood] WiFi restored: forcing repaint");
  }
  drainUdp();
  bool liveSignal = everRx && (now - lastFrameMs) < 5000;
  if (liveSignal && (int32_t)(now - manualTestUntil) >= 0)
    for (int i = 0; i < FLOOD_COUNT; i++) serviceFlood(i, now);
  advService(now);
  if (now - lastStatsLog >= 10000) {
    Serial.printf("[flood] stats frames=%u +%u/10s sends=%u signal=%d q=%d\n",
                  (unsigned)framesRx, (unsigned)(framesRx - framesLogged),
                  (unsigned)sendsQueued, everRx && (now - lastFrameMs) < 5000,
                  (qTail - qHead + QN) % QN);
    framesLogged = framesRx;
    lastStatsLog = now;
  }
}

static bool floodsSignal(uint32_t now) {
  return everRx && (now - lastFrameMs) < 5000;
}

static void floodsTestPattern() {
  if (!started) return;
  qHead = qTail = 0;
  manualTestUntil = millis() + 6000;
  for (int i = 0; i < 3; i++) {
    sendColor(1, 127, 255, 0, 0);
    sendColor(2, 127, 0, 255, 0);
    sendColor(3, 127, 0, 0, 255);
  }
  Serial.println("[flood] queued OUR-key RGB test pattern");
}

static void floodsFactoryKeyTestPattern() {
  if (!started) return;
  qHead = qTail = 0;
  manualTestUntil = millis() + 6000;
  for (int i = 0; i < 3; i++) {
    for (uint8_t id = 1; id <= FLOOD_COUNT; id++) {
      sendColorKey(id, 127, id == 1 ? 255 : 0, id == 2 ? 255 : 0, id == 3 ? 255 : 0, DEFAULT_KEY);
    }
  }
  Serial.println("[flood] queued FACTORY-key RGB test pattern");
}

static void floodsScanDebug() {
  ensureBleHost();
  stopBleAirtime();
  Serial.println("[flood] BLE scan debug 10s (Fastcon + BRlight mesh)");
  NimBLEScan *scan = NimBLEDevice::getScan();
  scan->setActiveScan(true);
  scan->setInterval(100);
  scan->setWindow(90);
  NimBLEScanResults res = scan->getResults(10000, false);
  scan->stop();
  NimBLEUUID meshProv((uint16_t)0x1827);
  NimBLEUUID meshProxy((uint16_t)0x1828);
  int printed = 0, mfrCount = 0, svcCount = 0, meshProvCount = 0, meshProxyCount = 0, brNameCount = 0;
  Serial.printf("[flood] BLE scan: devices=%d\n", res.getCount());
  for (int i = 0; i < res.getCount() && printed < 24; i++) {
    const NimBLEAdvertisedDevice *dev = res.getDevice(i);
    if (!dev) continue;
    std::string md = dev->haveManufacturerData() ? dev->getManufacturerData() : std::string();
    std::string name = dev->haveName() ? dev->getName() : std::string();
    uint8_t nsvc = dev->getServiceUUIDCount();
    bool meshProvSeen = dev->isAdvertisingService(meshProv);
    bool meshProxySeen = dev->isAdvertisingService(meshProxy);
    bool brNamed = name == "BR-RGBW Light" || name == "BS-RGBW Light";
    if (!md.empty()) mfrCount++;
    if (nsvc) svcCount++;
    if (meshProvSeen) meshProvCount++;
    if (meshProxySeen) meshProxyCount++;
    if (brNamed) brNameCount++;
    if (!md.empty() || nsvc || brNamed || printed < 10) {
      Serial.printf("[flood] BLE dev rssi=%d addr=%s type=%u conn=%d scan=%d name=\"%s\" svc=",
                    dev->getRSSI(), dev->getAddress().toString().c_str(),
                    (unsigned)dev->getAdvType(), dev->isConnectable(), dev->isScannable(), name.c_str());
      if (nsvc == 0) Serial.print("-");
      for (uint8_t s = 0; s < nsvc; s++) {
        if (s) Serial.print(",");
        Serial.print(dev->getServiceUUID(s).toString().c_str());
      }
      Serial.printf(" meshProv=%d meshProxy=%d mfr_len=%u data=",
                    meshProvSeen, meshProxySeen, (unsigned)md.length());
    } else {
      continue;
    }
    const uint8_t *p = (const uint8_t *)md.data();
    for (size_t j = 0; j < md.length() && j < 24; j++) Serial.printf("%02X", p[j]);
    Serial.println();
    printed++;
  }
  scan->clearResults();
  Serial.printf("[flood] BLE scan done: manufacturer_payloads=%d service_uuid_devices=%d brlight_unprovisioned=%d brlight_proxy=%d brlight_names=%d\n",
                mfrCount, svcCount, meshProvCount, meshProxyCount, brNameCount);
}

}  // namespace fastcon
