import os
import secrets
import sys

# Add the parent directory to sys.path to allow importing configuration modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import ws_config_handler as WebSocketConfig
from Config import config as cfg

# This module handles the creation, retrieval, and loading of WebSocket authentication tokens
# for both server and client modes. It interacts with configuration files and environment variables
# to securely manage tokens.

def get_or_create_token(console, mode):
    """
    Gets or creates a token for the specified mode ("server" or "client").
    For "server", generates and saves a token if it does not exist.
    For "client", returns the configured tokens.
    """
    uris, tokens, server_token = WebSocketConfig.get_ws_config()

    if mode == "server":
        # Only generate a new token if one does not exist in the .env file
        if not server_token:
            new_token = secrets.token_urlsafe(32)
            server_token = new_token
            WebSocketConfig.save_ws_config(server_token=server_token)
            console.print(
                f"[green]WebSocket server token generated and saved in {cfg.ENV_FILE}[/green]")
            console.print(
                f"[yellow]Server Token: [bold]{server_token}[/bold][/yellow]")
        else:
            console.print(
                f"[green]WebSocket server token already exists in {cfg.ENV_FILE}[/green]")
            console.print(
                f"[yellow]Server Token: [bold]{server_token}[/bold][/yellow]")
        # Set the token as an environment variable for the server
        os.environ["WS_TOKEN_SERVER"] = server_token
        return server_token

    elif mode == "client":
        # Print and return the configured client tokens
        console.print(WebSocketConfig.get_ws_config())
        return tokens

# Redundant import, but kept for clarity in this context
import os

def load_ws_token():
    """
    Loads the server token from the .env file using the WS_TOKEN_SERVER variable.
    If it does not exist, returns None (do not use a default value for security reasons).
    """
    env_file = ".env"
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                if line.startswith("WS_TOKEN_SERVER="):
                    return line.strip().split("=", 1)[1]
    return None
