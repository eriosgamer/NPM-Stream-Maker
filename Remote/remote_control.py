import json
import platform
import sqlite3
import time
from rich.console import Console
import asyncio
import os
import sys

# Add the parent directory to sys.path to allow relative imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Remote import menu
from Streams import stream_creation_db as scdb
from npm import npm_handler as npm
from Config import config as cfg
from Streams import stream_handler as sh
from Wireguard import wireguard_tools as wg_tools


console = Console()

def start_remote_control():
    """
    Starts the remote control interface.
    Runs the remote control menu asynchronously.
    """
    console.rule("[bold blue]Remote Control")

    try:
        console.print(
            "[bold cyan]Starting remote control interface...[/bold cyan]")
        asyncio.run(menu.remote_control_menu())

    except Exception as e:
        console.print(
            f"[bold red]Error starting remote control: {e}[/bold red]")

    input("\nPress Enter to continue...")

async def execute_local_command(command):
    """
    Executes local commands by running subprocesses or internal functions.
    Supported commands:
        - restart_ws_client: Restarts the WebSocket client process.
        - update_port_scanner: Runs the port scanner script.
        - clear_all_streams: Runs the NPM_Cleaner script to clear streams.
        - sync_nginx_config: Syncs NGINX config with SQLite and reloads NPM.
    Returns True if the command was successful, False otherwise.
    """
    try:
        import subprocess
        env = os.environ.copy()
        env["RUN_FROM_PANEL"] = "1"

        if command == "restart_ws_client":
            # Kill existing ws_client processes and restart
            try:
                # Kill existing processes depending on the OS
                if platform.system().lower() == "windows":
                    subprocess.run(["taskkill", "/F", "/IM", "python.exe", "/FI", "WINDOWTITLE eq ws_client*"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.run(["pkill", "-f", "ws_client.py"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                # Start new ws_client process
                result = subprocess.run([sys.executable, "ws_client.py"], env=env, capture_output=True)
                return result.returncode == 0
            except Exception as e:
                console.print(f"[bold red][WS][/bold red] Error restarting ws_client: {e}")
                return False

        elif command == "update_port_scanner":
            # Run the port scanner script
            result = subprocess.run([sys.executable, "Port_Scanner.py"], env=env, capture_output=True)
            return result.returncode == 0

        elif command == "clear_all_streams":
            # Run the NPM_Cleaner script to clear all streams
            result = subprocess.run([sys.executable, "NPM_Cleaner.py"], env=env, capture_output=True)
            return result.returncode == 0

        elif command == "sync_nginx_config":
            # Sync NGINX configuration with SQLite and reload NPM
            scdb.sync_streams_conf_with_sqlite()
            npm.reload_npm()
            return True

        return False

    except Exception as e:
        console.print(f"[bold red][WS][/bold red] Error executing local command {command}: {e}")
        return False

# Copied
def format_uptime(uptime_seconds):
    """
    Formats uptime in a human-readable format.
    Example: 1h 23m 45s
    """
    try:
        hours, remainder = divmod(int(uptime_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except Exception:
        return "unknown"

async def handle_remote_command(data, websocket):
    """
    Handles remote commands sent from Remote_Control.py via WebSocket.
    Supported commands:
        - restart_ws_client
        - update_port_scanner
        - clear_all_streams
        - sync_nginx_config
        - get_status
        - update_forwarding_ips
    Sends a response back through the websocket.
    """
    command = data.get("remote_command")
    console.print(f"[bold cyan][WS][/bold cyan] Received remote command: {command}")

    try:
        if command == "restart_ws_client":
            # Send command to local ws_client to restart
            result = await execute_local_command("restart_ws_client")
            await websocket.send(json.dumps({
                "status": "ok" if result else "error",
                "msg": "WebSocket client restart command sent" if result else "Failed to restart WebSocket client"
            }))

        elif command == "update_port_scanner":
            # Update ports.txt by running the port scanner
            result = await execute_local_command("update_port_scanner")
            await websocket.send(json.dumps({
                "status": "ok" if result else "error",
                "msg": "Port scanner updated" if result else "Failed to update port scanner"
            }))

        elif command == "clear_all_streams":
            # Clear all streams using NPM_Cleaner
            result = await execute_local_command("clear_all_streams")
            await websocket.send(json.dumps({
                "status": "ok" if result else "error",
                "msg": "All streams cleared" if result else "Failed to clear streams"
            }))

        elif command == "sync_nginx_config":
            # Sync NGINX configuration with SQLite and reload NPM
            result = await execute_local_command("sync_nginx_config")
            await websocket.send(json.dumps({
                "status": "ok" if result else "error",
                "msg": "NGINX configuration synced" if result else "Failed to sync NGINX configuration"
            }))

        elif command == "get_status":
            # Get server status and send it back
            console.print("[bold cyan][WS][/bold cyan] Getting server status")
            status = await get_server_status()
            await websocket.send(json.dumps({
                "status": "ok",
                "server_status": status
            }))

        elif command == "update_forwarding_ips":
            # Update stream forwarding IPs with provided mappings
            ip_mappings = data.get("ip_mappings", {})
            result = await sh.update_forwarding_ips(ip_mappings)
            await websocket.send(json.dumps({
                "status": "ok" if result else "error",
                "msg": f"Updated {len(ip_mappings)} forwarding IPs" if result else "Failed to update forwarding IPs"
            }))

        else:
            # Unknown command received
            await websocket.send(json.dumps({
                "status": "error",
                "msg": f"Unknown remote command: {command}"
            }))

    except Exception as e:
        console.print(f"[bold red][WS][/bold red] Error executing remote command {command}: {e}")
        await websocket.send(json.dumps({
            "status": "error",
            "msg": f"Error executing command: {str(e)}"
        }))

# Copied
async def get_server_status():
    """
    Gets current server status information.
    Returns a dictionary with:
        - active_streams: Number of active streams in the database.
        - connected_clients: Number of currently connected clients.
        - wireguard_available: Whether WireGuard is available.
        - server_type: "wireguard" if available, otherwise "conflict_resolution".
        - uptime: Server uptime in seconds.
        - uptime_formatted: Human-readable uptime.
    """
    try:
        # Count active streams from the SQLite database
        active_streams = 0
        if os.path.exists(cfg.SQLITE_DB_PATH):
            conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM stream WHERE is_deleted=0 AND enabled=1")
                active_streams = cur.fetchone()[0]
            finally:
                conn.close()

        # Count connected clients from config
        connected_clients_count = len(cfg.connected_clients)

        # Get WireGuard status (True if wg0 interface has an IP)
        wg_status = wg_tools.get_local_wg_ip("wg0") is not None

        # Calculate uptime since server start
        uptime_seconds = time.time() - cfg.server_start_time

        return {
            "active_streams": active_streams,
            "connected_clients": connected_clients_count,
            "wireguard_available": wg_status,
            "server_type": "wireguard" if wg_status else "conflict_resolution",
            "uptime": uptime_seconds,
            "uptime_formatted": format_uptime(uptime_seconds)
        }

    except Exception as e:
        console.print(f"[bold red][WS][/bold red] Error getting server status: {e}")
        return {"error": str(e)}
