import asyncio
import json
import socket
import time
import os
import sys
from rich.console import Console
import websockets
from Client import ws_client as wsc
from Client import port_file_reader as pfr
console = Console()

# Add parent directory to sys.path to allow imports from sibling modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Wireguard import wireguard_tools as wg_tools
from Core import id_tools as id
from ports import port_scanner as ps
from WebSockets import diagnostics

# -----------------------------------------------------------------------------
# This module implements the main WebSocket client loop for the NPM Stream Maker.
# It discovers available servers, establishes a persistent connection,
# authenticates, and periodically sends information about allowed and active
# listening ports to the server. It also handles reconnection logic and
# notifies the server about inactive ports.
# -----------------------------------------------------------------------------

async def ws_client_main_loop():
    """
    Main client loop that maintains persistent connection and detects server disconnects.
    Discovers servers, authenticates, sends allowed listening ports, and handles reconnections.
    """
    console.print("[bold green][WS_CLIENT][/bold green] Starting main client loop with server discovery...")

    # Load client assignments and ensure the ports file exists
    wsc.load_client_assignments()
    wsc.ensure_ports_file()
    allowed_ports = pfr.load_ports("ports.txt")
    console.print(f"[bold cyan][WS_CLIENT][/bold cyan] Loaded {len(allowed_ports)} allowed ports")

    if not allowed_ports:
        console.print("[bold red][WS_CLIENT][/bold red] No allowed ports found, cannot continue")
        return

    # Get local IP and hostname for identification
    local_ip = wg_tools.get_local_ip()
    hostname = socket.gethostname()
    console.print(f"[bold cyan][WS_CLIENT][/bold cyan] Client info: {hostname} ({local_ip})")

    # Discover servers only once at startup
    conflict_resolution_servers, wireguard_servers = await id.discover_server_types()
    if not conflict_resolution_servers and not wireguard_servers:
        console.print("[bold red][WS_CLIENT][/bold red] No servers available")
        return

    # Select the first available server (can be improved)
    # Ensure only the first two values of each tuple are used
    all_servers = []
    for s in conflict_resolution_servers + wireguard_servers:
        if isinstance(s, (list, tuple)) and len(s) >= 2:
            all_servers.append((s[0], s[1]))
    if not all_servers:
        console.print("[bold red][WS_CLIENT][/bold red] No servers found for persistent connection")
        return
    server_uri, server_token = all_servers[0]

    sent_ports = set()
    port_last_seen = {}
    ping_interval = 90     # Increased from 60 to 90 seconds
    inactive_timeout = 600  # 10 minutes

    while True:
        try:
            console.print(f"[bold cyan][WS_CLIENT][/bold cyan] Connecting to server {server_uri} ...")
            async with websockets.connect(
                server_uri, 
                ping_interval=ping_interval, 
                ping_timeout=30,    # Increased from 10 to 30 seconds
                close_timeout=15    # Added close timeout
            ) as websocket:
                # Initial authentication
                await websocket.send(json.dumps({"token": server_token}))
                token_response = await asyncio.wait_for(websocket.recv(), timeout=10)  # Increased timeout
                token_result = json.loads(token_response)
                if token_result.get("status") != "ok":
                    console.print(f"[bold red][WS_CLIENT][/bold red] Token rejected by server")
                    await asyncio.sleep(10)
                    continue

                console.print(f"[bold green][WS_CLIENT][/bold green] Connected and authenticated with server")

                while True:
                    # --- Port logic ---
                    current_ports = ps.get_listening_ports_with_proto()
                    allowed_and_listening = [(port, proto) for port, proto in current_ports if port in allowed_ports]
                    current_port_set = set(allowed_and_listening)
                    new_ports = current_port_set - sent_ports

                    if new_ports:
                        console.print(f"[bold cyan][WS_CLIENT][/bold cyan] Found {len(new_ports)} new ports - sending to server...")
                        data = {
                            "token": server_token,
                            "ip": local_ip,
                            "hostname": hostname,
                            "ports": [{"port": port, "protocol": proto} for port, proto in new_ports]
                        }
                        await websocket.send(json.dumps(data))
                        sent_ports.update(new_ports)
                        for port, proto in new_ports:
                            port_last_seen[(port, proto)] = time.time()
                        console.print(f"[bold green][WS_CLIENT][/bold green] Sent {len(new_ports)} new ports to server")
                    else:
                        # Send a logical ping (you can change the content if you want)
                        await websocket.send(json.dumps({"token": server_token, "ping": True}))

                    # Update last_seen timestamps
                    current_time = time.time()
                    for port, proto in current_port_set:
                        port_last_seen[(port, proto)] = current_time

                    # Handle inactive ports
                    inactive_ports = []
                    for (port, proto), last_seen in list(port_last_seen.items()):
                        if current_time - last_seen > inactive_timeout:
                            inactive_ports.append({"port": port, "protocol": proto})
                            del port_last_seen[(port, proto)]
                            sent_ports.discard((port, proto))

                    if inactive_ports:
                        remove_data = {
                            "token": server_token,
                            "remove_ports": inactive_ports
                        }
                        await websocket.send(json.dumps(remove_data))
                        console.print(f"[bold yellow][WS_CLIENT][/bold yellow] Notified server about {len(inactive_ports)} inactive ports")

                    # Wait before next cycle
                    await asyncio.sleep(ping_interval)

        except (websockets.ConnectionClosed, ConnectionRefusedError) as e:
            console.print(f"[bold yellow][WS_CLIENT][/bold yellow] Connection lost: {e}. Reconnecting in 10 seconds...")  # Aumentado tiempo de reconexión
            await asyncio.sleep(10)  # Aumentado de 5 a 10 segundos
        except Exception as e:
            console.print(f"[bold red][WS_CLIENT][/bold red] Error in main loop: {e}")
            await asyncio.sleep(10)  # Aumentado de 5 a 10 segundos


# -----------------------------------------------------------------------------
# Function to notify all servers about inactive ports.
# -----------------------------------------------------------------------------
async def notify_inactive_ports_to_all_servers(inactive_ports):
    """
    Notify all servers about inactive ports.
    """
    uri_token_pairs = diagnostics.get_ws_uris_and_tokens()

    for uri, token in uri_token_pairs:
        try:
            async with websockets.connect(uri, ping_timeout=10) as websocket:
                # Send token first
                token_data = {"token": token}
                await websocket.send(json.dumps(token_data))

                # Wait for token validation
                token_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                token_result = json.loads(token_response)

                if token_result.get("status") != "ok":
                    continue

                # Send inactive ports notification
                remove_data = {
                    "token": token,
                    "remove_ports": inactive_ports
                }
                await websocket.send(json.dumps(remove_data))

                console.print(f"[bold yellow][WS_CLIENT][/bold yellow] Notified {uri} about {len(inactive_ports)} inactive ports")

        except Exception as e:
            console.print(f"[bold red][WS_CLIENT][/bold red] Failed to notify {uri} about inactive ports: {e}")
