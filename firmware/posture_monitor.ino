/*
 * ============================================================
 * Smart Posture Correction System — ESP32-C3 Firmware
 * ============================================================
 * Hardware: Seeed XIAO ESP32-C3
 * Sensors : Flex Sensor (GPIO 2), FSR 402 (GPIO 3), MPU6050 IMU (I2C)
 * Output  : Vibration Motor via LEDC PWM (GPIO 21)
 * Protocol: WiFi UDP listener — receives '1' (bad) / '0' (good)
 *           from Python computer vision host
 *
 * Industry Award Winner — 9th EE Capstone Showcase (EECS 2026)
 * Universiti Teknologi Malaysia
 * ============================================================
 */

#include <Wire.h>
#include <MPU6050.h>
#include <math.h>
#include <WiFi.h>
#include <WiFiUdp.h>

MPU6050 mpu;

// ===============================
// WIFI SETTINGS  ← Fill these in
// ===============================
const char* STASSID = "YOUR_WIFI_NAME";     // <--- ENTER YOUR WIFI SSID
const char* STAPSK  = "YOUR_WIFI_PASSWORD"; // <--- ENTER YOUR WIFI PASSWORD
unsigned int localPort = 4210;              // UDP port (must match Python script)

WiFiUDP udp;
char packetBuffer[255];

// ===============================
// PIN DEFINITIONS (XIAO ESP32-C3)
// ===============================
const int FLEX_PIN  = 2;   // ADC1 — Safe with WiFi active
const int FSR_PIN   = 3;   // ADC1 — Safe with WiFi active
const int MOTOR_PIN = 21;  // D10 — Vibration motor (via S8050 BJT driver)
const int SDA_PIN   = 6;   // D4
const int SCL_PIN   = 7;   // D5

// ===============================
// TUNING PARAMETERS
// ===============================
const int   FSR_THRESHOLD  = 300;   // Min ADC reading = wearable is worn
const int   FLEX_BAD       = 2300;  // Flex sensor threshold for slouch detection
const int   HYSTERESIS     = 50;    // Debounce band around FLEX_BAD
const float IMU_TOLERANCE  = 15.0;  // Max allowable tilt deviation (degrees)
const int   MOTOR_MAX_PWM  = 200;   // Max vibration intensity (0-255)

// ===============================
// VARIABLES
// ===============================
const int FLEX_SAMPLES = 20;
int flexBuf[FLEX_SAMPLES];
int flexIndex = 0;

float uprightAngle  = 0;
bool  isSystemActive = false;
bool  calibrating    = false;

unsigned long lastRead       = 0;
unsigned long fsrTriggerTime = 0;
unsigned long removalTimer   = 0;

// Webcam / computer vision state
bool  webcamBad      = false;
unsigned long lastWebcamCmd = 0;

// ============================================================
// SETUP
// ============================================================
void setup() {
  Serial.begin(115200);

  // Hardware init
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);
  pinMode(FLEX_PIN, INPUT);
  pinMode(FSR_PIN,  INPUT);
  ledcAttach(MOTOR_PIN, 200, 8);   // 200 Hz PWM, 8-bit resolution
  Wire.begin(SDA_PIN, SCL_PIN);
  mpu.initialize();

  // Flex buffer init
  int initVal = analogRead(FLEX_PIN);
  for (int i = 0; i < FLEX_SAMPLES; i++) flexBuf[i] = initVal;

  // WiFi connect
  Serial.print("Connecting to WiFi");
  WiFi.begin(STASSID, STAPSK);
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(500);
  }
  Serial.println("\nWiFi connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP()); // <--- Copy this IP into the Python script

  // Start UDP listener
  udp.begin(localPort);
  Serial.println("--- System Ready. Waiting for wearable... ---");
}

// ============================================================
// HELPERS
// ============================================================

// 20-sample moving average for flex sensor (reduces noise)
int readFlexSmooth() {
  flexBuf[flexIndex] = analogRead(FLEX_PIN);
  flexIndex = (flexIndex + 1) % FLEX_SAMPLES;
  long sum = 0;
  for (int i = 0; i < FLEX_SAMPLES; i++) sum += flexBuf[i];
  return sum / FLEX_SAMPLES;
}

