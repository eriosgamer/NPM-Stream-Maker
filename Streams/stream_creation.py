"""
stream_creation.py

This module provides functions for managing stream entries in the SQLite database
for the NPM Stream Maker application. It includes utilities for updating stream forwarding IPs,
cleaning up inactive ports, and adding new streams with extended IP handling.
WireGuard integration is supported for dynamic IP resolution.

Dependencies:
- rich.console for colored console output
- sqlite3 for database operations
- json, os, sys, time for system and file handling
- Config and Wireguard modules from the project

Author: [Your Name or Team]
"""

from rich.console import Console

console = Console()

import json
import os
import sys
import sqlite3
import time

# Add parent directory to sys.path to import project modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg
from Wireguard import wireguard_tools as wg_tools

def update_stream_forwarding_ip(port, new_ip):
    """
    Updates the forwarding IP of an existing stream in the database.
    Returns True if updated, False otherwise.
    """
    if not os.path.exists(cfg.SQLITE_DB_PATH):
        return False
    conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE stream SET forwarding_host=? WHERE incoming_port=?", (new_ip, port))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def remove_inactive_ports_from_streams():
    """
    Removes streams only by explicit client request.
    Does not automatically remove due to server inactivity.
    Cleans ws_ports.json to keep only active ports (for housekeeping).
    """
    # Only clean ws_ports.json to keep active ports (for housekeeping)
    now = int(time.time())
    timeout = 600  # 10 minutes
    if not os.path.exists(cfg.WS_PORTS_FILE):
        return
    try:
        with open(cfg.WS_PORTS_FILE, "r") as f:
            data = json.load(f)
    except Exception:
        data = []
    # Clean ws_ports.json to only keep active ports
    new_data = [entry for entry in data if (
        entry.get("timestamp") and now - int(entry["timestamp"]) <= timeout)]
    with open(cfg.WS_PORTS_FILE, "w") as f:
        json.dump(new_data, f, indent=2)

# Copied


