"""
ws_server_messages.py

This module handles the communication between the client and the WebSocket server.
It processes incoming messages, sends notifications about port conflicts, broadcasts messages,
and manages the sequential flow for sending port information to the server.
It also handles token validation, port scanning, and removal of inactive ports.

Dependencies:
- asyncio, websockets: For asynchronous networking.
- rich.console: For colored console output.
- Custom modules: ws_client, websocket_config, ws_config_handler, config, wireguard_tools, port_scanner, diagnostics.

Author: eriosgamer
"""

import asyncio
import os
import sys
import json
import time
import socket
import websockets
from rich.console import Console

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ports import port_scanner
from Wireguard import wireguard_tools as wg_tools
from Core import message_handler as msg_handler
from Config import config as cfg
from WebSockets import websocket_config as ws_config
from Client import ws_client_main_thread as wsc
from UI.console_handler import ws_info, ws_error, ws_success, ws_warning

# Set to keep track of ports already sent to the server
sent_ports = set()
# Dictionary to keep track of the last time each port was seen active
port_last_seen = {}

console = Console()

# =========================
# Main message handler loop
# =========================


async def handle_server_messages(websocket):
    """
    Handles incoming messages from the WebSocket server.
    Processes each received message asynchronously.
    """
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                message_type = data.get("type")
                if message_type and message_type.startswith("client_"):
                    await msg_handler.handle_server_message(data)
            except json.JSONDecodeError as e:
                ws_error("[WS_CLIENT]", f"Invalid JSON received: {e}")
            except Exception as e:
                ws_error("[WS_CLIENT]", f"Error handling server message: {e}")
    except websockets.ConnectionClosed:
        ws_info("[WS_CLIENT]", "Server connection closed")
    except Exception as e:
        ws_error("[WS_CLIENT]", f"Error in message handler: {e}")


# =========================
# Port conflict notification
# =========================


async def send_port_conflict_notification(websocket, conflict_info):
    """
    Sends a port conflict notification to the server.
    """
    try:
        message = {
            "type": "port_conflict",
            "conflict_info": conflict_info,
            "timestamp": time.time(),
        }
        await websocket.send(json.dumps(message))
        ws_info("[WS_CLIENT]", f"Sent port conflict notification: {conflict_info}")
    except Exception as e:
        ws_error("[WS_CLIENT]", f"Error sending conflict notification: {e}")


# =========================
# Broadcast message sender
# =========================


async def send_broadcast_message(websocket, message_type, message_data):
    """
    Sends a broadcast message to the server with additional information.
    """
    try:
        local_ip = wg_tools.get_local_ip()
        hostname = socket.gethostname()

        message = {
            "token": "your_token_here",  # Will be replaced by calling function
            "ip": local_ip,
            "hostname": hostname,
            "broadcast_message": {"type": message_type, **message_data},
        }

        await websocket.send(json.dumps(message))
        ws_info("[WS_CLIENT]", f"Sent broadcast message: {message_type}")
    except Exception as e:
        ws_error("[WS_CLIENT]", f"Error sending broadcast message: {e}")


# =========================
# Sequential port sending logic
# =========================