// Returns absolute tilt angle from MPU6050 accelerometer
float readBackAngle() {
  int16_t ax, ay, az;
  mpu.getAcceleration(&ax, &ay, &az);
  float angle = atan2(ax, az) * 180.0 / M_PI;
  return abs(angle);
}

// ============================================================
// MAIN LOOP
// ============================================================
void loop() {
  unsigned long now = millis();

  // ── 1. READ UDP FROM PYTHON COMPUTER VISION HOST ─────────
  int packetSize = udp.parsePacket();
  if (packetSize) {
    int len = udp.read(packetBuffer, 255);
    if (len > 0) packetBuffer[len] = 0;
    char cmd = packetBuffer[0];
    if (cmd == '1') {
      webcamBad    = true;
      lastWebcamCmd = now;
    } else {
      webcamBad = false;
    }
  }
  // Safety timeout: if Python host stops sending, clear bad flag after 2s
  if (webcamBad && (now - lastWebcamCmd > 2000)) webcamBad = false;

  // ── 2. FSR DEBOUNCE (prevents false removal on brief shifts) ─
  int fsrValue = analogRead(FSR_PIN);
  if (fsrValue < FSR_THRESHOLD) {
    if (removalTimer == 0) removalTimer = now;
    if (now - removalTimer > 2000) {
      if (isSystemActive) {
        Serial.println(">> Device Removed. Resetting...");
        isSystemActive = false;
        ledcWrite(MOTOR_PIN, 0);
      }
      removalTimer = 0;
      return;
    }
  } else {
    removalTimer = 0;
  }

  // ── 3. CALIBRATION STATE ─────────────────────────────────
  // On first sit-down: 3-second settle → record upright angle
  if (fsrValue >= FSR_THRESHOLD && !isSystemActive) {
    if (!calibrating) {
      Serial.println(">> Pressure detected. Calibrating...");
      calibrating    = true;
      fsrTriggerTime = now;
      ledcWrite(MOTOR_PIN, 150); delay(100); ledcWrite(MOTOR_PIN, 0); // Feedback buzz
    }
    if (now - fsrTriggerTime > 3000) {
      uprightAngle   = readBackAngle();
      isSystemActive = true;
      calibrating    = false;
      Serial.print(">> CALIBRATED. ESP32 IP: ");
      Serial.println(WiFi.localIP());
      ledcWrite(MOTOR_PIN, 200); delay(400); ledcWrite(MOTOR_PIN, 0); // Ready buzz
    }
    return;
  }

  // ── 4. ACTIVE POSTURE MONITORING (50 ms loop) ─────────────
  if (isSystemActive && (now - lastRead >= 50)) {
    lastRead = now;

    int   flexValue  = readFlexSmooth();
    float angleDiff  = abs(readBackAngle() - uprightAngle);

    // Hardware trigger: BOTH flex AND IMU must exceed thresholds
    bool hardwareBad = (flexValue < (FLEX_BAD - HYSTERESIS)) && (angleDiff > IMU_TOLERANCE);

    // ── 5. MERGED TRIGGER: hardware sensors OR computer vision ──
    int motorPWM = 0;
    if (hardwareBad || webcamBad) {
      // Variable intensity based on how far flex has deviated
      motorPWM = hardwareBad
        ? map(flexValue, FLEX_BAD, 1500, 100, MOTOR_MAX_PWM)
        : 150; // Webcam-only detection: fixed medium buzz
      motorPWM = constrain(motorPWM, 0, MOTOR_MAX_PWM);
    }

    ledcWrite(MOTOR_PIN, motorPWM);

    // Debug print every ~1 s
    static unsigned long lastPrint = 0;
    if (now - lastPrint > 1000) {
      lastPrint = now;
      Serial.print("HW_BAD:"); Serial.print(hardwareBad);
      Serial.print(" | WC_BAD:"); Serial.print(webcamBad);
      Serial.print(" | Flex:"); Serial.print(flexValue);
      Serial.print(" | Tilt:"); Serial.println(angleDiff, 1);
    }
  }
}
