#include "esphome/core/log.h"
#include "esphome/core/hal.h"
#include "esphome/components/light/color_mode.h"
#include "fastcon_controller.h"
#include "protocol.h"
#include "utils.h"

#ifdef USE_ESP32
#include <esp_gap_ble_api.h>
#endif

namespace esphome
{
    namespace fastcon
    {
        static const char *const TAG = "fastcon.controller";

        // Factory type codes lights report while unpaired (dsclee1/BRmesh-esp32-mqtt)
        static const uint8_t TYPE_SMART[2] = {0x39, 0xae};
        static const uint8_t TYPE_RGBW[2] = {0xa1, 0xa8};
        static const uint8_t TYPE_RGB[2] = {0xa0, 0xa8};

        static const char *type_name(const std::array<uint8_t, 2> &t)
        {
            if (t[0] == TYPE_RGBW[0] && t[1] == TYPE_RGBW[1])
                return "RGBW";
            if (t[0] == TYPE_RGB[0] && t[1] == TYPE_RGB[1])
                return "RGB";
            if (t[0] == TYPE_SMART[0] && t[1] == TYPE_SMART[1])
                return "Smart";
            return "unknown";
        }

        static std::string mac_to_hex(const std::array<uint8_t, 6> &mac)
        {
            char buf[13];
            snprintf(buf, sizeof(buf), "%02X%02X%02X%02X%02X%02X", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
            return std::string(buf);
        }

        void FastconController::queueCommand(uint32_t light_id_, const std::vector<uint8_t> &data)
        {
            std::lock_guard<std::mutex> lock(queue_mutex_);
            if (queue_.size() >= max_queue_size_)
            {
                ESP_LOGW(TAG, "Command queue full (size=%d), dropping command for light %d",
                         queue_.size(), light_id_);
                return;
            }

            Command cmd;
            cmd.data = data;
            cmd.timestamp = millis();
            cmd.retries = 0;

            queue_.push(cmd);
            ESP_LOGV(TAG, "Command queued, queue size: %d", queue_.size());
        }

        void FastconController::clear_queue()
        {
            std::lock_guard<std::mutex> lock(queue_mutex_);
            std::queue<Command> empty;
            std::swap(queue_, empty);
        }

        void FastconController::setup()
        {
            ESP_LOGCONFIG(TAG, "Setting up Fastcon BLE Controller...");
            ESP_LOGCONFIG(TAG, "  Advertisement interval: %d-%d", this->adv_interval_min_, this->adv_interval_max_);
            ESP_LOGCONFIG(TAG, "  Advertisement duration: %dms", this->adv_duration_);
            ESP_LOGCONFIG(TAG, "  Advertisement gap: %dms", this->adv_gap_);
        }

        void FastconController::loop()
        {
            const uint32_t now = millis();

            if (pairing_active_)
            {
                if ((int32_t)(now - pairing_deadline_) >= 0)
                {
                    pairing_active_ = false;
                    ESP_LOGI(TAG, "Pairing window closed. %s", this->pairing_summary().c_str());
                }
                else
                {
                    std::lock_guard<std::mutex> lock(pair_mutex_);
                    if (now - last_wake_ms_ >= 700)
                    {
                        last_wake_ms_ = now;
                        this->queue_wake_probe_();
                    }
                    for (auto &cand : pair_candidates_)
                    {
                        if (!cand.confirmed && (now - cand.last_keyset_ms >= 900))
                        {
                            cand.last_keyset_ms = now;
                            this->queue_keyset_(cand);
                        }
                    }
                }
            }

            switch (adv_state_)
            {
            case AdvertiseState::IDLE:
            {
                std::lock_guard<std::mutex> lock(queue_mutex_);
                if (queue_.empty())
                    return;

                Command cmd = queue_.front();
                queue_.pop();

                esp_ble_adv_params_t adv_params = {
                    .adv_int_min = adv_interval_min_,
                    .adv_int_max = adv_interval_max_,
                    .adv_type = ADV_TYPE_NONCONN_IND,
                    .own_addr_type = BLE_ADDR_TYPE_PUBLIC,
                    .peer_addr = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00},
                    .peer_addr_type = BLE_ADDR_TYPE_PUBLIC,
                    .channel_map = ADV_CHNL_ALL,
                    .adv_filter_policy = ADV_FILTER_ALLOW_SCAN_ANY_CON_ANY,
                };

                uint8_t adv_data_raw[31] = {0};
                uint8_t adv_data_len = 0;

                // Add flags
                adv_data_raw[adv_data_len++] = 2;
                adv_data_raw[adv_data_len++] = ESP_BLE_AD_TYPE_FLAG;
                adv_data_raw[adv_data_len++] = ESP_BLE_ADV_FLAG_BREDR_NOT_SPT | ESP_BLE_ADV_FLAG_GEN_DISC;

                // Manufacturer data; AD length counts the type byte plus the
                // 2-byte company id plus the payload (matches app captures)
                adv_data_raw[adv_data_len++] = cmd.data.size() + 3;
                adv_data_raw[adv_data_len++] = ESP_BLE_AD_MANUFACTURER_SPECIFIC_TYPE;
                adv_data_raw[adv_data_len++] = MANUFACTURER_DATA_ID & 0xFF;
                adv_data_raw[adv_data_len++] = (MANUFACTURER_DATA_ID >> 8) & 0xFF;

                memcpy(&adv_data_raw[adv_data_len], cmd.data.data(), cmd.data.size());
                adv_data_len += cmd.data.size();

                esp_err_t err = esp_ble_gap_config_adv_data_raw(adv_data_raw, adv_data_len);
                if (err != ESP_OK)
                {
                    ESP_LOGW(TAG, "Error setting raw advertisement data (err=%d): %s", err, esp_err_to_name(err));
                    return;
                }

                err = esp_ble_gap_start_advertising(&adv_params);
                if (err != ESP_OK)
                {
                    ESP_LOGW(TAG, "Error starting advertisement (err=%d): %s", err, esp_err_to_name(err));
                    return;
                }

                adv_state_ = AdvertiseState::ADVERTISING;
                state_start_time_ = now;
                ESP_LOGV(TAG, "Started advertising");
                break;
            }

            case AdvertiseState::ADVERTISING:
            {
                if (now - state_start_time_ >= adv_duration_)
                {
                    esp_ble_gap_stop_advertising();
                    adv_state_ = AdvertiseState::GAP;
                    state_start_time_ = now;
                    ESP_LOGV(TAG, "Stopped advertising, entering gap period");
                }
                break;
            }

            case AdvertiseState::GAP:
            {
                if (now - state_start_time_ >= adv_gap_)
                {
                    adv_state_ = AdvertiseState::IDLE;
                    ESP_LOGV(TAG, "Gap period complete");
                }
                break;
            }
            }
        }

