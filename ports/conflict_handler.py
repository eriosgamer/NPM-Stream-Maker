"""
conflict_handler.py

This module provides functions to handle port conflicts in the stream manager application.
It includes utilities for summarizing conflict resolutions, querying and assigning ports,
notifying clients about conflicts, and managing alternative port assignments.

Key functionalities:
- Displaying a summary of current conflict resolutions.
- Querying conflict resolution information from the database.
- Finding and assigning alternative ports in case of conflicts.
- Notifying connected clients about their port assignments and conflicts.
- Saving and retrieving alternative port assignments.

Dependencies:
- Uses SQLite for persistent storage of stream and port information.
- Relies on a global configuration object (cfg) for shared state.
- Uses the 'rich' library for console output.
"""

import json
import logging
import os
from rich.console import Console
import sqlite3
import sys

# Add parent directory to sys.path to allow relative imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Config import config as cfg
from ports import conflict_resolution as cf_res
from UI.console_handler import ws_info, ws_error, ws_warning

console = Console()


def show_conflict_summary():
    """
    Displays a summary of the current conflict resolutions.
    """
    console.rule("[bold blue]Conflict Resolution Summary")
    cf_res.view_port_conflict_resolutions()


def get_conflict_resolution_info():
    """
    Retrieves information about all conflict resolution streams from the database.
    Returns a list of tuples with details for each conflict.
    """
    if not os.path.exists(cfg.SQLITE_DB_PATH):
        return []

    conflict_streams = []
    conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT incoming_port, forwarding_host, forwarding_port, tcp_forwarding, udp_forwarding FROM stream WHERE is_deleted=0 AND incoming_port != forwarding_port"
        )

        for row in cur.fetchall():
            incoming_port, forwarding_host, forwarding_port, tcp_f, udp_f = row
            protocols = []
            if tcp_f:
                protocols.append("TCP")
            if udp_f:
                protocols.append("UDP")

            conflict_streams.append(
                (incoming_port, forwarding_host, forwarding_port, protocols)
            )

    except Exception as e:
        ws_error("[STREAM_MANAGER]", f"Error getting conflict resolution info: {e}")
    finally:
        conn.close()

    return conflict_streams


# Not used
def find_conflict_resolution_by_multiple_ips(original_port, protocol, client_ips):
    """
    Searches for an existing conflict resolution for a port/protocol for any of the given IPs.
    Returns (alternative_port, resolved_ip) if exists, None otherwise.
    """
    if not os.path.exists(cfg.SQLITE_DB_PATH):
        return None

    conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
    try:
        cur = conn.cursor()

        # Check for existing conflict resolutions for any of the client IPs
        for client_ip in client_ips:
            cur.execute(
                "SELECT incoming_port, forwarding_host FROM stream WHERE forwarding_port=? AND is_deleted=0 AND incoming_port!=forwarding_port",
                (original_port,),
            )

            for row in cur.fetchall():
                incoming_port, forwarding_host = row

                # Check if this matches our protocol and any of our client IPs
                if forwarding_host in client_ips:
                    cur.execute(
                        "SELECT tcp_forwarding, udp_forwarding FROM stream WHERE incoming_port=? AND forwarding_host=? AND is_deleted=0",
                        (incoming_port, forwarding_host),
                    )
                    stream_row = cur.fetchone()

                    if stream_row:
                        tcp_f, udp_f = stream_row
                        has_protocol = (protocol.lower() == "tcp" and tcp_f) or (
                            protocol.lower() == "udp" and udp_f
                        )

                        if has_protocol:
                            return (incoming_port, forwarding_host)

        return None

    except Exception as e:
        ws_error("[STREAM_MANAGER]", f"Error finding conflict resolution: {e}")
        return None
    finally:
        conn.close()


# Copied
def get_next_available_port(
    used_ports, preferred_port, ip, proto, used_by, wg_mode=False, wg_map=None
):
    """
    Returns the next available port not in used_ports, starting from preferred_port.
    If preferred_port is available for this ip/proto, returns it.
    Only assigns a new port if another IP is already using the preferred_port for the same proto.
    If wg_mode is True, use wg_map to assign the same incoming_port as the non-WG server for the same (ip, port, proto).
    """
    # If in WireGuard mode and mapping is provided, use the mapped incoming_port if exists
    if wg_mode and wg_map is not None:
        key = (ip, preferred_port, proto)
        if key in wg_map:
            return wg_map[key]
    # Allow same IP to use the same port for different protocols (tcp/udp)
    # Only conflict if another IP is using the same port/proto
    for (fhost, fport, fproto), assigned_port in used_by.items():
        if fport == preferred_port and fproto == proto and fhost != ip:
            break
    else:
        return preferred_port
    min_port, max_port = 35000, 35099
    for port in range(min_port, max_port):
        if port not in used_ports:
            return port
    raise RuntimeError("No available ports in the specified range.")


