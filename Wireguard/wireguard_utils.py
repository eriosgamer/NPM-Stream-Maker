import ipaddress
import platform
import socket
import sqlite3
import struct
import subprocess
import sys
import os

# Add parent directory to sys.path to allow relative imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Config import config as cfg
from Streams import stream_creation as sc
from Streams import stream_creation_db as stream_db
from npm import npm_handler as npm
from Wireguard import wireguard_tools as wg_tools
from rich.console import Console
console = Console()

# This module provides utility functions for managing WireGuard streams and resolving port conflicts.
# It interacts with the database, WireGuard interface, and NPM (Nginx Proxy Manager) to automate stream creation and updates.

def get_peer_ip_for_client():
    """
    Scan the WireGuard subnet and return the first peer IP that responds to ping.
    This function doesn't receive a client_ip as argument since the goal is to find
    the actual peer IP by scanning the WG subnet.
    """
    try:
        local_ip = wg_tools.get_local_wg_ip()
        if not local_ip:
            return None

        # Get subnet from interface
        try:
            output = subprocess.check_output(["ip", "addr", "show", "wg0"], text=True)
            subnet = None
            for line in output.splitlines():
                if "inet " in line:
                    subnet = line.split()[1]
                    break
            if not subnet:
                return None

            net = ipaddress.ip_network(subnet, strict=False)
            # Generate candidate IPs in the subnet, excluding the local WireGuard IP
            candidates = [str(ip) for ip in net.hosts() if str(ip) != local_ip]

            param = "-n" if platform.system().lower() == "windows" else "-c"
            for ip in candidates:
                try:
                    # Ping each candidate IP to check if it is reachable
                    result = subprocess.run(
                        ["ping", param, "1", "-W", "1", ip],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    if result.returncode == 0:
                        return ip
                except Exception:
                    continue
        except Exception:
            pass
        return None
    except Exception as e:
        console.print(f"[bold yellow][WS][/bold yellow] Error finding WireGuard peer: {e}")
        return None

def find_existing_port_for_wg_peer(ip, port, proto):
    """
    Search if there is already a stream for the same port and protocol but with a different (non-WG) IP.
    If it exists, return that IP (the non-WG peer) to keep the port assignment consistent.
    """
    try:
        conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
        cur = conn.cursor()
        # Search for a stream with the same port and protocol, but with a different IP than the WG peer
        cur.execute(
            "SELECT forwarding_host FROM stream WHERE incoming_port=? AND ((tcp_forwarding=1 AND ?='tcp') OR (udp_forwarding=1 AND ?='udp')) AND forwarding_host!=? AND is_deleted=0",
            (port, proto, proto, ip)
        )
        row = cur.fetchone()
        if row:
            return row[0]
    except Exception:
        pass
    finally:
        if 'conn' in locals():
            conn.close()
    return None

async def create_wg_conflict_resolution_streams(wg_streams):
    """
    Create WireGuard streams that forward alternative ports to alternative ports on other servers.
    This allows WireGuard clients to connect to alternative ports and reach the alternative ports on non-WG servers.
    """
    if not wg_streams:
        return

    try:
        new_entries = []

        for incoming_port, protocol, server_ip, forwarding_port in wg_streams:
            # Create stream: incoming alternative_port → server_ip:alternative_port
            console.print(f"[bold green][WS][/bold green] Creating WG stream: incoming port {incoming_port} ({protocol}) → {server_ip}:{forwarding_port}")

            # Check if a stream already exists for the incoming port
            conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, forwarding_host, forwarding_port FROM stream WHERE incoming_port=? AND ((tcp_forwarding=1 AND ?='tcp') OR (udp_forwarding=1 AND ?='udp')) AND is_deleted=0",
                    (incoming_port, protocol, protocol)
                )
                existing = cur.fetchone()

                if existing:
                    stream_id, current_host, current_port = existing
                    console.print(f"[bold yellow][WS][/bold yellow] Stream already exists for port {incoming_port} ({protocol}): {current_host}:{current_port}")

                    # Only update if it's pointing to a different server or port
                    if current_host != server_ip or current_port != forwarding_port:
                        cur.execute(
                            "UPDATE stream SET forwarding_host=?, forwarding_port=?, modified_on=datetime('now') WHERE id=?",
                            (server_ip, forwarding_port, stream_id)
                        )
                        conn.commit()
                        console.print(f"[bold cyan][WS][/bold cyan] Updated existing stream {stream_id} for port {incoming_port} to forward to {server_ip}:{forwarding_port}")
                    else:
                        console.print(f"[bold blue][WS][/bold blue] Stream {stream_id} for port {incoming_port} already correctly configured")
                else:
                    # Create new stream entry for the incoming port
                    new_entries.append((incoming_port, protocol, server_ip, forwarding_port))
                    console.print(f"[bold green][WS][/bold green] Queued new stream: {incoming_port} ({protocol}) → {server_ip}:{forwarding_port}")
            finally:
                conn.close()

        # Create new streams for alternative ports
        if new_entries:
            # Use the extended function to ensure correct forwarding_port
            sc.add_streams_sqlite_with_ip_extended(new_entries)

        # Sync configuration and reload NPM
        if new_entries or any(existing for incoming_port, protocol, server_ip, forwarding_port in wg_streams):
            stream_db.sync_streams_conf_with_sqlite()
            npm.reload_npm()
            console.print(f"[bold green][WS][/bold green] Successfully created/updated {len(new_entries)} WireGuard streams")
        else:
            console.print(f"[bold blue][WS][/bold blue] No new WireGuard streams needed, all ports already configured")

    except Exception as e:
        console.print(f"[bold red][WS][/bold red] Error creating WG streams: {e}")
        raise
