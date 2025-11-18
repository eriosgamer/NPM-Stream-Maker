import os
import sys
import json
from rich.console import Console

console = Console()

# Add the parent directory to sys.path to allow imports from sibling modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from WebSockets import diagnostics
from UI.console_handler import ws_error, ws_info, ws_warning

def check_pending_uri_updates():
    """
    Check for pending URI configuration updates.
    This function checks if there are any configuration changes to apply.
    """
    pending_file = "pending_uri_updates.json"

    if os.path.exists(pending_file):
        try:
            with open(pending_file, "r") as f:
                pending_updates = json.load(f)

            # Print the number of pending URI updates found
            ws_info("[WS_CLIENT]", f"[bold cyan] Found pending URI updates: {len(pending_updates)} changes[/bold cyan]")

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
            ws_error("[WS_CLIENT]", f"[bold red] Error applying pending updates: {e}[/bold red]")
    else:
        # Print if no pending updates were found
        ws_info("[WS_CLIENT]", "[bold blue] No pending URI updates found[/bold blue]")


# Copied
def has_uri_config_changed():
    """
    Check if URI configuration has changed since last run.
    Returns True if configuration has changed.
    """
    config_hash_file = "uri_config_hash.txt"

    # Get current configuration (list of URI/token pairs)
    uri_token_pairs = diagnostics.get_ws_uris_and_tokens()
    current_config = json.dumps(uri_token_pairs, sort_keys=True)

    # Calculate current hash using MD5
    import hashlib
    current_hash = hashlib.md5(current_config.encode()).hexdigest()

    # Check against saved hash from previous run
    if os.path.exists(config_hash_file):
        try:
            with open(config_hash_file, "r") as f:
                saved_hash = f.read().strip()

            if current_hash != saved_hash:
                # Print if configuration has changed
                ws_info("[WS_CLIENT]", "[bold cyan] URI configuration has changed[/bold cyan]")
                return True
            else:
                # Print if configuration is unchanged
                ws_info("[WS_CLIENT]", "[bold green] URI configuration unchanged[/bold green]")
                return False

        except Exception as e:
            # Print warning if there was a problem reading the hash
            ws_warning("[WS_CLIENT]", f" Error reading config hash: {e}")
            return True
    else:
        # Print if no previous configuration hash was found
        ws_info("[WS_CLIENT]", "[bold cyan] No previous configuration hash found[/bold cyan]")
        return True


# Copied
def save_last_uri_config():
    """
    Save the current URI configuration hash for change detection.
    """
    config_hash_file = "uri_config_hash.txt"

    try:
        # Get current configuration (list of URI/token pairs)
        uri_token_pairs = diagnostics.get_ws_uris_and_tokens()
        current_config = json.dumps(uri_token_pairs, sort_keys=True)

        # Calculate and save hash using MD5
        import hashlib
        current_hash = hashlib.md5(current_config.encode()).hexdigest()

        with open(config_hash_file, "w") as f:
            f.write(current_hash)

        # Print confirmation that the hash was saved
        ws_info("[WS_CLIENT]", "[bold green] Saved URI configuration hash[/bold green]")

    except Exception as e:
        # Print error if there was a problem saving the hash
        ws_error("[WS_CLIENT]", f"[bold red] Error saving config hash: {e}[/bold red]")
