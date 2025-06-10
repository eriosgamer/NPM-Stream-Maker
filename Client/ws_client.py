import asyncio
import json
import os
import sys
from rich.console import Console

# Add parent directory to sys.path to allow relative imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from WebSockets import websocket_config as ws_config
from Config import ws_config_handler as WebSocketConfig
from Config import config as cfg
from Client import ws_client_main_thread as wscth
from WebSockets import uri_config

console = Console()

# This file manages the startup and main loop of the WebSocket client,
# including configuration validation, connection testing, and port assignment management.

def start_ws_client():
    """
    Starts the WebSocket client.
    Validates configuration and tests connection to servers before proceeding.
    """
    console.rule("[bold blue]Start WebSocket Client")

    # Get URIs and tokens from .env using the new class
    uris, tokens, _ = WebSocketConfig.get_ws_config()

    if not uris or not tokens or not any(tokens):
        console.print("[bold red]No WebSocket URIs or tokens configured.[/bold red]")
        console.print("[bold yellow]Please use option 3 (Edit WebSocket URIs) to configure servers and tokens first.[/bold yellow]")
        input("\nPress Enter to continue...")
        return

    # Test connections before starting
    console.print(
        "[bold cyan]Testing connections to configured servers...[/bold cyan]")
    successful_connections = 0

    for uri, token in zip(uris, tokens):
        if not uri or not token:
            continue
        console.print(f"[cyan]Testing {uri}...[/cyan]")
        if ws_config.test_ws_connection(uri, token):
            console.print(f"[green]✅ Connection to {uri} successful[/green]")
            successful_connections += 1
        else:
            console.print(f"[red]❌ Connection to {uri} failed[/red]")

    if successful_connections == 0:
        console.print(
            "[bold red]No valid connections found. Cannot start client.[/bold red]")
        input("\nPress Enter to continue...")
        return

    console.print(
        f"[bold green]Found {successful_connections} valid connections. Starting client...[/bold green]")
    
    # Start the WebSocket client
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[bold yellow][WS_CLIENT][/bold yellow] Client stopped by user")
    except Exception as e:
        console.print(f"[bold red][WS_CLIENT][/bold red] Client error: {e}")
        
    console.print("[bold green][WS_CLIENT][/bold green] WebSocket client finished")

def is_ports_file_outdated():
    """
    Checks if the ports.txt file is outdated (by age or size).
    Returns True if it should be regenerated.
    """
    ports_file = "ports.txt"
    
    if not os.path.exists(ports_file):
        return True
    
    try:
        # Check file age (regenerate if older than 7 days)
        import time
        file_age = time.time() - os.path.getmtime(ports_file)
        if file_age > 7 * 24 * 60 * 60:  # 7 days
            return True
        
        # Check file size (should be reasonable)
        file_size = os.path.getsize(ports_file)
        if file_size < 1000:  # Too small
            return True
            
        return False
    except Exception as e:
        console.print(f"[bold yellow][WS_CLIENT][/bold yellow] Error checking ports file: {e}")
        return True

def ensure_ports_file():
    """
    Ensures that the ports.txt file exists and is up to date.
    If not, it generates it by running the Port_Scanner.
    """
    ports_file = "ports.txt"
    
    # Check if file exists and is up to date
    needs_update = is_ports_file_outdated()
    
    if needs_update:
        console.print("[bold yellow][WS_CLIENT][/bold yellow] Ports file needs update, generating...")
        try:
            # Try to run Port_Scanner to generate ports.txt
            import subprocess
            import sys
            
            # Set environment variable for Port_Scanner
            env = os.environ.copy()
            env["RUN_FROM_PANEL"] = "1"
            
            result = subprocess.run(
                [sys.executable, os.path.join("ports", "port_scanner_main.py")],
                env=env,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                console.print("[bold green][WS_CLIENT][/bold green] Ports file generated successfully")
            else:
                console.print(f"[bold red][WS_CLIENT][/bold red] Failed to generate ports file: {result.stderr}")
        except Exception as e:
            console.print(f"[bold red][WS_CLIENT][/bold red] Error generating ports file: {e}")
    else:
        console.print("[bold green][WS_CLIENT][/bold green] Ports file is up to date")

async def main():
    """
    Main function to run the WebSocket client with server discovery.
    Handles configuration changes and runs the main client loop.
    """
    console.print("[bold green][WS_CLIENT][/bold green] Starting WebSocket client with server discovery...")
    
    # Check for pending URI updates
    uri_config.check_pending_uri_updates()

    # Check if configuration changed and save hash ONLY if user made changes
    config_changed = uri_config.has_uri_config_changed()
    if config_changed:
        console.print("[bold cyan][WS_CLIENT][/bold cyan] Configuration change detected")
        uri_config.save_last_uri_config()
    
    try:
        # Run the main client loop - this should run indefinitely
        await wscth.ws_client_main_loop()
    except KeyboardInterrupt:
        console.print("\n[bold yellow][WS_CLIENT][/bold yellow] Shutting down...")
    except Exception as e:
        console.print(f"[bold red][WS_CLIENT][/bold red] Main loop error: {e}")
        raise
    finally:
        # Save final state (but NOT URI configuration)
        save_client_assignments()
        console.print("[bold green][WS_CLIENT][/bold green] WebSocket client stopped")

def save_client_assignments():
    """
    Saves the client's port assignments to a JSON file.
    Converts tuple keys to strings for JSON serialization.
    """
    try:
        # Convert tuple keys to strings for JSON serialization
        serializable_assignments = {}
        for (port, proto), assignment in cfg.client_assignments.items():
            key = f"{port}|{proto}"
            serializable_assignments[key] = assignment
        
        with open(cfg.CLIENT_ASSIGNMENTS_FILE, "w") as f:
            json.dump(serializable_assignments, f, indent=2)
    except Exception as e:
        console.print(f"[bold red][WS_CLIENT][/bold red] Error saving client assignments: {e}")

def load_client_assignments():
    """
    Loads the client's port assignments from a JSON file.
    Converts string keys back to tuples.
    """
    global client_assignments
    try:
        if os.path.exists(cfg.CLIENT_ASSIGNMENTS_FILE):
            with open(cfg.CLIENT_ASSIGNMENTS_FILE, "r") as f:
                data = json.load(f)
            
            # Convert string keys back to tuples
            client_assignments = {}
            for key, assignment in data.items():
                if "|" in key:
                    port, proto = key.split("|", 1)
                    if port.isdigit():
                        client_assignments[(int(port), proto)] = assignment
                        
            console.print(f"[bold green][WS_CLIENT][/bold green] Loaded {len(client_assignments)} client assignments")
    except Exception as e:
        console.print(f"[bold red][WS_CLIENT][/bold red] Error loading client assignments: {e}")