        std::vector<uint8_t> FastconController::get_light_data(light::LightState *state)
        {
            std::vector<uint8_t> light_data = {
                0, // 0 - On/Off Bit + 7-bit Brightness
                0, // 1 - Blue byte
                0, // 2 - Red byte
                0, // 3 - Green byte
                0, // 4 - Warm byte
                0  // 5 - Cold byte
            };

            auto values = state->current_values;

            bool is_on = values.is_on();
            if (!is_on)
            {
                return std::vector<uint8_t>({0x00});
            }

            auto color_mode = values.get_color_mode();
            bool has_white = (static_cast<uint8_t>(color_mode) & static_cast<uint8_t>(light::ColorCapability::WHITE)) != 0;
            float brightness = std::min(values.get_brightness() * 127.0f, 127.0f); // clamp the value to at most 127
            light_data[0] = 0x80 + static_cast<uint8_t>(brightness);

            if (has_white)
            {
                return std::vector<uint8_t>({static_cast<uint8_t>(brightness)});
            }

            bool has_rgb = (static_cast<uint8_t>(color_mode) & static_cast<uint8_t>(light::ColorCapability::RGB)) != 0;
            if (has_rgb)
            {
                light_data[1] = static_cast<uint8_t>(values.get_blue() * 255.0f);
                light_data[2] = static_cast<uint8_t>(values.get_red() * 255.0f);
                light_data[3] = static_cast<uint8_t>(values.get_green() * 255.0f);
            }

            bool has_cold_warm = (static_cast<uint8_t>(color_mode) & static_cast<uint8_t>(light::ColorCapability::COLD_WARM_WHITE)) != 0;
            if (has_cold_warm)
            {
                light_data[4] = static_cast<uint8_t>(values.get_warm_white() * 255.0f);
                light_data[5] = static_cast<uint8_t>(values.get_cold_white() * 255.0f);
            }

            bool has_temp = (static_cast<uint8_t>(color_mode) & static_cast<uint8_t>(light::ColorCapability::COLOR_TEMPERATURE)) != 0;
            if (has_temp)
            {
                float temperature = values.get_color_temperature();
                if (temperature < 153)
                {
                    light_data[4] = 0xff;
                    light_data[5] = 0x00;
                }
                else if (temperature > 500)
                {
                    light_data[4] = 0x00;
                    light_data[5] = 0xff;
                }
                else
                {
                    light_data[4] = (uint8_t)(((500 - temperature) * 255.0f + (temperature - 153) * 0x00) / (500 - 153));
                    light_data[5] = (uint8_t)(((temperature - 153) * 255.0f + (500 - temperature) * 0x00) / (500 - 153));
                }
            }

            return light_data;
        }

