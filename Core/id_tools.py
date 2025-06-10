import sys, os
from rich.console import Console

# Initialize a rich console for colored output
console = Console()

# Add the parent directory to sys.path to allow module imports from parent
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from WebSockets import diagnostics
from Client import server_querys as sq

# ---------------------------------------------------------------
# This module provides tools for discovering and classifying
# configured servers based on their capabilities.
# ---------------------------------------------------------------

async def discover_server_types():
    """
    Discovers the types of all configured servers and organizes them into two lists:
    - conflict_resolution_servers: servers for conflict resolution
    - wireguard_servers: servers with WireGuard capability
    Returns a tuple with both lists.
    """
    # Retrieve list of (uri, token) pairs for all configured servers
    uri_token_pairs = diagnostics.get_ws_uris_and_tokens()

    if not uri_token_pairs:
        console.print("[bold red][WS_CLIENT][/bold red] No servers configured")
        return [], []

    console.print(f"[bold cyan][WS_CLIENT][/bold cyan] Discovering capabilities of {len(uri_token_pairs)} servers...")

    conflict_resolution_servers = []
    wireguard_servers = []

    # Iterate through each server and query its capabilities
    for i, (uri, token) in enumerate(uri_token_pairs, 1):
        console.print(f"[bold cyan][WS_CLIENT][/bold cyan] Querying server {i}/{len(uri_token_pairs)}: {uri}")

        try:
            # Query the server for its capabilities
            capabilities = await sq.query_server_capabilities(uri, token)

            if capabilities:
                # Check if the server is a conflict resolution server
                if capabilities.get("conflict_resolution_server", False):
                    conflict_resolution_servers.append((uri, token, capabilities))
                    console.print(f"[bold yellow][WS_CLIENT][/bold yellow] ✓ Conflict resolution server: {uri}")
                # Check if the server has WireGuard capability
                elif capabilities.get("has_wireguard", False):
                    wireguard_servers.append((uri, token, capabilities))
                    console.print(f"[bold blue][WS_CLIENT][/bold blue] ✓ WireGuard server: {uri}")
                else:
                    # Unknown server type
                    console.print(f"[bold red][WS_CLIENT][/bold red] ⚠ Unknown server type: {uri}")
                    console.print(f"[bold white]    Capabilities: {capabilities}[/bold white]")
            else:
                # Failed to get capabilities from the server
                console.print(f"[bold red][WS_CLIENT][/bold red] ✗ Failed to query: {uri}")

        except Exception as e:
            # Handle errors during querying
            console.print(f"[bold red][WS_CLIENT][/bold red] ✗ Error querying {uri}: {e}")

    # Print summary of discovered servers
    console.print(f"[bold green][WS_CLIENT][/bold green] Discovery complete:")
    console.print(f"[bold white]  - Conflict resolution servers: {len(conflict_resolution_servers)}[/bold white]")
    console.print(f"[bold white]  - WireGuard servers: {len(wireguard_servers)}[/bold white]")

    return conflict_resolution_servers, wireguard_servers
