import json
import logging
import os
import sys
import time

# Ensure parent directory is in sys.path for local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from rich.console import Console

from Config import config as cfg
from Streams import stream_com_handler as sch
from Streams import stream_creation as sc
from Streams import stream_creation_db as scdb
from npm import npm_handler as npm
from UI.console_handler import ws_info, ws_error, ws_warning

console = Console()

"""
conflict_resolution.py

This module handles port conflict detection and resolution for the NPM Stream Maker system.
It provides utilities to check for port conflicts in the database, display current conflict resolutions,
and process incoming port requests from clients, resolving conflicts as needed.

Key functionalities:
- Display summaries of current conflict resolutions (from DB and files)
- Check for port conflicts for incoming client requests
- Broadcast conflict resolutions to connected clients
- Process and resolve port conflicts, updating the database and notifying clients

Intended for use by the main server process and websocket handlers.
"""

def print_conflict_resolution_summary():
    """
    Prints a summary of all current conflict resolutions stored in the database.
    """
    # Import here to avoid circular import issues
    from ports.conflict_handler import get_conflict_resolution_info

    ws_info("[CONFLICT]", "[bold cyan]🔍 DATABASE CONFLICT RESOLUTIONS:[/bold cyan]")

    conflict_streams = get_conflict_resolution_info()

    if conflict_streams:
        for incoming_port, forwarding_host, forwarding_port, protocols in conflict_streams:
            protocol_str = "/".join(protocols)
            ws_info("[CONFLICT]", f"[bold green]🔄[/bold green] Incoming port {incoming_port} → {forwarding_host}:{forwarding_port} ({protocol_str})")
        ws_info("[CONFLICT]", f"[bold cyan]Total database conflict resolutions: {len(conflict_streams)}[/bold cyan]")
    else:
        ws_info("[CONFLICT]", "[bold green]✅ No conflict resolutions found in database[/bold green]")


def view_port_conflict_resolutions():
    """
    Shows all current port conflict resolutions, both from the database and from files.
    Also includes client assignments.
    """
    ws_info("[CONFLICT]", "\n[bold cyan]📊 PORT CONFLICT RESOLUTIONS STATUS[/bold cyan]")
    ws_info("[CONFLICT]", "=" * 60)

    # Show database conflict resolutions
    try:
        print_conflict_resolution_summary()
    except Exception as e:
        ws_error("[CONFLICT]", f"Error reading database conflict resolutions: {e}")

    ws_info("[CONFLICT]", "")

    # Show saved conflict resolutions from ws_server
    try:
        import json
        import os

        resolutions_file = "port_conflict_resolutions.json"
        if os.path.exists(resolutions_file):
            with open(resolutions_file, "r") as f:
                saved_resolutions = json.load(f)

            if saved_resolutions:
                ws_info("[CONFLICT]", f"[bold cyan]💾 SAVED CONFLICT MAPPINGS ({len(saved_resolutions)}):[/bold cyan]")
                for key, alt_port in saved_resolutions.items():
                    original_port, protocol, server_ip = key.split("|", 2)
                    ws_info("[CONFLICT]", f"[bold green]📌[/bold green] Server {server_ip}: Port {original_port} ({protocol}) → Alternative port {alt_port}")
            else:
                ws_info("[CONFLICT]", "[bold green]💾 No saved conflict mappings found[/bold green]")
        else:
            ws_info("[CONFLICT]", "[bold yellow]💾 No port conflict resolutions file found[/bold yellow]")
    except Exception as e:
        ws_error("[CONFLICT]", f"Error reading saved conflict resolutions: {e}")

    ws_info("[CONFLICT]", "")

    # Show client assignments
    try:
        assignments_file = "client_assignments.json"
        if os.path.exists(assignments_file):
            with open(assignments_file, "r") as f:
                client_assignments = json.load(f)

            if client_assignments:
                ws_info("[CONFLICT]", f"[bold cyan]📱 CLIENT ASSIGNMENTS ({len(client_assignments)}):[/bold cyan]")
                for key, assignment in client_assignments.items():
                    port, proto = key.split("|", 1)
                    status = "ASSIGNED" if assignment["assigned"] else "CONFLICT RESOLVED"
                    incoming_port = assignment["incoming_port"]
                    if assignment["assigned"]:
                        ws_info("[CONFLICT]", f"[bold green]✓[/bold green] Port {port} ({proto}) → incoming {incoming_port} ({status})")
                    else:
                        ws_info("[CONFLICT]", f"[bold yellow]⚠[/bold yellow] Port {port} ({proto}) → alternative incoming {incoming_port} ({status})")
            else:
                ws_info("[CONFLICT]", "[bold green]📱 No client assignments found[/bold green]")
        else:
            ws_info("[CONFLICT]", "[bold yellow]📱 No client assignments file found[/bold yellow]")
    except Exception as e:
        ws_error("[CONFLICT]", f"Error reading client assignments: {e}")

    ws_info("[CONFLICT]", "\n[bold green]Press Enter to continue...[/bold green]")
    input()


