"""
remote_handler.py

This module provides asynchronous functions for managing remote servers via WebSocket.
It allows sending commands, broadcasting actions, managing streams, updating configurations,
and handling connections for a set of remote servers. The module uses the 'rich' library
for enhanced console output and user prompts.

Main features:
- Send remote commands to individual or multiple servers.
- Broadcast administrative actions (restart, update, sync, clear) to all or filtered servers.
- Manage streams remotely (create, delete, list).
- Update port and forwarding information across servers.
- Show connection and server status in formatted tables.
- Handle connection health and reconnection logic.

Intended for use in a system where multiple servers are orchestrated remotely,
such as in a streaming or network management context.
"""

import asyncio
import json
import time
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
import websockets

console = Console()

async def send_remote_command(self, server_key, command, params=None):
    """
    Sends a remote command to a specific server.
    Waits for the response and processes it.
    """
    if server_key not in self.connections:
        console.print(
            f"[bold red][REMOTE][/bold red] No connection to server {server_key}")
        return None

    # Ensure connection is alive
    if not await self.ensure_connection(server_key):
        console.print(
            f"[bold red][REMOTE][/bold red] Could not establish connection to {server_key}")
        return None

    connection = self.connections[server_key]
    websocket = connection["websocket"]
    token = connection["token"]

    try:
        command_data = {
            "token": token,
            "remote_command": command,
            "timestamp": int(time.time())
        }

        if params:
            command_data.update(params)

        console.print(
            f"[bold cyan][REMOTE][/bold cyan] Sending command '{command}' to {server_key}")
        await websocket.send(json.dumps(command_data))

        # Wait for response with longer timeout
        response = await asyncio.wait_for(websocket.recv(), timeout=60)  # Aumentado de 45 a 60 segundos
        result = json.loads(response)

        # Update last ping time
        connection["last_ping"] = time.time()

        if result.get("status") == "ok":
            console.print(
                f"[bold green][REMOTE][/bold green] Command '{command}' successful on {server_key}")
            return result
        else:
            error_msg = result.get("msg", "Unknown error")
            console.print(
                f"[bold red][REMOTE][/bold red] Command '{command}' failed on {server_key}: {error_msg}")
            return result

    except asyncio.TimeoutError:
        console.print(
            f"[bold red][REMOTE][/bold red] Timeout waiting for response from {server_key}")
        # Mark connection as potentially dead
        try:
            await websocket.close()
        except:
            pass
        return None
    except websockets.exceptions.ConnectionClosed:
        console.print(
            f"[bold red][REMOTE][/bold red] Connection to {server_key} was closed")
        return None
    except Exception as e:
        console.print(
            f"[bold red][REMOTE][/bold red] Error sending command to {server_key}: {e}")
        return None

async def broadcast_command(self, command, params=None, server_filter=None):
    """
    Sends a command to all connected servers or filtered servers.
    Returns a dictionary with results per server.
    """
    results = {}

    for server_key, connection in self.connections.items():
        # Apply server filter if provided
        if server_filter:
            capabilities = self.server_capabilities.get(server_key, {})
            if not server_filter(capabilities):
                continue

        result = await self.send_remote_command(server_key, command, params)
        results[server_key] = result

    return results

async def restart_ws_clients_on_all_servers(self):
    """
    Restarts WebSocket clients on all connected servers.
    """
    console.print(
        "[bold cyan][REMOTE][/bold cyan] Restarting WebSocket clients on all servers...")

    results = await self.broadcast_command("restart_ws_client")

    success_count = sum(1 for result in results.values()
                        if result and result.get("status") == "ok")
    console.print(
        f"[bold green][REMOTE][/bold green] WebSocket client restart: {success_count}/{len(results)} servers successful")

    return results

async def update_port_scanner_on_all_servers(self):
    """
    Updates the port scanner (ports.txt) on all servers.
    """
    console.print(
        "[bold cyan][REMOTE][/bold cyan] Updating port scanner on all servers...")

    results = await self.broadcast_command("update_port_scanner")

    success_count = sum(1 for result in results.values()
                        if result and result.get("status") == "ok")
    console.print(
        f"[bold green][REMOTE][/bold green] Port scanner update: {success_count}/{len(results)} servers successful")

    return results

async def clear_streams_on_all_servers(self):
    """
    Removes all streams on all connected servers.
    Requests confirmation before proceeding.
    """
    console.print(
        "[bold yellow][REMOTE][/bold yellow] Clearing all streams on all servers...")

    confirm = Prompt.ask(
        "[bold red]⚠️  This will clear ALL streams on ALL connected servers. Are you sure?[/bold red]",
        choices=["yes", "no"],
        default="no"
    )

    if confirm != "yes":
        console.print(
            "[bold yellow][REMOTE][/bold yellow] Operation cancelled")
        return {}

    results = await self.broadcast_command("clear_all_streams")

    success_count = sum(1 for result in results.values()
                        if result and result.get("status") == "ok")
    console.print(
        f"[bold green][REMOTE][/bold green] Stream clearing: {success_count}/{len(results)} servers successful")

    return results

