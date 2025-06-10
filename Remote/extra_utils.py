"""
extra_utils.py

This module provides utility functions and WebSocket handlers for remote management
of streams, port forwarding, and client connections in the NPM Stream Maker system.

Main responsibilities:
- Handle WebSocket connections and messages from remote clients.
- Process port forwarding requests, conflict resolution, and stream management.
- Manage client connection state and cleanup.
- Interface with WireGuard, NPM, and the local SQLite database.
"""

import sys
import os
import asyncio
import json
import sqlite3
import time
import websockets
import datetime
from rich.console import Console

console = Console()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg
from Wireguard import wireguard_tools as wg_tools
from Wireguard import wireguard_utils as wg_utils
from Server import ws_server
from ports import conflict_resolution as cr
from ports import conflict_handler as ch
from Streams import stream_creation as sc
from Streams import stream_creation_db as scdb
from npm import npm_handler as npm
from npm import npm_status as npmst
from Remote import remote_control

async def handler(websocket, path=None):
    """
    Main WebSocket handler for remote clients.
    Handles authentication, port forwarding, conflict resolution, remote commands,
    and stream management requests.
    """
    peer = websocket.remote_address
    console.print(f"[bold cyan][WS][/bold cyan] Client connected from {peer}")
    client_id = None
    try:
        async for message in websocket:
            try:
                data_preview = json.loads(message)
                data_preview = dict(data_preview)
                if "token" in data_preview:
                    data_preview["token"] = "***hidden***"
                msg_log = json.dumps(data_preview)
            except Exception:
                msg_log = message
            console.print(f"[bold cyan][WS][/bold cyan] Message received from {peer}: {msg_log}")

            try:
                data = json.loads(message)
                token = data.get("token")

                # Validate token
                if not token or str(token).strip() != str(cfg.WS_TOKEN).strip():
                    await websocket.send(json.dumps({"status": "error", "msg": "Invalid token"}))
                    continue

                # Handle token-only message
                if set(data.keys()) == {"token"}:
                    await websocket.send(json.dumps({"status": "ok", "msg": "Valid token, waiting for port data"}))
                    continue

                # --- NEW: Update last_seen on ping messages ---
                if "ping" in data:
                    # Find the client_id corresponding to this websocket
                    for cid, info in cfg.connected_clients.items():
                        if info.get("ws") is websocket:
                            info["last_seen"] = time.time()
                            client_id = cid
                            break
                    # Optionally: you can respond to the ping if you want
                    await websocket.send(json.dumps({"status": "ok", "msg": "pong"}))
                    continue
                # --- END NEW ---

                # NEW: Handle remote commands FIRST
                if "remote_command" in data:
                    console.print(f"[bold cyan][WS][/bold cyan] Processing remote command from {peer}")
                    await remote_control.handle_remote_command(data, websocket)
                    continue

                # NEW: Handle remote stream creation
                if data.get("remote_stream_create"):
                    console.print(f"[bold cyan][WS][/bold cyan] Processing remote stream creation from {peer}")
                    await handle_remote_stream_create(data, websocket)
                    continue

                # NEW: Handle remote stream deletion
                if data.get("remote_stream_delete"):
                    console.print(f"[bold cyan][WS][/bold cyan] Processing remote stream deletion from {peer}")
                    await handle_remote_stream_delete(data, websocket)
                    continue

                # NEW: Handle remote stream listing
                if data.get("remote_stream_list"):
                    console.print(f"[bold cyan][WS][/bold cyan] Processing remote stream list request from {peer}")
                    await handle_remote_stream_list(data, websocket)
                    continue

                # Handle server capabilities query
                if data.get("query_capabilities"):
                    console.print(f"[bold cyan][WS][/bold cyan] Server capabilities query from {peer}")

                    # Check WireGuard availability
                    wg_available = wg_tools.get_local_wg_ip("wg0") is not None
                    wg_peer_ip = wg_utils.get_peer_ip_for_client() if wg_available else None

                    capabilities = {
                        "status": "ok",
                        "server_capabilities": {
                            "has_wireguard": wg_available,
                            "wireguard_ip": wg_tools.get_local_wg_ip("wg0") if wg_available else None,
                            "wireguard_peer_ip": wg_peer_ip,
                            "conflict_resolution_server": not wg_available,  # Non-WG servers handle conflict resolution
                            "port_forwarding_server": wg_available,  # WG servers handle port forwarding only
                            "server_type": "wireguard" if wg_available else "conflict_resolution"
                        }
                    }

                    console.print(f"[bold green][WS][/bold green] Server type: {capabilities['server_capabilities']['server_type']}")
                    await websocket.send(json.dumps(capabilities))
                    continue

                # Handle test connection from Control Panel
                if data.get("test_connection"):
                    hostname = data.get("hostname", "unknown")
                    console.print(f"[bold cyan][WS][/bold cyan] Test connection from {hostname} ({peer}) - token valid")
                    await websocket.send(json.dumps({
                        "status": "ok",
                        "msg": "Connection test successful"
                    }))
                    continue

                # Handle regular port data with conflict resolution
                if "ports" in data:
                    ip = data.get("ip")
                    hostname = data.get("hostname", "unknown")
                    ports = data.get("ports", [])
                    ports_pre_approved = data.get("ports_pre_approved", False)  # Check if ports are pre-approved

                    console.print(f"[bold cyan][WS][/bold cyan] Received {len(ports)} ports from {hostname} ({ip})")
                    console.print(f"[bold cyan][WS][/bold cyan] Ports pre-approved: {ports_pre_approved}")

                    # Check if this is a WireGuard server
                    wg_mode = wg_tools.get_local_wg_ip("wg0") is not None

                    if not wg_mode:
                        # Conflict resolution server (non-WG): Handle conflict resolution
                        if ports_pre_approved:
                            console.print(f"[bold yellow][WS][/bold yellow] WARNING: Received pre-approved ports on conflict resolution server - this should not happen")
                            await websocket.send(json.dumps({
                                "status": "error",
                                "msg": "Pre-approved ports should not be sent to conflict resolution server"
                            }))
                            continue

                        console.print(f"[bold yellow][WS][/bold yellow] Processing as conflict resolution server (non-WG)")

                        # Register this client for conflict detection
                        client_id = ws_server.get_client_id(ip, hostname)

                        if client_id not in cfg.connected_clients:
                            cfg.connected_clients[client_id] = {
                                "ip": ip,
                                "hostname": hostname,
                                "ws": websocket,
                                "ports": set(),
                                "last_seen": time.time(),
                                "assigned_ports": {}
                            }

                        # Update client information
                        port_set = set((entry.get("port"), entry.get("protocol", "tcp")) for entry in ports if entry.get("port"))
                        cfg.connected_clients[client_id]["ports"] = port_set
                        cfg.connected_clients[client_id]["last_seen"] = time.time()
                        cfg.connected_clients[client_id]["ws"] = websocket

                        # Process with conflict resolution
                        try:
                            conflict_resolutions = await cr.process_ports_with_conflict_resolution(ip, hostname, ports, websocket)
                            console.print(f"[bold green][WS][/bold green] Successfully processed ports with {len(conflict_resolutions)} conflicts resolved")
                        except Exception as e:
                            console.print(f"[bold red][WS][/bold red] Error in conflict resolution processing: {e}")
                            await websocket.send(json.dumps({
                                "status": "error",
                                "msg": f"Error processing ports: {str(e)}"
                            }))
                    else:
                        # WireGuard server: Only process pre-approved ports
                        if not ports_pre_approved:
                            console.print(f"[bold red][WS][/bold red] ERROR: Received non-pre-approved ports on WG server from {hostname} ({ip})")
                            console.print(f"[bold red][WS][/bold red] WireGuard servers should only receive pre-approved ports")
                            await websocket.send(json.dumps({
                                "status": "error",
                                "msg": "WireGuard servers only accept pre-approved ports. Please process through conflict resolution server first."
                            }))
                            continue

                        console.print(f"[bold green][WS][/bold green] Processing pre-approved ports as WireGuard server")

                        # Determine peer IP for WireGuard if applicable
                        wg_peer_ip = wg_utils.get_peer_ip_for_client()
                        final_ip = wg_peer_ip if wg_peer_ip else ip
                        console.print(f"[bold cyan][WS][/bold cyan] Using final IP for streams: {final_ip} (WireGuard peer IP: {wg_peer_ip})")

                        # Process ports and create streams
                        new_entries_to_add = []
                        result_ports = []

                        for entry in ports:
                            port = entry.get("port")
                            proto = entry.get("protocol", "tcp")
                            incoming_port = entry.get("incoming_port", port)
                            conflict_resolved = entry.get("conflict_resolved", False)

                            if port is None:
                                continue

                            # CRITICAL FIX: For WireGuard, if there is conflict resolution,
                            # use incoming_port for both incoming and forwarding
                            if conflict_resolved and incoming_port != port:
                                # WireGuard client connects directly to the alternate port
                                forwarding_port = incoming_port
                                console.print(f"[bold yellow][WS][/bold yellow] WG conflict resolution: incoming={incoming_port} → {final_ip}:{forwarding_port} (original port: {port})")
                            else:
                                # No conflict, use the original port
                                forwarding_port = port
                                console.print(f"[bold cyan][WS][/bold cyan] WG normal: incoming={incoming_port} → {final_ip}:{forwarding_port}")

                            new_entries_to_add.append((incoming_port, proto, final_ip, forwarding_port))

                            result_ports.append({
                                "puerto": port,
                                "protocolo": proto,
                                "incoming_port": incoming_port,
                                "forwarding_port": forwarding_port,  # Add for clarity
                                "updated": True,
                                "conflict_resolved": conflict_resolved
                            })

                        console.print(f"[bold cyan][WS][/bold cyan] Processing {len(new_entries_to_add)} pre-approved stream entries for WG database...")

                        if new_entries_to_add:
                            try:
                                sc.add_streams_sqlite_with_ip_extended(new_entries_to_add)
                                scdb.sync_streams_conf_with_sqlite()
                                npm.reload_npm()

                                console.print(f"[bold green][WS][/bold green] Successfully processed {len(new_entries_to_add)} WG streams")

                            except Exception as e:
                                console.print(f"[bold red][WS][/bold red] Error processing WG streams: {e}")
                                await websocket.send(json.dumps({
                                    "status": "error",
                                    "msg": f"Error processing streams: {str(e)}"
                                }))
                                continue

                        # Send successful response
                        result = {
                            "status": "ok",
                            "msg": f"WG Streams synchronized for {ip}. {len(new_entries_to_add)} pre-approved entries processed.",
                            "resultados": result_ports
                        }
                        await websocket.send(json.dumps(result))

                # Handle removal of inactive ports
                elif "remove_ports" in data:
                    remove_ports = data["remove_ports"]
                    conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
                    try:
                        cur = conn.cursor()
                        removed = []
                        for entry in remove_ports:
                            port = entry.get("puerto")
                            proto = entry.get("protocolo", "tcp")
                            # Set is_deleted=1 and enabled=0 for the matching stream and protocol
                            cur.execute(
                                "SELECT id, tcp_forwarding, udp_forwarding FROM stream WHERE incoming_port=? AND is_deleted=0", (port,))
                            row = cur.fetchone()
                            if row:
                                stream_id, tcp_f, udp_f = row
                                if proto == "tcp" and tcp_f:
                                    cur.execute("UPDATE stream SET tcp_forwarding=0, is_deleted=1, enabled=0 WHERE id=?", (stream_id,))
                                    removed.append(f"{port}/tcp")
                                elif proto == "udp" and udp_f:
                                    cur.execute("UPDATE stream SET udp_forwarding=0, is_deleted=1, enabled=0 WHERE id=?", (stream_id,))
                                    removed.append(f"{port}/udp")
                        conn.commit()
                        if removed:
                            console.print(f"[bold yellow][WS][/bold yellow] Removed inactive ports by client request: {removed}")
                        await websocket.send(json.dumps({"status": "ok", "msg": f"Removed inactive ports: {removed}"}))
                    finally:
                        conn.close()
                    continue

            except json.JSONDecodeError as e:
                console.print(f"[bold red][WS][/bold red] Invalid JSON from {peer}: {e}")
                try:
                    await websocket.send(json.dumps({
                        "status": "error",
                        "msg": "Invalid JSON format"
                    }))
                except:
                    pass
            except Exception as e:
                console.print(f"[bold red][WS][/bold red] Error processing message from {peer}: {e}")
                try:
                    await websocket.send(json.dumps({
                        "status": "error",
                        "msg": f"Server error: {str(e)}"
                    }))
                except:
                    pass

    except websockets.ConnectionClosed:
        console.print(f"[bold cyan][WS][/bold cyan] Client {peer} disconnected")
    finally:
        if client_id and client_id in cfg.connected_clients:
            del cfg.connected_clients[client_id]
            await ch.notify_clients_of_conflicts_and_assignments()

