import asyncio
import sys
import os
import json
import time
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
import websockets

console = Console()

# Add parent directory to sys.path to allow importing local modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import ws_config_handler as WebSocketConfig
from Streams import stream_handler as s_handler

class RemoteControl:
    """
    Remote control client to manage NPM Stream Maker servers.
    Allows connecting to WebSocket servers and sending remote commands.
    """
    
    def __init__(self):
        """
        Initializes connection structures and server capabilities.
        """
        self.connections = {}
        self.server_capabilities = {}
    
    async def is_connection_alive(self, server_key):
        """
        Checks if a WebSocket connection is alive.
        """
        if server_key not in self.connections:
            return False
        
        connection = self.connections[server_key]
        websocket = connection["websocket"]
        
        try:
            # Check if websocket is closed
            if websocket.closed:
                return False
            
            # Try a simple ping
            await asyncio.wait_for(websocket.ping(), timeout=5)
            return True
        except Exception:
            return False
    
    async def reconnect_to_server(self, server_key):
        """
        Attempts to reconnect to a server that lost connection.
        """
        if server_key not in self.connections:
            return False
        
        connection = self.connections[server_key]
        uri = connection["uri"]
        token = connection["token"]
        
        console.print(f"[bold yellow][REMOTE][/bold yellow] Reconnecting to {server_key}...")
        
        try:
            # Close old connection if still open
            try:
                await connection["websocket"].close()
            except:
                pass
            
            # Establish new connection
            success = await self.connect_to_server(uri, token, server_key)
            if success:
                console.print(f"[bold green][REMOTE][/bold green] Successfully reconnected to {server_key}")
                return True
            else:
                console.print(f"[bold red][REMOTE][/bold red] Failed to reconnect to {server_key}")
                return False
        except Exception as e:
            console.print(f"[bold red][REMOTE][/bold red] Reconnection error for {server_key}: {e}")
            return False
    
    async def ensure_connection(self, server_key):
        """
        Ensures a connection is alive, reconnecting if necessary.
        """
        if not await self.is_connection_alive(server_key):
            console.print(f"[bold yellow][REMOTE][/bold yellow] Connection to {server_key} lost, attempting reconnection...")
            return await self.reconnect_to_server(server_key)
        return True

    async def connect_to_server(self, uri, token, server_name=None):
        """
        Connects to a WebSocket server and stores the connection.
        Validates the token and queries server capabilities.
        """
        try:
            console.print(f"[bold cyan][REMOTE][/bold cyan] Connecting to {uri}...")
            
            # Use longer timeout and configure connection parameters
            websocket = await websockets.connect(
                uri, 
                ping_timeout=60,    # Aumentado de 30 a 60 segundos
                ping_interval=120,  # Aumentado de 60 a 120 segundos  
                close_timeout=20,   # Aumentado de 15 a 20 segundos
                max_size=2**20,     # 1MB
                max_queue=2**5      # 32 messages
            )
            
            # Validate token
            token_data = {"token": token}
            await websocket.send(json.dumps(token_data))
            
            # Wait for token validation
            response = await asyncio.wait_for(websocket.recv(), timeout=20)  # Aumentado timeout
            result = json.loads(response)
            
            if result.get("status") != "ok":
                console.print(f"[bold red][REMOTE][/bold red] Token validation failed for {uri}")
                await websocket.close()
                return False
            
            # Query capabilities
            capabilities_query = {"token": token, "query_capabilities": True}
            await websocket.send(json.dumps(capabilities_query))
            
            capabilities_response = await asyncio.wait_for(websocket.recv(), timeout=20)  # Aumentado timeout
            capabilities = json.loads(capabilities_response)
            
            if capabilities.get("status") == "ok":
                server_caps = capabilities.get("server_capabilities", {})
                server_key = server_name or uri
                
                self.connections[server_key] = {
                    "websocket": websocket,
                    "uri": uri,
                    "token": token,
                    "capabilities": server_caps,
                    "last_ping": time.time()
                }
                self.server_capabilities[server_key] = server_caps
                
                console.print(f"[bold green][REMOTE][/bold green] Connected to {server_key}")
                console.print(f"[bold white]  Type: {server_caps.get('server_type', 'unknown')}[/bold white]")
                console.print(f"[bold white]  WireGuard: {server_caps.get('has_wireguard', False)}[/bold white]")
                return True
            else:
                console.print(f"[bold red][REMOTE][/bold red] Failed to get capabilities from {uri}")
                await websocket.close()
                return False
                
        except Exception as e:
            console.print(f"[bold red][REMOTE][/bold red] Failed to connect to {uri}: {e}")
            return False

    async def disconnect_all(self):
        """
        Disconnects from all servers and cleans up connections.
        """
        console.print(f"[bold cyan][REMOTE][/bold cyan] Disconnecting from all servers...")
        
        for server_key, connection in self.connections.items():
            try:
                if not connection["websocket"].closed:
                    await connection["websocket"].close()
                console.print(f"[bold green][REMOTE][/bold green] Disconnected from {server_key}")
            except Exception as e:
                console.print(f"[bold yellow][REMOTE][/bold yellow] Error disconnecting from {server_key}: {e}")
        
        self.connections.clear()
        self.server_capabilities.clear()

    def show_connected_servers(self):
        """
        Displays a table with connected servers and their capabilities.
        """
        if not self.connections:
            console.print("[bold yellow][REMOTE][/bold yellow] No servers connected")
            return

        table = Table(title="Connected Servers", show_lines=True)
        table.add_column("Server", style="cyan")
        table.add_column("URI", style="magenta")
        table.add_column("Type", style="green")
        table.add_column("Connection", style="white")
        table.add_column("WireGuard", style="blue")
        table.add_column("Conflict Resolution", style="yellow")

        for server_key, connection in self.connections.items():
            capabilities = connection["capabilities"]

            # Check connection status
            try:
                connection_status = "🟢 Active" if not connection["websocket"].closed else "🔴 Closed"
            except:
                connection_status = "🔴 Error"

            table.add_row(
                server_key,
                connection["uri"],
                capabilities.get("server_type", "unknown"),
                connection_status,
                "✅" if capabilities.get("has_wireguard", False) else "❌",
                "✅" if capabilities.get("conflict_resolution_server", False) else "❌"
            )

        console.print(table)

    async def send_remote_command(self, server_key, command, **kwargs):
        """
        Sends a command to a specific server.
        """
        if server_key not in self.connections:
            console.print(f"[bold red][REMOTE][/bold red] No connection to server {server_key}")
            return None

        # Ensure connection is alive
        if not await self.ensure_connection(server_key):
            console.print(f"[bold red][REMOTE][/bold red] Could not establish connection to {server_key}")
            return None

        connection = self.connections[server_key]
        websocket = connection["websocket"]
        token = connection["token"]

        try:
            command_data = {
                "token": token,
                "remote_command": command,  # Changed from "command" to "remote_command"
                "timestamp": int(time.time()),
                **kwargs
            }

            console.print(f"[bold cyan][REMOTE][/bold cyan] Sending command '{command}' to {server_key}")
            await websocket.send(json.dumps(command_data))

            # Wait for response with longer timeout
            response = await asyncio.wait_for(websocket.recv(), timeout=45)
            result = json.loads(response)

            # Update last ping time
            connection["last_ping"] = time.time()

            if result.get("status") == "ok":
                console.print(f"[bold green][REMOTE][/bold green] Command '{command}' successful on {server_key}")
                return result
            else:
                error_msg = result.get("message", result.get("msg", "Unknown error"))
                console.print(f"[bold red][REMOTE][/bold red] Command '{command}' failed on {server_key}: {error_msg}")
                return result

        except asyncio.TimeoutError:
            console.print(f"[bold red][REMOTE][/bold red] Timeout waiting for response from {server_key}")
            # Mark connection as potentially dead
            try:
                await websocket.close()
            except:
                pass
            return None
        except Exception as e:
            console.print(f"[bold red][REMOTE][/bold red] Error sending command to {server_key}: {e}")
            return None

    async def broadcast_command(self, command, server_filter=None, **kwargs):
        """
        Sends a command to all connected servers or filtered servers.
        Returns a dictionary with results per server.
        """
        console.print(f"[bold cyan][REMOTE][/bold cyan] Broadcasting command '{command}' to all servers...")
        
        results = {}
        for server_key, connection in self.connections.items():
            # Apply server filter if provided
            if server_filter:
                capabilities = self.server_capabilities.get(server_key, {})
                if not server_filter(capabilities):
                    continue

            result = await self.send_remote_command(server_key, command, **kwargs)
            results[server_key] = result
        
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
            result = results.get(server_key) if results else None
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

    async def restart_ws_clients_on_all_servers(self):
        """
        Restarts WebSocket clients on all servers.
        """
        console.print(f"[bold cyan][REMOTE][/bold cyan] Restarting WebSocket clients on all servers...")
        await self.broadcast_command("restart_ws_clients")

    async def update_port_scanner_on_all_servers(self):
        """
        Updates port scanner on all servers.
        """
        console.print(f"[bold cyan][REMOTE][/bold cyan] Updating port scanner on all servers...")
        await self.broadcast_command("update_port_scanner")

    async def clear_streams_on_all_servers(self):
        """
        Clears all streams on all servers.
        """
        console.print(f"[bold cyan][REMOTE][/bold cyan] Clearing all streams on all servers...")
        await self.broadcast_command("clear_all_streams")

    async def sync_configuration_on_all_servers(self):
        """
        Syncs NGINX configuration on all servers.
        """
        console.print(f"[bold cyan][REMOTE][/bold cyan] Syncing NGINX configuration on all servers...")
        await self.broadcast_command("sync_nginx_config")

    async def update_stream_forwarding_ips(self, port_ip_mapping):
        """
        Updates stream forwarding IPs on all servers.
        """
        console.print(f"[bold cyan][REMOTE][/bold cyan] Updating stream forwarding IPs...")
        await self.broadcast_command("update_forwarding_ips", port_ip_mapping=port_ip_mapping)

    async def check_all_connections(self):
        """
        Checks and repairs all server connections.
        """
        console.print(f"[bold cyan][REMOTE][/bold cyan] Checking all connections...")
        
        reconnected_count = 0
        failed_count = 0

        for server_key in list(self.connections.keys()):
            if not await self.is_connection_alive(server_key):
                console.print(f"[bold yellow][REMOTE][/bold yellow] {server_key} connection lost, attempting reconnection...")
                if await self.reconnect_to_server(server_key):
                    reconnected_count += 1
                else:
                    failed_count += 1
            else:
                console.print(f"[bold green][REMOTE][/bold green] {server_key} connection is healthy")

        if reconnected_count > 0:
            console.print(f"[bold green][REMOTE][/bold green] Reconnected to {reconnected_count} servers")
        if failed_count > 0:
            console.print(f"[bold red][REMOTE][/bold red] Failed to reconnect to {failed_count} servers")

    # También necesitamos agregar métodos que faltan para crear, eliminar y listar streams remotamente
    async def create_remote_stream(self, server_key, stream_config):
        """
        Creates a stream remotely on a server.
        """
        if server_key not in self.connections:
            console.print(f"[bold red][REMOTE][/bold red] No connection to server {server_key}")
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

            console.print(f"[bold cyan][REMOTE][/bold cyan] Creating stream on {server_key}: {stream_config['incoming_port']} → {stream_config['forwarding_host']}:{stream_config['forwarding_port']}")
            await websocket.send(json.dumps(command_data))

            response = await asyncio.wait_for(websocket.recv(), timeout=30)
            result = json.loads(response)

            if result.get("status") == "ok":
                console.print(f"[bold green][REMOTE][/bold green] Stream created successfully on {server_key}")
                return result
            else:
                error_msg = result.get("msg", "Unknown error")
                console.print(f"[bold red][REMOTE][/bold red] Failed to create stream on {server_key}: {error_msg}")
                return result

        except Exception as e:
            console.print(f"[bold red][REMOTE][/bold red] Error creating stream on {server_key}: {e}")
            return None

    async def delete_remote_stream(self, server_key, port, protocol):
        """
        Deletes a stream remotely on a server.
        """
        if server_key not in self.connections:
            console.print(f"[bold red][REMOTE][/bold red] No connection to server {server_key}")
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

            console.print(f"[bold cyan][REMOTE][/bold cyan] Deleting stream on {server_key}: Port {port} ({protocol})")
            await websocket.send(json.dumps(command_data))

            response = await asyncio.wait_for(websocket.recv(), timeout=15)
            result = json.loads(response)

            if result.get("status") == "ok":
                console.print(f"[bold green][REMOTE][/bold green] Stream deleted successfully on {server_key}")
                return result
            else:
                error_msg = result.get("msg", "Unknown error")
                console.print(f"[bold red][REMOTE][/bold red] Failed to delete stream on {server_key}: {error_msg}")
                return result

        except Exception as e:
            console.print(f"[bold red][REMOTE][/bold red] Error deleting stream on {server_key}: {e}")
            return None

    async def list_remote_streams(self, server_key):
        """
        Gets the list of streams from a remote server.
        """
        if server_key not in self.connections:
            console.print(f"[bold red][REMOTE][/bold red] No connection to server {server_key}")
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

            console.print(f"[bold cyan][REMOTE][/bold cyan] Getting stream list from {server_key}")
            await websocket.send(json.dumps(command_data))

            response = await asyncio.wait_for(websocket.recv(), timeout=15)
            result = json.loads(response)

            if result.get("status") == "ok":
                streams = result.get("streams", [])
                console.print(f"[bold green][REMOTE][/bold green] Retrieved {len(streams)} streams from {server_key}")
                return streams
            else:
                error_msg = result.get("msg", "Unknown error")
                console.print(f"[bold red][REMOTE][/bold red] Failed to get streams from {server_key}: {error_msg}")
                return None

        except Exception as e:
            console.print(f"[bold red][REMOTE][/bold red] Error getting streams from {server_key}: {e}")
            return None

    