# Copied from other module: checks for port conflicts in the database
def check_port_conflicts(requested_ports, client_ip=None):
    """
    Checks for port conflicts in the database for the requested ports.
    Only considers a conflict if the port is used by a different IP.
    Returns a dictionary with the status of each port.
    """
    ws_info("[STREAM_MANAGER]", f"Checking conflicts for {len(requested_ports)} ports from client {client_ip}")

    if not os.path.exists(cfg.SQLITE_DB_PATH):
        ws_info("[STREAM_MANAGER]", f"Database not found: {cfg.SQLITE_DB_PATH}")
        return {port: {"has_conflict": False, "existing_stream": None} for port, _ in requested_ports}

    conflict_info = {}

    conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
    try:
        cur = conn.cursor()

        for port, protocol in requested_ports:
            ws_info("[STREAM_MANAGER]", f"Checking port {port} ({protocol})")

            # Check if port is used by a DIFFERENT IP address
            if protocol.lower() == "tcp":
                cur.execute(
                    "SELECT id, forwarding_host, forwarding_port, tcp_forwarding FROM stream WHERE incoming_port=? AND tcp_forwarding=1 AND is_deleted=0 AND forwarding_host!=?",
                    (port, client_ip or "")
                )
            elif protocol.lower() == "udp":
                cur.execute(
                    "SELECT id, forwarding_host, forwarding_port, udp_forwarding FROM stream WHERE incoming_port=? AND udp_forwarding=1 AND is_deleted=0 AND forwarding_host!=?",
                    (port, client_ip or "")
                )
            else:
                # Both TCP and UDP
                cur.execute(
                    "SELECT id, forwarding_host, forwarding_port, tcp_forwarding, udp_forwarding FROM stream WHERE incoming_port=? AND (tcp_forwarding=1 OR udp_forwarding=1) AND is_deleted=0 AND forwarding_host!=?",
                    (port, client_ip or "")
                )

            existing_stream = cur.fetchone()

            if existing_stream:
                # Real conflict found - port used by different IP
                ws_error("[STREAM_MANAGER]", f"CONFLICT: Port {port} ({protocol}) already used by different IP: {existing_stream[1]}")
                conflict_info[port] = {
                    "has_conflict": True,
                    "existing_stream": {
                        "id": existing_stream[0],
                        "forwarding_host": existing_stream[1],
                        "forwarding_port": existing_stream[2]
                    }
                }
            else:
                # Check if same client is already using this port (not a conflict)
                if protocol.lower() == "tcp":
                    cur.execute(
                        "SELECT id, forwarding_host, forwarding_port FROM stream WHERE incoming_port=? AND tcp_forwarding=1 AND is_deleted=0 AND forwarding_host=?",
                        (port, client_ip or "")
                    )
                elif protocol.lower() == "udp":
                    cur.execute(
                        "SELECT id, forwarding_host, forwarding_port FROM stream WHERE incoming_port=? AND udp_forwarding=1 AND is_deleted=0 AND forwarding_host=?",
                        (port, client_ip or "")
                    )
                else:
                    cur.execute(
                        "SELECT id, forwarding_host, forwarding_port FROM stream WHERE incoming_port=? AND (tcp_forwarding=1 OR udp_forwarding=1) AND is_deleted=0 AND forwarding_host=?",
                        (port, client_ip or "")
                    )

                same_client_stream = cur.fetchone()

                if same_client_stream:
                    ws_info("[STREAM_MANAGER]", f"No conflict: Port {port} ({protocol}) already used by same client {client_ip}")
                else:
                    ws_info("[STREAM_MANAGER]", f"No conflict: Port {port} ({protocol}) is available")

                conflict_info[port] = {
                    "has_conflict": False,
                    "existing_stream": None
                }

    except Exception as e:
        ws_error("[STREAM_MANAGER]", f"Error checking port conflicts: {e}")
        # Return no conflicts on error to be safe
        conflict_info = {port: {"has_conflict": False,
                                "existing_stream": None} for port, _ in requested_ports}
    finally:
        conn.close()

    conflicts_found = sum(
        1 for info in conflict_info.values() if info["has_conflict"])
    ws_info("[STREAM_MANAGER]", f"Conflict check complete: {conflicts_found} real conflicts found out of {len(requested_ports)} ports")

    return conflict_info


