import hashlib
import json
import os
import sys

from rich.console import Console

console = Console()

# Add the parent directory to sys.path to allow imports from sibling modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from UI.console_handler import ws_error, ws_info, ws_warning
from WebSockets import diagnostics


def check_pending_uri_updates():
    """
    Check for pending URI configuration updates.
    This function checks if there are any configuration changes to apply.
    """
    pending_file = "pending_uri_updates.json"

    if os.path.exists(pending_file):
        try:
            with open(pending_file) as f:
                pending_updates = json.load(f)

            # Print the number of pending URI updates found
            ws_info(
                "[WS_CLIENT]",
                f"[bold cyan] Found pending URI updates: {len(pending_updates)} changes[/bold cyan]",
            )

            # Apply updates to environment variables (typically done by Control Panel)
            if "uris" in pending_updates:
                os.environ["WS_URIS"] = ",".join(pending_updates["uris"])
            if "tokens" in pending_updates:
                os.environ["WS_TOKENS"] = ",".join(pending_updates["tokens"])

            # Remove the pending file after applying updates
            os.remove(pending_file)
            ws_info("[WS_CLIENT]", "[bold green] Applied pending URI updates[/bold green]")

        except Exception as e:
            # Print error if there was a problem applying updates
            ws_error(
                "[WS_CLIENT]",
                f"[bold red] Error applying pending updates: {e}[/bold red]",
            )
    else:
        # Print if no pending updates were found
        ws_info("[WS_CLIENT]", "[bold blue] No pending URI updates found[/bold blue]")


CONFIG_HASH_FILE = "uri_config_hash.txt"


def _get_current_config_hash():
    """
    Calculate the current configuration hash using SHA-256.
    """
    uri_token_pairs = diagnostics.get_ws_uris_and_tokens()
    current_config = json.dumps(uri_token_pairs, sort_keys=True)
    return hashlib.sha256(current_config.encode()).hexdigest()


def has_uri_config_changed():
    """
    Check if URI configuration has changed since last run.
    Returns True if configuration has changed.
    """
    current_hash = _get_current_config_hash()

    if os.path.exists(CONFIG_HASH_FILE):
        try:
            with open(CONFIG_HASH_FILE) as f:
                saved_hash = f.read().strip()

            if current_hash != saved_hash:
                ws_info(
                    "[WS_CLIENT]",
                    "[bold cyan] URI configuration has changed[/bold cyan]",
                )
                return True
            else:
                ws_info(
                    "[WS_CLIENT]",
                    "[bold green] URI configuration unchanged[/bold green]",
                )
                return False

        except Exception as e:
            ws_warning("[WS_CLIENT]", f" Error reading config hash: {e}")
            return True
    else:
        ws_info(
            "[WS_CLIENT]",
            "[bold cyan] No previous configuration hash found[/bold cyan]",
        )
        return True


def save_last_uri_config():
    """
    Save the current URI configuration hash for change detection.
    """
    try:
        current_hash = _get_current_config_hash()

        with open(CONFIG_HASH_FILE, "w") as f:
            f.write(current_hash)

        ws_info("[WS_CLIENT]", "[bold green] Saved URI configuration hash[/bold green]")

    except Exception as e:
        ws_error("[WS_CLIENT]", f"[bold red] Error saving config hash: {e}[/bold red]")
