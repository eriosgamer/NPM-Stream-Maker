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
from UI import console_handler as ch
import ctypes
import subprocess

# Add parent directory to sys.path to allow imports from sibling modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Wireguard import wireguard_tools as wg_tools
from Core import id_tools as id
from ports import port_scanner as ps
from ports import port_scanner_main as psm
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


async def ws_client_main_loop(on_connect=None):
    """
    Main client loop that maintains persistent connection and detects server disconnects.
    """
    # Detectar y advertir si el proceso no tiene privilegios suficientes en Windows
    if os.name == "nt":
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            is_admin = False
        if not is_admin:
            Console().print("[bold red][WS_CLIENT][/bold red] ⚠️ Python NO se está ejecutando como administrador. Algunas funciones pueden fallar (lectura de puertos, permisos de red, etc). Ejecuta PowerShell/cmd como Administrador si es posible.")
        else:
            Console().print("[bold green][WS_CLIENT][/bold green] Python se está ejecutando como administrador.")

    ch.ws_info("WS_CLIENT", "Starting main client loop with server discovery")

    # Load client assignments and ensure the ports file exists
    wsc.load_client_assignments()
    wsc.ensure_ports_file()

    # Mueve la inicialización aquí para que se reinicie en cada reconexión
    global allowed_ports, sent_ports, port_last_seen
    
    

    # Get local IP and hostname for identification
    local_ip = wg_tools.get_local_ip()
    hostname = socket.gethostname()

    ch.ws_info("WS_CLIENT", f"Client info: {hostname} ({local_ip})")

    # Discover servers only once at startup
    conflict_resolution_servers, wireguard_servers = await id.discover_server_types()
    if not conflict_resolution_servers and not wireguard_servers:
        ch.ws_error("WS_CLIENT", "No servers available")
        return

    # Select the first available server (can be improved)
    # Ensure only the first two values of each tuple are used
    all_servers = []
    for s in conflict_resolution_servers + wireguard_servers:
        if isinstance(s, (list, tuple)) and len(s) >= 2:
            all_servers.append((s[0], s[1]))
    if not all_servers:
        ch.ws_error("WS_CLIENT", "No servers found for persistent connection")
        return
    server_uri, server_token = all_servers[0]

    while True:
        sent_ports = set()
        port_last_seen = {}
        force_resend = True  # <--- NUEVO: bandera para forzar reenvío tras reconexión
        try:
            ch.ws_connection("WS_CLIENT", server_uri, "connecting")
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
                    ch.ws_error("WS_CLIENT", "Token rejected by server")
                    await asyncio.sleep(10)
                    continue

                ch.ws_connection("WS_CLIENT", server_uri, "connected")

                # Call the on_connect callback if provided
                if on_connect is not None:
                    await on_connect(websocket)

                from rich.table import Table
                from rich.panel import Panel
                from rich import box

                # --- FORZAR ENVÍO DE PUERTOS INMEDIATAMENTE TRAS CONEXIÓN ---
                allowed_ports = pfr.load_ports("ports.txt")
                # DEBUG: Imprimir contenido de ports.txt en Windows
                if os.name == "nt":
                    console = Console()
                    try:
                        with open("ports.txt", "r") as f:
                            ports_txt_content = f.read()
                        console.print("[bold yellow]Contenido de ports.txt:[/bold yellow]")
                        console.print(ports_txt_content)
                    except Exception as e:
                        console.print(f"[red]Error leyendo ports.txt: {e}[/red]")

                current_ports = ps.get_listening_ports_with_proto()
                # DEBUG: Imprimir puertos parseados por el cliente en Windows
                if os.name == "nt":
                    console.print("[bold yellow]Puertos parseados por el cliente:[/bold yellow]")
                    for port, proto in current_ports:
                        console.print(f"{port} / {proto}")

                # Refuerzo: filtrar y validar puertos correctamente (estricto en ambos sistemas)
                allowed_and_listening = []
                for port, proto in current_ports:
                    try:
                        port_int = int(port)
                    except Exception:
                        continue
                    if port_int in allowed_ports:
                        allowed_and_listening.append((port_int, proto))
                current_port_set = set(allowed_and_listening)
                # Log de advertencia si la cantidad de puertos es sospechosamente baja
                if len(current_port_set) < 3:
                    ch.ws_warning("WS_CLIENT", f"⚠️ Se detectaron pocos puertos válidos ({len(current_port_set)}). Puede haber un problema de permisos o configuración.")

                if current_port_set:
                    port_list = [
                        {"port": port, "protocol": proto}
                        for port, proto in current_port_set
                    ]
                    table = Table(title="Puertos enviados al servidor (reconexión)", box=box.SIMPLE, show_lines=True)
                    table.add_column("Puerto", style="magenta", justify="right")
                    table.add_column("Protocolo", style="cyan", justify="center")
                    for p in port_list:
                        table.add_row(str(p["port"]), p["protocol"].upper())
                    console = Console()
                    console.print(Panel(table, title="[bold green]WS_CLIENT[/bold green]", expand=False))
                    data = {
                        "token": server_token,
                        "ip": local_ip,
                        "hostname": hostname,
                        "ports": port_list,
                    }
                    await websocket.send(json.dumps(data))
                    sent_ports.update(current_port_set)
                    for port, proto in current_port_set:
                        port_last_seen[(port, proto)] = time.time()
                    ch.ws_success(
                        "WS_CLIENT", f"Enviados {len(current_port_set)} puertos al servidor tras reconexión"
                    )
                else:
                    ch.ws_warning("WS_CLIENT", "No hay puertos para enviar tras reconexión")

                force_resend = False  # Ya forzamos el reenvío tras reconexión

                while True:
                    allowed_ports = pfr.load_ports("ports.txt")
                    # --- Port logic ---
                    # Check if ports.txt needs to be regenerated (missing, empty, or older than 24 hours)
                    needs_regeneration = (
                        not allowed_ports or  # No ports loaded (file missing or empty)
                        psu.should_regenerate_ports_file()  # File older than 24 hours
                    )

                    if needs_regeneration:
                        if not allowed_ports:
                            ch.ws_warning("WS_CLIENT", "No allowed ports configurados, escaneando...")
                        else:
                            ch.ws_warning("WS_CLIENT", "ports.txt necesita regeneración, re-escaneando...")
                        psm.main()
                        allowed_ports = pfr.load_ports("ports.txt")
                        if not allowed_ports:
                            ch.ws_error("WS_CLIENT", "No se encontraron puertos tras la regeneración, abortando")
                            return
                        ch.ws_success("WS_CLIENT", f"Cargados {len(allowed_ports)} puertos tras regeneración")
                    else:
                        ch.ws_info("WS_CLIENT", f"Usando ports.txt existente con {len(allowed_ports)} puertos")

                    current_ports = ps.get_listening_ports_with_proto()
                    allowed_and_listening = [
                        (port, proto)
                        for port, proto in current_ports
                        if port in allowed_ports
                    ]
                    current_port_set = set(allowed_and_listening)

                    # --- CAMBIO CLAVE ---
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
                        # Salida condensada con Rich Table
                        table = Table(title="Puertos enviados al servidor", box=box.SIMPLE, show_lines=True)
                        table.add_column("Puerto", style="magenta", justify="right")
                        table.add_column("Protocolo", style="cyan", justify="center")
                        for p in port_list:
                            table.add_row(str(p["port"]), p["protocol"].upper())
                        console = Console()
                        console.print(Panel(table, title="[bold green]WS_CLIENT[/bold green]", expand=False))

                        data = {
                            "token": server_token,
                            "ip": local_ip,
                            "hostname": hostname,
                            "ports": port_list,
                        }
                        await websocket.send(json.dumps(data))
                        sent_ports.update(new_ports)
                        for port, proto in new_ports:
                            port_last_seen[(port, proto)] = time.time()
                        ch.ws_success(
                            "WS_CLIENT", f"Enviados {len(new_ports)} puertos nuevos al servidor"
                        )
                    else:
                        # Send a logical ping
                        await websocket.send(
                            json.dumps({"token": server_token, "ping": True})
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
                            "token": server_token,
                            "remove_ports": inactive_ports,
                        }
                        await websocket.send(json.dumps(remove_data))
                        ch.ws_warning(
                            "WS_CLIENT",
                            f"Notified server about {len(inactive_ports)} inactive ports",
                        )

                    # Wait before next cycle
                    await asyncio.sleep(ping_interval)

        except (websockets.ConnectionClosed, ConnectionRefusedError) as e:
            ch.ws_warning(
                "WS_CLIENT", f"Connection lost: {e}. Reconnecting in 10 seconds"
            )
            await asyncio.sleep(10)
        except Exception as e:
            ch.ws_error("WS_CLIENT", f"Error in main loop: {e}")
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

                ch.ws_warning(
                    "WS_CLIENT",
                    f"Notified {uri} about {len(inactive_ports)} inactive ports",
                )

        except Exception as e:
            ch.ws_error(
                "WS_CLIENT", f"Failed to notify {uri} about inactive ports: {e}"
            )

def run_as_admin_windows(cmd):
    """
    Intenta ejecutar un comando con privilegios elevados en Windows.
    Devuelve True si se lanzó correctamente, False si no.
    """
    if os.name != "nt":
        return False
    try:
        params = ' '.join([f'"{c}"' for c in cmd])
        completed = subprocess.run([
            'powershell',
            '-Command',
            f'Start-Process python -ArgumentList "{params}" -Verb RunAs'
        ])
        return completed.returncode == 0
    except Exception as e:
        Console().print(f"[bold red][WS_CLIENT][/bold red] Error al intentar elevar privilegios: {e}")
        return False
