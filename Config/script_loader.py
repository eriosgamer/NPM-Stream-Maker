from Core import token_manager as tm
import os
from rich.console import Console
import subprocess
import sys
from dotenv import load_dotenv

# Add the parent directory to sys.path to allow imports from sibling modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg
from Config import ws_config_handler as websocket_config
from WebSockets import websocket_config as ws_config_handler
from UI.console_handler import ws_error, ws_info

console = Console()

# Load environment variables from .env file
load_dotenv()


def run_script(script):
    """
    Runs a Python script (such as ws_server.py or ws_client.py) with the appropriate environment.
    Validates configuration and dependencies before execution.
    """
    # Check if the script file exists
    if not os.path.exists(script):
        ws_error("[WS_SERVER]", f"File {script} does not exist.")
        return
    # Check if the script is ws_server.py or ws_client.py
    if script == "ws_server.py":
        # Ensure a server token exists or create one if needed
        tm.get_or_create_token(console, "server")
    elif script == "ws_client.py":
        # Get URIs and tokens from .env using the new class
        uris, tokens, _ = websocket_config.get_ws_config()
        if not uris or not tokens:
            ws_error("[WS_CLIENT]", "No WebSocket URIs or tokens found in .env.")
            return
        # Try to connect to all nodes, continue if at least one is successful
        successful = False
        for uri, token in zip(uris, tokens):
            if not uri or not token:
                continue
            ws_info("[WS_CLIENT]", f"Testing connection to {uri}...")
            if ws_config_handler.test_ws_connection(uri, token):
                ws_info("[WS_CLIENT]", f"Connection to {uri} successful.")
                # Do NOT save URI - just set environment variables for this session only
                os.environ["WS_TOKEN"] = token
                os.environ["WS_URI"] = uri
                successful = True
            else:
                ws_error("[WS_CLIENT]", f"Connection to {uri} failed or invalid token.")
        if not successful:
            ws_error(
                "[WS_CLIENT]",
                "No valid WebSocket connections found. Please check your .env.",
            )
            return
    # Print a rule in the console indicating which script is being run
    console.rule(f"[bold cyan]Running: {script}")
    # Pass the URI as an environment variable if running ws_client.py
    env = os.environ.copy()
    if script == "ws_client.py" and os.path.exists(cfg.ENV_FILE):
        # Don't override URIs, just pass them as environment variables
        uris, tokens, _ = websocket_config.get_ws_config()
        if uris:
            env["WS_URIS"] = ",".join(uris)
        if tokens:
            env["WS_TOKENS"] = ",".join(tokens)
    # Add protection to allow execution only from the panel
    if script in (
        "ws_client.py",
        "ws_server.py",
        "Port_Scanner.py",
        "NPM_Cleaner.py",
        "Stream_Manager.py",
    ):
        env["RUN_FROM_PANEL"] = "1"
    # Run the script as a subprocess with the prepared environment
    result = subprocess.run([sys.executable, script], text=True, env=env)
    if result.returncode == 0:
        ws_info("[WS_SERVER]", f"{script} finished successfully.")
    else:
        ws_error("[WS_SERVER]", f"Error running {script} (code {result.returncode})")


# This module provides a utility to safely run core scripts (such as WebSocket server/client, port scanner, etc.)
# It ensures that all required configuration and tokens are present before execution,
# and that scripts are only run from the intended management panel.
