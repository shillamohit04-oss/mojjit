/*
 * ============================================================================
 * Smart HVAC Control System — ESP32 Firmware
 * ============================================================================
 *
 * Bidirectional HVAC controller with:
 *   - DHT22 temperature/humidity sensing
 *   - PIR motion-based occupancy detection
 *   - Three-zone control (Cooling / Idle / Heating)
 *   - Hysteresis + compressor short-cycle protection
 *   - WiFi connectivity + MQTT telemetry
 *   - OTA firmware updates
 *   - Watchdog timer for reliability
 *   - EEPROM setpoint persistence
 *
 * Hardware:
 *   - ESP32 DevKit v1
 *   - DHT22 on GPIO 4 (with 10kΩ pull-up)
 *   - PIR sensor on GPIO 14
 *   - Cooling relay on GPIO 26
 *   - Heating relay on GPIO 27
 *   - Status LED on GPIO 2 (onboard)
 *
 * Author: Smart HVAC Control System
 * License: MIT
 * ============================================================================
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <EEPROM.h>
#include <ArduinoOTA.h>
#include <ArduinoJson.h>
#include <esp_task_wdt.h>

// ============================================================================
// PIN DEFINITIONS
// ============================================================================
#define DHT_PIN           4       // DHT22 data pin
#define PIR_PIN           14      // PIR motion sensor
#define RELAY_COOLING     26      // Relay for cooling (AC compressor)
#define RELAY_HEATING     27      // Relay for heating (heat pump reverse valve)
#define LED_STATUS        2       // Onboard LED for status indication

// ============================================================================
// SENSOR CONFIGURATION
// ============================================================================
#define DHT_TYPE          DHT22
#define SENSOR_READ_INTERVAL  2000   // ms — DHT22 minimum interval
#define SENSOR_AVG_SAMPLES    5      // Number of readings to average

// ============================================================================
// CONTROL PARAMETERS (EEPROM-backed defaults)
// ============================================================================
struct ControlConfig {
    float cooling_threshold;     // °C — start cooling above this (default: 26.0)
    float heating_threshold;     // °C — start heating below this (default: 20.0)
    float hysteresis;            // °C — deadband to prevent oscillation (default: 0.5)
    float unoccupied_cooling;    // °C — unoccupied cooling setback (default: 28.0)
    float unoccupied_heating;    // °C — unoccupied heating setback (default: 18.0)
    float humidity_override;     // % — force cooling above this humidity (default: 70.0)
    uint16_t min_cycle_time_sec; // Compressor protection time (default: 180)
    uint16_t pir_timeout_sec;    // Occupancy timeout after last motion (default: 300)
    uint8_t checksum;            // Simple checksum for validation
};

ControlConfig config;

// ============================================================================
// WiFi / MQTT CONFIGURATION
// ============================================================================
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* MQTT_SERVER   = "YOUR_MQTT_BROKER_IP";
const int   MQTT_PORT     = 1883;
const char* MQTT_CLIENT   = "hvac_esp32";
const char* MQTT_USER     = "";  // Optional
const char* MQTT_PASS     = "";  // Optional

// MQTT Topics
const char* TOPIC_SENSOR   = "hvac/sensor";
const char* TOPIC_STATE    = "hvac/state";
const char* TOPIC_CONTROL  = "hvac/control";
const char* TOPIC_CONFIG   = "hvac/config";
const char* TOPIC_STATUS   = "hvac/status";

// ============================================================================
// GLOBAL STATE
// ============================================================================

// HVAC operating modes
enum HVACMode {
    MODE_IDLE,
    MODE_COOLING,
    MODE_HEATING
};

// Sensor data (averaged)
float temperature     = 23.0;
float humidity        = 50.0;
bool  sensorValid     = false;
float tempReadings[SENSOR_AVG_SAMPLES];
float humReadings[SENSOR_AVG_SAMPLES];
int   readingIndex    = 0;
bool  bufferFull      = false;

// Occupancy
bool  motionDetected  = false;
bool  isOccupied      = false;
unsigned long lastMotionTime = 0;

// HVAC state
HVACMode currentMode     = MODE_IDLE;
bool     coolingActive   = false;
bool     heatingActive   = false;
unsigned long lastModeChange = 0;
bool     protectionActive = false;

// Energy tracking
unsigned long coolingRuntime = 0;  // Total milliseconds
unsigned long heatingRuntime = 0;
unsigned long lastRuntimeCheck = 0;

// Timing
unsigned long lastSensorRead = 0;
unsigned long lastMqttPublish = 0;
unsigned long lastStatusBlink = 0;
const unsigned long MQTT_PUBLISH_INTERVAL = 5000;  // 5 seconds

// Objects
DHT dht(DHT_PIN, DHT_TYPE);
WiFiClient espClient;
PubSubClient mqtt(espClient);

// ============================================================================
// SETUP
// ============================================================================
void setup() {
    Serial.begin(115200);
    Serial.println("\n========================================");
    Serial.println("  Smart HVAC Control System — ESP32");
    Serial.println("  Bidirectional Heat Pump Controller");
    Serial.println("========================================\n");

    // Pin configuration
    pinMode(RELAY_COOLING, OUTPUT);
    pinMode(RELAY_HEATING, OUTPUT);
    pinMode(LED_STATUS, OUTPUT);
    pinMode(PIR_PIN, INPUT);

    // Start with relays OFF (active-low relay modules)
    digitalWrite(RELAY_COOLING, HIGH);
    digitalWrite(RELAY_HEATING, HIGH);

    // Initialize sensor
    dht.begin();
    Serial.println("[OK] DHT22 sensor initialized");

    // Load configuration from EEPROM
    EEPROM.begin(sizeof(ControlConfig));
    loadConfig();

    // Connect WiFi
    setupWiFi();

    // Configure MQTT
    mqtt.setServer(MQTT_SERVER, MQTT_PORT);
    mqtt.setCallback(mqttCallback);
    mqtt.setBufferSize(1024);

    // Configure OTA
    setupOTA();

    // Configure watchdog (30 second timeout)
    esp_task_wdt_init(30, true);
    esp_task_wdt_add(NULL);

    Serial.println("[OK] System ready\n");
    lastRuntimeCheck = millis();
}

// ============================================================================
// MAIN LOOP
// ============================================================================
void loop() {
    // Feed watchdog
    esp_task_wdt_reset();

    // Handle OTA updates
    ArduinoOTA.handle();

    // Maintain MQTT connection
    if (!mqtt.connected()) {
        reconnectMQTT();
    }
    mqtt.loop();

    unsigned long now = millis();

    // --- Read sensors ---
    if (now - lastSensorRead >= SENSOR_READ_INTERVAL) {
        readSensors();
        lastSensorRead = now;
    }

    // --- Check occupancy ---
    checkOccupancy(now);

    // --- HVAC control logic ---
    if (sensorValid) {
        controlHVAC(now);
    }

    // --- Track runtime ---
    trackRuntime(now);

    // --- Publish MQTT data ---
    if (now - lastMqttPublish >= MQTT_PUBLISH_INTERVAL) {
        publishSensorData();
        publishHVACState();
        lastMqttPublish = now;
    }

    // --- Status LED ---
    blinkStatus(now);
}

// ============================================================================
// SENSOR READING (with averaging and error handling)
// ============================================================================
void readSensors() {
    float t = dht.readTemperature();
    float h = dht.readHumidity();

    if (isnan(t) || isnan(h)) {
        Serial.println("[WARN] DHT22 read failure — using last valid reading");
        sensorValid = false;
        return;
    }

    // Sanity check
    if (t < -40 || t > 80 || h < 0 || h > 100) {
        Serial.printf("[WARN] Sensor out of range: T=%.1f H=%.1f\n", t, h);
        sensorValid = false;
        return;
    }

    // Store in ring buffer
    tempReadings[readingIndex] = t;
    humReadings[readingIndex] = h;
    readingIndex = (readingIndex + 1) % SENSOR_AVG_SAMPLES;
    if (readingIndex == 0) bufferFull = true;

    // Compute moving average
    int count = bufferFull ? SENSOR_AVG_SAMPLES : readingIndex;
    float tempSum = 0, humSum = 0;
    for (int i = 0; i < count; i++) {
        tempSum += tempReadings[i];
        humSum  += humReadings[i];
    }
    temperature = tempSum / count;
    humidity    = humSum / count;
    sensorValid = true;
}

// ============================================================================
// OCCUPANCY DETECTION (PIR with timeout)
// ============================================================================
void checkOccupancy(unsigned long now) {
    motionDetected = digitalRead(PIR_PIN) == HIGH;

    if (motionDetected) {
        lastMotionTime = now;
        if (!isOccupied) {
            isOccupied = true;
            Serial.println("[OCC] Room occupied — motion detected");
        }
    }

    // Timeout check
    if (isOccupied && (now - lastMotionTime > (unsigned long)config.pir_timeout_sec * 1000)) {
        isOccupied = false;
        Serial.println("[OCC] Room unoccupied — timeout");
    }
}

// ============================================================================
// HVAC CONTROL LOGIC — Three-Zone Bidirectional
// ============================================================================
void controlHVAC(unsigned long now) {
    // Determine active thresholds based on occupancy
    float coolOn, coolOff, heatOn, heatOff;

    if (isOccupied) {
        coolOn  = config.cooling_threshold + config.hysteresis;
        coolOff = config.cooling_threshold - config.hysteresis;
        heatOn  = config.heating_threshold - config.hysteresis;
        heatOff = config.heating_threshold + config.hysteresis;
    } else {
        // Wider deadband when unoccupied (energy saving)
        coolOn  = config.unoccupied_cooling + config.hysteresis;
        coolOff = config.unoccupied_cooling - config.hysteresis;
        heatOn  = config.unoccupied_heating - config.hysteresis;
        heatOff = config.unoccupied_heating + config.hysteresis;
    }

    // Compressor short-cycle protection
    unsigned long timeSinceModeChange = now - lastModeChange;
    bool canChange = (timeSinceModeChange >= (unsigned long)config.min_cycle_time_sec * 1000);
    protectionActive = !canChange;

    // Determine desired mode
    HVACMode desiredMode = currentMode;

    switch (currentMode) {
        case MODE_IDLE:
            if (temperature > coolOn) {
                desiredMode = MODE_COOLING;
            } else if (temperature < heatOn) {
                desiredMode = MODE_HEATING;
            }
            // Humidity override
            if (humidity > config.humidity_override && desiredMode == MODE_IDLE) {
                desiredMode = MODE_COOLING;
            }
            break;

        case MODE_COOLING:
            if (temperature <= coolOff) {
                desiredMode = MODE_IDLE;
            }
            break;

        case MODE_HEATING:
            if (temperature >= heatOff) {
                desiredMode = MODE_IDLE;
            }
            break;
    }

    // Apply mode change (respecting protection timer)
    if (desiredMode != currentMode) {
        if (canChange) {
            setHVACMode(desiredMode);
        } else {
            Serial.printf("[PROT] Mode change blocked — %lu ms remaining\n",
                          (unsigned long)config.min_cycle_time_sec * 1000 - timeSinceModeChange);
        }
    }
}

// ============================================================================
// HVAC MODE SWITCHING (with relay control)
// ============================================================================
void setHVACMode(HVACMode newMode) {
    // Safety: never have both relays active simultaneously
    digitalWrite(RELAY_COOLING, HIGH);  // OFF
    digitalWrite(RELAY_HEATING, HIGH);  // OFF
    delay(100);  // 100ms dead time between switching

    currentMode = newMode;
    lastModeChange = millis();

    switch (newMode) {
        case MODE_COOLING:
            digitalWrite(RELAY_COOLING, LOW);  // ON (active-low)
            coolingActive = true;
            heatingActive = false;
            Serial.printf("[HVAC] ❄️  COOLING ON — T=%.1f°C (threshold=%.1f°C)\n",
                          temperature, config.cooling_threshold);
            break;

        case MODE_HEATING:
            digitalWrite(RELAY_HEATING, LOW);  // ON (active-low)
            coolingActive = false;
            heatingActive = true;
            Serial.printf("[HVAC] 🔥 HEATING ON — T=%.1f°C (threshold=%.1f°C)\n",
                          temperature, config.heating_threshold);
            break;

        case MODE_IDLE:
            coolingActive = false;
            heatingActive = false;
            Serial.printf("[HVAC] ⏸️  IDLE — T=%.1f°C (comfort zone)\n", temperature);
            break;
    }
}

// ============================================================================
// RUNTIME TRACKING
// ============================================================================
void trackRuntime(unsigned long now) {
    unsigned long elapsed = now - lastRuntimeCheck;
    lastRuntimeCheck = now;

    if (coolingActive) coolingRuntime += elapsed;
    if (heatingActive) heatingRuntime += elapsed;
}

// ============================================================================
// MQTT PUBLISHING
// ============================================================================
void publishSensorData() {
    StaticJsonDocument<256> doc;
    doc["temperature"] = round(temperature * 10) / 10.0;
    doc["humidity"]    = round(humidity * 10) / 10.0;
    doc["occupied"]    = isOccupied;
    doc["motion"]      = motionDetected;
    doc["valid"]       = sensorValid;

    char buffer[256];
    serializeJson(doc, buffer);
    mqtt.publish(TOPIC_SENSOR, buffer);
}

void publishHVACState() {
    StaticJsonDocument<384> doc;

    const char* modeStr;
    switch (currentMode) {
        case MODE_COOLING: modeStr = "cooling"; break;
        case MODE_HEATING: modeStr = "heating"; break;
        default:           modeStr = "idle";    break;
    }

    doc["mode"]           = modeStr;
    doc["cooling_active"] = coolingActive;
    doc["heating_active"] = heatingActive;
    doc["protection"]     = protectionActive;
    doc["temperature"]    = round(temperature * 10) / 10.0;
    doc["humidity"]       = round(humidity * 10) / 10.0;
    doc["occupied"]       = isOccupied;
    doc["cooling_runtime_min"] = coolingRuntime / 60000;
    doc["heating_runtime_min"] = heatingRuntime / 60000;
    doc["uptime_sec"]     = millis() / 1000;

    char buffer[384];
    serializeJson(doc, buffer);
    mqtt.publish(TOPIC_STATE, buffer);
}

// ============================================================================
// MQTT CALLBACK (receive commands)
// ============================================================================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
    char message[256];
    int len = min((int)length, 255);
    memcpy(message, payload, len);
    message[len] = '\0';

    Serial.printf("[MQTT] Received on %s: %s\n", topic, message);

    if (strcmp(topic, TOPIC_CONFIG) == 0) {
        // Update configuration
        StaticJsonDocument<256> doc;
        DeserializationError err = deserializeJson(doc, message);
        if (err) {
            Serial.printf("[MQTT] JSON parse error: %s\n", err.c_str());
            return;
        }

        if (doc.containsKey("cooling_threshold"))
            config.cooling_threshold = doc["cooling_threshold"].as<float>();
        if (doc.containsKey("heating_threshold"))
            config.heating_threshold = doc["heating_threshold"].as<float>();
        if (doc.containsKey("hysteresis"))
            config.hysteresis = doc["hysteresis"].as<float>();

        saveConfig();
        Serial.println("[CONFIG] Updated and saved to EEPROM");
    }
}

// ============================================================================
// WiFi SETUP
// ============================================================================
void setupWiFi() {
    Serial.printf("[WiFi] Connecting to %s", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\n[WiFi] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
    } else {
        Serial.println("\n[WiFi] Connection failed — running in offline mode");
    }
}

// ============================================================================
// MQTT RECONNECTION
// ============================================================================
void reconnectMQTT() {
    if (WiFi.status() != WL_CONNECTED) return;

    static unsigned long lastAttempt = 0;
    unsigned long now = millis();
    if (now - lastAttempt < 5000) return;  // Retry every 5 seconds
    lastAttempt = now;

    Serial.println("[MQTT] Connecting...");
    if (mqtt.connect(MQTT_CLIENT, MQTT_USER, MQTT_PASS)) {
        Serial.println("[MQTT] Connected");
        mqtt.subscribe(TOPIC_CONTROL);
        mqtt.subscribe(TOPIC_CONFIG);

        // Publish online status
        mqtt.publish(TOPIC_STATUS, "{\"status\":\"online\"}");
    } else {
        Serial.printf("[MQTT] Failed, rc=%d\n", mqtt.state());
    }
}

// ============================================================================
// OTA SETUP
// ============================================================================
void setupOTA() {
    ArduinoOTA.setHostname("hvac-controller");
    ArduinoOTA.onStart([]() {
        Serial.println("[OTA] Update starting...");
        // Safety: turn off all relays during OTA
        digitalWrite(RELAY_COOLING, HIGH);
        digitalWrite(RELAY_HEATING, HIGH);
    });
    ArduinoOTA.onEnd([]() {
        Serial.println("[OTA] Update complete!");
    });
    ArduinoOTA.onError([](ota_error_t error) {
        Serial.printf("[OTA] Error: %u\n", error);
    });
    ArduinoOTA.begin();
    Serial.println("[OK] OTA updates enabled");
}

// ============================================================================
// EEPROM CONFIG MANAGEMENT
// ============================================================================
void loadConfig() {
    EEPROM.get(0, config);

    // Validate checksum
    uint8_t calc = calculateChecksum();
    if (config.checksum != calc) {
        Serial.println("[CONFIG] Invalid EEPROM — loading defaults");
        loadDefaults();
        saveConfig();
    } else {
        Serial.println("[CONFIG] Loaded from EEPROM");
    }

    printConfig();
}

void saveConfig() {
    config.checksum = calculateChecksum();
    EEPROM.put(0, config);
    EEPROM.commit();
}

void loadDefaults() {
    config.cooling_threshold   = 26.0;
    config.heating_threshold   = 20.0;
    config.hysteresis          = 0.5;
    config.unoccupied_cooling  = 28.0;
    config.unoccupied_heating  = 18.0;
    config.humidity_override   = 70.0;
    config.min_cycle_time_sec  = 180;    // 3 minutes
    config.pir_timeout_sec     = 300;    // 5 minutes
}

uint8_t calculateChecksum() {
    uint8_t sum = 0;
    uint8_t* ptr = (uint8_t*)&config;
    for (size_t i = 0; i < sizeof(ControlConfig) - 1; i++) {
        sum ^= ptr[i];
    }
    return sum;
}

void printConfig() {
    Serial.println("\n  ┌─────────────────────────────────┐");
    Serial.println("  │      CONTROL CONFIGURATION      │");
    Serial.println("  ├─────────────────────────────────┤");
    Serial.printf( "  │ Cooling threshold: %6.1f °C    │\n", config.cooling_threshold);
    Serial.printf( "  │ Heating threshold: %6.1f °C    │\n", config.heating_threshold);
    Serial.printf( "  │ Hysteresis:        %6.1f °C    │\n", config.hysteresis);
    Serial.printf( "  │ Unocc. cooling:    %6.1f °C    │\n", config.unoccupied_cooling);
    Serial.printf( "  │ Unocc. heating:    %6.1f °C    │\n", config.unoccupied_heating);
    Serial.printf( "  │ Humidity override:  %5.1f %%     │\n", config.humidity_override);
    Serial.printf( "  │ Min cycle time:     %4d sec    │\n", config.min_cycle_time_sec);
    Serial.printf( "  │ PIR timeout:        %4d sec    │\n", config.pir_timeout_sec);
    Serial.println("  └─────────────────────────────────┘\n");
}

// ============================================================================
// STATUS LED INDICATION
// ============================================================================
void blinkStatus(unsigned long now) {
    unsigned long interval;

    if (!sensorValid)          interval = 100;   // Fast blink — sensor error
    else if (coolingActive)    interval = 500;   // Medium — cooling
    else if (heatingActive)    interval = 1000;  // Slow — heating
    else                       interval = 3000;  // Very slow — idle

    if (now - lastStatusBlink >= interval) {
        digitalWrite(LED_STATUS, !digitalRead(LED_STATUS));
        lastStatusBlink = now;
    }
}
