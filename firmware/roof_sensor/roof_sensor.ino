#include <WiFi.h>
#include <HTTPClient.h>
#include <NetworkClientSecure.h>
#include <time.h>
#include "ca_cert.h"
#include <OneWire.h>
#include <DallasTemperature.h>
#include <esp_sleep.h>
#include <esp_system.h>
#include <math.h>
#include "secrets.h"

#ifndef ROOF_SLEEP_SECONDS
#define ROOF_SLEEP_SECONDS 300
#endif
#ifndef ROOF_BATTERY_SENSE
#define ROOF_BATTERY_SENSE 0
#endif
#ifndef ROOF_TEST_WIFI_FAILURE
#define ROOF_TEST_WIFI_FAILURE 0
#endif
#ifndef ROOF_TEST_HTTPS_FAILURE
#define ROOF_TEST_HTTPS_FAILURE 0
#endif
static_assert(A0 == 0, "Battery divider must use D0 / GPIO0");
static_assert(D2 == 2, "Select XIAO ESP32-C6");
static_assert(ROOF_SLEEP_SECONDS >= 1 && ROOF_SLEEP_SECONDS <= 3600, "Sleep must be 1..3600 seconds");
constexpr uint32_t AWAKE_LIMIT_MS = 20000;
RTC_DATA_ATTR uint32_t bootCount = 0;
RTC_DATA_ATTR uint32_t sessionId = 0;
RTC_DATA_ATTR uint32_t failures = 0;
RTC_DATA_ATTR uint32_t previousStage = 0;
RTC_DATA_ATTR int previousHttpStatus = 0;
OneWire bus(D2);
DallasTemperature sensors(&bus);
NetworkClientSecure transport;
char eventId[32];
bool acknowledged = false;
uint32_t awakeStart;

void sleepNow() {
  esp_sleep_enable_timer_wakeup(uint64_t(ROOF_SLEEP_SECONDS) * 1000000ULL);
  esp_deep_sleep_start();
}

void deadlineTask(void *) {
  vTaskDelay(pdMS_TO_TICKS(AWAKE_LIMIT_MS));
  // Independent task bounds even a blocking network/library operation.
  sleepNow();
}