# Copied
async def notify_clients_of_conflicts_and_assignments():
    """
    Notify all connected clients about port conflicts and which ports are assigned to which client.
    Assign ports deterministically (first come, first served).
    """
    connected_clients_copy = dict(cfg.connected_clients)
    port_map = {}
    for client_id, info in connected_clients_copy.items():
        for port_proto in info.get("ports", set()):
            port_map.setdefault(port_proto, []).append(client_id)

    new_assigned_ports = {}
    port_conflicts = {}
    for port_proto, clients in port_map.items():
        new_assigned_ports[port_proto] = clients[0]
        if len(clients) > 1:
            port_conflicts[port_proto] = clients

    prev_assigned_ports = dict(cfg.assigned_ports)
    cfg.assigned_ports = new_assigned_ports

    connected_clients_copy = dict(cfg.connected_clients)
    for client_id, info in connected_clients_copy.items():
        assigned = []
        conflicts = []
        for port_proto in info.get("ports", set()):
            owner = cfg.assigned_ports.get(port_proto)
            if owner == client_id:
                assigned.append(
                    {
                        "port": port_proto[0],
                        "protocol": port_proto[1],
                        "assigned": True,
                        "incoming_port": port_proto[0],
                    }
                )
            else:
                alt_port = None
                used_incoming_ports = set(
                    p for (p, _), cid in cfg.assigned_ports.items()
                )
                min_port, max_port = 20000, 60000
                for candidate in range(min_port, max_port):
                    if candidate not in used_incoming_ports:
                        alt_port = candidate
                        break
                if alt_port is not None:
                    assigned.append(
                        {
                            "port": port_proto[0],
                            "protocol": port_proto[1],
                            "assigned": False,
                            "incoming_port": alt_port,
                        }
                    )
                    cfg.assigned_ports[(alt_port, port_proto[1])] = client_id
                conflicts.append(
                    {
                        "port": port_proto[0],
                        "protocol": port_proto[1],
                        "clients": port_map[port_proto],
                        "assigned_to": owner,
                    }
                )
        try:
            ws = info["ws"]
            if hasattr(ws, "closed") and ws.closed:
                continue
            await ws.send(
                json.dumps(
                    {
                        "type": "client_port_assignments",
                        "assignments": assigned,
                        "conflicts": conflicts,
                    }
                )
            )
        except Exception as ex:
            logging.debug(f"Client {client_id} websocket closed or error: {ex}")

    # Notificación de cambios de asignación y conflictos
    for port_proto, clients in port_map.items():
        changed = prev_assigned_ports.get(port_proto) != clients[0]
        client_id = clients[0]
        info = cfg.connected_clients.get(client_id)
        if not info or (hasattr(info["ws"], "closed") and info["ws"].closed):
            continue
        ws = info["ws"]
        try:
            if len(clients) == 1 and changed:
                await ws.send(
                    json.dumps(
                        {
                            "type": "client_port_assignment_update",
                            "port": port_proto[0],
                            "protocol": port_proto[1],
                            "assigned": True,
                            "incoming_port": port_proto[0],
                        }
                    )
                )
                logging.info(
                    f"Port {port_proto[0]} ({port_proto[1]}) assigned to {client_id} after conflict resolution"
                )
            elif len(clients) > 1 and changed:
                await ws.send(
                    json.dumps(
                        {
                            "type": "client_port_assignment_update",
                            "port": port_proto[0],
                            "protocol": port_proto[1],
                            "assigned": False,
                            "incoming_port": port_proto[0],
                        }
                    )
                )
                await ws.send(
                    json.dumps(
                        {
                            "type": "client_port_conflict_resolution",
                            "port": port_proto[0],
                            "protocol": port_proto[1],
                            "conflicting_clients": clients,
                            "assigned_to": client_id,
                        }
                    )
                )
        except Exception as ex:
            try:
                if hasattr(ws, "closed") and not ws.closed:
                    ws_error(
                        "[WS]",
                        f"Error notifying client {client_id} of port assignment/conflict update: {ex}",
                    )
            except Exception:
                logging.debug(
                    f"Error checking websocket status for client {client_id}: {ex}"
                )


# Copied
def get_saved_alternative_port(original_port, protocol, server_ip):
    """
    Retrieve a previously saved alternative port for a given original port, protocol, and server IP.
    """
    key = f"{original_port}|{protocol}|{server_ip}"
    return cfg.port_conflict_resolutions.get((original_port, protocol, server_ip))


# Copied
def save_alternative_port(original_port, protocol, server_ip, alternative_port):
    """
    Save an alternative port assignment for a given original port, protocol, and server IP.
    """
    cfg.port_conflict_resolutions[(original_port, protocol, server_ip)] = (
        alternative_port
    )
