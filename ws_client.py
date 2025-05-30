import asyncio
import websockets
import socket
import json
import subprocess
import re
import sys
import os
import time


def load_ws_token():
    token_file = ".wstoken"
    if os.path.exists(token_file):
        with open(token_file, "r") as f:
            return f.read().strip()
    return os.environ.get("WS_TOKEN", "my_secret_token")


WS_TOKEN = load_ws_token()


def get_listening_ports():
    # Detect the operating system and use the appropriate command
    ports = set()
    try:
        if sys.platform.startswith("win"):
            # Windows: use netstat -ano
            output = subprocess.check_output(
                ["netstat", "-ano"], text=True, encoding="utf-8", errors="ignore")
            for line in output.splitlines():
                if "LISTENING" in line:
                    match = re.search(r':(\d+)', line)
                    if match:
                        ports.add(int(match.group(1)))
        else:
            # Linux/Unix: use ss -tuln
            output = subprocess.check_output(["ss", "-tuln"], text=True)
            for line in output.splitlines():
                if re.search(r'LISTEN', line):
                    match = re.search(r':(\d+)', line)
                    if match:
                        ports.add(int(match.group(1)))
        return list(ports)
    except Exception:
        return []


def get_listening_ports_with_proto():
    """
    Returns a list of tuples (port, protocol) for listening ports.
    Protocol is 'tcp' or 'udp'.
    """
    ports = set()
    try:
        if sys.platform.startswith("win"):
            # Windows: use netstat -ano
            output = subprocess.check_output(
                ["netstat", "-ano"], text=True, encoding="utf-8", errors="ignore")
            for line in output.splitlines():
                if "LISTENING" in line:
                    match = re.search(r':(\d+)', line)
                    if match:
                        ports.add((int(match.group(1)), "tcp"))
            # UDP not handled on Windows in this example
        else:
            # Linux/Unix: use ss -tuln and ss -uln
            output_tcp = subprocess.check_output(["ss", "-tnl"], text=True)
            output_udp = subprocess.check_output(["ss", "-unl"], text=True)
            for line in output_tcp.splitlines():
                if re.search(r'LISTEN', line):
                    match = re.search(r':(\d+)', line)
                    if match:
                        ports.add((int(match.group(1)), "tcp"))
            for line in output_udp.splitlines():
                match = re.search(r':(\d+)', line)
                if match:
                    ports.add((int(match.group(1)), "udp"))
        return list(ports)
    except Exception:
        return []


def get_local_ip():
    # Get the main local IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def get_ws_uri():
    uri = os.environ.get("WS_URI")
    if uri:
        return uri
    # Fallback to interactive only if run manually
    return input("Enter WebSocket server URI (e.g. ws://1.2.3.4:8765): ")


def expand_ports(line):
    """Converts a line like '80,443,1000:1005' into a set of integers."""
    ports = set()
    import re
    parts = re.split(r'[,\n]+', line)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if ':' in part:
            ini, fin = part.split(':')
            ports.update(range(int(ini), int(fin) + 1))
        else:
            ports.add(int(part))
    return ports


def load_ports(path):
    if not os.path.exists(path):
        return set()
    with open(path, 'r') as f:
        content = f.read()
    return expand_ports(content)


async def main():
    uri = get_ws_uri()
    local_ip = get_local_ip()
    hostname = socket.gethostname()
    sent_ports = set()
    # Load allowed ports from ports.txt
    allowed_ports = load_ports("ports.txt")
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                while True:
                    # Get (port, protocol) tuples
                    port_proto_list = get_listening_ports_with_proto()
                    # Filter only allowed ports
                    filtered = [(p, proto) for (p, proto) in port_proto_list if p in allowed_ports]
                    new_ports = [item for item in filtered if item not in sent_ports]
                    for port, proto in new_ports:
                        data = {
                            "ip": local_ip,
                            "puerto": port,
                            "token": WS_TOKEN,
                            "protocolo": proto,
                            "hostname": hostname,
                            "timestamp": int(time.time())
                        }
                        await websocket.send(json.dumps(data))
                        resp = await websocket.recv()
                        print(f"Sent {data}, received: {resp}")
                    sent_ports |= set(new_ports)
                    # Wait 10 seconds before scanning again
                    await asyncio.sleep(10)
        except Exception as e:
            print(
                f"WebSocket connection error: {e}. Retrying in 10 seconds...")
            await asyncio.sleep(10)

if __name__ == "__main__":
    if os.environ.get("RUN_FROM_PANEL") != "1":
        print("This script must be run from Control_Panel.py")
        sys.exit(1)
    asyncio.run(main())