void setup() {
  awakeStart = millis();
  Serial.begin(115200);
  if (!sessionId) sessionId = esp_random();
  ++bootCount;
  const uint32_t lastStage = previousStage;
  ++failures; // Cleared only after the receiver commits and acknowledges this reading.
  previousStage = 1;
  snprintf(eventId, sizeof(eventId), "%08lx-%lu", (unsigned long)sessionId, (unsigned long)bootCount);
  if (xTaskCreate(deadlineTask, "awake-deadline", 3072, nullptr, 5, nullptr) != pdPASS) sleepNow();
  Serial.printf("WAKE %s reset=%d previous_stage=%lu\n", eventId, int(esp_reset_reason()), (unsigned long)lastStage);

  // Use the C6's built-in antenna.
  pinMode(3, OUTPUT); digitalWrite(3, LOW);
  pinMode(14, OUTPUT); digitalWrite(14, LOW);
  sensors.begin();
  DeviceAddress address;
  char rom[17] = "";
  float c = DEVICE_DISCONNECTED_C;
  bool sensorOk = sensors.getDeviceCount() == 1 && sensors.getAddress(address, 0) && address[0] == 0x28;
  if (sensorOk) {
    for (int i = 0; i < 8; ++i) snprintf(rom + i * 2, 3, "%02X", address[i]);
    sensors.setResolution(address, 12);
    sensors.setWaitForConversion(true);
    sensors.requestTemperatures();
    c = sensors.getTempC(address);
    sensorOk = isfinite(c) && c != DEVICE_DISCONNECTED_C && c >= -55 && c <= 125;
  }
  // 100k/100k divider with 100nF to GND: RC=5ms. Sample before radio load.
  uint32_t batterySumMv = 0;
  if (ROOF_BATTERY_SENSE) {
    pinMode(A0, INPUT);
    analogReadResolution(12);
    analogSetPinAttenuation(A0, ADC_11db);
    delay(50);
    analogReadMilliVolts(A0); // Discard initial conversion.
    for (int i = 0; i < 32; ++i) {
      delay(5);
      batterySumMv += analogReadMilliVolts(A0);
    }
  }
  const float batteryAdcMv = batterySumMv / 32.0f;
  const float batteryV = batteryAdcMv * 2.0f / 1000.0f;
  // Plausibility only, not state-of-charge or proof of wiring integrity.
  const bool batteryOk = ROOF_BATTERY_SENSE && batteryV >= 2.0f && batteryV <= 4.5f;
  char batteryText[24] = "null";
  if (batteryOk) snprintf(batteryText, sizeof(batteryText), "%.3f", batteryV);
  Serial.printf("Battery ADC=%.1f mV battery=%s V valid=%s\n",
                batteryAdcMv, batteryText, batteryOk ? "yes" : "no");
  previousStage = 2;
  WiFi.mode(WIFI_STA);
  WiFi.begin((ROOF_TEST_WIFI_FAILURE && bootCount == 1) ? "solar-sensor-failure-test-unavailable" : WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED && millis() - awakeStart < 12000) delay(50);
  if (WiFi.status() != WL_CONNECTED) {
    Serial.printf("Wi-Fi unavailable; sleep at %lu ms\n", (unsigned long)(millis() - awakeStart));
    sleepNow();
  }
  previousStage = 3;
  // Match the established guest-network workaround: DHCP precedes usable DNS.
  delay(2500);
  // Guest Wi-Fi reaches the receiver through authenticated HTTPS.
  // NTP provides wall time for certificate validity checks.
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  while (time(nullptr) < 1767225600 && millis() - awakeStart < 15000) delay(50);
  if (time(nullptr) < 1767225600) {
    Serial.println("Clock sync unavailable; sleeping without insecure TLS fallback");
    sleepNow();
  }
  transport.setCACert(ROOT_CA);
  transport.setHandshakeTimeout(4);
  transport.setConnectionTimeout(2500);
  HTTPClient http;
  http.setConnectTimeout(2500);
  http.setTimeout(3500);
  char tempC[24] = "null", tempF[24] = "null";
  if (sensorOk) {
    snprintf(tempC, sizeof(tempC), "%.4f", c);
    snprintf(tempF, sizeof(tempF), "%.4f", c * 1.8f + 32);
  }
  char payload[800];
  snprintf(payload, sizeof(payload),
    "{\"sensor\":\"roof-solar-reference\",\"event_id\":\"%s\",\"sensor_rom\":\"%s\","
    "\"temp_ok\":%s,\"temperature_c\":%s,\"temperature_f\":%s,"
    "\"battery_ok\":%s,\"battery_v\":%s,\"battery_adc_mv\":%.1f,"
    "\"wifi_rssi_dbm\":%d,\"boot_count\":%lu,\"reset_reason\":%d,\"sleep_seconds\":%u,"
    "\"previous_failures\":%lu,\"previous_stage\":%lu,\"previous_http_status\":%d,\"awake_before_publish_ms\":%lu}",
    eventId, rom, sensorOk ? "true" : "false", tempC, tempF,
    batteryOk ? "true" : "false", batteryText, batteryAdcMv, WiFi.RSSI(),
    (unsigned long)bootCount, int(esp_reset_reason()), ROOF_SLEEP_SECONDS,
    (unsigned long)(failures - 1), (unsigned long)lastStage, previousHttpStatus, (unsigned long)(millis() - awakeStart));
  previousStage = 4;
  int status = 0;
  const String url = (ROOF_TEST_HTTPS_FAILURE && bootCount == 2)
      ? String(INGEST_URL) + "/unavailable" : String(INGEST_URL);
  for (int attempt = 0; attempt < 2 && !acknowledged && millis() - awakeStart < 15000; ++attempt) {
    if (http.begin(transport, url)) {
      http.addHeader("Content-Type", "application/json");
      http.addHeader("Authorization", String("Bearer ") + INGEST_TOKEN);
      status = http.POST((uint8_t *)payload, strlen(payload));
      if (status == 200) acknowledged = http.getString() == eventId;
      http.end();
    }
    if (status >= 400 && status < 500) break;
    if (!acknowledged) delay(750);
  }
  previousHttpStatus = status;
  if (acknowledged) { failures = 0; previousStage = 0; }
  Serial.printf("Receiver stored=%s HTTP=%d temp=%s F RSSI=%d sleep=%u s awake=%lu ms\n",
                acknowledged ? "yes" : "no", status, tempF, WiFi.RSSI(), ROOF_SLEEP_SECONDS,
                (unsigned long)(millis() - awakeStart));
  sleepNow();
}
void loop() {}
