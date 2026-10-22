#include "../firmware/usb_sensor/update_policy.h"
#include <cassert>

int main() {
  using namespace usb_update;
  static_assert(https_url("https://receiver.test/usb-temperature"));
  static_assert(!https_url("http://receiver.test/usb-temperature"));
  static_assert(!https_url("") && !https_url("https://"));
  Persistent s;
  assert(!recover(s, 1));
  assert(!newer_release(0, 1) && !newer_release(1, 1));
  assert(!newer_release(UINT32_MAX, 1));
  assert(newer_release(2, 1));
  s.attempted = 2; s.source = 1; s.stage = 1; s.result = INSTALLING;
  // Power loss during transfer / before the completion callback is conservative.
  assert(recover(s, 1));
  assert(s.result == FAILED && s.stage == 0 && s.blocked == 2);
  assert(!eligible(2, 1, s) && eligible(3, 1, s));
  s = {}; s.attempted = 2; s.source = 1; s.stage = 2; s.result = INSTALLING;
  assert(recover(s, 2));
  assert(s.result == INSTALLED && s.stage == 2);
  assert(!recover(s, 2));  // Healthy reboot does not rewrite NVS.
  assert(recover(s, 1));  // Bootloader fell back to the previous image.
  assert(s.result == ROLLED_BACK && s.blocked == 2 && !eligible(2, 1, s));
  assert(eligible(3, 1, s));
  s = {}; s.attempted = 2; s.stage = 1; s.result = INSTALLING;
  assert(recover(s, 2));  // New slot booted before the completion callback saved.
  assert(s.result == INSTALLED && s.stage == 2);
}
