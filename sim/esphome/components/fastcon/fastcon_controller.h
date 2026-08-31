#pragma once

#include <queue>
#include <mutex>
#include <vector>
#include <array>
#include "esphome/core/component.h"
#include "esphome/components/light/light_state.h"
#include "esphome/components/esp32_ble_tracker/esp32_ble_tracker.h"

namespace esphome
{
    namespace fastcon
    {

        class FastconController : public Component, public esp32_ble_tracker::ESPBTDeviceListener
        {
        public:
            FastconController() = default;

            void setup() override;
            void loop() override;

            std::vector<uint8_t> get_light_data(light::LightState *state);
            std::vector<uint8_t> single_control(uint32_t addr, const std::vector<uint8_t> &light_data);

            void queueCommand(uint32_t light_id_, const std::vector<uint8_t> &data);

            void clear_queue();
            bool is_queue_empty() const
            {
                std::lock_guard<std::mutex> lock(queue_mutex_);
                return queue_.empty();
            }
            size_t get_queue_size() const
            {
                std::lock_guard<std::mutex> lock(queue_mutex_);
                return queue_.size();
            }
            void set_max_queue_size(size_t size) { max_queue_size_ = size; }

            void set_mesh_key(std::array<uint8_t, 4> key) { mesh_key_ = key; }
            void set_adv_interval_min(uint16_t val) { adv_interval_min_ = val; }
            void set_adv_interval_max(uint16_t val)
            {
                adv_interval_max_ = val;
                if (adv_interval_max_ < adv_interval_min_)
                {
                    adv_interval_max_ = adv_interval_min_;
                }
            }
            void set_adv_duration(uint16_t val) { adv_duration_ = val; }
            void set_adv_gap(uint16_t val) { adv_gap_ = val; }

            // App-free pairing: broadcast a wake probe, collect unpaired lights
            // (they advertise the factory key), then assign them sequential light
            // ids and our mesh key. Ported from dsclee1/BRmesh-esp32-mqtt.
            void start_pairing(uint32_t duration_ms);
            void stop_pairing();
            bool is_pairing() const { return pairing_active_; }
            std::string pairing_summary() const;

            bool parse_device(const esp32_ble_tracker::ESPBTDevice &device) override;

        protected:
            struct Command
            {
                std::vector<uint8_t> data;
                uint32_t timestamp;
                uint8_t retries{0};
                static constexpr uint8_t MAX_RETRIES = 3;
            };

            std::queue<Command> queue_;
            mutable std::mutex queue_mutex_;
            size_t max_queue_size_{100};

            enum class AdvertiseState
            {
                IDLE,
                ADVERTISING,
                GAP
            };

            AdvertiseState adv_state_{AdvertiseState::IDLE};
            uint32_t state_start_time_{0};

            // Protocol implementation
            std::vector<uint8_t> generate_command(uint8_t n, uint32_t light_id_, const std::vector<uint8_t> &data, bool forward = true);
            std::vector<uint8_t> generate_command_with_key(uint8_t n, uint32_t light_id_, const std::vector<uint8_t> &data,
                                                           bool forward, const std::array<uint8_t, 4> &key, bool zero_key_probe);

            // Pairing internals
            struct PairCandidate
            {
                std::array<uint8_t, 6> ble_mac{};   // raw bytes from the light's advert, keyset echoes them back
                std::array<uint8_t, 2> type_code{}; // 0xA8A0 RGB / 0xA8A1 RGBW / 0xAE39 smart
                uint8_t assigned_id{0};
                uint32_t last_keyset_ms{0};
                bool keyset_sent{false};
                bool confirmed{false};
            };
            void queue_wake_probe_();
            void queue_keyset_(PairCandidate &cand);
            std::vector<PairCandidate> pair_candidates_;
            std::mutex pair_mutex_;
            bool pairing_active_{false};
            uint32_t pairing_deadline_{0};
            uint32_t last_wake_ms_{0};

            std::array<uint8_t, 4> mesh_key_{};

            uint16_t adv_interval_min_{0x20};
            uint16_t adv_interval_max_{0x40};
            uint16_t adv_duration_{50};
            uint16_t adv_gap_{10};

            static const uint16_t MANUFACTURER_DATA_ID = 0xfff0;
        };

    } // namespace fastcon
} // namespace esphome