def add_streams_sqlite_with_ip_extended(new_entries):
    """
    Adds multiple streams to the SQLite database with explicit IP handling.
    Groups by port and updates or inserts as appropriate.
    Applies WireGuard logic if available.
    """
    console.print(
        f"[bold green][STREAM_MANAGER][/bold green] Adding {len(new_entries)} pre-processed streams to database...")

    if not new_entries:
        return
    if not os.path.exists(cfg.SQLITE_DB_PATH):
        print("NPM SQLite database not found.")
        return

    conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
    try:
        cur = conn.cursor()
        # Check if the 'stream' table exists
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='stream';")
        if not cur.fetchone():
            print(
                "The 'stream' table does not exist in the database. Cannot add streams.")
            return

        # Get the first user ID (usually admin)
        cur.execute("SELECT id FROM user ORDER BY id LIMIT 1")
        user_row = cur.fetchone()
        if not user_row:
            print("No user found in database. Cannot create streams.")
            return
        owner_user_id = user_row[0]

        # Default metadata for new streams
        default_meta = json.dumps({
            "dns_provider_credentials": "",
            "letsencrypt_agree": False,
            "dns_challenge": True,
            "nginx_online": True,
            "nginx_err": None
        })

        by_port = {}
        console.print(
            f"[bold green][STREAM_MANAGER][/bold green] Adding {len(new_entries)} pre-processed streams to database...")

        # Group entries by incoming port
        for incoming_port, proto, ip, forwarding_port in new_entries:
            if incoming_port not in by_port:
                # New port detected, initialize protocol flags and store IP/forwarding_port
                console.print(
                    f"[bold yellow][STREAM_MANAGER][/bold yellow] New port: incoming={incoming_port}, forwarding={forwarding_port}, IP={ip}")
                by_port[incoming_port] = {
                    "tcp": 0, "udp": 0, "ip": ip, "forwarding_port": forwarding_port}

            # Update protocol flags for this port
            if proto == "tcp":
                by_port[incoming_port]["tcp"] = 1
            elif proto == "udp":
                by_port[incoming_port]["udp"] = 1

            by_port[incoming_port]["ip"] = ip
            by_port[incoming_port]["forwarding_port"] = forwarding_port

        console.print(
            f"[bold green][STREAM_MANAGER][/bold green] Processing {len(by_port)} unique ports...")

        # Check if WireGuard is available (for IP resolution only)
        def wireguard_present():
            # WireGuard is considered present if /etc/wireguard exists or 'wg' binary is found in PATH
            return os.path.exists('/etc/wireguard') or any(
                os.access(os.path.join(path, 'wg'), os.X_OK)
                for path in os.environ.get("PATH", "").split(os.pathsep)
            )

        wg_available = wireguard_present()
        console.print(
            f"[bold cyan][STREAM_MANAGER][/bold cyan] WireGuard available: {wg_available}")

        for incoming_port, protos in by_port.items():
            original_ip = protos["ip"]
            forwarding_port = protos["forwarding_port"]
            final_ip = original_ip

            # Apply WireGuard IP logic if available
            if wg_available:
                peer_ip = wg_tools.get_peer_ip_for_client_stream()
                if peer_ip:
                    console.print(
                        f"[bold cyan][STREAM_MANAGER][/bold cyan] Using WireGuard peer IP: {peer_ip} (client: {original_ip})")
                    final_ip = peer_ip
                else:
                    console.print(
                        f"[bold yellow][STREAM_MANAGER][/bold yellow] WireGuard available but no peer found, using client IP: {original_ip}")
            else:
                console.print(
                    f"[bold green][STREAM_MANAGER][/bold green] No WireGuard, using client IP: {original_ip}")

            console.print(
                f"[bold cyan][STREAM_MANAGER][/bold cyan] Final stream config: incoming={incoming_port}, forwarding_host={final_ip}, forwarding_port={forwarding_port}")

            # Check for existing stream (update vs insert)
            cur.execute(
                "SELECT id, tcp_forwarding, udp_forwarding, forwarding_host, forwarding_port FROM stream WHERE incoming_port=? AND is_deleted=0", (incoming_port,))
            existing_stream = cur.fetchone()

            if existing_stream:
                # Update existing stream with new protocol flags and IP/port if needed
                stream_id, existing_tcp, existing_udp, existing_host, existing_fwd_port = existing_stream
                new_tcp = max(existing_tcp, protos["tcp"])
                new_udp = max(existing_udp, protos["udp"])

                console.print(
                    f"[bold green][STREAM_MANAGER][/bold green] Updating existing stream {stream_id}: TCP {existing_tcp}→{new_tcp}, UDP {existing_udp}→{new_udp}, IP {existing_host}→{final_ip}, fwd_port {existing_fwd_port}→{forwarding_port}")

                cur.execute(
                    "UPDATE stream SET tcp_forwarding=?, udp_forwarding=?, forwarding_host=?, forwarding_port=?, modified_on=datetime('now') WHERE id=?",
                    (new_tcp, new_udp, final_ip, forwarding_port, stream_id)
                )
            else:
                # Insert new stream with all required fields
                console.print(
                    f"[bold green][STREAM_MANAGER][/bold green] Creating new stream: incoming={incoming_port}, forwarding={forwarding_port}, IP={final_ip}, TCP={protos['tcp']}, UDP={protos['udp']}")

                cur.execute(
                    "INSERT INTO stream (created_on, modified_on, owner_user_id, is_deleted, incoming_port, forwarding_host, forwarding_port, tcp_forwarding, udp_forwarding, meta, enabled, certificate_id) VALUES (datetime('now'), datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        owner_user_id,            # owner_user_id
                        0,                        # is_deleted
                        # incoming_port (already processed by ws_server)
                        int(incoming_port),
                        final_ip,                 # forwarding_host
                        int(forwarding_port),     # forwarding_port
                        protos["tcp"],           # tcp_forwarding
                        protos["udp"],           # udp_forwarding
                        default_meta,            # meta
                        1,                       # enabled
                        0                        # certificate_id
                    )
                )

        conn.commit()
        console.print(
            f"[bold green][STREAM_MANAGER][/bold green] Successfully processed {len(by_port)} streams")

    except Exception as e:
        console.print(
            f"[bold red][STREAM_MANAGER][/bold red] Error adding streams to database: {e}")
    finally:
        conn.close()
