// USB bench test: adapter VCC -> 3V3, GND -> GND, DAT -> D2.
// No Wi-Fi or deep sleep: keep serial available while checking the wiring.
#include <OneWire.h>
#include <DallasTemperature.h>
#include <math.h>

static_assert(D2 == 2, "Build for XIAO ESP32-C6 (D2 = GPIO2)");
OneWire bus(D2);
DallasTemperature sensors(&bus);
uint32_t sample = 0;

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("XIAO ESP32-C6 probe test: D2/GPIO2, powered 3-wire DS18B20");
}

void loop() {
  // Re-scan so an unplugged/reconnected probe recovers without a reset.
  sensors.begin();
  DeviceAddress address;
  ++sample;
  if (sensors.getDeviceCount() != 1 || !sensors.getAddress(address, 0) || address[0] != 0x28) {
    Serial.printf("{\"sample\":%lu,\"temp_ok\":false,\"error\":\"expected_one_ds18b20\",\"devices\":%u}\n",
                  (unsigned long)sample, sensors.getDeviceCount());
  } else {
    sensors.setResolution(address, 12);
    sensors.setWaitForConversion(true);
    sensors.requestTemperatures();
    const float c = sensors.getTempC(address); // Library verifies scratchpad CRC.
    const bool ok = isfinite(c) && c != DEVICE_DISCONNECTED_C && c >= -55 && c <= 125;
    Serial.printf("{\"sample\":%lu,\"sensor_rom\":\"", (unsigned long)sample);
    for (uint8_t b : address) Serial.printf("%02X", b);
    if (ok) {
      Serial.printf("\",\"temp_ok\":true,\"temperature_c\":%.4f,\"temperature_f\":%.4f}\n", c, c * 1.8f + 32);
    } else {
      Serial.println("\",\"temp_ok\":false,\"error\":\"conversion_or_read_failed\"}");
    }
  }
  delay(1250);
}
