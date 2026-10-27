// Genius Coil Detector - ESP32 pulse-induction metal detector that talks to the Genius app.
// Made by Ssali Muto. Hobby build: test it and tune it yourself. Untested reference design.
//
// What Genius expects: Wi-Fi "Genius-Detector" (password genius123), and a JSON reading at
// http://192.168.4.1/data like {"v": 1234.5, "base": 1200.0}. Metal changes "v".
//
// Parts (roughly 40,000 to 70,000 UGX in Kampala electronics shops):
//  - ESP32 DevKit board
//  - IRF740 (or IRFZ44N) N-channel MOSFET, 100 ohm gate resistor, 10k gate pull-down
//  - Search coil: about 25 turns of 0.5 mm enamel copper wire on a 20 cm round form (about 300 uH)
//  - 1N4007 diode + 390 ohm damping resistor across the coil (tune 220 to 470 ohm)
//  - LM358 op-amp as a x100 amplifier, two 1N4148 clamp diodes at its input
//  - 9 to 12 V battery for the coil, 5 V (power bank) for the ESP32, common ground
//
// MINI PINPOINTER (pen size): uncomment the next line and use an ESP32-C3 SuperMini,
// AO3400 MOSFET, 3.7 V LiPo + TP4056, coil of 100 turns 0.2 mm wire on a 15 mm tube, buzzer on GPIO3.
// #define GENIUS_MINI
//
// Wiring (big detector): GPIO25 -> 100R -> MOSFET gate. Coil between +12V and MOSFET drain.
//         Coil/drain node -> 1k -> clamp diodes -> LM358 input. LM358 output -> GPIO34 (keep it under 3.3 V).

#include <WiFi.h>
#include <WebServer.h>

#ifdef GENIUS_MINI
const int PULSE_PIN = 5;     // drives the MOSFET
const int SENSE_PIN = 1;     // amplified decay signal (ADC1)
const int BUZZ_PIN  = 3;     // little buzzer, beeps on its own too
const int PULSE_US  = 40;
#else
const int PULSE_PIN = 25;    // drives the MOSFET
const int SENSE_PIN = 34;    // amplified decay signal (ADC)
const int BUZZ_PIN  = -1;
const int PULSE_US  = 60;    // how long the coil is charged
#endif
const int LATE_US   = 40;    // second, later sample: tells fast (gold, thin) from slow (iron, big) targets
const int DELAY_US  = 12;    // wait after the pulse before reading (tune 8 to 30)
const int SAMPLES   = 32;    // pulses averaged per reading

WebServer server(80);
float baseVal = 0, val = 0, lateBase = 0, lateVal = 0;
unsigned long lastBeep = 0;

float pulseRead(int waitUs) {
  digitalWrite(PULSE_PIN, HIGH);
  delayMicroseconds(PULSE_US);
  digitalWrite(PULSE_PIN, LOW);
  delayMicroseconds(waitUs);
  return analogRead(SENSE_PIN);
}

void handleData() {
  String j = "{\"v\":" + String(val, 1) + ",\"base\":" + String(baseVal, 1) +
             ",\"late\":" + String(lateVal, 1) + ",\"lbase\":" + String(lateBase, 1) + "}";
  server.sendHeader("Cache-Control", "no-store");
  server.send(200, "application/json", j);
}

void setup() {
  pinMode(PULSE_PIN, OUTPUT);
  digitalWrite(PULSE_PIN, LOW);
  analogSetAttenuation(ADC_11db);
  if (BUZZ_PIN >= 0) { pinMode(BUZZ_PIN, OUTPUT); digitalWrite(BUZZ_PIN, LOW); }
  WiFi.softAP("Genius-Detector", "genius123");   // the phone joins this Wi-Fi
  server.on("/data", handleData);
  server.begin();
  long s = 0, sl = 0;
  for (int i = 0; i < 200; i++) { s += pulseRead(DELAY_US); delay(1); sl += pulseRead(LATE_US); delay(1); }
  baseVal = s / 200.0;      // keep the coil away from metal while it starts
  lateBase = sl / 200.0;
  val = baseVal; lateVal = lateBase;
}

void loop() {
  long s = 0, sl = 0;
  for (int i = 0; i < SAMPLES; i++) {
    s += pulseRead(DELAY_US); delayMicroseconds(700);
    sl += pulseRead(LATE_US); delayMicroseconds(700);
  }
  val = 0.7 * val + 0.3 * (s / (float)SAMPLES);
  lateVal = 0.7 * lateVal + 0.3 * (sl / (float)SAMPLES);
  if (BUZZ_PIN >= 0) {                       // beep faster as the signal grows
    float d = fabs(val - baseVal);
    unsigned long gap = d < 6 ? 0 : (d < 20 ? 500 : (d < 60 ? 220 : 80));
    if (gap && millis() - lastBeep > gap) { lastBeep = millis(); digitalWrite(BUZZ_PIN, HIGH); delay(15); digitalWrite(BUZZ_PIN, LOW); }
  }
  server.handleClient();
}