# Copied: broadcasts conflict resolutions to all connected clients
async def broadcast_port_conflict_resolutions(conflicts):
    """
    Broadcast port conflict resolutions to other connected clients (WireGuard servers).
    This tells WireGuard servers what alternative ports to use when connecting to this server.
    """
    if not conflicts:
        return

    # Build message for other servers
    conflict_message = {
        "type": "client_port_conflict_resolutions",
        "conflicts": conflicts,
        "timestamp": int(time.time())
    }

    disconnected_clients = []
    broadcasted_to = 0

    for client_id, client_info in cfg.connected_clients.items():
        try:
            ws = client_info["ws"]
            if hasattr(ws, 'closed') and ws.closed:
                disconnected_clients.append(client_id)
                continue

            # Send the conflict resolution to this client
            await ws.send(json.dumps(conflict_message))
            broadcasted_to += 1
            ws_info("[WS]", f"Sent conflict resolutions to {client_info.get('hostname', 'unknown')} ({client_info.get('ip', 'unknown')})")

        except Exception as ex:
            logging.debug(f"Failed to send conflict resolution to {client_id}: {ex}")
            disconnected_clients.append(client_id)

    # Clean up disconnected clients
    for dc_id in disconnected_clients:
        if dc_id in cfg.connected_clients:
            del cfg.connected_clients[dc_id]

    ws_info("[WS]", f"Broadcasted port conflict resolutions to {broadcasted_to} servers")

