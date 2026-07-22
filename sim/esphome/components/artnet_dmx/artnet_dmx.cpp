#include "artnet_dmx.h"
#include "esphome/core/log.h"
#include "esphome/core/hal.h"

#include <cstring>

#ifdef USE_ESP_IDF
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <driver/uart.h>
#include <esp_rom_sys.h>
#include <soc/soc_caps.h>
#include <lwip/sockets.h>
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <fcntl.h>
#include <unistd.h>
#include <cerrno>
#endif

namespace esphome {
namespace artnet_dmx {

static const char *const TAG = "artnet_dmx";

// DMX512-A timing: break >= 92us (176 typical), mark-after-break >= 12us.
static const uint32_t DMX_BREAK_US = 176;
static const uint32_t DMX_MAB_US = 12;
// Frame pacing target. A full 513-byte frame occupies ~22.6ms of wire at
// 250kbaud, so the wire itself caps us just under 44Hz; the task re-clocks
// the LAST RECEIVED frame forever — WiFi loss holds the look, never blackout.
static const uint32_t DMX_FRAME_MS = 23;

void ArtnetDMX::setup() {
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

  if (this->uart_num_ >= SOC_UART_NUM) {
    ESP_LOGE(TAG, "UART%u does not exist on this chip", this->uart_num_);
  } else {
    uart_config_t cfg;
    memset(&cfg, 0, sizeof(cfg));
    cfg.baud_rate = 250000;
    cfg.data_bits = UART_DATA_8_BITS;
    cfg.parity = UART_PARITY_DISABLE;
    cfg.stop_bits = UART_STOP_BITS_2;
    cfg.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    cfg.source_clk = UART_SCLK_DEFAULT;
    // tx ring buffer 0: uart_write_bytes blocks in OUR task until the frame is
    // in the FIFO — that block IS the pacing, and no ESPHome loop time is spent.
    if (uart_driver_install((uart_port_t) this->uart_num_, 256, 0, 0, nullptr, 0) != ESP_OK ||
        uart_param_config((uart_port_t) this->uart_num_, &cfg) != ESP_OK ||
        uart_set_pin((uart_port_t) this->uart_num_, this->tx_pin_, UART_PIN_NO_CHANGE,
                     UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE) != ESP_OK) {
      // Most likely another component owns this UART — stay up as a receiver
      // (signal sensor keeps diagnosing WiFi) but say so loudly.
      ESP_LOGE(TAG, "UART%u unavailable (taken by a sensor?) — set uart_num", this->uart_num_);
    } else {
      this->uart_ok_ = true;
      xTaskCreate(ArtnetDMX::tx_task, "dmx_tx", 3072, this, 2, nullptr);
    }
  }
#else
  int flags = ::fcntl(this->sock_, F_GETFL, 0);
  ::fcntl(this->sock_, F_SETFL, flags | O_NONBLOCK);
#endif
}

void ArtnetDMX::drain_udp_() {
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
    memcpy(this->frame_ + 1, buf + 18, dlen);  // short packet = leading channels
    this->last_packet_ms_ = millis();
    this->frames_rx_ = this->frames_rx_ + 1;
  }
}

#ifdef USE_ESP_IDF
void ArtnetDMX::tx_task(void *param) {
  auto *self = static_cast<ArtnetDMX *>(param);
  TickType_t wake = xTaskGetTickCount();
  for (;;) {
    self->drain_udp_();
    self->send_frame_();
    vTaskDelayUntil(&wake, pdMS_TO_TICKS(DMX_FRAME_MS));
  }
}

void ArtnetDMX::send_frame_() {
  auto port = (uart_port_t) this->uart_num_;
  // Previous frame fully on the wire before the next break tears into it.
  uart_wait_tx_done(port, pdMS_TO_TICKS(100));
  uart_set_line_inverse(port, UART_SIGNAL_TXD_INV);  // break: TXD held low
  esp_rom_delay_us(DMX_BREAK_US);
  uart_set_line_inverse(port, 0);
  esp_rom_delay_us(DMX_MAB_US);
  uart_write_bytes(port, (const char *) this->frame_, 1 + this->channels_);
}
#endif

void ArtnetDMX::loop() {
#ifndef USE_ESP_IDF
  this->drain_udp_();  // host build: no task, receive here
#endif
  uint32_t now = millis();
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

void ArtnetDMX::dump_config() {
  ESP_LOGCONFIG(TAG, "Art-Net DMX out:");
  ESP_LOGCONFIG(TAG, "  Universe %u on UDP :%u", this->universe_, this->port_);
  ESP_LOGCONFIG(TAG, "  DMX TX: GPIO%u via UART%u, %u channels%s", this->tx_pin_,
                this->uart_num_, this->channels_, this->uart_ok_ ? "" : " (UART DISABLED)");
}

}  // namespace artnet_dmx
}  // namespace esphome
