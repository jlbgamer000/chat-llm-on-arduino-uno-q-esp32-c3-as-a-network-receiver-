#include <WiFi.h>

const char* ssid     = "vivo X200";
const char* password = "vivox2001234";

WiFiClient client;
uint8_t buf[256];

void setup() {
  Serial.begin(115200);
  // ESP32-C3 UART pins: RX = GPIO 7, TX = GPIO 6
  Serial1.begin(115200, SERIAL_8N1, 7, 6);
  Serial1.setRxBufferSize(4096);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(200);
  }
}

void loop() {
  if (Serial1.available()) {
    String cmd = Serial1.readStringUntil('\n');
    cmd.trim();

    if (cmd.startsWith("CONNECT ")) {
      String target = cmd.substring(8);
      int colonIdx = target.indexOf(':');
      if (colonIdx > 0) {
        String host = target.substring(0, colonIdx);
        int port = target.substring(colonIdx + 1).toInt();

        client.stop();
        if (client.connect(host.c_str(), port)) {
          client.setNoDelay(true);
          Serial1.print("PROXY_OK\n");

          while (client.connected() || client.available() || Serial1.available()) {
            // Forward from Google -> UNO Q (Paced in 32-byte chunks)
            int len = client.available();
            if (len > 0) {
              if (len > 32) len = 32;
              int r = client.read(buf, len);
              if (r > 0) {
                Serial1.write(buf, r);
                Serial1.flush();
                delay(2);
              }
            }

            // Forward from UNO Q -> Google
            int s_len = Serial1.available();
            if (s_len > 0) {
              if (s_len > sizeof(buf) - 1) s_len = sizeof(buf) - 1;
              int r = Serial1.readBytes(buf, s_len);
              if (r > 0) {
                // Intercept the Hang Up signal to close keep-alive TCP connections
                char temp[256];
                memcpy(temp, buf, r);
                temp[r] = '\0';
                if (strstr(temp, "+++CLOSE_TCP") != NULL) {
                  break;
                }
                client.write(buf, r);
              }
            }
            yield();
          }
          client.stop();
        } else {
          Serial1.print("PROXY_FAIL\n");
        }
      }
    }
  }
}