# Copied
async def handle_remote_stream_create(data, websocket):
    """
    Handle remote stream creation requests.
    """
    try:
        stream_config = data.get("stream_config", {})
        incoming_port = stream_config.get("incoming_port")
        forwarding_host = stream_config.get("forwarding_host")
        forwarding_port = stream_config.get("forwarding_port")
        protocol = stream_config.get("protocol", "tcp")
        access_control = stream_config.get("access_control", {})

        if not all([incoming_port, forwarding_host, forwarding_port]):
            await websocket.send(json.dumps({
                "status": "error",
                "msg": "Missing required stream configuration parameters"
            }))
            return

        console.print(f"[bold cyan][WS][/bold cyan] Creating remote stream: {incoming_port} ({protocol}) → {forwarding_host}:{forwarding_port}")

        # Check if stream already exists
        conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM stream WHERE incoming_port=? AND ((tcp_forwarding=1 AND ?='tcp') OR (udp_forwarding=1 AND ?='udp')) AND is_deleted=0",
                (incoming_port, protocol, protocol)
            )
            existing = cur.fetchone()

            if existing:
                await websocket.send(json.dumps({
                    "status": "error",
                    "msg": f"Stream already exists for port {incoming_port} ({protocol})"
                }))
                return

            # Create stream entry
            tcp_forwarding = 1 if protocol in ["tcp", "both"] else 0
            udp_forwarding = 1 if protocol in ["udp", "both"] else 0

            # Prepare access control metadata
            meta_data = {}
            if access_control.get("enabled", False):
                meta_data["access_list"] = {
                    "enabled": True,
                    "allowed_ips": access_control.get("allowed_ips", []),
                    "denied_ips": access_control.get("denied_ips", [])
                }

            meta_json = json.dumps(meta_data) if meta_data else "{}"

            cur.execute("""
                INSERT INTO stream (incoming_port, forwarding_host, forwarding_port,
                                  tcp_forwarding, udp_forwarding, enabled, is_deleted,
                                  created_on, modified_on, meta)
                VALUES (?, ?, ?, ?, ?, 1, 0, datetime('now'), datetime('now'), ?)
            """, (incoming_port, forwarding_host, forwarding_port, tcp_forwarding, udp_forwarding, meta_json))

            stream_id = cur.lastrowid
            conn.commit()

            console.print(f"[bold green][WS][/bold green] Created stream ID {stream_id}")

            # Sync configuration and reload NPM
            scdb.sync_streams_conf_with_sqlite()
            npm.reload_npm()

            await websocket.send(json.dumps({
                "status": "ok",
                "msg": f"Stream created successfully - ID: {stream_id}",
                "stream_id": stream_id
            }))

        finally:
            conn.close()

    except Exception as e:
        console.print(f"[bold red][WS][/bold red] Error creating remote stream: {e}")
        await websocket.send(json.dumps({
            "status": "error",
            "msg": f"Error creating stream: {str(e)}"
        }))

