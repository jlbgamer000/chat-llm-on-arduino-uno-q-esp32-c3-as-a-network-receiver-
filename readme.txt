Arduino UNO Q — ESP32-C3 Wi-Fi Serial Bridge & Cloud LLM

A high-reliability, low-overhead hardware and software bridge architecture that restores full cloud networking (HTTPS/TLS) to an Arduino UNO Q with a non-functional onboard Wi-Fi chip using an external ESP32-C3 Super Mini coprocessor.

1. System Architecture

The UNO Q combines an STM32 microcontroller (real-time hardware side) and a Linux SoC (running Debian and containerized App Lab applications). Because Docker containers in App Lab cannot directly access host devices like /dev/ttyHS1 or GPIO chips, the system routes traffic across an integrated multi-layer pipeline:

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ [Internet / Google Gemini API]                                                          │
└────────────────────────────────────────▲────────────────────────────────────────────────┘
                                         │ Wi-Fi (TCP/TLS)
┌────────────────────────────────────────▼────────────────────────────────────────────────┐
│ [ESP32-C3 Coprocessor] (esp32_wifi_bridge.ino)                                          │
│ - Connects to local Wi-Fi                                                               │
│ - Translates incoming CONNECT host:port into outbound TCP sockets                       │
│ - Paces inbound data in 32-byte chunks with 2ms delays to protect STM32 buffers         │
│ - Listens for '+++CLOSE_TCP' hang-up signal to tear down Keep-Alive connections         │
└────────────────────────────────────────▲────────────────────────────────────────────────┘
                                         │ Hardware UART (115200 baud, D0/D1 pins)
┌────────────────────────────────────────▼────────────────────────────────────────────────┐
│ [STM32 MCU] (sketch/sketch.ino)                                                         │
│ - Transparent bidirectional byte passthrough: Serial1 (D0/D1) <-> Serial2 (/dev/ttyHS1)│
└────────────────────────────────────────▲────────────────────────────────────────────────┘
                                         │ Level-Shifter Circuit (Locked HIGH by GPIO 70)
                                         │ Internal Linux Serial Bus (/dev/ttyHS1)
┌────────────────────────────────────────▼────────────────────────────────────────────────┐
│ [Linux Host Daemon] (fridge_bridge_daemon.py via systemd: fridge-bridge.service)        │
│ - Holds GPIO 70 active via persistent background subprocess                             │
│ - Locks /dev/ttyHS1 termios configuration (115200 baud, raw mode)                       │
│ - Exposes an HTTP CONNECT proxy server bound to 0.0.0.0:18080                           │
│ - Paces outbound client payload in 32-byte chunks                                       │
│ - Emits '+++CLOSE_TCP' after client disconnection                                       │
└────────────────────────────────────────▲────────────────────────────────────────────────┘
                                         │ Local Docker Virtual Network Gateway (e.g. 172.18.0.1:18080)
┌────────────────────────────────────────▼────────────────────────────────────────────────┐
│ [App Lab Container / Python App] (main.py + WebUI)                                      │
│ - Dynamically discovers container gateway IP via /proc/net/route                        │
│ - Routes HTTPS traffic through http_proxy / https_proxy environment variables           │
│ - Runs Google Gemini 3.6 Flash using CloudLLM Brick                                     │
│ - Extracts raw text from structured JSON payloads                                       │
│ - Serves browser-based Chat UI on port 7000                                             │
└─────────────────────────────────────────────────────────────────────────────────────────┘

2. Hardware Wiring

ESP32-C3 Super Mini Pin    Arduino UNO Q Pin    Description
GPIO 6 (TX)                D0 (RX)              Serial transmission from ESP32 to UNO Q
GPIO 7 (RX)                D1 (TX)              Serial transmission from UNO Q to ESP32
GND                        GND                  Common ground reference
5V / VBUS                  5V / USB             Board power supply

3. Key Problems & Engineering Solutions

1. Docker Hardware Isolation
   Issue: App Lab apps run inside a container that cannot touch /dev/ttyHS1 or GPIO lines.
   Fix: A dedicated Python host daemon runs directly on Debian via systemd, managing the serial port and level shifter while exposing an internal HTTP CONNECT proxy at 18080.

2. Microcontroller Serial Buffer Overflows
   Issue: The STM32 hardware UART buffer is limited to 64 bytes without hardware flow control. Blasting large payloads (like the ~5.5 KB Google TLS Certificate Chain) resulted in dropped bytes and corrupted SSL handshakes (Server disconnected without sending a response).
   Fix: Symmetrical 32-byte throttling with a 2 ms delay was introduced on both the Linux daemon (_send_tcp_chunk) and ESP32 firmware (client.read(buf, 32)).

3. HTTP Keep-Alive Deadlock
   Issue: Google servers keep TLS connections open for pipelining. After the first prompt completed, the ESP32 stayed trapped in its forwarding loop. Subsequent CONNECT commands were treated as raw payload data and ignored.
   Fix: A sentinel protocol (+++CLOSE_TCP) was implemented. When the App Lab client finishes its request and closes the local socket, the Linux daemon sends +++CLOSE_TCP across the UART, commanding the ESP32 to immediately terminate the remote TCP connection.

4. SSL Clock Desynchronization
   Issue: Without active NTP on boot, the UNO Q clock reset to an older date, triggering [SSL: CERTIFICATE_VERIFY_FAILED] certificate is not yet valid.
   Fix: Manual or network-based system date synchronization (sudo date -s "...") ensures local time falls within the validity window of Google's root certificates.

5. App Lab LLM Model Deprecation & Memory Parsing Bug
   Issue: Default CloudModel.GOOGLE_GEMINI requested the deprecated gemini-2.5-flash model (404 error). When upgraded to google:gemini-3.6-flash, the API returned structured JSON lists instead of plain strings, causing an internal sequence item 0: expected str instance, list found crash in the closed-source with_memory() aggregator.
   Fix: Explicitly configured model="google:gemini-3.6-flash", disabled with_memory(), and built a custom extract_text() recursive parser in main.py.