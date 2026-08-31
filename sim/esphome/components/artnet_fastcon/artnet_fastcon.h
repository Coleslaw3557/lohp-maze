#pragma once

#include <vector>
#include "esphome/core/component.h"
#include "esphome/components/binary_sensor/binary_sensor.h"

#ifdef USE_ESP32
#include "esphome/components/fastcon/fastcon_controller.h"
#endif

namespace esphome {
namespace artnet_fastcon {

class ArtnetFastcon : public Component {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;
  // Socket bind needs the network stack up.
  float get_setup_priority() const override { return setup_priority::AFTER_WIFI; }

#ifdef USE_ESP32
  void set_controller(fastcon::FastconController *controller) { this->controller_ = controller; }
#else
  void set_controller(void *controller) {}
#endif
  void set_universe(uint16_t universe) { this->universe_ = universe; }
  void set_port(uint16_t port) { this->port_ = port; }
  void add_flood(uint8_t light_id, uint16_t start_address) {
    this->floods_.push_back(Flood{light_id, start_address});
  }
  void set_signal_sensor(binary_sensor::BinarySensor *s) { this->signal_sensor_ = s; }

 protected:
  struct Flood {
    uint8_t light_id;
    uint16_t start;  // 1-based DMX channel of the fixture's 8-ch block
    uint8_t last_sent[4]{0, 0, 0, 0};  // bri, B, R, G as last broadcast
    bool last_off{true};
    bool ever_sent{false};
    bool strobe_on_phase{true};
    uint32_t last_flip_ms{0};
    uint32_t last_send_ms{0};
  };

  void drain_udp_();
  void service_flood_(Flood &flood, size_t idx, uint32_t now);

  int sock_{-1};
  uint16_t universe_{0};
  uint16_t port_{6454};
  std::vector<Flood> floods_;
#ifdef USE_ESP32
  fastcon::FastconController *controller_{nullptr};
#endif
  binary_sensor::BinarySensor *signal_sensor_{nullptr};

  uint8_t frame_[512]{};  // channels 1..512 at [0..511]
  uint32_t last_packet_ms_{0};
  uint32_t frames_rx_{0};
  uint32_t frames_logged_{0};
  uint32_t last_log_ms_{0};
  bool signal_state_{false};
};

}  // namespace artnet_fastcon
}  // namespace esphome