# Copied: main entry point for processing incoming port requests and resolving conflicts
async def process_ports_with_conflict_resolution(ip, hostname, ports, websocket):
    """
    NEW: Process ports with conflict resolution as the first step.
    This function handles the new flow where the server without WireGuard
    is the first to process and resolve conflicts.

    Steps:
    - Check for port conflicts for each requested port
    - If a port is already used by this client, acknowledge it
    - If a port has an existing conflict resolution, acknowledge it
    - If a port is free, create a new stream for it
    - If a port is in conflict, assign an alternative port and create a conflict resolution
    - Sync configuration and reload NPM if changes were made
    - Send results back to the client
    """

    ws_info("[WS]", f"Processing {len(ports)} ports from {hostname} ({ip}) - conflict resolution mode")

    # Convert ports to check format and pass client IP
    ports_to_check = [(entry.get("port"), entry.get("protocol", "tcp")) for entry in ports if entry.get("port")]

    # Check for conflicts, excluding same client conflicts
    conflict_info = check_port_conflicts(ports_to_check, client_ip=ip)

    # Separate ports with and without conflicts
    no_conflict_ports = []
    conflict_ports = []
    existing_client_ports = []  # Ports that already exist for this client
    existing_conflict_resolutions = []  # Ports that already have conflict resolutions

    for entry in ports:
        port = entry.get("port")
        protocol = entry.get("protocol", "tcp")

        if not port:
            continue

        # First, check if this exact stream already exists for this client (same incoming and forwarding port)
        existing_stream_id = sch.check_if_stream_exists_for_client(port, protocol, ip)

        if existing_stream_id:
            # Stream already exists for this client - just acknowledge it
            ws_info("[WS]", f"Stream already exists for client {ip}: Port {port} ({protocol}) - Stream ID {existing_stream_id}")
            existing_client_ports.append(entry)
        else:
            # Check if there's an existing conflict resolution for this port
            existing_resolution = sch.check_existing_conflict_resolution(ip, port, protocol)

            if existing_resolution:
                incoming_port, stream_id = existing_resolution
                ws_info("[WS]", f"Existing conflict resolution found for {ip}: Port {port} ({protocol}) → incoming port {incoming_port} (Stream ID {stream_id})")
                existing_conflict_resolutions.append({
                    "entry": entry,
                    "incoming_port": incoming_port,
                    "stream_id": stream_id
                })
            elif not conflict_info.get(port, {}).get("has_conflict", False):
                # No conflict with other clients
                no_conflict_ports.append(entry)
            else:
                # Real conflict with different client - needs new resolution
                conflict_ports.append(entry)

    ws_info("[WS]", f"Existing client streams: {len(existing_client_ports)}")
    ws_info("[WS]", f"Existing conflict resolutions: {len(existing_conflict_resolutions)}")
    ws_info("[WS]", f"Ports without conflicts: {len(no_conflict_ports)}")
    ws_info("[WS]", f"Ports needing new conflict resolution: {len(conflict_ports)}")

    # Process results
    result_ports = []
    conflict_resolutions = []

    # Handle existing client ports (no action needed, just acknowledge)
    for entry in existing_client_ports:
        result_ports.append({
            "puerto": entry.get("port"),
            "protocolo": entry.get("protocol", "tcp"),
            "incoming_port": entry.get("port"),  # Same port for existing streams
            "conflict_resolved": False,
            "status": "existing"
        })

    # Handle existing conflict resolutions (no action needed, just acknowledge)
    for resolution in existing_conflict_resolutions:
        entry = resolution["entry"]
        incoming_port = resolution["incoming_port"]
        result_ports.append({
            "puerto": entry.get("port"),
            "protocolo": entry.get("protocol", "tcp"),
            "incoming_port": incoming_port,
            "conflict_resolved": True,
            "status": "existing_conflict_resolution"
        })

    # Process ports without conflicts normally
    if no_conflict_ports:
        # Create streams for non-conflicting ports
        new_entries = []
        for entry in no_conflict_ports:
            port = entry.get("port")
            protocol = entry.get("protocol", "tcp")
            new_entries.append((port, protocol, ip, port))  # incoming=forwarding for no conflicts

        if new_entries:
            sc.add_streams_sqlite_with_ip_extended(new_entries)
            ws_info("[WS]", f"Created {len(new_entries)} new streams without conflicts")

        # Add to results
        for entry in no_conflict_ports:
            result_ports.append({
                "puerto": entry.get("port"),
                "protocolo": entry.get("protocol", "tcp"),
                "incoming_port": entry.get("port"),
                "conflict_resolved": False,
                "status": "created"
            })

    # Handle new conflict resolution (only for ports that don't have existing resolutions)
    if conflict_ports:
        # Get alternative ports for real conflicts
        conflict_port_numbers = [entry.get("port") for entry in conflict_ports]
        alternative_ports = sch.get_next_available_ports(conflict_port_numbers, len(conflict_ports))

        # Create streams with alternative ports
        conflict_entries = []
        for i, entry in enumerate(conflict_ports):
            original_port = entry.get("port")
            protocol = entry.get("protocol", "tcp")
            alternative_port = alternative_ports[i] if i < len(alternative_ports) else original_port + 10000

            # Create stream: alternative_port -> ip:original_port
            conflict_entries.append((alternative_port, protocol, ip, original_port))

            result_ports.append({
                "puerto": original_port,
                "protocolo": protocol,
                "incoming_port": alternative_port,
                "conflict_resolved": True,
                "status": "new_conflict_resolution"
            })

            conflict_resolutions.append({
                "original_port": original_port,
                "protocol": protocol,
                "alternative_port": alternative_port,
                "client_ip": ip,
                "client_hostname": hostname
            })

        if conflict_entries:
            sc.add_streams_sqlite_with_ip_extended(conflict_entries)
            ws_info("[WS]", f"Created {len(conflict_entries)} NEW conflict resolution streams")

    # Sync and reload NPM only if there were actual changes
    if no_conflict_ports or conflict_ports:
        scdb.sync_streams_conf_with_sqlite()
        npm.reload_npm()
        ws_info("[WS]", f"Configuration synced and NPM reloaded")
    else:
        ws_info("[WS]", f"No new streams created - all ports already exist or have existing resolutions")

    # Send response to client
    total_processed = len(existing_client_ports) + len(existing_conflict_resolutions) + len(no_conflict_ports) + len(conflict_ports)

    response = {
        "status": "ok",
        "type": "client_port_conflict_resolution_response",
        "msg": f"Processed {total_processed} ports. {len(existing_client_ports)} existing, {len(existing_conflict_resolutions)} existing resolutions, {len(no_conflict_ports)} new, {len(conflict_resolutions)} new conflicts resolved.",
        "resultados": result_ports,
        "conflict_resolutions": conflict_resolutions,
        "summary": {
            "existing_streams": len(existing_client_ports),
            "existing_conflict_resolutions": len(existing_conflict_resolutions),
            "new_streams": len(no_conflict_ports),
            "new_conflict_resolutions": len(conflict_resolutions),
            "total_processed": total_processed
        }
    }

    await websocket.send(json.dumps(response))

    return conflict_resolutions
