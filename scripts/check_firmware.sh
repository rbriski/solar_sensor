#!/usr/bin/env bash
# Compile only. Never reads real credentials and never uploads to hardware.
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="$(mktemp -d)"
trap 'rm -rf -- "$build_dir"' EXIT
mkdir -p "$build_dir/roof_sensor"
cp -f "$repo_dir/firmware/roof_sensor/roof_sensor.ino" "$repo_dir/firmware/roof_sensor/ca_cert.h" "$build_dir/roof_sensor/"
cp -f "$repo_dir/firmware/roof_sensor/secrets.h.example" "$build_dir/roof_sensor/secrets.h"
board='esp32:esp32:XIAO_ESP32C6:CDCOnBoot=cdc'
arduino-cli compile --fqbn "$board" --libraries "$repo_dir/firmware/libraries" "$repo_dir/firmware/probe_test"
arduino-cli compile --fqbn "$board" --libraries "$repo_dir/firmware/libraries" "$build_dir/roof_sensor"
arduino-cli compile --fqbn "$board" --libraries "$repo_dir/firmware/libraries" --build-property 'build.extra_flags=-DROOF_SLEEP_SECONDS=30 -DROOF_BATTERY_SENSE=1 -DROOF_TEST_WIFI_FAILURE=1 -DROOF_TEST_HTTPS_FAILURE=1' "$build_dir/roof_sensor"
