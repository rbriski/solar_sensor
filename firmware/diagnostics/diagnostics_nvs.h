#pragma once
#include "diagnostics.h"
#include <nvs.h>
namespace diagnostics {
inline bool load(State &state) {
  nvs_handle_t h;
  auto err=nvs_open("sensor_diag",NVS_READONLY,&h);
  if(err==ESP_ERR_NVS_NOT_FOUND) return true;
  if(err!=ESP_OK) return false;
  State loaded; size_t size=sizeof(loaded);
  err=nvs_get_blob(h,"state",&loaded,&size); nvs_close(h);
  if(err==ESP_ERR_NVS_NOT_FOUND) return true;
  if(err!=ESP_OK || size!=sizeof(loaded) || loaded.magic!=state.magic || loaded.count>4) return false;
  state=loaded; return true;
}
inline bool save(const State &state) {
  nvs_handle_t h;
  if(nvs_open("sensor_diag",NVS_READWRITE,&h)!=ESP_OK) return false;
  bool ok=nvs_set_blob(h,"state",&state,sizeof(state))==ESP_OK && nvs_commit(h)==ESP_OK;
  nvs_close(h); return ok;
}
// Caller retains these values in RTC RAM for a sleeping sensor. At most one
// fault checkpoint per ten minutes, plus one cold boot checkpoint. A power
// loss during the throttled window can lose pending history (reported on wire).
inline void checkpoint(State &s, bool &dirty, bool &storage_ok,
                       uint32_t now, uint32_t &last_write, bool &wrote) {
  if(!dirty || (wrote && uint32_t(now-last_write)<600)) return;
  storage_ok=save(s); last_write=now; wrote=true;
  if(storage_ok) dirty=false;
}
}
