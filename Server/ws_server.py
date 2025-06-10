import asyncio
import logging
import os
import platform
import socket
import sys
import time
import subprocess
import websockets
from rich.console import Console
import datetime

from Core import token_manager as tm
from Config import config as cfg
from WebSockets import websocket_config as ws_cfg
from Remote import extra_utils as ex_util
from ports import ports_utils as pu
from npm import npm_handler as npm

console = Console()

# --- File Overview ---
# This file is the main entry point for the WebSocket server of the NPM Stream Maker project.
# It is responsible for initializing the server, checking NPM and port status, managing client connections,
# handling periodic cleanup, and providing detailed logging and status reporting.
# The server is designed to be started from the Control Panel script and includes robust error handling.

# Main async function to run the WebSocket server
async def main():
    """
    Main async function to initialize and run the WebSocket server.
    Handles NPM checks, port availability, and starts the server and periodic tasks.
    """
    console.print(f"[bold green][WS][/bold green] Starting WebSocket server initialization...")
    console.print(f"[bold cyan][WS][/bold cyan] Server start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not cfg.WS_TOKEN:
        console.print("[bold red][WS][/bold red] No WebSocket server token found in .env file")
        console.print("[bold yellow][WS][/bold yellow] Please run Control_Panel.py to generate a server token")
        return False
    
    console.print(f"[bold cyan][WS][/bold cyan] Token loaded: {cfg.WS_TOKEN[:8]}...")
    
    # Check if we should skip NPM check (for debugging)
    skip_npm = os.environ.get("SKIP_NPM_CHECK", "").lower() == "true"
    
    if not skip_npm:
        console.print("[bold cyan][WS][/bold cyan] Performing NPM status check...")
        # Check and optionally start NPM with timeout
        try:
            npm_check_start = time.time()
            npm_ready = ex_util.check_and_start_npm()
            npm_check_duration = time.time() - npm_check_start
            
            console.print(f"[bold cyan][WS][/bold cyan] NPM check completed in {npm_check_duration:.2f} seconds")
            
            if not npm_ready:
                console.print("[bold red][WS][/bold red] NPM container is not accessible")
                console.print("[bold yellow][WS][/bold yellow] Server will start anyway but streams may not work properly")
                console.print("[bold white]  To fix NPM issues:[/bold white]")
                console.print("[bold white]  1. cd npm && docker-compose up -d[/bold white]")
                console.print("[bold white]  2. Or use the Control Panel to start NPM[/bold white]")
                console.print("[bold white]  3. Make sure NPM is accessible at http://localhost:81[/bold white]")
                console.print("[bold white]  4. Set SKIP_NPM_CHECK=true to skip this check[/bold white]")
                # Don't exit - continue with server startup
        except Exception as e:
            console.print(f"[bold red][WS][/bold red] Error during NPM check: {e}")
            console.print("[bold yellow][WS][/bold yellow] Continuing with server startup anyway...")
    else:
        console.print("[bold yellow][WS][/bold yellow] Skipping NPM check (SKIP_NPM_CHECK=true)")
    
    # Check if port 8765 is available
    console.print("[bold cyan][WS][/bold cyan] Checking if port 8765 is available...")
    
    try:
        port_check_start = time.time()
        port_in_use = pu.is_port_in_use(8765)
        port_check_duration = time.time() - port_check_start
        
        console.print(f"[bold cyan][WS][/bold cyan] Port check completed in {port_check_duration:.2f} seconds")
        
        if port_in_use:
            console.print(f"[bold yellow][WS][/bold yellow] Port 8765 is already in use")
            
            try:
                processes = pu.get_process_using_port(8765)
                
                if processes:
                    console.print(f"[bold yellow][WS][/bold yellow] Process(es) using port 8765:")
                    for i, (pid, command) in enumerate(processes, 1):
                        console.print(f"[bold white]  {i}. PID: {pid}, Command: {command}[/bold white]")
                    
                    # Check if any of the processes are likely our own WebSocket server
                    our_processes = []
                    for pid, command in processes:
                        if "ws_server.py" in command or ("python" in command.lower() and "ws_server" in command):
                            our_processes.append((pid, command))
                    
                    if our_processes:
                        console.print(f"[bold cyan][WS][/bold cyan] Found {len(our_processes)} likely WebSocket server process(es)")
                        console.print("[bold yellow][WS][/bold yellow] Attempting to terminate existing WebSocket server processes...")
                        
                        terminated_count = 0
                        for pid, command in our_processes:
                            try:
                                if platform.system().lower() == "windows":
                                    result = subprocess.run(["taskkill", "/F", "/PID", str(pid)], 
                                                         capture_output=True, text=True, timeout=10)
                                    if result.returncode == 0:
                                        console.print(f"[bold green][WS][/bold green] Terminated process {pid}")
                                        terminated_count += 1
                                    else:
                                        console.print(f"[bold red][WS][/bold red] Failed to terminate process {pid}: {result.stderr}")
                                else:
                                    os.kill(int(pid), 9)
                                    console.print(f"[bold green][WS][/bold green] Terminated process {pid}")
                                    terminated_count += 1
                            except Exception as e:
                                console.print(f"[bold red][WS][/bold red] Failed to terminate process {pid}: {e}")
                        
                        if terminated_count > 0:
                            console.print(f"[bold green][WS][/bold green] Successfully terminated {terminated_count} process(es)")
                            console.print("[bold cyan][WS][/bold cyan] Waiting 5 seconds for ports to be released...")
                            time.sleep(5)
                            
                            # Check again if port is now available
                            if not pu.is_port_in_use(8765):
                                console.print("[bold green][WS][/bold green] Port 8765 is now available")
                            else:
                                console.print("[bold red][WS][/bold red] Port 8765 is still in use after termination attempts")
                                console.print("[bold yellow][WS][/bold yellow] Will attempt to start server anyway...")
                        else:
                            console.print("[bold red][WS][/bold red] Failed to terminate any existing processes")
                    else:
                        console.print("[bold yellow][WS][/bold yellow] Non-WebSocket processes are using port 8765")
                        console.print("[bold yellow][WS][/bold yellow] Will attempt to start server anyway...")
                else:
                    console.print("[bold yellow][WS][/bold yellow] Could not identify the process using port 8765")
                    console.print("[bold yellow][WS][/bold yellow] Will attempt to start server anyway...")
            except Exception as e:
                console.print(f"[bold red][WS][/bold red] Error checking port usage: {e}")
                console.print("[bold yellow][WS][/bold yellow] Will attempt to start server anyway...")
        else:
            console.print("[bold green][WS][/bold green] Port 8765 is available")
    except Exception as e:
        console.print(f"[bold red][WS][/bold red] Error checking port availability: {e}")
        console.print("[bold yellow][WS][/bold yellow] Will attempt to start server anyway...")
    
    try:
        console.print("[bold cyan][WS][/bold cyan] Initializing WebSocket server...")
        
        # Start the WebSocket server with compatible settings
        server = await websockets.serve(
            ex_util.handler,
            "0.0.0.0",
            8765,
            ping_interval=20,  # Send ping every 20 seconds
            ping_timeout=10,   # Wait 10 seconds for pong
            close_timeout=5,   # Quick close timeout
            max_size=2**20,    # 1MB max message size
            max_queue=32,      # Max 32 messages in queue
            compression=None   # Disable compression for better compatibility
        )
        
        console.print("[bold green][WS][/bold green] WebSocket server started successfully!")
        console.print(f"[bold cyan][WS][/bold cyan] Server accessible via:")
    
        # Try to get local IP for additional connection info
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            console.print(f"[bold white]  - ws://{local_ip}:8765[/bold white]")
        except:
            pass
        
        console.print(f"[bold yellow][WS][/bold yellow] Press Ctrl+C to stop the server")
        
        # Start periodic cleanup task
        console.print("[bold cyan][WS][/bold cyan] Starting periodic cleanup task...")
        cleanup_task = asyncio.create_task(ex_util.periodic_cleanup())
        console.print("[bold green][WS][/bold green] Periodic cleanup task started")
        
        # Keep the server running indefinitely
        console.print("[bold green][WS][/bold green] Server is now running and waiting for connections...")
        
        try:
            # Create a task that will run forever
            server_task = asyncio.create_task(server.wait_closed())
            
            # Also create a heartbeat task to keep the event loop alive
            async def heartbeat():
                """
                Periodic heartbeat task that prints the current status of connected clients.
                Shows formatted last_seen times and WebSocket status for each client.
                """
                while True:
                    await asyncio.sleep(60)  # Heartbeat every minute
                    current_time = time.strftime('%H:%M:%S')
                    # Show only relevant info for each client, with formatted times
                    clients_info = {}
                    for k, v in cfg.connected_clients.items():
                        ws = v.get("ws")
                        ws_status = None
                        try:
                            if ws is None:
                                ws_status = "None"
                            elif hasattr(ws, "closed"):
                                ws_status = "closed" if ws.closed else "open"
                            else:
                                ws_status = "unknown"
                        except Exception:
                            ws_status = "unknown"
                        # Format last_seen
                        last_seen_ts = v.get("last_seen")
                        if last_seen_ts:
                            last_seen_fmt = datetime.datetime.fromtimestamp(last_seen_ts).strftime("%d/%m/%Y %I:%M:%S %p")
                        else:
                            last_seen_fmt = "N/A"
                        clients_info[k] = {
                            "ip": v.get("ip"),
                            "hostname": v.get("hostname"),
                            "ws_status": ws_status,
                            "ports": list(v.get("ports", [])),
                            "last_seen": last_seen_fmt,
                        }
                    console.print(f"[bold gray][WS][/bold gray] connected_clients summary: {clients_info}")
                    console.print(f"[bold gray][WS][/bold gray] Server heartbeat: {current_time} - {len(cfg.connected_clients)} clients connected")
            
            heartbeat_task = asyncio.create_task(heartbeat())
            
            # Wait for either the server to close or manual interruption
            done, pending = await asyncio.wait(
                [server_task, heartbeat_task, cleanup_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        except KeyboardInterrupt:
            console.print("[bold yellow][WS][/bold yellow] Received shutdown signal...")
        except Exception as e:
            console.print(f"[bold red][WS][/bold red] Server error: {e}")
        finally:
            console.print("[bold cyan][WS][/bold cyan] Cleaning up server resources...")
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
            
            console.print("[bold yellow][WS][/bold yellow] Server shutdown completed")
        
        return True
        
    except OSError as e:
        if "Address already in use" in str(e):
            console.print(f"[bold red][WS][/bold red] Port 8765 is still in use after cleanup attempts")
            console.print(f"[bold yellow][WS][/bold yellow] This may indicate:")
            console.print(f"[bold white]  - Another WebSocket server is running[/bold white]")
            console.print(f"[bold white]  - A process is still releasing the port[/bold white]")
            console.print(f"[bold white]  - System networking issue[/bold white]")
            console.print(f"[bold cyan][WS][/bold cyan] Try waiting a few moments and running the server again")
        else:
            console.print(f"[bold red][WS][/bold red] Failed to bind to port 8765: {e}")
        
        console.print(f"[bold yellow][WS][/bold yellow] You can try:")
        console.print(f"[bold white]  - Use 'netstat -tulpn | grep 8765' to check what's using the port[/bold white]")
        console.print(f"[bold white]  - Kill the process manually: sudo kill -9 <PID>[/bold white]")
        console.print(f"[bold white]  - Wait for the process to finish[/bold white]")
        console.print(f"[bold white]  - Restart your system if necessary[/bold white]")
        return False
    except Exception as e:
        console.print(f"[bold red][WS][/bold red] Unexpected error starting WebSocket server: {e}")
        console.print(f"[bold red][WS][/bold red] Error type: {type(e).__name__}")
        
        # Print more detailed error information
        import traceback
        console.print(f"[bold red][WS][/bold red] Traceback:")
        for line in traceback.format_exc().split('\n'):
            if line.strip():
                console.print(f"[bold red]  {line}[/bold red]")
        
        return False

def start_ws_server():
    """
    Starts the WebSocket server.
    Generates the server token if it does not exist.
    Loads saved state, configures logging, and runs the main async loop.
    """
    console.rule("[bold blue]Start WebSocket Server")

    if os.environ.get("RUN_FROM_PANEL") != "1":
        console.print(
            "[bold red][WS][/bold red] This script must be run from Control_Panel.py")
        console.print(
            "[bold yellow][WS][/bold yellow] Use option 5 in the Control Panel to start the WebSocket server")
        sys.exit(1)

    # Check token availability
    if not cfg.WS_TOKEN:
        console.print(
            "[bold red][WS][/bold red] No WebSocket server token found in .env file")
        # Generate a new token
        cfg.WS_TOKEN = tm.get_or_create_token(console, "server")

    console.print(
        f"[bold cyan][WS][/bold cyan] WebSocket server token: {cfg.WS_TOKEN}")

    # Load saved state
    console.print("[bold cyan][WS][/bold cyan] Loading saved state...")
    try:
        ws_cfg.load_state()
        console.print(
            "[bold green][WS][/bold green] State loaded successfully")
    except Exception as e:
        console.print(
            f"[bold yellow][WS][/bold yellow] Error loading state: {e}")
        console.print(
            "[bold cyan][WS][/bold cyan] Starting with clean state...")

    # Setup logging to reduce handshake error noise
    console.print("[bold cyan][WS][/bold cyan] Configuring logging...")
    logging.getLogger('websockets').setLevel(
        logging.WARNING)  # Reduce websockets logging
    logging.getLogger('websockets.server').setLevel(
        logging.ERROR)  # Even more strict for server
    logging.getLogger('websockets.protocol').setLevel(
        logging.ERROR)  # Hide protocol errors

    # Filter out common harmless errors
    class HandshakeErrorFilter(logging.Filter):
        def filter(self, record):
            message = record.getMessage()
            # Filter out common harmless connection errors
            if any(phrase in message.lower() for phrase in [
                "opening handshake failed",
                "connection closed while reading http request line",
                "stream ends after 0 bytes",
                "close_code = 1006"
            ]):
                return False
            return True
    # Apply filter to websockets loggers
    for logger_name in ['websockets', 'websockets.server', 'websockets.protocol']:
        logger = logging.getLogger(logger_name)
        logger.addFilter(HandshakeErrorFilter())

    console.print(
        "[bold green][WS][/bold green] Logging configured - handshake errors filtered")

    # Run the server
    try:
        console.print(
            "[bold green][WS][/bold green] Starting WebSocket server main loop...")

        # Set up signal handling for graceful shutdown
        import signal

        def signal_handler(signum, frame):
            console.print(
                f"[bold yellow][WS][/bold yellow] Received signal {signum}")
            console.print(
                "[bold yellow][WS][/bold yellow] Initiating graceful shutdown...")
            # The KeyboardInterrupt will be caught by the asyncio.run() try/catch
            raise KeyboardInterrupt()

        # Register signal handlers (Unix only)
        if platform.system() != "Windows":
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

        # Run the main async function
        success = asyncio.run(main())

        if success:
            console.print(
                "[bold green][WS][/bold green] WebSocket server completed successfully")
            sys.exit(0)
        else:
            console.print(
                "[bold red][WS][/bold red] WebSocket server failed to start")
            sys.exit(1)

    except KeyboardInterrupt:
        console.print(
            "[bold yellow][WS][/bold yellow] Server shutdown requested by user")
        npm.stop_npm()
        sys.exit(0)
    except Exception as e:
        console.print(
            f"[bold red][WS][/bold red] Fatal error in server startup: {e}")

        # Print detailed error information
        import traceback
        console.print(f"[bold red][WS][/bold red] Full traceback:")
        for line in traceback.format_exc().split('\n'):
            if line.strip():
                console.print(f"[bold red]  {line}[/bold red]")

        sys.exit(1)
    time.sleep(3)  # Give time for logging to take effect

def get_client_id(ip, hostname):
    """
    Returns a unique client ID string based on IP and hostname.
    """
    return f"{ip}|{hostname}"

# --- Module summary ---
# This file is the main entry point for the WebSocket server.
# It handles initialization, port and NPM checks, client connection management,
# periodic cleanup, and provides detailed logging and status reporting.
