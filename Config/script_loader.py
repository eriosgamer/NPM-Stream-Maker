from Config import config as cfg
from WebSockets import websocket_config as WebSocketConfig
from Core import token_manager as tm
import os
from rich.console import Console
import subprocess
import sys

# Add the parent directory to sys.path to allow imports from sibling modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

console = Console()


def run_script(script):
    """
    Runs a Python script (such as ws_server.py or ws_client.py) with the appropriate environment.
    Validates configuration and dependencies before execution.
    """
    # Check if the script file exists
    if not os.path.exists(script):
        console.print(f"[red]File {script} does not exist.[/red]")
        return
    # Check if the script is ws_server.py or ws_client.py
    if script == "ws_server.py":
        # Ensure a server token exists or create one if needed
        tm.get_or_create_token(console, "server")
    elif script == "ws_client.py":
        # Get URIs and tokens from .env using the new class
        uris, tokens, _ = WebSocketConfig.get_ws_config()
        if not uris or not tokens:
            console.print(
                "[red]No WebSocket URIs or tokens found in .env.[/red]")
            return
        # Try to connect to all nodes, continue if at least one is successful
        successful = False
        for uri, token in zip(uris, tokens):
            if not uri or not token:
                continue
            console.print(f"[cyan]Testing connection to {uri}...[/cyan]")
            if WebSocketConfig.test_ws_connection(uri, token):
                console.print(
                    f"[green]Connection to {uri} successful.[/green]")
                # Do NOT save URI - just set environment variables for this session only
                os.environ["WS_TOKEN"] = token
                os.environ["WS_URI"] = uri
                successful = True
            else:
                console.print(
                    f"[red]Connection to {uri} failed or invalid token.[/red]")
        if not successful:
            console.print(
                "[red]No valid WebSocket connections found. Please check your .env.[/red]")
            return
    # Print a rule in the console indicating which script is being run
    console.rule(f"[bold cyan]Running: {script}")
    # Pass the URI as an environment variable if running ws_client.py
    env = os.environ.copy()
    if script == "ws_client.py" and os.path.exists(cfg.ENV_FILE):
        # Don't override URIs, just pass them as environment variables
        uris, tokens, _ = WebSocketConfig.get_ws_config()
        if uris:
            env["WS_URIS"] = ",".join(uris)
        if tokens:
            env["WS_TOKENS"] = ",".join(tokens)
    # Add protection to allow execution only from the panel
    if script in ("ws_client.py", "ws_server.py", "Port_Scanner.py", "NPM_Cleaner.py", "Stream_Manager.py"):
        env["RUN_FROM_PANEL"] = "1"
    # Run the script as a subprocess with the prepared environment
    result = subprocess.run([sys.executable, script], text=True, env=env)
    if result.returncode == 0:
        console.print(f"[green]{script} finished successfully.[/green]")
    else:
        console.print(
            f"[red]Error running {script} (code {result.returncode})[/red]")

# This module provides a utility to safely run core scripts (such as WebSocket server/client, port scanner, etc.)
# It ensures that all required configuration and tokens are present before execution,
# and that scripts are only run from the intended management panel.
