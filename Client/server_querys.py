import asyncio
import time
import websockets
import json
from rich.console import Console
from UI.console_handler import ws_info, ws_error
from WebSockets import diagnostics as diagnostics

console = Console()

# This module provides utility functions for querying server capabilities and sending ports
# to a conflict resolution server over WebSocket connections.


async def query_server_capabilities(uri, token):
    """
    Query the capabilities of a WebSocket server.
    Lets the client know if the server has WireGuard or is a conflict resolution server.
    Returns a dictionary with the capabilities or None if the query fails.

    Args:
        uri (str): WebSocket server URI
        token (str): Authentication token

    Returns:
        dict: Server capabilities or None if query failed
    """
    try:
        async with websockets.connect(
            uri,
            ping_timeout=60,  # Increased from 30 to 60 seconds
            ping_interval=120,  # Increased from 60 to 120 seconds
            close_timeout=20,  # Added close timeout
        ) as websocket:
            # Send token for authentication
            token_data = {"token": token}
            await websocket.send(json.dumps(token_data))

            # Wait for token validation
            token_response = await asyncio.wait_for(
                websocket.recv(), timeout=15
            )  # Increased timeout
            token_result = json.loads(token_response)

            if token_result.get("status") != "ok":
                ws_error("[WS_CLIENT]", f"Token validation failed for {uri}")
                return None

            # Query server capabilities
            capabilities_query = {
                "type": "query_capabilities",
                "token": token,
                "query_capabilities": True,
            }

            await websocket.send(json.dumps(capabilities_query))

            # Wait for capabilities response
            capabilities_response = await asyncio.wait_for(
                websocket.recv(), timeout=15
            )  # Increased timeout
            capabilities = json.loads(capabilities_response)

            if capabilities.get("status") == "ok":
                server_caps = capabilities.get("server_capabilities", {})
                ws_info("[WS_CLIENT]", f"Server {uri} capabilities:")
                ws_info(
                    "[WS_CLIENT]",
                    f"  - Type: {server_caps.get('server_type', 'unknown')}",
                )
                ws_info(
                    "[WS_CLIENT]",
                    f"  - Has WireGuard: {server_caps.get('has_wireguard', False)}",
                )
                ws_info(
                    "[WS_CLIENT]",
                    f"  - Conflict Resolution: {server_caps.get('conflict_resolution_server', False)}",
                )
                return server_caps
            else:
                ws_error(
                    "[WS_CLIENT]",
                    f"Failed to query capabilities for {uri}: {capabilities.get('msg', 'unknown error')}",
                )
                return None

    except Exception as e:
        ws_error("[WS_CLIENT]", f"Error querying capabilities for {uri}: {e}")
        return None


# Copied
async def send_ports_to_conflict_resolution_server(
    uri, token, local_ip, hostname, new_ports
):
    """
    Sends a list of ports to a conflict resolution server and gets the processed results.
    Returns the server's response or None if it fails.

    Args:
        uri (str): WebSocket server URI
        token (str): Authentication token
        local_ip (str): Client's local IP address
        hostname (str): Client's hostname
        new_ports (set): Set of (port, protocol) tuples to send

    Returns:
        dict: Server response or None if failed
    """
    ws_info(
        "[WS_CLIENT]",
        f"Sending {len(new_ports)} ports to conflict resolution server: {uri}",
    )

    try:
        async with websockets.connect(
            uri,
            ping_timeout=60,  # Increased from 15 to 60 seconds
            ping_interval=120,  # Added ping interval
            close_timeout=20,  # Added close timeout
        ) as websocket:
            # Send token for authentication
            token_data = {"token": token}
            await websocket.send(json.dumps(token_data))

            # Wait for token validation
            token_response = await asyncio.wait_for(
                websocket.recv(), timeout=15
            )  # Increased timeout
            token_result = json.loads(token_response)

            if token_result.get("status") != "ok":
                ws_error("[WS_CLIENT]", "Token validation failed")
                return None

            # Send ports for conflict resolution
            data = {
                "type": "conflict_resolution_ports",
                "ip": local_ip,
                "hostname": hostname,
                "token": token,
                "timestamp": int(time.time()),
                "ports": [
                    {"port": port, "protocol": proto} for port, proto in new_ports
                ],
                "ports_pre_approved": False,  # Not pre-approved for conflict resolution
            }

            await websocket.send(json.dumps(data))

            # Wait for response
            response_msg = await asyncio.wait_for(
                websocket.recv(), timeout=45
            )  # Increased from 30 to 45 seconds
            response = json.loads(response_msg)

            if response.get("status") == "ok":
                ws_info("[WS_CLIENT]", "Conflict resolution successful")
                # Log cantidad de puertos aprobados
                resultados = response.get("resultados", [])
                ws_info("[WS_CLIENT]", f"Puertos aprobados por CR: {len(resultados)}")
                return response
            else:
                ws_error(
                    "[WS_CLIENT]",
                    f"Conflict resolution failed: {response.get('msg', 'unknown error')}",
                )
                return None

    except Exception as e:
        ws_error("[WS_CLIENT]", f"Error with conflict resolution server: {e}")
        return None


async def send_pre_approved_ports_to_wireguard_servers(approved_ports, local_ip, hostname):
    """
    Sends approved ports to all configured WireGuard servers.
    Uses diagnostics.get_ws_uris_and_tokens to get URIs/tokens, queries capabilities,
    and sends the pre-approved payload to any server that reports as a WG server.
    """
    from WebSockets import diagnostics as diag

    if not approved_ports:
        ws_info("[WS_CLIENT]", "No approved ports to forward to WireGuard servers")
        return []

    uri_token_pairs = diag.get_ws_uris_and_tokens()
    successes = []
    for uri, token in uri_token_pairs:
        try:
            caps = await query_server_capabilities(uri, token)
            if not caps:
                continue
            if not caps.get("has_wireguard", False):
                continue

            ws_info("[WS_CLIENT]", f"Forwarding pre-approved ports to WG server: {uri}")
            async with websockets.connect(uri, ping_timeout=60, ping_interval=120, close_timeout=20) as websocket:
                # Send token for auth
                await websocket.send(json.dumps({"token": token}))
                token_response = await asyncio.wait_for(websocket.recv(), timeout=10)
                token_result = json.loads(token_response)
                if token_result.get("status") != "ok":
                    ws_error("[WS_CLIENT]", f"Token validation failed for {uri}")
                    continue

                wg_data = {
                    "type": "conflict_resolution_ports",
                    "token": token,
                    "ip": local_ip,
                    "hostname": hostname,
                    "ports": approved_ports,
                    "ports_pre_approved": True,
                }
                await websocket.send(json.dumps(wg_data))
                resp = await asyncio.wait_for(websocket.recv(), timeout=15)
                r = json.loads(resp)
                if r.get("status") == "ok":
                    successes.append(uri)
                    ws_info("[WS_CLIENT]", f"WG server {uri} processed approved ports")
                else:
                    ws_error("[WS_CLIENT]", f"WG server {uri} rejected approved ports: {r}")
        except Exception as e:
            ws_error("[WS_CLIENT]", f"Error sending to WG server {uri}: {e}")
            continue

    return successes


# --- Module summary ---
# This file contains asynchronous functions for:
# - Querying server capabilities (WireGuard, conflict resolution, etc.)
# - Sending port lists to a conflict resolution server and handling the response.
# All communication is done via WebSocket using JSON messages.