        std::vector<uint8_t> FastconController::single_control(uint32_t light_id_, const std::vector<uint8_t> &light_data)
        {
            std::vector<uint8_t> result_data(light_data.size() + 2);

            result_data[0] = 2 | (((0xfffffff & (light_data.size() + 1)) << 4));
            result_data[1] = light_id_;
            std::copy(light_data.begin(), light_data.end(), result_data.begin() + 2);

            auto hex_str = vector_to_hex_string(result_data).data();
            ESP_LOGD(TAG, "Inner Payload (%d bytes): %s", result_data.size(), hex_str);

            return this->generate_command(5, light_id_, result_data, true);
        }

        std::vector<uint8_t> FastconController::generate_command(uint8_t n, uint32_t light_id_, const std::vector<uint8_t> &data, bool forward)
        {
            return this->generate_command_with_key(n, light_id_, data, forward, this->mesh_key_, false);
        }

        std::vector<uint8_t> FastconController::generate_command_with_key(uint8_t n, uint32_t light_id_, const std::vector<uint8_t> &data,
                                                                          bool forward, const std::array<uint8_t, 4> &key, bool zero_key_probe)
        {
            static uint8_t sequence = 0;

            // Pairing frames (wake probe n=0, keyset n=2) always carry a
            // 12-byte body zero-padded like the app sends them; control frames
            // stay variable-length.
            size_t data_area = (n == 0 || n == 2) ? 12 : data.size();
            if (data.size() > data_area)
                data_area = data.size();

            std::vector<uint8_t> body(data_area + 4, 0);
            uint8_t i2 = (light_id_ / 256);

            body[0] = (i2 & 0b1111) | ((n & 0b111) << 4) | (forward ? 0x80 : 0);
            body[1] = sequence++;
            if (sequence >= 255)
                sequence = 1;

            body[2] = zero_key_probe ? 0xff : key[3]; // Safe key

            std::copy(data.begin(), data.end(), body.begin() + 4);

            // Checksum covers header plus the real data length only, even
            // though the padded tail is transmitted (matches app behavior)
            uint8_t checksum = 0;
            for (size_t i = 0; i < data.size() + 4; i++)
            {
                if (i != 3)
                {
                    checksum = checksum + body[i];
                }
            }
            body[3] = checksum;

            for (size_t i = 0; i < 4; i++)
            {
                body[i] = DEFAULT_ENCRYPT_KEY[i & 3] ^ body[i];
            }

            for (size_t i = 0; i < data_area; i++)
            {
                body[4 + i] = key[i & 3] ^ body[4 + i];
            }

            if (zero_key_probe)
            {
                // The wake probe's data area is the factory key pattern in the
                // clear; unpaired lights answer it with their identity advert
                for (size_t i = 4; i < body.size(); i++)
                {
                    body[i] = DEFAULT_ENCRYPT_KEY[i & 3];
                }
            }

            std::vector<uint8_t> addr = {DEFAULT_BLE_FASTCON_ADDRESS.begin(), DEFAULT_BLE_FASTCON_ADDRESS.end()};
            return prepare_payload(addr, body);
        }

        void FastconController::start_pairing(uint32_t duration_ms)
        {
            {
                std::lock_guard<std::mutex> lock(pair_mutex_);
                pair_candidates_.clear();
            }
            pairing_active_ = true;
            pairing_deadline_ = millis() + duration_ms;
            last_wake_ms_ = 0;
            ESP_LOGI(TAG, "Pairing started for %.1fs: broadcasting wake probe, listening for factory-key lights...",
                     duration_ms / 1000.0f);
            ESP_LOGI(TAG, "Lights already paired elsewhere must be factory-reset first (power-cycle 5x)");
        }

        void FastconController::stop_pairing()
        {
            if (!pairing_active_)
                return;
            pairing_active_ = false;
            ESP_LOGI(TAG, "Pairing stopped. %s", this->pairing_summary().c_str());
        }

        std::string FastconController::pairing_summary() const
        {
            std::string out;
            size_t confirmed = 0;
            for (const auto &cand : pair_candidates_)
            {
                if (cand.confirmed)
                    confirmed++;
            }
            char head[64];
            snprintf(head, sizeof(head), "Found %u light(s), %u confirmed on our key.",
                     (unsigned)pair_candidates_.size(), (unsigned)confirmed);
            out += head;
            for (const auto &cand : pair_candidates_)
            {
                char line[80];
                snprintf(line, sizeof(line), " [id %u mac %s type %s %s]",
                         cand.assigned_id, mac_to_hex(cand.ble_mac).c_str(),
                         type_name(cand.type_code), cand.confirmed ? "CONFIRMED" : "unconfirmed");
                out += line;
            }
            return out;
        }

