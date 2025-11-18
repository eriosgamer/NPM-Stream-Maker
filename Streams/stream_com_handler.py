import os
import sqlite3
from rich.console import Console
import sys

# Add the parent directory to sys.path to allow importing the config module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg
from UI.console_handler import ws_error, ws_info, ws_warning

console = Console()

def check_if_stream_exists_for_client(incoming_port, protocol, client_ip):
    """
    Checks if a stream already exists for a specific client and port combination.
    Returns the stream ID if it exists, None otherwise.
    """
    # Check if the database file exists
    if not os.path.exists(cfg.SQLITE_DB_PATH):
        return None

    conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
    try:
        cur = conn.cursor()

        # Query depending on the protocol (TCP/UDP)
        if protocol.lower() == "tcp":
            cur.execute(
                "SELECT id FROM stream WHERE incoming_port=? AND tcp_forwarding=1 AND is_deleted=0 AND forwarding_host=?",
                (incoming_port, client_ip)
            )
        elif protocol.lower() == "udp":
            cur.execute(
                "SELECT id FROM stream WHERE incoming_port=? AND udp_forwarding=1 AND is_deleted=0 AND forwarding_host=?",
                (incoming_port, client_ip)
            )
        else:
            cur.execute(
                "SELECT id FROM stream WHERE incoming_port=? AND (tcp_forwarding=1 OR udp_forwarding=1) AND is_deleted=0 AND forwarding_host=?",
                (incoming_port, client_ip)
            )

        result = cur.fetchone()
        return result[0] if result else None

    except Exception as e:
        ws_error("[STREAM_MANAGER]", f"Error checking existing stream: {e}")
        return None
    finally:
        conn.close()


def get_next_available_ports(conflict_ports, count_needed):
    """
    Gets alternative ports for conflicting ports.
    Searches in a predefined range and avoids already used ports.
    """
    # Check if the database file exists
    if not os.path.exists(cfg.SQLITE_DB_PATH):
        ws_warning("[STREAM_MANAGER]", f"Database not found: {cfg.SQLITE_DB_PATH}")
        # Return default alternative ports
        return [port + 10000 for port in conflict_ports[:count_needed]]

    ws_info("[STREAM_MANAGER]", f"Finding {count_needed} alternative ports for: {conflict_ports}")

    # Get all ports currently in use
    used_ports = set()
    conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT incoming_port FROM stream WHERE is_deleted=0")
        for row in cur.fetchall():
            used_ports.add(row[0])
    finally:
        conn.close()

    ws_info("[STREAM_MANAGER]", f"Found {len(used_ports)} ports already in use")

    # Search for available ports in the alternative range
    alternative_ports = []
    search_range_start = 35000
    search_range_end = 35999

    ws_info("[STREAM_MANAGER]", f"Searching in range {search_range_start}-{search_range_end}")

    for port in range(search_range_start, search_range_end + 1):
        if port not in used_ports:
            alternative_ports.append(port)
            if len(alternative_ports) >= count_needed:
                break

    if len(alternative_ports) < count_needed:
        ws_warning("[STREAM_MANAGER]", f"Warning: Only found {len(alternative_ports)} alternative ports, needed {count_needed}")
        # Fill remaining with higher ports
        for i in range(len(alternative_ports), count_needed):
            alternative_ports.append(search_range_end + 1 + i)

    ws_info("[STREAM_MANAGER]", f"Alternative ports assigned: {alternative_ports}")
    return alternative_ports


def check_existing_conflict_resolution(client_ip, original_port, protocol):
    """
    Checks if a conflict resolution already exists for a given client and port.
    Returns (incoming_port, stream_id) if it exists, None otherwise.
    """
    # Check if the database file exists
    if not os.path.exists(cfg.SQLITE_DB_PATH):
        return None

    conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
    try:
        cur = conn.cursor()

        # Look for existing conflict resolution stream for this client
        # A conflict resolution stream has incoming_port != forwarding_port
        if protocol.lower() == "tcp":
            cur.execute(
                "SELECT incoming_port, id FROM stream WHERE forwarding_host=? AND forwarding_port=? AND tcp_forwarding=1 AND is_deleted=0 AND incoming_port!=forwarding_port",
                (client_ip, original_port)
            )
        elif protocol.lower() == "udp":
            cur.execute(
                "SELECT incoming_port, id FROM stream WHERE forwarding_host=? AND forwarding_port=? AND udp_forwarding=1 AND is_deleted=0 AND incoming_port!=forwarding_port",
                (client_ip, original_port)
            )
        else:
            cur.execute(
                "SELECT incoming_port, id FROM stream WHERE forwarding_host=? AND forwarding_port=? AND (tcp_forwarding=1 OR udp_forwarding=1) AND is_deleted=0 AND incoming_port!=forwarding_port",
                (client_ip, original_port)
            )

        result = cur.fetchone()
        return result if result else None

    except Exception as e:
        ws_error("[STREAM_MANAGER]", f"Error checking existing conflict resolution: {e}")
        return None
    finally:
        conn.close()

# --------------------------------------------------------------------------------
# Module: stream_com_handler.py
# Purpose: Provides utility functions to manage and resolve port conflicts for streams
#          in the NPM Stream Maker application. Handles checking for existing streams,
#          finding available ports, and resolving conflicts for TCP/UDP forwarding.
# Usage:
#   - check_if_stream_exists_for_client: Check if a stream exists for a client/port/protocol.
#   - get_next_available_ports: Suggest alternative ports if conflicts are detected.
#   - check_existing_conflict_resolution: Check if a conflict resolution already exists.
# Dependencies:
#   - Requires a SQLite database defined in cfg.SQLITE_DB_PATH.
#   - Uses the 'rich' library for colored console output.
# --------------------------------------------------------------------------------