async def sync_configuration_on_all_servers(self):
    """
    Synchronizes the NGINX configuration on all servers.
    """
    console.print(
        "[bold cyan][REMOTE][/bold cyan] Syncing NGINX configuration on all servers...")

    results = await self.broadcast_command("sync_nginx_config")

    success_count = sum(1 for result in results.values()
                        if result and result.get("status") == "ok")
    console.print(
        f"[bold green][REMOTE][/bold green] NGINX sync: {success_count}/{len(results)} servers successful")

    return results

async def get_server_status_from_all(self):
    """
    Gets the status of all connected servers and displays a summary table.
    """
    console.print(
        "[bold cyan][REMOTE][/bold cyan] Getting status from all servers...")

    results = await self.broadcast_command("get_status")

    # Display status table
    table = Table(title="Server Status", show_lines=True)
    table.add_column("Server", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Connection", style="white")
    table.add_column("Status", style="green")
    table.add_column("Active Streams", style="yellow")
    table.add_column("Connected Clients", style="blue")

    for server_key in self.connections.keys():
        result = results.get(server_key)
        server_type = self.server_capabilities.get(
            server_key, {}).get("server_type", "unknown")

        # Check connection status
        connection_alive = await self.is_connection_alive(server_key)
        connection_status = "🟢 Connected" if connection_alive else "🔴 Disconnected"

        if result and result.get("status") == "ok":
            status_data = result.get("server_status", {})

            table.add_row(
                server_key,
                server_type,
                connection_status,
                "✅ Online",
                str(status_data.get("active_streams", "N/A")),
                str(status_data.get("connected_clients", "N/A"))
            )
        else:
            error_reason = "Connection Lost" if not connection_alive else "Command Failed"
            table.add_row(
                server_key,
                server_type,
                connection_status,
                f"❌ {error_reason}",
                "N/A",
                "N/A"
            )

    console.print(table)
    return results

async def send_ports_to_conflict_resolution_servers(self, ports_data):
    """
    Sends port data specifically to conflict resolution servers.
    """
    console.print(
        f"[bold cyan][REMOTE][/bold cyan] Sending {len(ports_data)} ports to conflict resolution servers...")

    # Filter for conflict resolution servers
    def is_conflict_resolution_server(capabilities):
        return capabilities.get("conflict_resolution_server", False)

    results = await self.broadcast_command(
        "process_ports",
        {"ports": ports_data, "ports_pre_approved": False},
        server_filter=is_conflict_resolution_server
    )

    success_count = sum(1 for result in results.values()
                        if result and result.get("status") == "ok")
    console.print(
        f"[bold green][REMOTE][/bold green] Port processing: {success_count}/{len(results)} conflict resolution servers successful")

    return results

async def forward_approved_ports_to_wireguard_servers(self, approved_ports):
    """
    Forwards pre-approved ports to WireGuard servers.
    """
    console.print(
        f"[bold cyan][REMOTE][/bold cyan] Forwarding {len(approved_ports)} approved ports to WireGuard servers...")

    # Filter for WireGuard servers
    def is_wireguard_server(capabilities):
        return capabilities.get("has_wireguard", False)

    results = await self.broadcast_command(
        "process_ports",
        {"ports": approved_ports, "ports_pre_approved": True},
        server_filter=is_wireguard_server
    )

    success_count = sum(1 for result in results.values()
                        if result and result.get("status") == "ok")
    console.print(
        f"[bold green][REMOTE][/bold green] Port forwarding: {success_count}/{len(results)} WireGuard servers successful")

    return results

async def update_stream_forwarding_ips(self, ip_mappings):
    """
    Updates stream forwarding IPs on all servers.
    """
    console.print(
        f"[bold cyan][REMOTE][/bold cyan] Updating stream forwarding IPs for {len(ip_mappings)} ports...")

    results = await self.broadcast_command("update_forwarding_ips", {"ip_mappings": ip_mappings})

    success_count = sum(1 for result in results.values()
                        if result and result.get("status") == "ok")
    console.print(
        f"[bold green][REMOTE][/bold green] IP update: {success_count}/{len(results)} servers successful")

    return results

async def create_remote_stream(self, server_key, stream_config):
    """
    Creates a stream remotely on a server, including access control.
    """
    if server_key not in self.connections:
        console.print(
            f"[bold red][REMOTE][/bold red] No connection to server {server_key}")
        return None

    connection = self.connections[server_key]
    websocket = connection["websocket"]
    token = connection["token"]

    try:
        command_data = {
            "token": token,
            "remote_stream_create": True,
            "stream_config": stream_config,
            "timestamp": int(time.time())
        }

        console.print(
            f"[bold cyan][REMOTE][/bold cyan] Creating stream on {server_key}: {stream_config['incoming_port']} → {stream_config['forwarding_host']}:{stream_config['forwarding_port']}")
        await websocket.send(json.dumps(command_data))

        # Wait for response
        response = await asyncio.wait_for(websocket.recv(), timeout=30)
        result = json.loads(response)

        if result.get("status") == "ok":
            console.print(
                f"[bold green][REMOTE][/bold green] Stream created successfully on {server_key}")
            console.print(
                f"[bold white]  Details: {result.get('msg', 'No details')}[/bold white]")
            return result
        else:
            error_msg = result.get("msg", "Unknown error")
            console.print(
                f"[bold red][REMOTE][/bold red] Failed to create stream on {server_key}: {error_msg}")
            return result

    except Exception as e:
        console.print(
            f"[bold red][REMOTE][/bold red] Error creating stream on {server_key}: {e}")
        return None

async def delete_remote_stream(self, server_key, port, protocol):
    """
    Deletes a specific stream remotely on a server.
    """
    if server_key not in self.connections:
        console.print(
            f"[bold red][REMOTE][/bold red] No connection to server {server_key}")
        return None

    connection = self.connections[server_key]
    websocket = connection["websocket"]
    token = connection["token"]

    try:
        command_data = {
            "token": token,
            "remote_stream_delete": True,
            "port": port,
            "protocol": protocol,
            "timestamp": int(time.time())
        }

        console.print(
            f"[bold cyan][REMOTE][/bold cyan] Deleting stream on {server_key}: Port {port} ({protocol})")
        await websocket.send(json.dumps(command_data))

        # Wait for response
        response = await asyncio.wait_for(websocket.recv(), timeout=15)
        result = json.loads(response)

        if result.get("status") == "ok":
            console.print(
                f"[bold green][REMOTE][/bold green] Stream deleted successfully on {server_key}")
            return result
        else:
            error_msg = result.get("msg", "Unknown error")
            console.print(
                f"[bold red][REMOTE][/bold red] Failed to delete stream on {server_key}: {error_msg}")
            return result

    except Exception as e:
        console.print(
            f"[bold red][REMOTE][/bold red] Error deleting stream on {server_key}: {e}")
        return None

async def list_remote_streams(self, server_key):
    """
    Gets the list of streams from a remote server.
    """
    if server_key not in self.connections:
        console.print(
            f"[bold red][REMOTE][/bold red] No connection to server {server_key}")
        return None

    connection = self.connections[server_key]
    websocket = connection["websocket"]
    token = connection["token"]

    try:
        command_data = {
            "token": token,
            "remote_stream_list": True,
            "timestamp": int(time.time())
        }

        console.print(
            f"[bold cyan][REMOTE][/bold cyan] Getting stream list from {server_key}")
        await websocket.send(json.dumps(command_data))

        # Wait for response
        response = await asyncio.wait_for(websocket.recv(), timeout=15)
        result = json.loads(response)

        if result.get("status") == "ok":
            streams = result.get("streams", [])
            console.print(
                f"[bold green][REMOTE][/bold green] Retrieved {len(streams)} streams from {server_key}")
            return streams
        else:
            error_msg = result.get("msg", "Unknown error")
            console.print(
                f"[bold red][REMOTE][/bold red] Failed to get streams from {server_key}: {error_msg}")
            return None

    except Exception as e:
        console.print(
            f"[bold red][REMOTE][/bold red] Error getting streams from {server_key}: {e}")
        return None

async def disconnect_all(self):
    """
    Disconnects from all servers.
    """
    console.print(
        "[bold cyan][REMOTE][/bold cyan] Disconnecting from all servers...")

    for server_key, connection in self.connections.items():
        try:
            if not connection["websocket"].closed:
                await connection["websocket"].close()
            console.print(
                f"[bold green][REMOTE][/bold green] Disconnected from {server_key}")
        except Exception as e:
            console.print(
                f"[bold yellow][REMOTE][/bold yellow] Error disconnecting from {server_key}: {e}")

    self.connections.clear()
    self.server_capabilities.clear()

async def check_all_connections(self):
    """
    Checks and repairs all server connections.
    """
    console.print(
        "[bold cyan][REMOTE][/bold cyan] Checking all connections...")

    reconnected_count = 0
    failed_count = 0

    for server_key in list(self.connections.keys()):
        if not await self.is_connection_alive(server_key):
            console.print(
                f"[bold yellow][REMOTE][/bold yellow] {server_key} connection lost, attempting reconnection...")
            if await self.reconnect_to_server(server_key):
                reconnected_count += 1
            else:
                failed_count += 1
        else:
            console.print(
                f"[bold green][REMOTE][/bold green] {server_key} connection is healthy")

    if reconnected_count > 0:
        console.print(
            f"[bold green][REMOTE][/bold green] Reconnected to {reconnected_count} servers")
    if failed_count > 0:
        console.print(
            f"[bold red][REMOTE][/bold red] Failed to reconnect to {failed_count} servers")
