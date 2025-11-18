import json
import time
from Config import config as cfg
import socket
import os
import sys
import subprocess
import platform
from rich.console import Console
from UI.console_handler import ws_info, ws_warning, ws_error

console = Console()

# Add the parent directory to sys.path to allow imports from sibling modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
ports_utils.py

This module provides utility functions for managing and inspecting network ports,
including checking if a port is in use, finding processes using a port, clearing
conflict resolution files, and saving WebSocket port assignments.

Intended for use in the NPM Stream Maker project.
"""


def clear_conflict_resolution_files():
    """
    Removes all conflict resolution files when cleaning streams.
    """
    cleared_files = []
    for file_path in cfg.CONFLICT_FILES:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                cleared_files.append(file_path)
        except Exception as e:
            ws_warning("[WS]", f"Could not clear {file_path}: {e}")

    if cleared_files:
        ws_info(
            "[WS]", f"🧹 Cleared conflict resolution files: {', '.join(cleared_files)}"
        )
    else:
        ws_info("[WS]", "🧹 No conflict resolution files to clear")


def is_port_in_use(port):
    """
    Checks if a specific port is currently in use.
    Returns True if it is in use, False otherwise.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", port))
            return False
    except OSError:
        return True


def get_process_using_port(port):
    """
    Returns a list of processes (pid, command) that are using the given port.
    Uses different methods depending on the operating system.
    """
    processes = []
    try:
        if platform.system().lower() == "windows":
            # Windows: use netstat -ano and tasklist
            output = subprocess.check_output(
                ["netstat", "-ano"], text=True, errors="ignore"
            )
            pids = []
            for line in output.splitlines():
                if f":{port}" in line and (
                    "LISTENING" in line or "ESTABLISHED" in line
                ):
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        if pid.isdigit():
                            pids.append(pid)

            # Get process info for each PID
            for pid in set(pids):  # Remove duplicates
                try:
                    task_output = subprocess.check_output(
                        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"],
                        text=True,
                        errors="ignore",
                    )
                    lines = task_output.strip().split("\n")
                    if len(lines) > 1:
                        # Parse CSV format
                        task_info = lines[1].replace('"', "").split(",")
                        if len(task_info) >= 1:
                            processes.append((pid, task_info[0]))
                        else:
                            processes.append((pid, "unknown"))
                    else:
                        processes.append((pid, "unknown"))
                except Exception:
                    processes.append((pid, "unknown"))
        else:
            # Linux/Unix: try multiple approaches
            try:
                # Try lsof first (most detailed)
                output = subprocess.check_output(
                    ["lsof", "-i", f":{port}"], text=True, errors="ignore"
                )
                for line in output.splitlines()[1:]:  # Skip header
                    parts = line.split()
                    if len(parts) >= 2:
                        command = parts[0]
                        pid = parts[1]
                        processes.append((pid, command))
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Fallback to netstat + ps
                try:
                    output = subprocess.check_output(
                        ["netstat", "-tlnp"], text=True, errors="ignore"
                    )
                    for line in output.splitlines():
                        if f":{port}" in line and "LISTEN" in line:
                            parts = line.split()
                            if len(parts) >= 6:
                                pid = parts[6].split("/")[0]
                                command = parts[0]
                                if pid.isdigit():
                                    processes.append((pid, command))
                except Exception:
                    # Last resort: ss command
                    try:
                        output = subprocess.check_output(
                            ["ss", "-tlnp"], text=True, errors="ignore"
                        )
                        for line in output.splitlines():
                            if ":" in line and line.split()[-1] != "-":
                                parts = line.split()
                                if len(parts) > 0:
                                    pid_info = parts[-1]
                                    if "pid=" in pid_info:
                                        pid = pid_info.split("pid=")[1].split(",")[0]
                                        command = (
                                            parts[0] if len(parts) > 0 else "unknown"
                                        )
                                        processes.append((pid, command))
                    except Exception:
                        pass
    except Exception as e:
        ws_warning("[PORT_DETECTION]", f"Error detecting processes on port {port}: {e}")

    return processes


def save_ws_port(ip, assigned_port):
    """
    Saves or updates the assigned WebSocket port for a given IP address,
    along with a timestamp, in the configured WS_PORTS_FILE.
    """
    try:
        if os.path.exists(cfg.WS_PORTS_FILE):
            with open(cfg.WS_PORTS_FILE, "r") as f:
                data = json.load(f)
        else:
            data = []

        # Update or add entry
        for entry in data:
            if entry.get("ip") == ip:
                entry["port"] = assigned_port
                entry["timestamp"] = int(time.time())
                break
        else:
            data.append(
                {"ip": ip, "port": assigned_port, "timestamp": int(time.time())}
            )

        with open(cfg.WS_PORTS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        ws_error("[WS]", f"Error saving WS port: {e}")


def load_ws_ports():
    """
    Loads the WebSocket ports from the configured WS_PORTS_FILE.
    Returns a list of dictionaries with 'ip', 'port', and 'timestamp'.
    """
    try:
        if os.path.exists(cfg.WS_PORTS_FILE):
            with open(cfg.WS_PORTS_FILE, "r") as f:
                return json.load(f)
        else:
            return []
    except Exception as e:
        ws_error("[WS]", f"Error loading WS ports: {e}")
        return []


def port_file_age():
    """
    Returns the age of the port file in seconds.
    If the file does not exist, returns None.
    """
    if not os.path.exists(cfg.WS_PORTS_FILE):
        return None
    return int(time.time() - os.path.getmtime(cfg.WS_PORTS_FILE))


def ports_file_age():
    """
    Returns the age of the ports.txt file in seconds.
    If the file does not exist, returns None.
    """
    ports_file_path = "ports.txt"
    if not os.path.exists(ports_file_path):
        return None
    return int(time.time() - os.path.getmtime(ports_file_path))


def should_regenerate_ports_file():
    """
    Determines if the ports.txt file should be regenerated.
    Returns True if the file doesn't exist or is older than 24 hours.
    """
    age = ports_file_age()
    if age is None:
        ws_warning("[PORT_SCANNER]", "ports.txt not found, regeneration needed")
        return True

    # 24 hours in seconds
    max_age = 60 * 60 * 24
    if age > max_age:
        ws_warning(
            "[PORT_SCANNER]", f"ports.txt is {age//3600} hours old, regeneration needed"
        )
        return True

    return False
