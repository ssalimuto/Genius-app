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
// Wiring: GPIO25 -> 100R -> MOSFET gate. Coil between +12V and MOSFET drain.
//         Coil/drain node -> 1k -> clamp diodes -> LM358 input. LM358 output -> GPIO34 (keep it under 3.3 V).

#include <WiFi.h>
#include <WebServer.h>

const int PULSE_PIN = 25;    // drives the MOSFET
const int SENSE_PIN = 34;    // amplified decay signal (ADC)
const int PULSE_US  = 60;    // how long the coil is charged
const int DELAY_US  = 12;    // wait after the pulse before reading (tune 8 to 30)
const int SAMPLES   = 32;    // pulses averaged per reading

WebServer server(80);
float baseVal = 0, val = 0;

float pulseRead() {
  digitalWrite(PULSE_PIN, HIGH);
  delayMicroseconds(PULSE_US);
  digitalWrite(PULSE_PIN, LOW);
  delayMicroseconds(DELAY_US);
  return analogRead(SENSE_PIN);
}

void handleData() {
  String j = "{\"v\":" + String(val, 1) + ",\"base\":" + String(baseVal, 1) + "}";
  server.sendHeader("Cache-Control", "no-store");
  server.send(200, "application/json", j);
}

void setup() {
  pinMode(PULSE_PIN, OUTPUT);
  digitalWrite(PULSE_PIN, LOW);
  analogSetAttenuation(ADC_11db);
  WiFi.softAP("Genius-Detector", "genius123");   // the phone joins this Wi-Fi
  server.on("/data", handleData);
  server.begin();
  long s = 0;
  for (int i = 0; i < 200; i++) { s += pulseRead(); delay(2); }
  baseVal = s / 200.0;      // keep the coil away from metal while it starts
  val = baseVal;
}

void loop() {
  long s = 0;
  for (int i = 0; i < SAMPLES; i++) { s += pulseRead(); delayMicroseconds(1500); }
  val = 0.7 * val + 0.3 * (s / (float)SAMPLES);
  server.handleClient();
}