# Copied
async def handle_remote_stream_delete(data, websocket):
    """
    Handle remote stream deletion requests.
    """
    try:
        port = data.get("port")
        protocol = data.get("protocol", "tcp")

        if not port:
            await websocket.send(json.dumps({
                "status": "error",
                "msg": "Missing port parameter"
            }))
            return

        console.print(f"[bold cyan][WS][/bold cyan] Deleting remote stream: Port {port} ({protocol})")

        conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
        try:
            cur = conn.cursor()

            # Find the stream
            cur.execute(
                "SELECT id, tcp_forwarding, udp_forwarding FROM stream WHERE incoming_port=? AND is_deleted=0",
                (port,)
            )
            row = cur.fetchone()

            if not row:
                await websocket.send(json.dumps({
                    "status": "error",
                    "msg": f"No active stream found for port {port}"
                }))
                return

            stream_id, tcp_f, udp_f = row

            # Delete based on protocol
            if protocol == "tcp" and tcp_f:
                if udp_f:
                    # Only disable TCP, keep UDP
                    cur.execute("UPDATE stream SET tcp_forwarding=0, is_deleted=1, enabled=0 WHERE id=?", (stream_id,))
                    console.print(f"[bold yellow][WS][/bold yellow] Disabled TCP for stream {stream_id}, UDP remains active")
                else:
                    # Delete entire stream
                    cur.execute("UPDATE stream SET is_deleted=1, enabled=0 WHERE id=?", (stream_id,))
                    console.print(f"[bold red][WS][/bold red] Deleted stream {stream_id}")
            elif protocol == "udp" and udp_f:
                if tcp_f:
                    # Only disable UDP, keep TCP
                    cur.execute("UPDATE stream SET udp_forwarding=0 WHERE id=?", (stream_id,))
                    console.print(f"[bold yellow][WS][/bold yellow] Disabled UDP for stream {stream_id}, TCP remains active")
                else:
                    # Delete entire stream
                    cur.execute("UPDATE stream SET is_deleted=1, enabled=0 WHERE id=?", (stream_id,))
                    console.print(f"[bold red][WS][/bold red] Deleted stream {stream_id}")
            elif protocol == "both":
                # Delete entire stream
                cur.execute("UPDATE stream SET is_deleted=1, enabled=0 WHERE id=?", (stream_id,))
                console.print(f"[bold red][WS][/bold red] Deleted stream {stream_id}")
            else:
                await websocket.send(json.dumps({
                    "status": "error",
                    "msg": f"Stream for port {port} does not support protocol {protocol}"
                }))
                return

            conn.commit()

            # Sync configuration and reload NPM
            scdb.sync_streams_conf_with_sqlite()
            npm.reload_npm()

            await websocket.send(json.dumps({
                "status": "ok",
                "msg": f"Stream for port {port} ({protocol}) deleted successfully"
            }))

        finally:
            conn.close()

    except Exception as e:
        console.print(f"[bold red][WS][/bold red] Error deleting remote stream: {e}")
        await websocket.send(json.dumps({
            "status": "error",
            "msg": f"Error deleting stream: {str(e)}"
        }))

