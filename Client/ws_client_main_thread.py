import asyncio
import json
import socket
import time
import os
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
import websockets
from Client import ws_client as wsc
from Client import port_file_reader as pfr
from UI.console_handler import ws_info, ws_error, ws_warning, ws_success, ws_connection
import ctypes
from Client import (
    server_querys,
)  # Añadir import para query_server_capabilities y send_ports_to_conflict_resolution_server
from Core import (
    remote_message_handler,
)  # Importa el handler para acceder a pending_remote_ports, etc.

# Add parent directory to sys.path to allow imports from sibling modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Wireguard import wireguard_tools as wg_tools
from Core import id_tools as id
from ports import port_scanner as ps
from ports.port_scanner_main import gen_ports_file
from ports import ports_utils as psu
from WebSockets import diagnostics

ping_interval = 90
inactive_timeout = 600  # 10 minutes
# -----------------------------------------------------------------------------
# This module implements the main WebSocket client loop for the NPM Stream Maker.
# It discovers available servers, establishes a persistent connection,
# authenticates, and periodically sends information about allowed and active
# listening ports to the server. It also handles reconnection logic and
# notifies the server about inactive ports.
# -----------------------------------------------------------------------------


async def ws_client_main_loop(on_connect=None, server_uri=None, server_token=None):
    """
    Main client loop that maintains persistent connection and detects server disconnects.
    Now connects to a specific server_uri/token.
    """
    # Detect and warn if the process does not have sufficient privileges on Windows
    if os.name == "nt":
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            is_admin = False
        if not is_admin:
            ws_warning(
                "[WS_CLIENT]",
                "Python is NOT running as administrator. Some functions may fail (port reading, network permissions, etc). Run PowerShell/cmd as Administrator if possible.",
            )

        else:
            ws_info("[WS_CLIENT]", "Python is running as administrator.")

    ws_info("[WS_CLIENT]", "Starting main client loop with server discovery")

    # Load client assignments and ensure the ports file exists
    wsc.load_client_assignments()
    wsc.ensure_ports_file()

    # Move initialization here so it restarts on each reconnection
    global allowed_ports, sent_ports, port_last_seen

    # Get local IP and hostname for identification
    local_ip = wg_tools.get_local_ip()
    hostname = socket.gethostname()

    ws_info("WS_CLIENT", f"Client info: {hostname} ({local_ip})")

    # --- NUEVO: usar server_uri y server_token directamente ---
    if not server_uri or not server_token:
        ws_error("WS_CLIENT", "No server_uri or server_token provided to client loop")
        return

    # --- NUEVO: Consultar capacidades del servidor ---
    server_caps = await server_querys.query_server_capabilities(
        server_uri, server_token
    )
    if not server_caps:
        ws_error("WS_CLIENT", f"Could not get server capabilities for {server_uri}")
        return

    while True:
        sent_ports = set()
        port_last_seen = {}
        force_resend = True
        try:
            ws_connection("WS_CLIENT", server_uri, "connecting")
            async with websockets.connect(
                server_uri,
                ping_interval=ping_interval,
                ping_timeout=30,
                close_timeout=15,
            ) as websocket:
                # Initial authentication
                await websocket.send(json.dumps({"token": server_token}))
                token_response = await asyncio.wait_for(websocket.recv(), timeout=10)
                token_result = json.loads(token_response)
                if token_result.get("status") != "ok":
                    ws_error("WS_CLIENT", "Token rejected by server")
                    await asyncio.sleep(10)
                    continue

                ws_connection("WS_CLIENT", server_uri, "connected")

                # Call the on_connect callback if provided
                if on_connect is not None:
                    await on_connect(websocket)

                # --- NUEVO: Lógica de envío según tipo de servidor ---
                allowed_ports = pfr.load_ports("ports.txt")
                current_ports = ps.get_listening_ports_with_proto()
                allowed_and_listening = []
                for port, proto in current_ports:
                    try:
                        port_int = int(port)
                    except Exception:
                        continue
                    if port_int in allowed_ports:
                        allowed_and_listening.append((port_int, proto))
                current_port_set = set(allowed_and_listening)

                # --- AGREGAR PUERTOS REMOTOS PENDIENTES ---
                def process_pending_remote_ports():
                    # Limpieza automática antes de procesar
                    if hasattr(
                        remote_message_handler, "clean_old_pending_remote_ports"
                    ):
                        remote_message_handler.clean_old_pending_remote_ports()
                    extra_ports = []
                    if hasattr(remote_message_handler, "pending_remote_ports"):
                        while remote_message_handler.pending_remote_ports:
                            entry = remote_message_handler.pending_remote_ports.pop(0)
                            # Compatibilidad: si la tupla tiene 6 elementos, agregar timestamp actual
                            if len(entry) == 6:
                                entry = (*entry, int(time.time()))
                            extra_ports.append(entry)
                    forwarding_info = {}
                    new_entries = []
                    for (
                        port,
                        proto,
                        forwarding_host,
                        forwarding_port,
                        acl_allow_list,
                        acl_deny_list,
                    ) in extra_ports:
                        key = (port, proto)
                        if key not in current_port_set:
                            current_port_set.add(key)
                            forwarding_info[key] = {
                                "forwarding_host": forwarding_host,
                                "forwarding_port": forwarding_port,
                                "acl_allow_list": acl_allow_list,
                                "acl_deny_list": acl_deny_list,
                            }
                            new_entries.append(
                                (port, proto, forwarding_host, forwarding_port)
                            )
                    if new_entries:
                        from Streams import stream_creation

                        stream_creation.add_streams_sqlite_with_ip_extended(new_entries)
                    return forwarding_info

                # Procesar puertos remotos pendientes ANTES de cada ciclo de envío de puertos
                forwarding_info = process_pending_remote_ports()

                # --- FORCE IMMEDIATE PORT SEND AFTER CONNECTION ---
                allowed_ports = pfr.load_ports("ports.txt")
                # DEBUG: Print ports.txt content on Windows
                if os.name == "nt":
                    console = Console()
                    try:
                        with open("ports.txt", "r") as f:
                            ports_txt_content = f.read()
                        ws_info("[WS_CLIENT]", "Contents of ports.txt:")
                        ws_info("[WS_CLIENT]", ports_txt_content)
                    except Exception as e:
                        ws_error("[WS_CLIENT]", f"Error reading ports.txt: {e}")
                        
                # DEBUG: Print parsed ports by client on Windows
                if os.name == "nt":
                    ws_info("[WS_CLIENT]", "Ports parsed by the client:")
                    for port, proto in current_ports:
                        ws_info("[WS_CLIENT]", f"{port} / {proto}")

                # Reinforcement: filter and validate ports correctly (strict on both systems)
                allowed_and_listening = []
                for port, proto in current_ports:
                    try:
                        port_int = int(port)
                    except Exception:
                        continue
                    if port_int in allowed_ports:
                        allowed_and_listening.append((port_int, proto))
                current_port_set = set(allowed_and_listening)
                # Warning log if the number of ports is suspiciously low
                if len(current_port_set) < 3:
                    ws_warning(
                        "WS_CLIENT",
                        f"⚠️ Few valid ports detected ({len(current_port_set)}). There may be a permissions or configuration issue.",
                    )

                if current_port_set:
                    port_list = [
                        {"port": port, "protocol": proto}
                        for port, proto in current_port_set
                    ]
                    table = Table(
                        title="Ports sent to server (reconnection)",
                        box=box.SIMPLE,
                        show_lines=True,
                    )
                    table.add_column("Port", style="magenta", justify="right")
                    table.add_column("Protocol", style="cyan", justify="center")
                    for p in port_list:
                        table.add_row(str(p["port"]), p["protocol"].upper())
                    console = Console()
                    console.print(
                        Panel(
                            table,
                            title="[bold green]WS_CLIENT[/bold green]",
                            expand=False,
                        )
                    )
                    data = {
                        "type": "conflict_resolution_ports",
                        "token": server_token,
                        "ip": local_ip,
                        "hostname": hostname,
                        "ports": port_list,
                    }
                    await websocket.send(json.dumps(data))
                    sent_ports.update(current_port_set)
                    for port, proto in current_port_set:
                        port_last_seen[(port, proto)] = time.time()
                    ws_success(
                        "WS_CLIENT",
                        f"Sent {len(current_port_set)} ports to server after reconnection",
                    )

                    # Esperar respuesta del servidor de resolución
                    try:
                        response_msg = await asyncio.wait_for(websocket.recv(), timeout=30)
                        response = json.loads(response_msg)
                        if response.get("type") == "client_port_conflict_resolution_response":
                            approved_ports = response.get("resultados", [])
                            ws_info("WS_CLIENT", f"Received {len(approved_ports)} approved ports from conflict resolution server")
                            # Enviar puertos aprobados al WireGuard
                            wg_data = {
                                "type": "conflict_resolution_ports",
                                "token": server_token,
                                "ip": local_ip,
                                "hostname": hostname,
                                "ports": approved_ports,
                                "ports_pre_approved": True,
                            }
                            ws_info("WS_CLIENT", f"Enviando puertos aprobados al WireGuard con token: {server_token}")
                            await websocket.send(json.dumps(wg_data))
                            # Esperar confirmación del servidor WireGuard
                            try:
                                wg_response_msg = await asyncio.wait_for(websocket.recv(), timeout=15)
                                ws_info("WS_CLIENT", f"Respuesta recibida de WireGuard: {wg_response_msg}")
                                wg_response = json.loads(wg_response_msg)
                                if wg_response.get("status") == "ok":
                                    ws_success("WS_CLIENT", f"WireGuard server processed {len(approved_ports)} ports successfully")
                                    # Solo aquí marcar como procesados
                                    sent_ports.update(current_port_set)
                                else:
                                    ws_error("WS_CLIENT", f"WireGuard server did not confirm port processing: {wg_response}")
                            except Exception as e:
                                ws_error("WS_CLIENT", f"No confirmation from WireGuard server: {e}")
                        else:
                            ws_error("WS_CLIENT", f"Unexpected response from conflict resolution server: {response}")
                    except Exception as e:
                        ws_error("WS_CLIENT", f"Error waiting for approval response: {e}")
                else:
                    ws_warning("WS_CLIENT", "No ports to send after reconnection")

                force_resend = False  # Resend already forced after reconnection

                while True:
                    # Procesar y sincronizar puertos remotos en cada ciclo
                    forwarding_info = process_pending_remote_ports()
                    allowed_ports = pfr.load_ports("ports.txt")
                    # --- Port logic ---
                    # Check if ports.txt needs to be regenerated (missing, empty, or older than 24 hours)
                    needs_regeneration = (
                        not allowed_ports  # No ports loaded (file missing or empty)
                        or psu.should_regenerate_ports_file()  # File older than 24 hours
                    )

                    if needs_regeneration:
                        if not allowed_ports:
                            ws_warning(
                                "WS_CLIENT",
                                "No allowed ports configured, scanning...",
                            )
                        else:
                            ws_warning(
                                "WS_CLIENT",
                                "ports.txt needs regeneration, rescanning...",
                            )
                        gen_ports_file()
                        allowed_ports = pfr.load_ports("ports.txt")
                        if not allowed_ports:
                            ws_error(
                                "WS_CLIENT",
                                "No ports found after regeneration, aborting",
                            )
                            return
                        ws_success(
                            "WS_CLIENT",
                            f"Loaded {len(allowed_ports)} ports after regeneration",
                        )
                    else:
                        ws_info(
                            "WS_CLIENT",
                            f"Using existing ports.txt with {len(allowed_ports)} ports",
                        )

                    current_ports = ps.get_listening_ports_with_proto()
                    allowed_and_listening = [
                        (port, proto)
                        for port, proto in current_ports
                        if port in allowed_ports
                    ]
                    current_port_set = set(allowed_and_listening)

                    # --- INCLUIR PUERTOS REMOTOS MANUALES EN EL ENVÍO ---
                    # Añadir los puertos remotos pendientes a current_port_set y port_list
                    for key, info in forwarding_info.items():
                        if key not in current_port_set:
                            current_port_set.add(key)

                    # --- KEY CHANGE ---
                    if force_resend:
                        new_ports = current_port_set
                        force_resend = False
                    else:
                        new_ports = current_port_set - sent_ports

                    if new_ports:
                        port_list = [
                            {"port": port, "protocol": proto}
                            for port, proto in new_ports
                        ]
                        # Añadir detalles de forwarding_info si existen (para puertos remotos manuales)
                        for idx, entry in enumerate(port_list):
                            key = (entry["port"], entry["protocol"])
                            if key in forwarding_info:
                                entry.update(forwarding_info[key])
                        # Condensed output with Rich Table
                        table = Table(
                            title="Ports sent to server",
                            box=box.SIMPLE,
                            show_lines=True,
                        )
                        table.add_column("Port", style="magenta", justify="right")
                        table.add_column("Protocol", style="cyan", justify="center")
                        for p in port_list:
                            table.add_row(str(p["port"]), p["protocol"].upper())
                        console = Console()
                        console.print(
                            Panel(
                                table,
                                title="[bold green]WS_CLIENT[/bold green]",
                                expand=False,
                            )
                        )

                        data = {
                            "type": "conflict_resolution_ports",
                            "token": server_token,
                            "ip": local_ip,
                            "hostname": hostname,
                            "ports": port_list,
                        }
                        await websocket.send(json.dumps(data))
                        sent_ports.update(new_ports)
                        for port, proto in new_ports:
                            port_last_seen[(port, proto)] = time.time()
                        ws_success(
                            "WS_CLIENT",
                            f"Sent {len(new_ports)} new ports to server",
                        )
                    else:
                        # Send a logical ping
                        await websocket.send(
                            json.dumps({"type": "ping", "token": server_token})
                        )

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
                            "type": "remove_ports",
                            "token": server_token,
                            "remove_ports": inactive_ports,
                        }
                        await websocket.send(json.dumps(remove_data))
                        ws_warning(
                            "WS_CLIENT",
                            f"Notified server about {len(inactive_ports)} inactive ports",
                        )

                    # Wait before next cycle
                    await asyncio.sleep(ping_interval)

        except (websockets.ConnectionClosed, ConnectionRefusedError) as e:
            ws_warning("WS_CLIENT", f"Connection lost: {e}. Reconnecting in 10 seconds")
            await asyncio.sleep(10)
        except Exception as e:
            ws_error("WS_CLIENT", f"Error in main loop: {e}")
            await asyncio.sleep(10)


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
                remove_data = {"token": token, "remove_ports": inactive_ports}
                await websocket.send(json.dumps(remove_data))

                ws_warning(
                    "WS_CLIENT",
                    f"Notified {uri} about {len(inactive_ports)} inactive ports",
                )

        except Exception as e:
            ws_error("WS_CLIENT", f"Failed to notify {uri} about inactive ports: {e}")


def run_as_admin_windows(cmd):
    """
    Tries to run a command with elevated privileges on Windows.
    Returns True if launched successfully, False otherwise.
    """
    if os.name != "nt":
        return False
