import asyncio
import websockets
from websockets.exceptions import ConnectionClosedError, InvalidHandshake
from websockets.datastructures import Headers
import json
from rich.prompt import Prompt
from rich.console import Console
import os
import sys

# Add the parent directory to the path to import configuration modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import ws_config_handler as WebSocketConfig
from Config import config as cfg
from UI.console_handler import ws_error, ws_warning, ws_info

console = Console()

# Global state dictionaries for assigned ports, connected clients, and port conflict resolutions
assigned_ports = {}
connected_clients = {}
port_conflict_resolutions = {}
uris, _, _ = WebSocketConfig.get_ws_config()
uri = uris[0] if uris else None
# This file provides utility functions for managing WebSocket server configuration,
# testing connections, and persisting state related to assigned ports, connected clients,
# and port conflict resolutions.

def get_ws_uri(console):
    """
    Gets the WebSocket server URI from the .env or prompts the user if not configured.
    Saves the URI if it is new.
    """
    global uri
    # Try to read the URI from .env

    if not uri:
        uri = Prompt.ask(
            "[bold cyan]Enter the WebSocket server URI (e.g. ws://1.2.3.4:8765)[/bold cyan]")
        # Save the new URI to config
        if uri:
            existing_uris, existing_tokens, _ = WebSocketConfig.get_ws_config()
            if existing_uris:
                existing_uris[0] = uri
            else:
                existing_uris = [uri]
            WebSocketConfig.save_ws_config(
                uris=existing_uris, tokens=existing_tokens)
    return uri


def test_ws_connection(uri, token):
    """
    Tests the connection to a WebSocket server using the provided token.
    Returns True if the connection and validation are successful, False otherwise.
    """

    async def try_connect():
        try:
            # Simplified connection for maximum compatibility with timeout
            async with websockets.connect(
                uri,
                ping_interval=60,  # Increased from None to 60 seconds
                ping_timeout=30,   # Added ping timeout
                close_timeout=10      # Increased close timeout
            ) as websocket:
                # Send test message with token for validation
                test_data = {
                    "type": "test_connection",
                    "token": token,
                    "test_connection": True,
                    "ip": "control_panel_test",
                    "hostname": "control_panel_test"
                }
                await websocket.send(json.dumps(test_data))
                resp = await asyncio.wait_for(websocket.recv(), timeout=5)
                data = json.loads(resp)

                # Check for successful response
                if data.get("status") == "ok":
                    return True
                elif data.get("status") == "error":
                    error_msg = data.get("msg", "Unknown error")
                    if "token" in error_msg.lower():
                        ws_error("[WS_CLIENT]", f"[bold red]Token validation failed for {uri}: {error_msg}[/bold red]")
                    else:
                        ws_warning("[WS_CLIENT]", f"[bold yellow]Server error for {uri}: {error_msg}[/bold yellow]")
                    return False
                else:
                    # Any other response might indicate server is working
                    return True
        except InvalidHandshake as e:
            ws_error("[WS_CLIENT]", f"[bold red]WebSocket handshake failed for {uri}: {e}[/bold red]")
            ws_warning("[WS_CLIENT]", f"[bold yellow]Server may not be running or may not support WebSocket upgrades[/bold yellow]")
            return False
        except asyncio.TimeoutError:
            ws_error("[WS_CLIENT]", f"[bold red]Connection timeout for {uri} (server may be slow to respond)[/bold red]")
            return False
        except websockets.exceptions.ConnectionClosed:
            ws_error("[WS_CLIENT]", f"[bold red]Connection closed immediately for {uri}[/bold red]")
            return False
        except Exception as e:
            ws_error("[WS_CLIENT]", f"[bold red]Connection error for {uri}: {e}[/bold red]")
            return False

    try:
        return asyncio.run(try_connect())
    except Exception as e:
        ws_error("[WS_CLIENT]", f"[bold red]Async error testing {uri}: {e}[/bold red]")
        return False


def save_state():
    """
    Saves the current state of assigned ports, connected clients, and port conflict resolutions to disk.
    """
    with open(cfg.ASSIGNED_PORTS_FILE, "w") as f:
        json.dump(assigned_ports, f)
    with open(cfg.CONNECTED_CLIENTS_FILE, "w") as f:
        json.dump(connected_clients, f)
    # Save port conflict resolutions
    serializable_resolutions = {}
    for (original_port, protocol, server_ip), alt_port in port_conflict_resolutions.items():
        key = f"{original_port}|{protocol}|{server_ip}"
        serializable_resolutions[key] = alt_port
    with open(cfg.PORT_CONFLICT_RESOLUTIONS_FILE, "w") as f:
        json.dump(serializable_resolutions, f, indent=2)
    ws_info("[WS_CLIENT]", f"[bold green]Saved {len(port_conflict_resolutions)} port conflict resolutions[/bold green]")

# Copied
def load_state():
    """
    Loads the state of assigned ports, connected clients, and port conflict resolutions from disk.
    """
    global assigned_ports, connected_clients, port_conflict_resolutions
    if os.path.exists(cfg.ASSIGNED_PORTS_FILE):
        with open(cfg.ASSIGNED_PORTS_FILE, "r") as f:
            assigned_ports.update(json.load(f))
    if os.path.exists(cfg.CONNECTED_CLIENTS_FILE):
        with open(cfg.CONNECTED_CLIENTS_FILE, "r") as f:
            connected_clients.update(json.load(f))
    # Load port conflict resolutions
    if os.path.exists(cfg.PORT_CONFLICT_RESOLUTIONS_FILE):
        try:
            with open(cfg.PORT_CONFLICT_RESOLUTIONS_FILE, "r") as f:
                saved_resolutions = json.load(f)
            for key, alt_port in saved_resolutions.items():
                original_port, protocol, server_ip = key.split("|", 2)
                port_conflict_resolutions[(int(original_port), protocol, server_ip)] = alt_port
            ws_info("[WS_CLIENT]", f"[bold green]Loaded {len(port_conflict_resolutions)} port conflict resolutions from disk[/bold green]")
        except Exception as e:
            ws_warning("[WS_CLIENT]", f"[bold yellow]Error loading port conflict resolutions: {e}[/bold yellow]")


def is_first_server():
    """
    Checks if the current server is the first one in the list of WebSocket URIs.
    Returns True if it is the first server, False otherwise.
    """
    uris, _, _ = WebSocketConfig.get_ws_config()
    if not uris:
        return False
    return uris[0] == get_ws_uri(console)