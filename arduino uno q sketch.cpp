void setup() {
  // Serial1 bridges to external D0/D1 pins (ESP32)
  Serial1.begin(115200);
  // Serial2 bridges to internal Linux /dev/ttyHS1
  Serial2.begin(115200);
}

void loop() {
  while (Serial1.available()) {
    Serial2.write(Serial1.read());
  }
  while (Serial2.available()) {
    Serial1.write(Serial2.read());
  }
}