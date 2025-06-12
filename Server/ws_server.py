import asyncio
import logging
import os
import platform
import socket
import sys
import time
import subprocess
import websockets
import datetime

# Add the parent directory to sys.path to allow module imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Core import token_manager as tm
from Config import config as cfg
from WebSockets import websocket_config as ws_cfg
from Remote import extra_utils as ex_util
from ports import ports_utils as pu
from npm import npm_handler as npm
from UI.console_handler import (
    console_handler, ws_info, ws_success, ws_warning, ws_error, 
    ws_connection, ws_status, clear_console, MessageType,
    start_live_console, stop_live_console
)

# --- File Overview ---
# This file is the main entry point for the WebSocket server of the NPM Stream Maker project.
# It is responsible for initializing the server, checking NPM and port status, managing client connections,
# handling periodic cleanup, and providing detailed logging and status reporting.
# The server is designed to be started from the Control Panel script and includes robust error handling.

# Main async function to run the WebSocket server
async def main():
    """
    Main async function to initialize and run the WebSocket server.
    """
    # Iniciar consola en vivo al comenzar
    start_live_console("WebSocket Server", "Initialization & Live Monitoring")
    
    ws_info("WS_SERVER", "Starting WebSocket server initialization...")
    ws_info("WS_SERVER", f"Server start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    ws_info("WS_SERVER", f"Configured port: {cfg.WS_SERVER_PORT}")
    
    if not cfg.WS_TOKEN:
        ws_error("WS_SERVER", "No WebSocket server token found in .env file", 
                suggestions=["Run Control_Panel.py to generate a server token"])
        return False
    
    ws_info("WS_SERVER", f"Token loaded: {cfg.WS_TOKEN[:8]}...")
    
    # Check if we should skip NPM check (for debugging)
    skip_npm = os.environ.get("SKIP_NPM_CHECK", "").lower() == "true"
    
    if not skip_npm:
        ws_info("WS_SERVER", "Performing NPM status check...")
        # Check and optionally start NPM with timeout
        try:
            npm_check_start = time.time()
            npm_ready = ex_util.check_and_start_npm()
            npm_check_duration = time.time() - npm_check_start
            
            ws_info("WS_SERVER", f"NPM check completed in {npm_check_duration:.2f} seconds")
            
            if not npm_ready:
                ws_error("WS_SERVER", "NPM container is not accessible",
                        suggestions=[
                            "cd npm && docker-compose up -d",
                            "Use the Control Panel to start NPM",
                            "Make sure NPM is accessible at http://localhost:81",
                            "Set SKIP_NPM_CHECK=true to skip this check"
                        ])
                ws_warning("WS_SERVER", "Server will start anyway but streams may not work properly")
        except Exception as e:
            ws_error("WS_SERVER", f"Error during NPM check: {e}")
            ws_warning("WS_SERVER", "Continuing with server startup anyway...")
    else:
        ws_warning("WS_SERVER", "Skipping NPM check (SKIP_NPM_CHECK=true)")
    
    # Check if port is available
    ws_info("WS_SERVER", f"Checking if port {cfg.WS_SERVER_PORT} is available...")
    
    try:
        port_check_start = time.time()
        port_in_use = pu.is_port_in_use(cfg.WS_SERVER_PORT)
        port_check_duration = time.time() - port_check_start
        
        ws_info("WS_SERVER", f"Port check completed in {port_check_duration:.2f} seconds")
        
        if port_in_use:
            ws_warning("WS_SERVER", f"Port {cfg.WS_SERVER_PORT} is already in use")
            
            try:
                processes = pu.get_process_using_port(cfg.WS_SERVER_PORT)
                
                if processes:
                    process_details = {}
                    for i, (pid, command) in enumerate(processes, 1):
                        process_details[f"Process {i}"] = f"PID: {pid}, Command: {command}"
                    
                    ws_warning("WS_SERVER", f"Process(es) using port {cfg.WS_SERVER_PORT}:", process_details)
                    
                    # Check if any of the processes are likely our own WebSocket server
                    our_processes = []
                    for pid, command in processes:
                        if "ws_server.py" in command or ("python" in command.lower() and "ws_server" in command):
                            our_processes.append((pid, command))
                    
                    if our_processes:
                        ws_info("WS_SERVER", f"Found {len(our_processes)} likely WebSocket server process(es)")
                        ws_warning("WS_SERVER", "Attempting to terminate existing WebSocket server processes...")
                        
                        terminated_count = 0
                        for pid, command in our_processes:
                            try:
                                if platform.system().lower() == "windows":
                                    result = subprocess.run(["taskkill", "/F", "/PID", str(pid)], 
                                                         capture_output=True, text=True, timeout=10)
                                    if result.returncode == 0:
                                        ws_success("WS_SERVER", f"Terminated process {pid}")
                                        terminated_count += 1
                                    else:
                                        ws_error("WS_SERVER", f"Failed to terminate process {pid}: {result.stderr}")
                                else:
                                    os.kill(int(pid), 9)
                                    ws_success("WS_SERVER", f"Terminated process {pid}")
                                    terminated_count += 1
                            except Exception as e:
                                ws_error("WS_SERVER", f"Failed to terminate process {pid}: {e}")
                        
                        if terminated_count > 0:
                            ws_success("WS_SERVER", f"Successfully terminated {terminated_count} process(es)")
                            ws_info("WS_SERVER", "Waiting 5 seconds for ports to be released...")
                            time.sleep(5)
                            
                            # Check again if port is now available
                            if not pu.is_port_in_use(cfg.WS_SERVER_PORT):
                                ws_success("WS_SERVER", f"Port {cfg.WS_SERVER_PORT} is now available")
                            else:
                                ws_error("WS_SERVER", f"Port {cfg.WS_SERVER_PORT} is still in use after termination attempts")
                                ws_warning("WS_SERVER", "Will attempt to start server anyway...")
                        else:
                            ws_error("WS_SERVER", "Failed to terminate any existing processes")
                    else:
                        ws_warning("WS_SERVER", f"Non-WebSocket processes are using port {cfg.WS_SERVER_PORT}")
                        ws_warning("WS_SERVER", "Will attempt to start server anyway...")
                else:
                    ws_warning("WS_SERVER", f"Could not identify the process using port {cfg.WS_SERVER_PORT}")
                    ws_warning("WS_SERVER", "Will attempt to start server anyway...")
            except Exception as e:
                ws_error("WS_SERVER", f"Error checking port usage: {e}")
                ws_warning("WS_SERVER", "Will attempt to start server anyway...")
        else:
            ws_success("WS_SERVER", f"Port {cfg.WS_SERVER_PORT} is available")
    except Exception as e:
        ws_error("WS_SERVER", f"Error checking port availability: {e}")
        ws_warning("WS_SERVER", "Will attempt to start server anyway...")
    
    try:
        ws_info("WS_SERVER", "Initializing WebSocket server...")
        
        # Start the WebSocket server with compatible settings
        server = await websockets.serve(
            ex_util.handler,
            "0.0.0.0",
            cfg.WS_SERVER_PORT,
            ping_interval=60,
            ping_timeout=30,
            close_timeout=10,
            max_size=2**20,
            max_queue=32,
            compression=None
        )
        
        ws_success("WS_SERVER", "WebSocket server started successfully!")
    
        # Try to get local IP for additional connection info
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            connection_info = {
                "Local IP": f"ws://{local_ip}:{cfg.WS_SERVER_PORT}",
                "Localhost": f"ws://localhost:{cfg.WS_SERVER_PORT}",
                "Loopback": f"ws://127.0.0.1:{cfg.WS_SERVER_PORT}"
            }
        except:
            connection_info = {
                "Localhost": f"ws://localhost:{cfg.WS_SERVER_PORT}"
            }
        
        ws_info("WS_SERVER", "Server accessible via:", connection_info)
        ws_info("WS_SERVER", "Press Ctrl+C to stop the server")
        
        # Start periodic cleanup task
        ws_info("WS_SERVER", "Starting periodic cleanup task...")
        cleanup_task = asyncio.create_task(ex_util.periodic_cleanup())
        ws_success("WS_SERVER", "Periodic cleanup task started")
        
        # Keep the server running indefinitely
        ws_success("WS_SERVER", "Server is now running and waiting for connections...")
        
        try:
            # Create a task that will run forever
            server_task = asyncio.create_task(server.wait_closed())
            
            # Also create a heartbeat task to keep the event loop alive
            async def heartbeat():
                """
                Periodic heartbeat task that prints the current status of connected clients.
                """
                while True:
                    await asyncio.sleep(60)  # Heartbeat every minute
                    current_time = time.strftime('%H:%M:%S')
                    
                    # Preparar datos de estado para el dashboard
                    clients_status = {}
                    active_connections = 0
                    
                    for k, v in cfg.connected_clients.items():
                        try:
                            # Manejar tanto diccionarios como objetos ServerConnection
                            if hasattr(v, '__dict__'):
                                # Es un objeto ServerConnection
                                ws = getattr(v, 'ws', None) or getattr(v, 'websocket', None)
                                ip = getattr(v, 'ip', 'Unknown')
                                hostname = getattr(v, 'hostname', 'Unknown')
                                ports = getattr(v, 'ports', set())
                                last_seen = getattr(v, 'last_seen', None)
                            else:
                                # Es un diccionario
                                ws = v.get("ws")
                                ip = v.get("ip", 'Unknown')
                                hostname = v.get("hostname", 'Unknown')
                                ports = v.get("ports", set())
                                last_seen = v.get("last_seen")
                            
                            # Determinar estado de WebSocket
                            ws_status_val = "unknown"
                            try:
                                if ws is None:
                                    ws_status_val = "None"
                                elif hasattr(ws, "closed"):
                                    if ws.closed:
                                        ws_status_val = "closed"
                                    else:
                                        ws_status_val = "open"
                                        active_connections += 1
                                else:
                                    ws_status_val = "unknown"
                            except Exception:
                                ws_status_val = "error"
                            
                            # Format last_seen
                            if last_seen:
                                try:
                                    if isinstance(last_seen, (int, float)):
                                        last_seen_fmt = datetime.datetime.fromtimestamp(last_seen).strftime("%d/%m/%Y %H:%M:%S")
                                    else:
                                        last_seen_fmt = str(last_seen)
                                except:
                                    last_seen_fmt = "Invalid timestamp"
                            else:
                                last_seen_fmt = "N/A"
                            
                            # Convertir ports a lista si es necesario
                            if isinstance(ports, set):
                                ports_count = len(ports)
                            elif isinstance(ports, (list, tuple)):
                                ports_count = len(ports)
                            else:
                                ports_count = 0
                            
                            clients_status[k] = {
                                "ip": str(ip),
                                "hostname": str(hostname),
                                "ws_status": ws_status_val,
                                "ports": ports_count,
                                "last_seen": last_seen_fmt,
                            }
                            
                        except Exception as e:
                            # Si hay error procesando un cliente, registrarlo pero continuar
                            clients_status[k] = {
                                "ip": "Error",
                                "hostname": "Error",
                                "ws_status": "error",
                                "ports": 0,
                                "last_seen": f"Error: {str(e)[:50]}",
                            }
                    
                    # Usar el sistema de status
                    status_data = {
                        "current_time": current_time,
                        "connected_clients": len(cfg.connected_clients),
                        "active_connections": active_connections
                    }
                    
                    ws_status("WS_SERVER", status_data)
                    
                    # Mostrar detalles de clientes si hay alguno
                    if clients_status:
                        console_handler.print_message("WS_SERVER", "Connected clients summary", 
                                                    MessageType.DEBUG, clients_status)

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
            ws_warning("WS_SERVER", "Received shutdown signal...")
        except Exception as e:
            ws_error("WS_SERVER", f"Server error: {e}")
        finally:
            ws_info("WS_SERVER", "Cleaning up server resources...")
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass
            
            ws_warning("WS_SERVER", "Server shutdown completed")
            
            # Detener consola en vivo antes de salir
            stop_live_console()
        
        return True
        
    except OSError as e:
        if "Address already in use" in str(e):
            ws_error("WS_SERVER", f"Port {cfg.WS_SERVER_PORT} is still in use after cleanup attempts",
                    suggestions=[
                        f"Wait a few moments and run the server again",
                        f"Use a different port: --ws-server-port <PORT>",
                        f"Use 'netstat -tulpn | grep {cfg.WS_SERVER_PORT}' to check what's using the port",
                        f"Kill the process manually: sudo kill -9 <PID>",
                        f"Set environment variable: WS_SERVER_PORT=<PORT>",
                        f"Restart your system if necessary"
                    ])
        else:
            ws_error("WS_SERVER", f"Failed to bind to port {cfg.WS_SERVER_PORT}: {e}")
        
        return False
    except Exception as e:
        ws_error("WS_SERVER", f"Unexpected error starting WebSocket server: {e}")
        
        # Print more detailed error information
        import traceback
        error_details = {"error_type": type(e).__name__, "traceback": traceback.format_exc()}
        ws_error("WS_SERVER", "Detailed error information", error_details)
        
        return False

def start_ws_server():
    """
    Starts the WebSocket server with unified console handling.
    """
    # No limpiar consola aquí, se manejará en live mode
    
    if os.environ.get("RUN_FROM_PANEL") != "1":
        ws_error("WS_SERVER", "This script must be run from Control_Panel.py",
                suggestions=["Use option 5 in the Control Panel to start the WebSocket server"])
        sys.exit(1)

    # Check token availability
    if not cfg.WS_TOKEN:
        ws_error("WS_SERVER", "No WebSocket server token found in .env file")
        # Generate a new token
        cfg.WS_TOKEN = tm.get_or_create_token(console_handler.console, "server")

    ws_info("WS_SERVER", f"WebSocket server token: {cfg.WS_TOKEN}")

    # Load saved state
    ws_info("WS_SERVER", "Loading saved state...")
    try:
        ws_cfg.load_state()
        ws_success("WS_SERVER", "State loaded successfully")
    except Exception as e:
        ws_warning("WS_SERVER", f"Error loading state: {e}")
        ws_info("WS_SERVER", "Starting with clean state...")

    # Setup logging to reduce handshake error noise
    ws_info("WS_SERVER", "Configuring logging...")
    logging.getLogger('websockets').setLevel(logging.WARNING)
    logging.getLogger('websockets.server').setLevel(logging.ERROR)
    logging.getLogger('websockets.protocol').setLevel(logging.ERROR)

    # Filter out common harmless errors
    class HandshakeErrorFilter(logging.Filter):
        def filter(self, record):
            message = record.getMessage()
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

    ws_success("WS_SERVER", "Logging configured - handshake errors filtered")

    # Run the server
    try:
        ws_success("WS_SERVER", "Starting WebSocket server main loop...")

        # Set up signal handling for graceful shutdown
        import signal

        def signal_handler(signum, frame):
            ws_warning("WS_SERVER", f"Received signal {signum}")
            ws_warning("WS_SERVER", "Initiating graceful shutdown...")
            # The KeyboardInterrupt will be caught by the asyncio.run() try/catch
            raise KeyboardInterrupt()

        # Register signal handlers (Unix only)
        if platform.system() != "Windows":
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

        # Run the main async function
        success = asyncio.run(main())

        if success:
            ws_success("WS_SERVER", "WebSocket server completed successfully")
            sys.exit(0)
        else:
            ws_error("WS_SERVER", "WebSocket server failed to start")
            sys.exit(1)

    except KeyboardInterrupt:
        ws_warning("WS_SERVER", "Server shutdown requested by user")
        stop_live_console()  # Asegurar que se detenga la consola en vivo
        npm.stop_npm()
        sys.exit(0)
    except Exception as e:
        ws_error("WS_SERVER", f"Fatal error in server startup: {e}")
        stop_live_console()  # Asegurar que se detenga la consola en vivo

        # Print detailed error information
        import traceback
        error_details = {"traceback": traceback.format_exc()}
        ws_error("WS_SERVER", "Full traceback", error_details)

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
