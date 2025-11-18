import asyncio
import os
import sys
import websockets
import json
from dotenv import load_dotenv

from rich.console import Console

# Add the parent directory to the path to allow importing local modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Client import server_querys as sq
from UI.console_handler import ws_info, ws_error, ws_warning

console = Console()


def show_websocket_diagnostic():
    """
    Shows detailed WebSocket diagnostic information, including server discovery and flow validation.
    """
    ws_info("[WS_CLIENT]", "\n[bold cyan]🔍 WEBSOCKET DIAGNOSTIC[/bold cyan]")

    try:

        async def run_diagnostic():
            # Retrieve the list of (uri, token) pairs from environment or .env file
            uri_token_pairs = get_ws_uris_and_tokens()

            if not uri_token_pairs:
                ws_error("[WS_CLIENT]", "[bold red]❌ No servers configured[/bold red]")
                return

            ws_info("[WS_CLIENT]", f"[bold green]📡 Testing {len(uri_token_pairs)} configured servers...[/bold green]")

            conflict_resolution_servers = []
            wireguard_servers = []
            failed_servers = []

            # Iterate through each server and test connectivity and capabilities
            for i, (uri, token) in enumerate(uri_token_pairs, 1):
                ws_info("[WS_CLIENT]", f"\n[bold cyan]🔍 Server {i}: {uri}[/bold cyan]")

                # Test basic connectivity
                try:
                    async with websockets.connect(
                        uri,
                        ping_interval=60,  # Increased from 5 to 60 seconds
                        ping_timeout=30,   # Added ping timeout
                        close_timeout=10   # Added close timeout
                    ) as websocket:
                        ws_info("[WS_CLIENT]", "[bold green]  ✅ Connection: SUCCESS[/bold green]")

                        # Test token validation by sending the token and waiting for a response
                        token_data = {"token": token}
                        await websocket.send(json.dumps(token_data))
                        token_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                        token_result = json.loads(token_response)

                        if token_result.get("status") == "ok":
                            ws_info("[WS_CLIENT]", "[bold green]  ✅ Token: VALID[/bold green]")

                            # Query server capabilities (type, WireGuard, conflict resolution, etc.)
                            capabilities = await sq.query_server_capabilities(uri, token)

                            if capabilities:
                                server_type = capabilities.get(
                                    "server_type", "unknown")
                                has_wg = capabilities.get(
                                    "has_wireguard", False)
                                is_cr = capabilities.get(
                                    "conflict_resolution_server", False)

                                ws_info("[WS_CLIENT]", f"[bold green]  ✅ Capabilities: {server_type.upper()}[/bold green]")
                                ws_info("[WS_CLIENT]", f"[bold white]     - WireGuard: {'YES' if has_wg else 'NO'}[/bold white]")
                                ws_info("[WS_CLIENT]", f"[bold white]     - Conflict Resolution: {'YES' if is_cr else 'NO'}[/bold white]")

                                if has_wg:
                                    wg_ip = capabilities.get("wireguard_ip")
                                    peer_ip = capabilities.get(
                                        "wireguard_peer_ip")
                                    ws_info("[WS_CLIENT]", f"[bold white]     - WG Server IP: {wg_ip or 'N/A'}[/bold white]")
                                    ws_info("[WS_CLIENT]", f"[bold white]     - WG Peer IP: {peer_ip or 'N/A'}[/bold white]")

                                if is_cr:
                                    conflict_resolution_servers.append(
                                        (uri, token, capabilities))
                                elif has_wg:
                                    wireguard_servers.append(
                                        (uri, token, capabilities))
                            else:
                                ws_error("[WS_CLIENT]", "  ❌ Capabilities: FAILED TO QUERY")
                                failed_servers.append(uri)
                        else:
                            ws_error("[WS_CLIENT]", "  ❌ Token: INVALID")
                            failed_servers.append(uri)

                except asyncio.TimeoutError:
                    ws_error("[WS_CLIENT]", "  ❌ Connection: TIMEOUT")
                    failed_servers.append(uri)
                except Exception as e:
                    ws_error("[WS_CLIENT]", f"  ❌ Connection: ERROR - {e}")
                    failed_servers.append(uri)

            # Print a summary of the discovery process
            ws_info("[WS_CLIENT]", f"\n[bold cyan]📊 DISCOVERY SUMMARY[/bold cyan]")
            ws_info("[WS_CLIENT]", f"[bold green]✅ Conflict Resolution Servers: {len(conflict_resolution_servers)}[/bold green]")
            for uri, _, _ in conflict_resolution_servers:
                ws_info("[WS_CLIENT]", f"[bold white]   - {uri}[/bold white]")

            ws_info("[WS_CLIENT]", f"[bold blue]✅ WireGuard Servers: {len(wireguard_servers)}[/bold blue]")
            for uri, _, _ in wireguard_servers:
                ws_info("[WS_CLIENT]", f"[bold white]   - {uri}[/bold white]")

            if failed_servers:
                ws_info("[WS_CLIENT]", f"[bold red]❌ Failed Servers: {len(failed_servers)}[/bold red]")
                for uri in failed_servers:
                    ws_info("[WS_CLIENT]", f"[bold white]   - {uri}[/bold white]")

            ws_info("[WS_CLIENT]", f"[bold blue]✅ WireGuard Servers: {len(wireguard_servers)}[/bold blue]")
            for uri, _, _ in wireguard_servers:
                ws_info("[WS_CLIENT]", f"[bold white]   - {uri}[/bold white]")

            if failed_servers:
                ws_info("[WS_CLIENT]", f"[bold red]❌ Failed Servers: {len(failed_servers)}[/bold red]")
                for uri in failed_servers:
                    ws_info("[WS_CLIENT]", f"[bold white]   - {uri}[/bold white]")

            # Validate the workflow between conflict resolution and WireGuard servers
            ws_info("[WS_CLIENT]", f"\n[bold cyan]🔄 WORKFLOW VALIDATION[/bold cyan]")
            if conflict_resolution_servers and wireguard_servers:
                ws_info("[WS_CLIENT]", "[bold green]✅ Complete workflow: CR server → WG servers[/bold green]")
                ws_info("[WS_CLIENT]", f"[bold white]   1. Ports sent to: {conflict_resolution_servers[0][0]}[/bold white]")
                ws_info("[WS_CLIENT]", f"[bold white]   2. Approved ports forwarded to {len(wireguard_servers)} WG server(s)[/bold white]")
            elif conflict_resolution_servers:
                ws_info("[WS_CLIENT]", "[bold yellow]⚠️  Only conflict resolution available (no WG servers)[/bold yellow]")
            elif wireguard_servers:
                ws_info("[WS_CLIENT]", "[bold yellow]⚠️  Only WireGuard servers available (no conflict resolution)[/bold yellow]")
            else:
                ws_info("[WS_CLIENT]", "[bold red]❌ No functional servers detected[/bold red]")

        asyncio.run(run_diagnostic())

    except Exception as e:
        ws_error("[WS_CLIENT]", f"[bold red]❌ Diagnostic failed: {e}[/bold red]")