# Copied
async def remote_control_menu():
    """
    Interactive menu for remote control operations.
    Allows managing servers, restarting clients, syncing configuration, etc.
    """
    remote = RemoteControl()
    
    # Load server configurations
    uris, tokens, _ = WebSocketConfig.get_ws_config()
    
    if not uris or not tokens:
        console.print("[bold red][REMOTE][/bold red] No WebSocket servers configured")
        console.print("[bold yellow][REMOTE][/bold yellow] Please configure servers in Control Panel first")
        return
    
    # Connect to all configured servers
    console.print(f"[bold cyan][REMOTE][/bold cyan] Connecting to {len(uris)} configured servers...")
    
    connected_count = 0
    for i, (uri, token) in enumerate(zip(uris, tokens), 1):
        server_name = f"Server-{i}"
        success = await remote.connect_to_server(uri, token, server_name)
        if success:
            connected_count += 1
    
    if connected_count == 0:
        console.print("[bold red][REMOTE][/bold red] Failed to connect to any servers")
        return
    
    console.print(f"[bold green][REMOTE][/bold green] Connected to {connected_count}/{len(uris)} servers")
    
    try:
        while True:
            console.clear()
            console.rule("[bold blue]Remote Control Menu")
            
            # Show connected servers and their status
            remote.show_connected_servers()
            
            console.print("\n[bold cyan]Available Actions:[/bold cyan]")
            console.print("[bold green]1.[/bold green] Get server status")
            console.print("[bold green]2.[/bold green] Restart WebSocket clients")
            console.print("[bold green]3.[/bold green] Update port scanner")
            console.print("[bold green]4.[/bold green] Clear all streams")
            console.print("[bold green]5.[/bold green] Sync NGINX configuration")
            console.print("[bold green]6.[/bold green] Update stream forwarding IPs")
            console.print("[bold green]7.[/bold green] Create stream remotely")
            console.print("[bold green]8.[/bold green] Delete stream remotely")
            console.print("[bold green]9.[/bold green] List streams from server")
            console.print("[bold green]10.[/bold green] Send custom command")
            console.print("[bold green]11.[/bold green] Check/repair connections")  # NEW
            console.print("[bold green]0.[/bold green] Exit")
            
            choice = Prompt.ask("\n[bold yellow]Select an action", choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"])
            
            if choice == "0":
                break
            elif choice == "1":
                await remote.get_server_status_from_all()
            elif choice == "2":
                await remote.restart_ws_clients_on_all_servers()
            elif choice == "3":
                await remote.update_port_scanner_on_all_servers()
            elif choice == "4":
                await remote.clear_streams_on_all_servers()
            elif choice == "5":
                await remote.sync_configuration_on_all_servers()
            elif choice == "6":
                port = Prompt.ask("[bold cyan]Enter port to update")
                new_ip = Prompt.ask("[bold cyan]Enter new IP")
                try:
                    await remote.update_stream_forwarding_ips({int(port): new_ip})
                except ValueError:
                    console.print("[bold red][REMOTE][/bold red] Invalid port number")
            elif choice == "7":
                await s_handler.handle_create_stream_menu(remote)
            elif choice == "8":
                await s_handler.handle_delete_stream_menu(remote)
            elif choice == "9":
                await s_handler.handle_list_streams_menu(remote)
            elif choice == "10":
                command = Prompt.ask("[bold cyan]Enter command name")
                server_key = Prompt.ask("[bold cyan]Enter server name (or 'all' for broadcast)")
                
                if server_key == "all":
                    await remote.broadcast_command(command)
                else:
                    await remote.send_remote_command(server_key, command)
            elif choice == "11":  # NEW: Check/repair connections
                await remote.check_all_connections()
            
            if choice != "0":
                input("\nPress Enter to continue...")
    
    finally:
        await remote.disconnect_all()
