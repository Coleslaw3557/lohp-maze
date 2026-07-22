#pragma once

#include "esphome/core/component.h"
#include "esphome/components/binary_sensor/binary_sensor.h"

namespace esphome {
namespace artnet_dmx {

class ArtnetDMX : public Component {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;
  // Socket bind needs the network stack up.
  float get_setup_priority() const override { return setup_priority::AFTER_WIFI; }

  void set_tx_pin(uint8_t pin) { this->tx_pin_ = pin; }
  void set_universe(uint16_t universe) { this->universe_ = universe; }
  void set_port(uint16_t port) { this->port_ = port; }
  void set_uart_num(uint8_t num) { this->uart_num_ = num; }
  void set_channels(uint16_t channels) { this->channels_ = channels; }
  void set_signal_sensor(binary_sensor::BinarySensor *s) { this->signal_sensor_ = s; }

 protected:
  void drain_udp_();

  int sock_{-1};
  uint8_t tx_pin_{6};
  uint8_t uart_num_{2};
  uint16_t universe_{0};
  uint16_t port_{6454};
  uint16_t channels_{512};
  binary_sensor::BinarySensor *signal_sensor_{nullptr};

  // frame_[0] = DMX start code 0, then 512 slots. Written only by the task
  // that also transmits (IDF) / by loop() (host), so no cross-thread buffer.
  uint8_t frame_[513];
  volatile uint32_t last_packet_ms_{0};
  volatile uint32_t frames_rx_{0};
  uint32_t frames_logged_{0};
  uint32_t last_log_ms_{0};
  bool signal_state_{false};
  bool uart_ok_{false};

#ifdef USE_ESP_IDF
  static void tx_task(void *param);
  void send_frame_();
#endif
};

}  // namespace artnet_dmx
}  // namespace esphome