def get_ws_uris_and_tokens():
    """
    Returns a list of (uri, token) tuples read from .env or environment variables.
    Does not modify the configuration, only reads it.
    """
    uris = []
    tokens = []
    env_path = ".env"

    ws_info("[WS_CLIENT]", f"[bold cyan] Loading configuration from {env_path}[/bold cyan]")

    # First try environment variables (passed from Control Panel)
    env_uris = os.environ.get("WS_URIS")
    env_tokens = os.environ.get("WS_TOKENS")
    
    if env_uris:
        uris = [uri.strip() for uri in env_uris.split(",") if uri.strip()]
    if env_tokens:
        tokens = [token.strip() for token in env_tokens.split(",") if token.strip()]
    
    # If not in environment, read from .env file using dotenv
    if not uris or not tokens:
        load_dotenv(env_path)
        if not uris:
            env_uris = os.getenv("WS_URIS")
            if env_uris:
                uris = [uri.strip() for uri in env_uris.split(",") if uri.strip()]
        if not tokens:
            env_tokens = os.getenv("WS_TOKENS")
            if env_tokens:
                tokens = [token.strip() for token in env_tokens.split(",") if token.strip()]
    
    if not uris:
        ws_info("[WS_CLIENT]", "[bold red]❌ No WebSocket URIs configured[/bold red]")
        ws_info("[WS_CLIENT]", "[bold yellow]⚠️  Assuming first startup or server-only usage[/bold yellow]")
        return []
    
    if not tokens:
        ws_info("[WS_CLIENT]", "[bold red]❌ No WebSocket tokens configured[/bold red]")
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
    ws_info("[WS_CLIENT]", f"[bold green] Configured {len(uri_token_pairs)} URI-token pairs:[/bold green]")
    
    # Show configuration summary (without exposing full tokens)
    for i, (uri, token) in enumerate(uri_token_pairs, 1):
        masked_token = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "***"
        ws_info("[WS_CLIENT]", f"[bold white]  {i}. {uri} (token: {masked_token})[/bold white]")
    
    return uri_token_pairs
