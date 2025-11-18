import asyncio
import json
import os
import sys
from rich.console import Console
from dotenv import load_dotenv

# Add parent directory to sys.path to allow relative imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from WebSockets import websocket_config as ws_config
from Config import ws_config_handler as WebSocketConfig
from Config import config as cfg
from Client import ws_client_main_thread as wscth
from WebSockets import uri_config
from UI.console_handler import ws_info, ws_error, ws_success

# Load environment variables from .env file
load_dotenv()

console = Console()

# This file manages the startup and main loop of the WebSocket client,
# including configuration validation, connection testing, and port assignment management.


def start_ws_client():
    """
    Starts the WebSocket client.
    Validates configuration and tests connection to servers before proceeding.
    """
    console.rule("[bold blue]Start WebSocket Client")

    # Get URIs and tokens from .env using the new class
    uris, tokens, _ = WebSocketConfig.get_ws_config()

    if not uris or not tokens or not any(tokens):
        ws_error("[WS_CLIENT]", "No WebSocket URIs or tokens configured.")
        ws_info(
            "[WS_CLIENT]",
            "Please use option 3 (Edit WebSocket URIs) to configure servers and tokens first.",
        )
        input("\nPress Enter to continue...")
        return

    # Test connections before starting
    ws_info("[WS_CLIENT]", "Testing connections to configured servers...")
    successful_connections = 0
    valid_uri_token_pairs = []

    for uri, token in zip(uris, tokens):
        if not uri or not token:
            continue
        ws_info("[WS_CLIENT]", f"Testing {uri}...")
        if ws_config.test_ws_connection(uri, token):
            ws_info("[WS_CLIENT]", f"✅ Connection to {uri} successful")
            successful_connections += 1
            valid_uri_token_pairs.append((uri, token))
        else:
            ws_error("[WS_CLIENT]", f"❌ Connection to {uri} failed")

    if successful_connections == 0:
        ws_error("[WS_CLIENT]", "No valid connections found. Cannot start client.")
        input("\nPress Enter to continue...")
        return

    ws_info(
        "[WS_CLIENT]",
        f"Found {successful_connections} valid connections. Starting client...",
    )

    # Start the WebSocket client for all valid servers
    try:
        asyncio.run(main(valid_uri_token_pairs))
    except KeyboardInterrupt:
        ws_info("[WS_CLIENT]", "Client stopped by user")
    except Exception as e:
        ws_error("[WS_CLIENT]", f"Client error: {e}")

    ws_info("[WS_CLIENT]", "WebSocket client finished")


def is_ports_file_outdated():
    """
    Checks if the ports.txt file is outdated (by age or size).
    Returns True if it should be regenerated.
    """
    ports_file = "ports.txt"

    if not os.path.exists(ports_file):
        return True

    try:
        # Check file age (regenerate if older than 7 days)
        import time

        file_age = time.time() - os.path.getmtime(ports_file)
        if file_age > 7 * 24 * 60 * 60:  # 7 days
            return True

        # Check file size (should be reasonable)
        file_size = os.path.getsize(ports_file)
        if file_size < 1000:  # Too small
            return True

        return False
    except Exception as e:
        ws_error("[WS_CLIENT]", f"Error checking ports file: {e}")
        return True


def ensure_ports_file():
    """
    Ensures that the ports.txt file exists and is up to date.
    If not, it generates it by running the Port_Scanner.
    """
    ports_file = "ports.txt"

    # Check if file exists and is up to date
    needs_update = is_ports_file_outdated()

    if needs_update:
        ws_info("[WS_CLIENT]", "Ports file needs update, generating...")
        try:
            # Try to run Port_Scanner to generate ports.txt
            import subprocess
            import sys

            # Set environment variable for Port_Scanner
            env = os.environ.copy()
            env["RUN_FROM_PANEL"] = "1"

            from ports.port_scanner_main import gen_ports_file

            if gen_ports_file():
                ws_success("[WS_CLIENT]", "Ports file generated successfully")
            else:
                ws_error("[WS_CLIENT]", "Failed to generate ports file.")
        except Exception as e:
            ws_error("[WS_CLIENT]", f"Error generating ports file: {e}")
    else:
        ws_info("[WS_CLIENT]", "Ports file is up to date.")


async def send_ports_on_connect(ws):
    """
    Envía la lista de puertos activos al servidor solo al conectar/reconectar.
    """
    try:
        ports = []
        for (port, proto), assignment in cfg.client_assignments.items():
            # Solo incluir puertos activos (no todos los históricos)
            if assignment.get("assigned", True):
                ports.append({"port": port, "protocol": proto})
        msg = {"action": "register_ports", "ports": ports}
        await ws.send(json.dumps(msg))
    except Exception as e:
        ws_error("[WS_CLIENT]", f"Error sending ports after reconnection: {e}")


async def main(valid_uri_token_pairs=None):
    """
    Main function to run the WebSocket client with server discovery.
    Handles configuration changes and runs the main client loop.
    """
    ws_info("[WS_CLIENT]", "Starting WebSocket client with server discovery...")

    if valid_uri_token_pairs is None:
        uris, tokens, _ = WebSocketConfig.get_ws_config()
        valid_uri_token_pairs = [
            (uri, token) for uri, token in zip(uris, tokens) if uri and token
        ]

    # Lanzar una tarea por cada servidor/token
    tasks = []
    for uri, token in valid_uri_token_pairs:
        tasks.append(
            asyncio.create_task(
                wscth.ws_client_main_loop(
                    on_connect=send_ports_on_connect, server_uri=uri, server_token=token
                )
            )
        )
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        ws_info("[WS_CLIENT]", "Shutting down...")
    except Exception as e:
        ws_error("[WS_CLIENT]", f"Main loop error: {e}")
        input("\nPress Enter to exit...")
    finally:
        # Save final state (but NOT URI configuration)
        save_client_assignments()
        ws_info("[WS_CLIENT]", "WebSocket client stopped")


def save_client_assignments():
    """
    Saves the client's port assignments to a JSON file.
    Converts tuple keys to strings for JSON serialization.
    """
    try:
        # Convert tuple keys to strings for JSON serialization
        serializable_assignments = {}
        for (port, proto), assignment in cfg.client_assignments.items():
            key = f"{port}|{proto}"
            serializable_assignments[key] = assignment

        with open(cfg.CLIENT_ASSIGNMENTS_FILE, "w") as f:
            json.dump(serializable_assignments, f, indent=2)
    except Exception as e:
        ws_error("[WS_CLIENT]", f"Error saving client assignments: {e}")


def load_client_assignments():
    """
    Loads the client's port assignments from a JSON file.
    Converts string keys back to tuples.
    """
    global client_assignments
    try:
        if os.path.exists(cfg.CLIENT_ASSIGNMENTS_FILE):
            with open(cfg.CLIENT_ASSIGNMENTS_FILE, "r") as f:
                data = json.load(f)

            # Convert string keys back to tuples
            client_assignments = {}
            for key, assignment in data.items():
                if "|" in key:
                    port, proto = key.split("|", 1)
                    if port.isdigit():
                        client_assignments[(int(port), proto)] = assignment

            ws_info(
                "[WS_CLIENT]", f"Loaded {len(client_assignments)} client assignments"
            )
    except Exception as e:
        ws_error("[WS_CLIENT]", f"Error loading client assignments: {e}")
