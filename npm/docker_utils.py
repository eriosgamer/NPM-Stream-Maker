import datetime
import subprocess
import os
from rich.console import Console

console = Console()
import time
import asyncio
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg
from npm import npm_handler as npmh
from npm import npm_status as npmst
from ports import conflict_handler as ch
from UI.console_handler import ws_info, ws_error, ws_warning

# This module provides utility functions to check Docker availability
# and set an environment variable accordingly.


# Copied
async def periodic_cleanup():
    """
    Periodic cleanup task to remove disconnected clients.
    """
    while True:
        try:
            await asyncio.sleep(120)  # Increased from 60 to 120 seconds to reduce load
            cleanup_disconnected_clients()
        except Exception as e:
            ws_error("[WS]", f"Error in periodic cleanup: {e}")


def check_docker_available():
    """
    Checks if Docker is available on the system and sets the environment variable DOCKER_AVAILABLE.
    Returns True if Docker is available, False otherwise.
    """
    try:
        # Try to run 'docker --version' to check if Docker is installed and accessible
        result = subprocess.run(
            ["docker", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        if result.returncode == 0:
            # Docker is available, set environment variable to "1"
            os.environ["DOCKER_AVAILABLE"] = "1"
            return True
        else:
            # Docker command failed, set environment variable to "0"
            os.environ["DOCKER_AVAILABLE"] = "0"
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        # Exception occurred (timeout, not found, or other), set environment variable to "0"
        os.environ["DOCKER_AVAILABLE"] = "0"
        return False


def check_docker_compose_available():
    """
    Checks if Docker Compose is available on the system and sets the environment variable DOCKER_COMPOSE_AVAILABLE.
    Returns True if Docker Compose is available, False otherwise.
    """
    try:
        # Try to run 'docker-compose --version' to check if Docker Compose is installed and accessible
        result = subprocess.run(
            ["docker-compose", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        if result.returncode == 0:
            # Docker Compose is available, set environment variable to "1"
            os.environ["DOCKER_COMPOSE_AVAILABLE"] = "1"
            return True
        else:
            # Docker Compose command failed, set environment variable to "0"
            os.environ["DOCKER_COMPOSE_AVAILABLE"] = "0"
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        # Exception occurred (timeout, not found, or other), set environment variable to "0"
        os.environ["DOCKER_COMPOSE_AVAILABLE"] = "0"
        return False


def stop_running_docker_containers():
    """
    Stops all running Docker containers.
    Returns True if successful, False otherwise.
    """
    try:
        # Run 'docker stop $(docker ps -q)' to stop all running containers
        subprocess.run(
            ["docker", "stop", "$(docker", "ps", "-q)"], shell=True, check=True
        )
        return True
    except subprocess.CalledProcessError:
        return False
    except Exception as e:
        ws_error("[WS]", f"Error stopping Docker containers: {e}")
        return False


def check_and_start_npm():
    """
    Check NPM status and optionally try to start it if not running.
    Uses existing NPM_Cleaner functions to avoid code duplication.
    """
    ws_info("[WS]", "Checking NPM container status...")

    try:
        npm_status = npmst.check_npm()

        if npm_status:
            ws_info("[WS]", "NPM container is running and accessible")
            return True

        ws_warning("[WS]", "NPM container is not running or not accessible")
        ws_info("[WS]", "Attempting to start NPM container...")

        # Use existing restart_npm function from NPM_Cleaner
        try:
            npmh.restart_npm()
            ws_info("[WS]", "NPM container start command executed")

            # Wait a moment for NPM to initialize
            ws_info("[WS]", "Waiting for NPM to initialize...")
            time.sleep(10)

            # Check again
            npm_status = npmst.check_npm()
            if npm_status:
                ws_info("[WS]", "NPM is now running and accessible")
                return True
            else:
                ws_warning(
                    "[WS]", "NPM started but not yet accessible, waiting longer..."
                )
                # Give it more time
                time.sleep(15)
                npm_status = npmst.check_npm()
                if npm_status:
                    ws_info("[WS]", "NPM is now accessible")
                    return True
                else:
                    ws_error("[WS]", "NPM still not accessible after waiting")
                    return False
        except Exception as e:
            ws_error("[WS]", f"Error starting NPM: {e}")
            return False
    except Exception as e:
        ws_error("[WS]", f"Error checking NPM status: {e}")
        return False


def cleanup_disconnected_clients():
    """
    Remove clients that are no longer connected or haven't been seen recently.
    """
    current_time = time.time()
    timeout = 300  # 5 minutes

    disconnected = []
    for client_id, info in list(cfg.connected_clients.items()):
        try:
            ws = info.get("ws")
            last_seen = info.get("last_seen", 0)

            # CRITICAL: Fix websocket closed check
            ws_closed = False
            try:
                # websockets 10+ uses .closed (bool), older may use .close_code
                if ws is None:
                    ws_closed = True
                elif hasattr(ws, "closed"):
                    ws_closed = ws.closed
                elif hasattr(ws, "close_code"):
                    ws_closed = ws.close_code is not None
            except Exception:
                ws_closed = True  # Assume closed if we can't check

            # Format last_seen and current_time
            try:
                last_seen_fmt = (
                    datetime.datetime.fromtimestamp(last_seen).strftime(
                        "%d/%m/%Y %I:%M:%S %p"
                    )
                    if last_seen
                    else "N/A"
                )
                now_fmt = datetime.datetime.fromtimestamp(current_time).strftime(
                    "%d/%m/%Y %I:%M:%S %p"
                )
            except Exception:
                last_seen_fmt = str(last_seen)
                now_fmt = str(current_time)

            # Debug: Log client status
            ws_info(
                "[WS]",
                f"Checking client {client_id}: ws_closed={ws_closed}, last_seen={last_seen_fmt}, now={now_fmt}",
            )

            # Check if websocket is closed or client hasn't been seen recently
            if ws_closed or (current_time - last_seen > timeout):
                disconnected.append(client_id)
                del cfg.connected_clients[client_id]
        except Exception as e:
            ws_warning("[WS]", f"Error checking client {client_id}: {e}")
            disconnected.append(client_id)
            if client_id in cfg.connected_clients:
                del cfg.connected_clients[client_id]

    if disconnected:
        ws_warning(
            "[WS]",
            f"Cleaned up {len(disconnected)} disconnected clients: {disconnected}",
        )

        # Reassign ports after cleanup
        asyncio.create_task(ch.notify_clients_of_conflicts_and_assignments())