async def send_ports_to_server_sequential(
    websocket, token, local_ip, hostname, new_ports
):
    """
    Sends ports to the server following the sequential flow:
    1. Sends to conflict resolution server.
    2. Processes the response and resolves conflicts.
    3. Sends the approved port list to the WireGuard servers.

    This function is responsible for:
    - Connecting to the WebSocket server.
    - Validating the authentication token.
    - Scanning for allowed and listening ports.
    - Sending new ports to the server.
    - Removing inactive ports.
    - Handling reconnection and error logic.

    Args:
        websocket: The websocket connection object.
        token: Authentication token for the server.
        local_ip: Local IP address of the client.
        hostname: Hostname of the client.
        new_ports: Set of new ports to send.
    """
    ws_info(
        "[WS_CLIENT]",
        f"Starting client task for {ws_config.uri} (first server: {ws_config.is_first_server})",
    )

    max_connection_errors = 5  # Set a default or configurable value

    while True:
        try:
            ws_info("[WS_CLIENT]", f"Connecting to {ws_config.uri}...")

            async with websockets.connect(
                ws_config.uri,
                ping_interval=60,  # Aumentado para mejor estabilidad
                ping_timeout=30,  # Aumentado de 10 a 30 segundos
                close_timeout=10,  # Mantenido en 10 segundos
                max_size=2**20,
                max_queue=32,
                compression=None,
            ) as websocket:
                connection_errors = 0  # Reset error count on successful connection
                ws_success("[WS_CLIENT]", f"Connected to {ws_config.uri}")

                # Send token validation first
                token_data = {"token": token}
                await websocket.send(json.dumps(token_data))

                # Wait for token validation response
                try:
                    response_msg = await asyncio.wait_for(websocket.recv(), timeout=10)
                    response = json.loads(response_msg)
                    if response.get("status") != "ok":
                        ws_error(
                            "[WS_CLIENT]",
                            f"Token validation failed for {ws_config.uri}",
                        )
                        continue
                    ws_success("[WS_CLIENT]", f"Token validated for {ws_config.uri}")
                except Exception as e:
                    ws_error(
                        "[WS_CLIENT]",
                        f"Token validation error for {ws_config.uri}: {e}",
                    )
                    continue

                # Only process ports if this is the first server
                if not ws_config.is_first_server:
                    ws_info(
                        "[WS_CLIENT]",
                        f"This is not the first server ({ws_config.uri}), waiting for port forwarding from first server...",
                    )

                    # Keep connection alive but don't actively scan ports
                    while True:
                        await asyncio.sleep(
                            getattr(websocket, "ping_interval", 60)
                        )  # Wait for ping interval
                        # Handle any incoming messages (like port assignments)
                        try:
                            # Non-blocking check for messages
                            incoming_msg = await asyncio.wait_for(
                                websocket.recv(), timeout=1
                            )
                            await msg_handler.handle_server_message(
                                json.loads(incoming_msg)
                            )
                        except asyncio.TimeoutError:
                            pass  # No message, continue
                        except Exception as e:
                            ws_error(
                                "[WS_CLIENT]",
                                f"Error handling message on {ws_config.uri}: {e}",
                            )

                    return  # Exit this task for non-first servers

                # Main loop (only for first server)
                while True:
                    ws_info(
                        "[WS_CLIENT]",
                        f"Checking listening ports for first server {ws_config.uri}...",
                    )
                    current_ports = port_scanner.get_listening_ports_with_proto()
                    allowed_and_listening = [
                        (port, proto)
                        for port, proto in current_ports
                        if port in wsc.allowed_ports
                    ]

                    ws_info("[WS_CLIENT]", f"Detected ports: {len(current_ports)}")
                    ws_info(
                        "[WS_CLIENT]",
                        f"Allowed and listening ports: {len(allowed_and_listening)}",
                    )

                    # Check for new ports
                    current_port_set = set(allowed_and_listening)
                    new_ports = current_port_set - sent_ports

                    if new_ports:
                        ws_info(
                            "[WS_CLIENT]",
                            f"Found {len(new_ports)} new ports - starting sequential processing...",
                        )
                        success = await send_ports_to_server_sequential(
                            websocket, token, local_ip, hostname, new_ports
                        )

                        if success:
                            sent_ports.update(new_ports)
                            for port, proto in new_ports:
                                port_last_seen[(port, proto)] = time.time()
                            ws_info(
                                "[WS_CLIENT]",
                                f"Successfully processed {len(new_ports)} new ports via sequential flow",
                            )
                        else:
                            ws_error(
                                "[WS_CLIENT]",
                                f"Failed to process ports via sequential flow",
                            )

                    # Update last seen times for current ports
                    current_time = time.time()
                    for port, proto in current_port_set:
                        port_last_seen[(port, proto)] = current_time

                    # Check for inactive ports
                    inactive_ports = []
                    for (port, proto), last_seen in list(port_last_seen.items()):
                        if current_time - last_seen > wsc.inactive_timeout:
                            inactive_ports.append({"puerto": port, "protocolo": proto})
                            del port_last_seen[(port, proto)]
                            sent_ports.discard((port, proto))

                    if inactive_ports:
                        ws_warning(
                            "[WS_CLIENT]",
                            f"Removing {len(inactive_ports)} inactive ports",
                        )
                        remove_data = {
                            "type": "remove_ports",
                            "token": token,
                            "remove_ports": inactive_ports,
                        }
                        await websocket.send(json.dumps(remove_data))

                    # Wait before next check
                    ws_info(
                        "[WS_CLIENT]",
                        f"Waiting {getattr(websocket, 'ping_interval', 60)} seconds before next check...",
                    )
                    await asyncio.sleep(getattr(websocket, "ping_interval", 60))

        except websockets.exceptions.ConnectionClosed as e:
            connection_errors += 1
            ws_error("[WS_CLIENT]", f"Connection to {ws_config.uri} closed: {e}")

        except Exception as e:
            connection_errors += 1
            ws_error("[WS_CLIENT]", f"Error in connection to {ws_config.uri}: {e}")

        if connection_errors >= max_connection_errors:
            ws_error(
                "[WS_CLIENT]",
                f"Too many connection errors for {ws_config.uri}, stopping...",
            )
            break

        # Wait before reconnection
        await asyncio.sleep(5)
