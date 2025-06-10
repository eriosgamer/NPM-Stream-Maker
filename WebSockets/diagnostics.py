import asyncio
import os
import sys
import websockets
import json

from rich.console import Console

# Add the parent directory to the path to allow importing local modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Client import server_querys as sq

console = Console()


def show_websocket_diagnostic():
    """
    Shows detailed WebSocket diagnostic information, including server discovery and flow validation.
    """
    console.print("\n[bold cyan]🔍 WEBSOCKET DIAGNOSTIC[/bold cyan]")

    try:

        async def run_diagnostic():
            # Retrieve the list of (uri, token) pairs from environment or .env file
            uri_token_pairs = get_ws_uris_and_tokens()

            if not uri_token_pairs:
                console.print("[bold red]❌ No servers configured[/bold red]")
                return

            console.print(
                f"[bold green]📡 Testing {len(uri_token_pairs)} configured servers...[/bold green]")

            conflict_resolution_servers = []
            wireguard_servers = []
            failed_servers = []

            # Iterate through each server and test connectivity and capabilities
            for i, (uri, token) in enumerate(uri_token_pairs, 1):
                console.print(f"\n[bold cyan]🔍 Server {i}: {uri}[/bold cyan]")

                # Test basic connectivity
                try:
                    async with websockets.connect(uri, ping_timeout=5) as websocket:
                        console.print(
                            "[bold green]  ✅ Connection: SUCCESS[/bold green]")

                        # Test token validation by sending the token and waiting for a response
                        token_data = {"token": token}
                        await websocket.send(json.dumps(token_data))
                        token_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                        token_result = json.loads(token_response)

                        if token_result.get("status") == "ok":
                            console.print(
                                "[bold green]  ✅ Token: VALID[/bold green]")

                            # Query server capabilities (type, WireGuard, conflict resolution, etc.)
                            capabilities = await sq.query_server_capabilities(uri, token)

                            if capabilities:
                                server_type = capabilities.get(
                                    "server_type", "unknown")
                                has_wg = capabilities.get(
                                    "has_wireguard", False)
                                is_cr = capabilities.get(
                                    "conflict_resolution_server", False)

                                console.print(
                                    f"[bold green]  ✅ Capabilities: {server_type.upper()}[/bold green]")
                                console.print(
                                    f"[bold white]     - WireGuard: {'YES' if has_wg else 'NO'}[/bold white]")
                                console.print(
                                    f"[bold white]     - Conflict Resolution: {'YES' if is_cr else 'NO'}[/bold white]")

                                if has_wg:
                                    wg_ip = capabilities.get("wireguard_ip")
                                    peer_ip = capabilities.get(
                                        "wireguard_peer_ip")
                                    console.print(
                                        f"[bold white]     - WG Server IP: {wg_ip or 'N/A'}[/bold white]")
                                    console.print(
                                        f"[bold white]     - WG Peer IP: {peer_ip or 'N/A'}[/bold white]")

                                if is_cr:
                                    conflict_resolution_servers.append(
                                        (uri, token, capabilities))
                                elif has_wg:
                                    wireguard_servers.append(
                                        (uri, token, capabilities))
                            else:
                                console.print(
                                    "[bold red]  ❌ Capabilities: FAILED TO QUERY[/bold red]")
                                failed_servers.append(uri)
                        else:
                            console.print(
                                "[bold red]  ❌ Token: INVALID[/bold red]")
                            failed_servers.append(uri)

                except asyncio.TimeoutError:
                    console.print(
                        "[bold red]  ❌ Connection: TIMEOUT[/bold red]")
                    failed_servers.append(uri)
                except Exception as e:
                    console.print(
                        f"[bold red]  ❌ Connection: ERROR - {e}[/bold red]")
                    failed_servers.append(uri)

            # Print a summary of the discovery process
            console.print(f"\n[bold cyan]📊 DISCOVERY SUMMARY[/bold cyan]")
            console.print(
                f"[bold green]✅ Conflict Resolution Servers: {len(conflict_resolution_servers)}[/bold green]")
            for uri, _, _ in conflict_resolution_servers:
                console.print(f"[bold white]   - {uri}[/bold white]")

            console.print(
                f"[bold blue]✅ WireGuard Servers: {len(wireguard_servers)}[/bold blue]")
            for uri, _, _ in wireguard_servers:
                console.print(f"[bold white]   - {uri}[/bold white]")

            if failed_servers:
                console.print(
                    f"[bold red]❌ Failed Servers: {len(failed_servers)}[/bold red]")
                for uri in failed_servers:
                    console.print(f"[bold white]   - {uri}[/bold white]")

            # Validate the workflow between conflict resolution and WireGuard servers
            console.print(f"\n[bold cyan]🔄 WORKFLOW VALIDATION[/bold cyan]")
            if conflict_resolution_servers and wireguard_servers:
                console.print(
                    "[bold green]✅ Complete workflow: CR server → WG servers[/bold green]")
                console.print(
                    f"[bold white]   1. Ports sent to: {conflict_resolution_servers[0][0]}[/bold white]")
                console.print(
                    f"[bold white]   2. Approved ports forwarded to {len(wireguard_servers)} WG server(s)[/bold white]")
            elif conflict_resolution_servers:
                console.print(
                    "[bold yellow]⚠️  Only conflict resolution available (no WG servers)[/bold yellow]")
            elif wireguard_servers:
                console.print(
                    "[bold yellow]⚠️  Only WireGuard servers available (no conflict resolution)[/bold yellow]")
            else:
                console.print(
                    "[bold red]❌ No functional servers detected[/bold red]")

        asyncio.run(run_diagnostic())

    except Exception as e:
        console.print(f"[bold red]❌ Diagnostic failed: {e}[/bold red]")


