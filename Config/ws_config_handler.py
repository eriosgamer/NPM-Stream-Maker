import os
import sys

# Add the parent directory to the Python path to allow importing config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg

# This module handles reading and writing WebSocket configuration (URIs and tokens)
# from/to the .env file used by the application.


def get_ws_config():
    """
    Retrieves WebSocket URIs and tokens from the .env file.
    Returns (uris, tokens, server_token).
    """
    uris = []
    tokens = []
    server_token = None

    # Check if the .env file exists and read its contents
    if os.path.exists(cfg.ENV_FILE):
        with open(cfg.ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                # Parse the WS_URIS entry
                if line.startswith("WS_URIS="):
                    uris = [
                        u.strip() for u in line.split("=", 1)[1].split(",") if u.strip()
                    ]
                # Parse the WS_TOKENS entry
                elif line.startswith("WS_TOKENS="):
                    tokens = [
                        t.strip() for t in line.split("=", 1)[1].split(",") if t.strip()
                    ]
                # Parse the WS_TOKEN_SERVER entry
                elif line.startswith("WS_TOKEN_SERVER="):
                    server_token = line.split("=", 1)[1]

    # Ensure the number of tokens matches the number of URIs
    while len(tokens) < len(uris):
        tokens.append("")

    return uris, tokens, server_token


def save_ws_config(uris=None, tokens=None, server_token=None):
    """
    Saves the WebSocket configuration (URIs, tokens, server token) to the .env file.
    Only updates the entries provided (uris, tokens, server_token).
    """
    lines = []
    found_uris = found_tokens = found_server_token = False

    # Read the existing .env file and update relevant lines
    if os.path.exists(cfg.ENV_FILE):
        with open(cfg.ENV_FILE, "r") as f:
            for line in f:
                # Update WS_URIS if new URIs are provided
                if line.startswith("WS_URIS=") and uris is not None:
                    lines.append(f"WS_URIS={','.join(uris)}\n")
                    found_uris = True
                # Update WS_TOKENS if new tokens are provided
                elif line.startswith("WS_TOKENS=") and tokens is not None:
                    lines.append(f"WS_TOKENS={','.join(tokens)}\n")
                    found_tokens = True
                # Update WS_TOKEN_SERVER if a new server token is provided
                elif line.startswith("WS_TOKEN_SERVER=") and server_token is not None:
                    lines.append(f"WS_TOKEN_SERVER={server_token}\n")
                    found_server_token = True
                    continue
                else:
                    lines.append(line)

    # Add missing entries if they were not found in the file
    if uris is not None and not found_uris:
        lines.append(f"WS_URIS={','.join(uris)}\n")
    if tokens is not None and not found_tokens:
        lines.append(f"WS_TOKENS={','.join(tokens)}\n")
    if server_token is not None and not found_server_token:
        lines.append(f"WS_TOKEN_SERVER={server_token}\n")

    # Write the updated configuration back to the .env file
    with open(cfg.ENV_FILE, "w") as f:
        f.writelines(lines)
