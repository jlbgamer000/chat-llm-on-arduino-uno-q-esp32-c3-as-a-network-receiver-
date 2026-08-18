import os
import socket
import subprocess
import threading
import time
import queue
import termios

GPIO_CHIP = "/dev/gpiochip1"
GPIO_LINE = "70"
_gpio_proc = None

def _gpio_hold_thread():
    global _gpio_proc
    while True:
        if _gpio_proc is None or _gpio_proc.poll() is not None:
            try:
                _gpio_proc = subprocess.Popen(
                    ["gpioset", "-c", GPIO_CHIP, f"{GPIO_LINE}=1"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                print(f"[BRIDGE] gpioset holding GPIO{GPIO_LINE} active", flush=True)
            except Exception as e:
                print(f"[BRIDGE] gpioset launch error: {e}", flush=True)
        time.sleep(2)

SERIAL_PORT = "/dev/ttyHS1"
PROXY_PORT = 18080

_fd = None
_write_lock = threading.Lock()
_tunnel_lock = threading.Lock()
_tunnel_inbound_queue = None

def _configure_serial(fd):
    iflag, oflag, cflag, lflag, ispeed, ospeed, cc = termios.tcgetattr(fd)
    iflag = oflag = lflag = 0
    cflag &= ~(termios.PARENB | termios.CSTOPB | termios.CSIZE)
    cflag |= termios.CS8 | termios.CREAD | termios.CLOCAL
    cc[termios.VMIN] = 0
    cc[termios.VTIME] = 0
    speed = termios.B115200
    termios.tcsetattr(fd, termios.TCSANOW, [iflag, oflag, cflag, lflag, speed, speed, cc])

def _open_serial():
    global _fd
    _fd = os.open(SERIAL_PORT, os.O_RDWR | os.O_NOCTTY)
    _configure_serial(_fd)
    termios.tcflush(_fd, termios.TCIOFLUSH)

def _send_tcp_chunk(data: bytes):
    with _write_lock:
        for i in range(0, len(data), 32):
            os.write(_fd, data[i:i+32])
            time.sleep(0.002)

def _reader_thread():
    while True:
        try:
            chunk = os.read(_fd, 4096)
            if chunk:
                if _tunnel_inbound_queue is not None:
                    _tunnel_inbound_queue.put(chunk)
            else:
                time.sleep(0.005)
        except Exception:
            time.sleep(0.1)

def _handle_client(client_socket):
    global _tunnel_inbound_queue
    try:
        req = client_socket.recv(4096)
        if not req:
            return
            
        first_line = req.split(b"\r\n")[0].decode("utf-8", errors="ignore")
        parts = first_line.split()
        if len(parts) < 2 or parts[0] != "CONNECT":
            return
        url = parts[1]

        print(f"[BRIDGE] Incoming CONNECT request for: {url}", flush=True)

        if not _tunnel_lock.acquire(blocking=True, timeout=10):
            print(f"[BRIDGE] Tunnel busy, rejected {url}", flush=True)
            return

        try:
            inbound_q = queue.Queue()
            _tunnel_inbound_queue = inbound_q

            _send_tcp_chunk(f"\nCONNECT {url}\n".encode("utf-8"))

            resp = b""
            connected = False
            deadline = time.time() + 10
            while time.time() < deadline:
                try:
                    resp += inbound_q.get(timeout=0.2)
                except queue.Empty:
                    continue
                if b"PROXY_OK" in resp:
                    connected = True
                    print(f"[BRIDGE] ESP32 confirmed connection to {url}", flush=True)
                    break
                if b"PROXY_FAIL" in resp:
                    print(f"[BRIDGE] ESP32 failed to connect to {url}", flush=True)
                    break

            if not connected:
                print(f"[BRIDGE] Timeout waiting for ESP32 PROXY_OK on {url}", flush=True)
                return

            client_socket.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            stop_event = threading.Event()

            def socket_to_serial():
                try:
                    while not stop_event.is_set():
                        data = client_socket.recv(4096)
                        if not data:
                            break
                        print(f"[BRIDGE] [TX] App -> ESP32: {len(data)} bytes", flush=True)
                        _send_tcp_chunk(data)
                except Exception as e:
                    print(f"[BRIDGE] socket_to_serial error: {e}", flush=True)
                finally:
                    stop_event.set()

            def serial_to_socket():
                try:
                    while not stop_event.is_set():
                        try:
                            data = inbound_q.get(timeout=0.2)
                        except queue.Empty:
                            continue
                        print(f"[BRIDGE] [RX] ESP32 -> App: {len(data)} bytes", flush=True)
                        client_socket.sendall(data)
                except Exception as e:
                    print(f"[BRIDGE] serial_to_socket error: {e}", flush=True)
                finally:
                    stop_event.set()

            t1 = threading.Thread(target=socket_to_serial, daemon=True)
            t2 = threading.Thread(target=serial_to_socket, daemon=True)
            t1.start()
            t2.start()

            while not stop_event.is_set():
                time.sleep(0.05)

            print(f"[BRIDGE] Closed tunnel for: {url}", flush=True)

            # Signal the ESP32 to drop the socket and prepare for subsequent requests
            with _write_lock:
                time.sleep(0.05)
                os.write(_fd, b"+++CLOSE_TCP")
                time.sleep(0.05)

        finally:
            _tunnel_inbound_queue = None
            _tunnel_lock.release()

    except Exception as e:
        print(f"[BRIDGE] Proxy error: {e}", flush=True)
    finally:
        client_socket.close()

def _proxy_server_thread():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", PROXY_PORT))
    server.listen(5)
    print(f"[BRIDGE] HTTP(S) proxy listening on 0.0.0.0:{PROXY_PORT}", flush=True)
    while True:
        client_sock, _ = server.accept()
        threading.Thread(target=_handle_client, args=(client_sock,), daemon=True).start()

def main():
    threading.Thread(target=_gpio_hold_thread, daemon=True).start()
    time.sleep(1.0)
    _open_serial()
    threading.Thread(target=_reader_thread, daemon=True).start()
    threading.Thread(target=_proxy_server_thread, daemon=True).start()
    print("[BRIDGE] Raw fridge proxy running.", flush=True)
    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()