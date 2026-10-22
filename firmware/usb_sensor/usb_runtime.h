#pragma once
#include "update_policy.h"
#include "diagnostics_nvs.h"
#include <time.h>
#include <cmath>
#include <cstdio>
#include <string>
#include <esp_ota_ops.h>
#include <esp_random.h>
#include <esp_system.h>
#include <esp_timer.h>
#include <nvs.h>
#include "esphome/core/alloc_helpers.h"
#include "esphome/components/json/json_util.h"

namespace usb_update {
static Persistent state;
static uint32_t current = 0, candidate = 0, checked_at = 0;
static std::string checksum, image_url;
static esp_timer_handle_t deadline = nullptr;
static bool ready = false, storage_ok = false;

inline bool save() {
  nvs_handle_t h;
  if (nvs_open("usb_fw", NVS_READWRITE, &h) != ESP_OK) return storage_ok = false;
  bool ok = nvs_set_blob(h, "state", &state, sizeof(state)) == ESP_OK && nvs_commit(h) == ESP_OK;
  nvs_close(h);
  return storage_ok = ok;
}
inline void result(Result value) {
  if (state.result != value) { state.result = value; save(); }
}
inline const char *result_text() {
  switch (state.result) {
    case INSTALLED: return "installed";
    case FAILED: return "failed";
    case ROLLED_BACK: return "rolled_back";
    case CHECK_FAILED: return "check_failed";
    case INSTALLING: return "installing";
    default: return "none";
  }
}
inline const char *authorization(const char *node, const char *password) {
  const std::string value = std::string(node) + ":" + password;
  static std::string header;
  header = "Basic " + esphome::base64_encode(reinterpret_cast<const uint8_t *>(value.data()), value.size());
  return header.c_str();
}
inline void init(uint32_t release) {
  current = release;
  nvs_handle_t h;
  if (nvs_open("usb_fw", NVS_READWRITE, &h) == ESP_OK) {
    size_t size = sizeof(state);
    Persistent loaded;
    esp_err_t err = nvs_get_blob(h, "state", &loaded, &size);
    if (err == ESP_OK && size == sizeof(state) && loaded.magic == state.magic) {
      state = loaded;
      storage_ok = true;
    } else if (err == ESP_ERR_NVS_NOT_FOUND) storage_ok = true;
    nvs_close(h);
  }
  if (storage_ok && recover(state, current)) save();
}
inline void prepare(const std::string &body, const char *node, const char *base) {
  ready = false;
  candidate = 0;
  uint32_t checked = 0;
  bool valid = esphome::json::parse_json(body, [&](JsonObject root) {
    if (!root["sensor"].is<const char *>() || std::string(root["sensor"].as<const char *>()) != node ||
        !root["release"].is<uint32_t>() || !root["checked_at"].is<uint32_t>()) return false;
    checked = root["checked_at"].as<uint32_t>();
    uint32_t release = root["release"].as<uint32_t>();
    if (!newer_release(release, current)) {
      if (state.result == CHECK_FAILED) result(NONE);
      return true;
    }
    const auto *slot = esp_ota_get_next_update_partition(nullptr);
    if (!root["target"].is<const char *>() ||
        std::string(root["target"].as<const char *>()) != "usb-temperature-c6-v1" ||
        !root["size"].is<uint32_t>() || !slot || root["size"].as<uint32_t>() == 0 ||
        root["size"].as<uint32_t>() > slot->size || !root["md5"].is<const char *>()) return false;
    checksum = root["md5"].as<std::string>();
    if (checksum.size() != 32 || checksum.find_first_not_of("0123456789abcdef") != std::string::npos) return false;
    candidate = release;
    if (!eligible(release, current, state)) return true;
    image_url = std::string(base) + "/firmware/" + std::to_string(release) + ".bin";
    ready = storage_ok;
    return true;
  });
  if (!valid) result(CHECK_FAILED);
  else checked_at = checked;
}
inline bool begin() {
  if (!ready) return false;
  ready = false;
  esp_ota_img_states_t status;
  if (esp_ota_get_state_partition(esp_ota_get_running_partition(), &status) == ESP_OK &&
      status == ESP_OTA_IMG_PENDING_VERIFY) return false;
  if (!deadline) {
    esp_timer_create_args_t args{};
    args.callback = [](void *) { esp_restart(); };
    args.name = "usb_ota_deadline";
    if (esp_timer_create(&args, &deadline) != ESP_OK) return false;
  }
  state.attempted = candidate;
  state.source = current;
  state.stage = 1;
  state.result = INSTALLING;
  if (!save()) return false;
  return esp_timer_start_once(deadline, 180ULL * 1000000) == ESP_OK;
}
inline void finished() { state.stage = 2; save(); }
inline void failed() {
  ready = false;
  if (deadline) esp_timer_stop(deadline);
  state.stage = 0;
  state.result = FAILED;
  save();
}
}  // namespace usb_update