        void FastconController::queue_wake_probe_()
        {
            std::vector<uint8_t> data(6, 0);
            std::array<uint8_t, 4> zero_key{};
            auto payload = this->generate_command_with_key(0, 0, data, false, zero_key, true);
            // A couple of back-to-back copies; the adv machinery spaces them
            this->queueCommand(0, payload);
            this->queueCommand(0, payload);
        }

        void FastconController::queue_keyset_(PairCandidate &cand)
        {
            std::vector<uint8_t> data(12);
            for (size_t i = 0; i < 6; i++)
                data[i] = cand.ble_mac[i];
            data[6] = cand.assigned_id;
            data[7] = 0x01; // group id
            data[8] = mesh_key_[0];
            data[9] = mesh_key_[1];
            data[10] = mesh_key_[2];
            data[11] = mesh_key_[3];

            ESP_LOGI(TAG, "Assigning light id %u to mac %s (type %s)", cand.assigned_id,
                     mac_to_hex(cand.ble_mac).c_str(), type_name(cand.type_code));

            auto payload = this->generate_command_with_key(2, 0, data, false, DEFAULT_ENCRYPT_KEY, false);
            for (int i = 0; i < 6; i++)
                this->queueCommand(0, payload);
            cand.keyset_sent = true;
        }

        bool FastconController::parse_device(const esp32_ble_tracker::ESPBTDevice &device)
        {
            if (!pairing_active_)
                return false;

            for (const auto &mfr : device.get_manufacturer_datas())
            {
                // Company id bytes on air are F0 FF; accept either uint16 reading
                if (mfr.uuid != esp32_ble_tracker::ESPBTUUID::from_uint16(0xFFF0) &&
                    mfr.uuid != esp32_ble_tracker::ESPBTUUID::from_uint16(0xF0FF))
                    continue;
                if (mfr.data.size() != 16)
                    continue;

                // Layout after the company id (dsclee1): [4:10] light BLE mac,
                // [10:12] type code, [12:16] current mesh key in the clear
                std::array<uint8_t, 6> mac{};
                std::copy(mfr.data.begin() + 4, mfr.data.begin() + 10, mac.begin());
                std::array<uint8_t, 2> type{};
                std::copy(mfr.data.begin() + 10, mfr.data.begin() + 12, type.begin());
                std::array<uint8_t, 4> adv_key{};
                std::copy(mfr.data.begin() + 12, mfr.data.begin() + 16, adv_key.begin());

                std::lock_guard<std::mutex> lock(pair_mutex_);

                bool factory_key = std::equal(adv_key.begin(), adv_key.end(), DEFAULT_ENCRYPT_KEY.begin());
                bool our_key = std::equal(adv_key.begin(), adv_key.end(), mesh_key_.begin());

                if (factory_key)
                {
                    bool known = false;
                    for (auto &cand : pair_candidates_)
                    {
                        if (cand.ble_mac == mac)
                        {
                            known = true;
                            break;
                        }
                    }
                    if (!known)
                    {
                        PairCandidate cand;
                        cand.ble_mac = mac;
                        cand.type_code = type;
                        cand.assigned_id = (uint8_t)(pair_candidates_.size() + 1);
                        cand.last_keyset_ms = millis();
                        ESP_LOGI(TAG, "Unpaired %s light found, mac %s -> will assign id %u",
                                 type_name(type), mac_to_hex(mac).c_str(), cand.assigned_id);
                        pair_candidates_.push_back(cand);
                        this->queue_keyset_(pair_candidates_.back());
                    }
                }
                else if (our_key)
                {
                    for (auto &cand : pair_candidates_)
                    {
                        if (cand.ble_mac == mac && !cand.confirmed)
                        {
                            cand.confirmed = true;
                            ESP_LOGI(TAG, "Light id %u (mac %s) CONFIRMED on our mesh key",
                                     cand.assigned_id, mac_to_hex(cand.ble_mac).c_str());
                        }
                    }
                }
                else
                {
                    ESP_LOGD(TAG, "Fastcon advert with foreign key %02X%02X%02X%02X from mac %s (someone else's mesh?)",
                             adv_key[0], adv_key[1], adv_key[2], adv_key[3], mac_to_hex(mac).c_str());
                }
            }
            return false;
        }
    } // namespace fastcon
} // namespace esphome
