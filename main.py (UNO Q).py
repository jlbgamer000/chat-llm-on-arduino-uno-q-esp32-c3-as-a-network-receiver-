import os
import socket
import struct

# ============================================================
# 1. Dynamic Proxy Setup (Routes out through the host bridge)
# ============================================================
def get_docker_gateway():
    try:
        with open("/proc/net/route") as f:
            for line in f:
                fields = line.strip().split()
                if fields[1] == '00000000':
                    return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
    except Exception:
        pass
    return "172.18.0.1"

HOST_ADDR = get_docker_gateway()
PROXY_PORT = 18080

os.environ["http_proxy"] = f"http://{HOST_ADDR}:{PROXY_PORT}"
os.environ["https_proxy"] = f"http://{HOST_ADDR}:{PROXY_PORT}"
os.environ["HTTP_PROXY"] = f"http://{HOST_ADDR}:{PROXY_PORT}"
os.environ["HTTPS_PROXY"] = f"http://{HOST_ADDR}:{PROXY_PORT}"
os.environ["no_proxy"] = "localhost,127.0.0.1,0.0.0.0"

# ============================================================
# 2. App Lab LLM Setup
# ============================================================
from arduino.app_bricks.cloud_llm import CloudLLM
from arduino.app_bricks.web_ui import WebUI
from arduino.app_utils import App

def load_system_prompt():
    try:
        with open(os.path.join(os.path.dirname(__file__), "system_prompt.txt"), "r") as f:
            system_prompt = f.read()
    except Exception:
        system_prompt = "You are a generic AI Chatbot Assistant."
    return system_prompt

def extract_text(chunk):
    """Parses text out of structured JSON returned by Gemini models."""
    if isinstance(chunk, str):
        return chunk
    if isinstance(chunk, list):
        text = ""
        for item in chunk:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text += item.get("text", "")
            elif isinstance(item, str):
                text += item
        return text
    if isinstance(chunk, dict):
        if chunk.get("type") == "text":
            return chunk.get("text", "")
    return ""

def generate_prompt(_, data):
    try:
        prompt = data.get('prompt', '')
        for resp in llm.chat_stream(prompt):
            text = extract_text(resp)
            if text:
                ui.send_message("response", text)
        
        ui.send_message("stream_end", {})
    except Exception as e:
        print("ERROR:", repr(e), flush=True)
        ui.send_message("llm_error", {"error": str(e)})

def commands_handler(_, data):
    command = data.get('command', '')
    try:
        if command == "clear_chat":   
            llm.stop_stream()
            llm.clear_memory()
            ui.send_message("command_ok", {"command": command})
        elif command == "stop_stream":
            llm.stop_stream()
            ui.send_message("command_ok", {"command": command})
        else:
            ui.send_message("command_error", {"command": command, "error": "Unknown command"})
    except Exception as e:
        ui.send_message("command_error", {"command": command, "error": str(e)})

# ============================================================
# 3. Model Initialization
# ============================================================
llm = CloudLLM(
    model="google:gemini-3.6-flash",
    system_prompt=load_system_prompt()
)
# Note: llm.with_memory() is disabled to prevent library-level list/str crashes

ui = WebUI()
ui.on_message("prompt", generate_prompt)
ui.on_message("commands", commands_handler)

App.run()