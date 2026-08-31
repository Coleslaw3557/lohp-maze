#include "artnet_fastcon.h"
#include "esphome/core/log.h"
#include "esphome/core/hal.h"

#include <cstring>
#include <algorithm>

#ifdef USE_ESP_IDF
#include <lwip/sockets.h>
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <fcntl.h>
#include <unistd.h>
#include <cerrno>
#endif

namespace esphome {
namespace artnet_fastcon {

static const char *const TAG = "artnet_fastcon";

// BLE budget: the fastcon adv machinery moves ~16 commands/s (50ms adv + 10ms
// gap). Three floods at these numbers stay well inside it with headroom for
// the pairing service and manual light-entity pokes.
static const uint32_t FLOOD_MIN_INTERVAL_MS = 200;  // per-flood send floor
static const uint32_t FLOOD_REFRESH_MS = 5000;      // unchanged-state repaint
static const uint32_t FLOOD_REFRESH_STAGGER_MS = 700;
static const float STROBE_MAX_HZ = 2.0f;  // wire spec says 1-12Hz; BLE can't
static const uint8_t DEADBAND = 3;
static const size_t QUEUE_HIGH_WATER = 24;

void ArtnetFastcon::setup() {
  memset(this->frame_, 0, sizeof(this->frame_));

  this->sock_ = ::socket(AF_INET, SOCK_DGRAM, 0);
  if (this->sock_ < 0) {
    ESP_LOGE(TAG, "UDP socket failed");
    this->mark_failed();
    return;
  }
  struct sockaddr_in addr;
  memset(&addr, 0, sizeof(addr));
  addr.sin_family = AF_INET;
  addr.sin_addr.s_addr = htonl(INADDR_ANY);
  addr.sin_port = htons(this->port_);
  if (::bind(this->sock_, (struct sockaddr *) &addr, sizeof(addr)) < 0) {
    ESP_LOGE(TAG, "UDP bind :%u failed", this->port_);
    this->mark_failed();
    return;
  }
#ifdef USE_ESP_IDF
  int flags = lwip_fcntl(this->sock_, F_GETFL, 0);
  lwip_fcntl(this->sock_, F_SETFL, flags | O_NONBLOCK);
#else
  int flags = ::fcntl(this->sock_, F_GETFL, 0);
  ::fcntl(this->sock_, F_SETFL, flags | O_NONBLOCK);
#endif
}

void ArtnetFastcon::drain_udp_() {
  // A few packets per pass: the server bursts 44Hz while effects animate.
  uint8_t buf[18 + 512];
  for (int i = 0; i < 8; i++) {
    int n = ::recv(this->sock_, (char *) buf, sizeof(buf), 0);
    if (n < 18)
      break;
    if (memcmp(buf, "Art-Net\0", 8) != 0 || buf[8] != 0x00 || buf[9] != 0x50)
      continue;  // not ArtDMX
    uint16_t universe = buf[14] | (buf[15] << 8);
    if (universe != this->universe_)
      continue;
    uint16_t dlen = (buf[16] << 8) | buf[17];
    if (dlen > (uint16_t) (n - 18))
      dlen = n - 18;
    if (dlen > 512)
      dlen = 512;
    memcpy(this->frame_, buf + 18, dlen);  // short packet = leading channels
    this->last_packet_ms_ = millis();
    this->frames_rx_ = this->frames_rx_ + 1;
  }
}

void ArtnetFastcon::service_flood_(Flood &flood, size_t idx, uint32_t now) {
#ifdef USE_ESP32
  if (this->controller_ == nullptr)
    return;
  if (now - flood.last_send_ms < FLOOD_MIN_INTERVAL_MS)
    return;

  const uint8_t *ch = this->frame_ + (flood.start - 1);
  uint8_t total = ch[0], r = ch[1], g = ch[2], b = ch[3], w = ch[4], strobe = ch[5];

  // Camp Sign zone decode: white folds into the colour at 0.92
  auto blend = [](uint8_t c, uint8_t w_) -> uint8_t {
    uint16_t v = c + (uint16_t) ((w_ * 235u) / 255u);
    return (uint8_t) std::min<uint16_t>(v, 255);
  };
  uint8_t rr = blend(r, w), gg = blend(g, w), bb = blend(b, w);

  bool on = total > 0 && (rr | gg | bb) != 0;

  if (on && strobe > 5) {
    float hz = 1.0f + 11.0f * (float) (strobe - 6) / 249.0f;
    hz = std::min(hz, STROBE_MAX_HZ);
    uint32_t half_period = (uint32_t) (500.0f / hz);
    if (now - flood.last_flip_ms >= half_period) {
      flood.last_flip_ms = now;
      flood.strobe_on_phase = !flood.strobe_on_phase;
    }
    on = on && flood.strobe_on_phase;
  } else {
    flood.strobe_on_phase = true;
  }

  // Fastcon light_data, app layout: [on|bri7, B, R, G, warm, cold]
  uint8_t desired[4] = {(uint8_t) (total >> 1), bb, rr, gg};

  bool changed;
  if (!flood.ever_sent || on != !flood.last_off) {
    changed = true;
  } else if (!on) {
    changed = false;  // still off, nothing to say
  } else {
    changed = false;
    for (int i = 0; i < 4; i++) {
      int d = (int) desired[i] - (int) flood.last_sent[i];
      if (d >= DEADBAND || d <= -DEADBAND) {
        changed = true;
        break;
      }
    }
  }

  uint32_t refresh_due = FLOOD_REFRESH_MS + idx * FLOOD_REFRESH_STAGGER_MS;
  if (!changed && now - flood.last_send_ms < refresh_due)
    return;
  if (this->controller_->get_queue_size() >= QUEUE_HIGH_WATER)
    return;  // BLE backlog: drop this tick, newest frame wins next pass

  std::vector<uint8_t> light_data;
  if (!on) {
    light_data = {0x00};
  } else {
    light_data = {(uint8_t) (0x80 | (desired[0] & 0x7F)), desired[1], desired[2], desired[3], 0x00, 0x00};
  }

  auto payload = this->controller_->single_control(flood.light_id, light_data);
  this->controller_->queueCommand(flood.light_id, payload);

  memcpy(flood.last_sent, desired, 4);
  flood.last_off = !on;
  flood.ever_sent = true;
  flood.last_send_ms = now;
#endif
}

void ArtnetFastcon::loop() {
  this->drain_udp_();
  uint32_t now = millis();

  if (this->frames_rx_ > 0) {
    size_t idx = 0;
    for (auto &flood : this->floods_) {
      this->service_flood_(flood, idx, now);
      idx++;
    }
  }

  bool sig = this->frames_rx_ > 0 && (now - this->last_packet_ms_) < 5000;
  if (this->signal_sensor_ != nullptr && sig != this->signal_state_)
    this->signal_sensor_->publish_state(sig);
  this->signal_state_ = sig;
  if (now - this->last_log_ms_ >= 60000) {
    ESP_LOGI(TAG, "%u ArtDMX frames received (+%u/min), signal=%s",
             (unsigned) this->frames_rx_, (unsigned) (this->frames_rx_ - this->frames_logged_),
             sig ? "yes" : "HOLDING LAST FRAME");
    this->frames_logged_ = this->frames_rx_;
    this->last_log_ms_ = now;
  }
}

void ArtnetFastcon::dump_config() {
  ESP_LOGCONFIG(TAG, "Art-Net -> Fastcon BLE bridge:");
  ESP_LOGCONFIG(TAG, "  Universe %u on UDP :%u", this->universe_, this->port_);
  for (auto &flood : this->floods_) {
    ESP_LOGCONFIG(TAG, "  Flood light_id %u <- DMX %u-%u", flood.light_id, flood.start, flood.start + 7);
  }
}

}  // namespace artnet_fastcon
}  // namespace esphome