# Copied
async def handle_remote_stream_list(data, websocket):
    """
    Handle remote stream listing requests.
    """
    try:
        console.print(f"[bold cyan][WS][/bold cyan] Getting stream list for remote client")

        conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, incoming_port, forwarding_host, forwarding_port,
                       tcp_forwarding, udp_forwarding, enabled, meta
                FROM stream WHERE is_deleted=0
                ORDER BY incoming_port
            """)
            rows = cur.fetchall()

            streams = []
            for row in rows:
                stream_id, incoming_port, forwarding_host, forwarding_port, tcp_f, udp_f, enabled, meta = row

                streams.append({
                    "id": stream_id,
                    "incoming_port": incoming_port,
                    "forwarding_host": forwarding_host,
                    "forwarding_port": forwarding_port,
                    "tcp_forwarding": bool(tcp_f),
                    "udp_forwarding": bool(udp_f),
                    "enabled": bool(enabled),
                    "meta": meta or "{}"
                })

            console.print(f"[bold green][WS][/bold green] Retrieved {len(streams)} streams")

            await websocket.send(json.dumps({
                "status": "ok",
                "streams": streams
            }))

        finally:
            conn.close()

    except Exception as e:
        console.print(f"[bold red][WS][/bold red] Error listing remote streams: {e}")
        await websocket.send(json.dumps({
            "status": "error",
            "msg": f"Error listing streams: {str(e)}"
        }))

# Copied
def check_and_start_npm():
    """
    Check NPM status and optionally try to start it if not running.
    Uses existing NPM_Cleaner functions to avoid code duplication.
    """
    console.print("[bold cyan][WS][/bold cyan] Checking NPM container status...")

    try:
        npm_status = npmst.check_npm()

        if npm_status:
            console.print("[bold green][WS][/bold green] NPM container is running and accessible")
            return True

        console.print("[bold yellow][WS][/bold yellow] NPM container is not running or not accessible")
        console.print("[bold cyan][WS][/bold cyan] Attempting to start NPM container...")

        # Use existing restart_npm function from NPM_Cleaner
        try:
            npm.restart_npm()
            console.print("[bold green][WS][/bold green] NPM container start command executed")

            # Wait a moment for NPM to initialize
            console.print("[bold cyan][WS][/bold cyan] Waiting for NPM to initialize...")
            time.sleep(10)

            # Check again
            npm_status = npmst.check_npm()
            if npm_status:
                console.print("[bold green][WS][/bold green] NPM is now running and accessible")
                return True
            else:
                console.print("[bold yellow][WS][/bold yellow] NPM started but not yet accessible, waiting longer...")
                # Give it more time
                time.sleep(15)
                npm_status = npmst.check_npm()
                if npm_status:
                    console.print("[bold green][WS][/bold green] NPM is now accessible")
                    return True
                else:
                    console.print("[bold red][WS][/bold red] NPM still not accessible after waiting")
                    return False
        except Exception as e:
            console.print(f"[bold red][WS][/bold red] Error starting NPM: {e}")
            return False
    except Exception as e:
        console.print(f"[bold red][WS][/bold red] Error checking NPM status: {e}")
        return False

# Copied
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
                elif hasattr(ws, 'closed'):
                    ws_closed = ws.closed
                elif hasattr(ws, 'close_code'):
                    ws_closed = ws.close_code is not None
            except Exception:
                ws_closed = True  # Assume closed if we can't check

            # Format last_seen and current_time
            try:
                last_seen_fmt = datetime.datetime.fromtimestamp(last_seen).strftime("%d/%m/%Y %I:%M:%S %p") if last_seen else "N/A"
                now_fmt = datetime.datetime.fromtimestamp(current_time).strftime("%d/%m/%Y %I:%M:%S %p")
            except Exception:
                last_seen_fmt = str(last_seen)
                now_fmt = str(current_time)

            # Debug: Log client status
            console.print(f"[bold gray][WS][/bold gray] Checking client {client_id}: ws_closed={ws_closed}, last_seen={last_seen_fmt}, now={now_fmt}")

            # Check if websocket is closed or client hasn't been seen recently
            if ws_closed or (current_time - last_seen > timeout):
                disconnected.append(client_id)
                del cfg.connected_clients[client_id]
        except Exception as e:
            console.print(f"[bold yellow][WS][/bold yellow] Error checking client {client_id}: {e}")
            disconnected.append(client_id)
            if client_id in cfg.connected_clients:
                del cfg.connected_clients[client_id]

    if disconnected:
        console.print(f"[bold yellow][WS][/bold yellow] Cleaned up {len(disconnected)} disconnected clients: {disconnected}")

        # Reassign ports after cleanup
        asyncio.create_task(ch.notify_clients_of_conflicts_and_assignments())


# Copied
async def periodic_cleanup():
    """
    Periodic cleanup task to remove disconnected clients.
    """
    while True:
        try:
            await asyncio.sleep(60)  # Run every minute
            cleanup_disconnected_clients()
        except Exception as e:
            console.print(f"[bold red][WS][/bold red] Error in periodic cleanup: {e}")