namespace usb_sensor {
static uint32_t session = 0, sequence = 0, failures = 0;
static float temperature = NAN;
static std::string rom, event, payload;
static bool accepted = false;
static diagnostics::State diag;
static bool dirty=false, storage_ok=true, wrote=false;
static uint32_t last_write=0, disconnects=0, probe_code=diagnostics::NO_DEVICE;
static unsigned devices=0;
static int http_status=0;
inline uint32_t uptime() { return uint32_t(esp_timer_get_time()/1000000); }
inline uint32_t epoch() { time_t t=::time(nullptr); return t>=1767225600 ? uint32_t(t):0; }
inline void checkpoint() { diagnostics::checkpoint(diag,dirty,storage_ok,uptime(),last_write,wrote); }
inline void transport(uint32_t code) { dirty |= diagnostics::delivery(diag,code,epoch(),uptime()); }

inline void init() {
  session = esp_random();
  storage_ok=diagnostics::load(diag);
  diagnostics::increment(diag.boots);
  diagnostics::record(diag,diagnostics::BOOT,epoch(),uptime(),uint32_t(esp_reset_reason()));
  storage_ok=diagnostics::save(diag);
}
inline void prepare(const char *node, uint32_t interval, uint32_t release, const char *version, int rssi) {
  if (++sequence == 0) { session = esp_random(); sequence = 1; }
  char id[32];
  snprintf(id, sizeof(id), "%08lx-%lu", (unsigned long) session, (unsigned long) sequence);
  event = id;
  accepted = false;
  const bool valid = std::isfinite(temperature) && temperature >= -55 && temperature <= 125 && !rom.empty();
  dirty |= diagnostics::probe(diag,valid ? diagnostics::OK : probe_code,epoch(),uptime());
  checkpoint();
  char diagnostic_json[700];
  diagnostics::json(diag,diagnostic_json,sizeof(diagnostic_json),devices,uptime(),disconnects,http_status,storage_ok,dirty);
  payload = esphome::json::build_json([&](JsonObject root) {
    root["sensor"] = node;
    root["event_id"] = event;
    root["sensor_rom"] = rom;
    root["temp_ok"] = valid;
    if (valid) {
      root["temperature_c"] = temperature;
      root["temperature_f"] = temperature * 1.8f + 32;
    } else {
      root["temperature_c"] = nullptr;
      root["temperature_f"] = nullptr;
    }
    root["power_mode"] = "usb";
    root["report_interval_seconds"] = interval;
    root["sleep_seconds"] = 0;
    root["boot_count"] = diag.boots;
    root["diagnostics"] = serialized(diagnostic_json);
    root["sample_sequence"] = sequence;
    root["reset_reason"] = int(esp_reset_reason());
    root["wifi_rssi_dbm"] = rssi;
    root["previous_failures"] = failures;
    root["firmware_release"] = release;
    root["firmware_version"] = version;
    root["firmware_checked_at"] = usb_update::checked_at;
    root["attempted_release"] = usb_update::state.attempted;
    root["update_result"] = usb_update::result_text();
  });
}
inline void response(int status, const std::string &body) {
  http_status=status; accepted = status == 200 && body == event;
  transport(accepted ? diagnostics::DELIVERY_OK : status==200 ? diagnostics::ACK_FAILED : diagnostics::HTTP_FAILED);
}
inline void finish() { if (accepted) failures = 0; else if (failures != UINT32_MAX) ++failures; checkpoint(); }
}  // namespace usb_sensor
