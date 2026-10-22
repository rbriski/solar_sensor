#pragma once
#include <cstdint>

namespace usb_update {
constexpr bool https_url(const char *url) {
  constexpr char prefix[] = "https://";
  for (unsigned i = 0; i < sizeof(prefix) - 1; ++i) {
    if (url[i] != prefix[i]) return false;
  }
  return url[8] != '\0';
}
enum Result : uint32_t { NONE, INSTALLED, FAILED, ROLLED_BACK, CHECK_FAILED, INSTALLING };
struct Persistent {
  uint32_t magic = 0x55534231, attempted = 0, source = 0, blocked = 0, stage = 0;
  Result result = NONE;
};
inline bool newer_release(uint32_t available, uint32_t installed) {
  return available > installed && available <= 2147483647UL;
}
// Stage 2 remains available to the old slot if the candidate fails before
// ESPHome's boot confirmation. A rolled-back release must not install again.
inline bool recover(Persistent &s, uint32_t current) {
  if (!s.stage) return false;
  if (current == s.attempted) {
    if (s.result == INSTALLED && s.stage == 2) return false;
    s.result = INSTALLED;
    s.stage = 2;
  } else {
    // A reset may happen after the boot slot changes but before on_end saves
    // stage 2. Conservatively block either interrupted attempt after reboot.
    s.result = s.stage == 2 ? ROLLED_BACK : FAILED;
    s.blocked = s.attempted;
    s.stage = 0;
  }
  return true;
}
inline bool eligible(uint32_t candidate, uint32_t current, const Persistent &s) {
  return newer_release(candidate, current) && candidate != s.blocked;
}
}  // namespace usb_update