def get_ws_uris_and_tokens():
    """
    Returns a list of (uri, token) tuples read from .env or environment variables.
    Does not modify the configuration, only reads it.
    """
    uris = []
    tokens = []
    env_path = ".env"
    
    console.print(f"[bold cyan][WS_CLIENT][/bold cyan] Loading configuration from {env_path}")
    
    # First try environment variables (passed from Control Panel)
    env_uris = os.environ.get("WS_URIS")
    env_tokens = os.environ.get("WS_TOKENS")
    
    if env_uris:
        uris = [uri.strip() for uri in env_uris.split(",") if uri.strip()]
    if env_tokens:
        tokens = [token.strip() for token in env_tokens.split(",") if token.strip()]
    
    # If not in environment, read from .env file
    if not uris or not tokens:
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("WS_URIS=") and not uris:
                        uris_str = line.split("=", 1)[1]
                        uris = [uri.strip() for uri in uris_str.split(",") if uri.strip()]
                    elif line.startswith("WS_TOKENS=") and not tokens:
                        tokens_str = line.split("=", 1)[1]
                        tokens = [token.strip() for token in tokens_str.split(",") if token.strip()]
        else:
            console.print(f"[bold red][WS_CLIENT][/bold red] Configuration file {env_path} not found")
    
    if not uris:
        console.print("[bold red][WS_CLIENT][/bold red] No WebSocket URIs configured")
        return []
    
    if not tokens:
        console.print("[bold red][WS_CLIENT][/bold red] No WebSocket tokens configured")
        return []
    
    # If only one token, use it for all URIs
    if len(tokens) == 1 and len(uris) > 1:
        tokens = tokens * len(uris)
    
    # If tokens < uris, pad with last token
    if len(tokens) < len(uris) and tokens:
        last_token = tokens[-1]
        tokens.extend([last_token] * (len(uris) - len(tokens)))
    
    # If tokens > uris, truncate tokens
    if len(tokens) > len(uris):
        tokens = tokens[:len(uris)]
    
    uri_token_pairs = list(zip(uris, tokens))
    console.print(f"[bold green][WS_CLIENT][/bold green] Configured {len(uri_token_pairs)} URI-token pairs:")
    
    # Show configuration summary (without exposing full tokens)
    for i, (uri, token) in enumerate(uri_token_pairs, 1):
        masked_token = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "***"
        console.print(f"[bold white]  {i}. {uri} (token: {masked_token})[/bold white]")
    
    return uri_token_pairs
