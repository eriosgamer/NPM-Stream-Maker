import asyncio
import sys
import os
import json
import time
from rich.console import Console
from rich.prompt import Prompt
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
                ping_timeout=20,
                ping_interval=10,
                close_timeout=10,
                max_size=2**20,  # 1MB
                max_queue=2**5   # 32 messages
            )
            
            # Validate token
            token_data = {"token": token}
            await websocket.send(json.dumps(token_data))
            
            response = await asyncio.wait_for(websocket.recv(), timeout=15)
            result = json.loads(response)
            
            if result.get("status") != "ok":
                console.print(f"[bold red][REMOTE][/bold red] Token validation failed for {uri}")
                await websocket.close()
                return False
            
            # Query capabilities
            capabilities_query = {"token": token, "query_capabilities": True}
            await websocket.send(json.dumps(capabilities_query))
            
            capabilities_response = await asyncio.wait_for(websocket.recv(), timeout=15)
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
