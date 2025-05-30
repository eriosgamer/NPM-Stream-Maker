import asyncio
import websockets
import json
import sqlite3
import subprocess
import os
import ipaddress
import platform

SQLITE_DB_PATH = os.path.join("data", "database.sqlite")

def load_ws_token():
    token_file = ".wstoken"
    if os.path.exists(token_file):
        with open(token_file, "r") as f:
            return f.read().strip()
    return os.environ.get("WS_TOKEN", "my_secret_token")

WS_TOKEN = load_ws_token()

def get_local_wg_ip(interface="wg0"):
    """
    Get the local WireGuard interface IP address (e.g., 10.10.0.1).
    """
    try:
        import socket
        import fcntl
        import struct
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', interface[:15].encode('utf-8'))
        )[20:24])
    except Exception:
        # Fallback: parse `ip addr show wg0`
        try:
            output = subprocess.check_output(["ip", "addr", "show", interface], text=True)
            for line in output.splitlines():
                line = line.strip()
                if line.startswith("inet "):
                    ip = line.split()[1].split('/')[0]
                    return ip
        except Exception:
            pass
    return None

def get_peer_ip_for_client(_):
    """
    On a WireGuard server, scan the WG subnet and return the first client IP that responds to ping.
    """
    try:
        wg_interface = "wg0"
        local_ip = get_local_wg_ip(wg_interface)
        if not local_ip:
            return None
        # Get subnet from `ip addr show wg0`
        output = subprocess.check_output(["ip", "addr", "show", wg_interface], text=True)
        subnet = None
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                subnet = line.split()[1]
                break
        if not subnet:
            return None
        net = ipaddress.ip_network(subnet, strict=False)
        # Exclude server's own IP
        candidates = [str(ip) for ip in net.hosts() if str(ip) != local_ip]
        # Ping each candidate, return the first that responds
        param = "-n" if platform.system().lower() == "windows" else "-c"
        for ip in candidates:
            try:
                result = subprocess.run(
                    ["ping", param, "1", "-W", "1", ip],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                if result.returncode == 0:
                    return ip
            except Exception:
                continue
    except Exception:
        pass
    return None

def update_stream_forwarding_ip(port, new_ip):
    if not os.path.exists(SQLITE_DB_PATH):
        return False
    conn = sqlite3.connect(SQLITE_DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("UPDATE stream SET forwarding_host=? WHERE incoming_port=?", (new_ip, port))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()

async def handler(websocket, path):
    async for message in websocket:
        try:
            data = json.loads(message)
            token = data.get("token")
            if token != WS_TOKEN:
                await websocket.send(json.dumps({"status": "error", "msg": "Invalid token"}))
                continue
            ip = data.get("ip")
            port = data.get("puerto")
            if not ip or not port:
                await websocket.send(json.dumps({"status": "error", "msg": "Missing ip or puerto"}))
                continue
            # Check if the received IP belongs to any WireGuard peer
            wg_peer_ip = get_peer_ip_for_client(ip)
            final_ip = wg_peer_ip if wg_peer_ip else ip
            updated = update_stream_forwarding_ip(port, final_ip)
            if updated:
                await websocket.send(json.dumps({"status": "ok", "msg": f"Port {port} updated to {final_ip}"}))
            else:
                await websocket.send(json.dumps({"status": "error", "msg": f"Port {port} not found"}))
        except Exception as e:
            await websocket.send(json.dumps({"status": "error", "msg": str(e)}))

if __name__ == "__main__":
    if os.environ.get("RUN_FROM_PANEL") != "1":
        print("This script must be run from Control_Panel.py")
        import sys
        sys.exit(1)
    start_server = websockets.serve(handler, "0.0.0.0", 8765)
    print("WebSocket server listening on port 8765")
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
