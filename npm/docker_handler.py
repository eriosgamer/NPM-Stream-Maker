import json
import sqlite3
import time
import websockets
import os
import sys
from rich.console import Console

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg
from Wireguard import wireguard_tools as wg_tools
from Wireguard import wireguard_utils as wg_utils
from Server import ws_server
from ports import conflict_resolution as cr
from ports import conflict_handler as ch
from Streams import stream_creation as sc
from npm import npm_handler as npmh
from UI.console_handler import ws_info, ws_error, ws_warning

console = Console()

async def handler(websocket, path=None):
    """
    Main WebSocket handler for remote clients.
    Handles authentication, port forwarding, conflict resolution, remote commands,
    and stream management requests.
    """
    peer = websocket.remote_address
    ws_info("[WS]", f"Client connected from {peer}")
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
            ws_info("[WS]", f"Message received from {peer}: {msg_log} on {time.strftime('%Y-%m-%d %H:%M:%S')}")

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

                # Handle server capabilities query
                if data.get("query_capabilities"):
                    ws_info("[WS]", f"Server capabilities query from {peer}")

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

                    ws_info("[WS]", f"Server type: {capabilities['server_capabilities']['server_type']}")
                    await websocket.send(json.dumps(capabilities))
                    continue

                # Handle test connection from Control Panel
                if data.get("test_connection"):
                    hostname = data.get("hostname", "unknown")
                    ws_info("[WS]", f"Test connection from {hostname} ({peer}) - token valid")
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

                    ws_info("[WS]", f"Received {len(ports)} ports from {hostname} ({ip})")
                    ws_info("[WS]", f"Ports pre-approved: {ports_pre_approved}")

                    # Check if this is a WireGuard server
                    wg_mode = wg_tools.get_local_wg_ip("wg0") is not None

                    if not wg_mode:
                        # Conflict resolution server (non-WG): Handle conflict resolution
                        if ports_pre_approved:
                            ws_warning("[WS]", "Received pre-approved ports on conflict resolution server - this should not happen")
                            await websocket.send(json.dumps({
                                "status": "error",
                                "msg": "Pre-approved ports should not be sent to conflict resolution server"
                            }))
                            continue

                        ws_info("[WS]", f"Processing as conflict resolution server (non-WG)")

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
                            ws_info("[WS]", f"Successfully processed ports with {len(conflict_resolutions)} conflicts resolved")
                        except Exception as e:
                            ws_error("[WS]", f"Error in conflict resolution processing: {e}")
                            await websocket.send(json.dumps({
                                "status": "error",
                                "msg": f"Error processing ports: {str(e)}"
                            }))
                    else:
                        # WireGuard server: Only process pre-approved ports
                        if not ports_pre_approved:
                            ws_error("[WS]", f"Received non-pre-approved ports on WG server from {hostname} ({ip})")
                            ws_error("[WS]", f"WireGuard servers should only receive pre-approved ports")
                            await websocket.send(json.dumps({
                                "status": "error",
                                "msg": "WireGuard servers only accept pre-approved ports. Please process through conflict resolution server first."
                            }))
                            continue

                        ws_info("[WS]", f"Processing pre-approved ports as WireGuard server")

                        # Determine peer IP for WireGuard if applicable
                        wg_peer_ip = wg_utils.get_peer_ip_for_client()
                        final_ip = wg_peer_ip if wg_peer_ip else ip
                        ws_info("[WS]", f"Using final IP for streams: {final_ip} (WireGuard peer IP: {wg_peer_ip})")

                        # Process ports and create streams
                        new_entries_to_add = []
                        result_ports = []

                        for entry in ports:
                            # Permitir ambos formatos de clave: port/protocol y puerto/protocolo
                            port = entry.get("port")
                            if port is None:
                                port = entry.get("puerto")
                            proto = entry.get("protocol")
                            if proto is None:
                                proto = entry.get("protocolo")
                            incoming_port = entry.get("incoming_port", port)
                            conflict_resolved = entry.get("conflict_resolved", False)

                            if port is None or proto is None:
                                continue

                            # CRITICAL FIX: For WireGuard, if there is conflict resolution,
                            # use incoming_port for both incoming and forwarding
                            if conflict_resolved and incoming_port != port:
                                # WireGuard client connects directly to the alternate port
                                forwarding_port = incoming_port
                                ws_info("[WS]", f"WG conflict resolution: incoming={incoming_port} → {final_ip}:{forwarding_port} (original port: {port})")
                            else:
                                # No conflict, use the original port
                                forwarding_port = port
                                ws_info("[WS]", f"WG normal: incoming={incoming_port} → {final_ip}:{forwarding_port}")

                            new_entries_to_add.append((incoming_port, proto, final_ip, forwarding_port))

                            result_ports.append({
                                "puerto": port,
                                "protocolo": proto,
                                "incoming_port": incoming_port,
                                "forwarding_port": forwarding_port,  # Add for clarity
                                "updated": True,
                                "conflict_resolved": conflict_resolved
                            })

                        ws_info("[WS]", f"Processing {len(new_entries_to_add)} pre-approved stream entries for WG database...")

                        # --- NUEVO BLOQUE: Verificar si hay cambios reales ---
                        # Consultar streams existentes para este cliente y comparar
                        conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
                        try:
                            cur = conn.cursor()
                            unchanged = []
                            to_add = []
                            for entry in new_entries_to_add:
                                incoming_port, proto, ip_db, forwarding_port = entry
                                cur.execute(
                                    "SELECT forwarding_host, forwarding_port, tcp_forwarding, udp_forwarding FROM stream WHERE incoming_port=? AND is_deleted=0",
                                    (incoming_port,)
                                )
                                row = cur.fetchone()
                                if row:
                                    fwd_host, fwd_port, tcp_f, udp_f = row
                                    proto_tcp = proto == "tcp"
                                    proto_udp = proto == "udp"
                                    # Verifica si la configuración es idéntica
                                    if (
                                        str(fwd_host) == str(ip_db)
                                        and int(fwd_port) == int(forwarding_port)
                                        and ((proto_tcp and tcp_f) or (proto_udp and udp_f))
                                    ):
                                        unchanged.append(entry)
                                    else:
                                        to_add.append(entry)
                                else:
                                    to_add.append(entry)
                            # Si todos los streams ya existen y no hay cambios, responde y no recarga NPM
                            if len(to_add) == 0:
                                ws_info("[WS]", f"Todos los streams ya existen y no requieren actualización. No se sincroniza ni recarga NPM.")
                                await websocket.send(json.dumps({
                                    "status": "ok",
                                    "msg": "No hay cambios en los streams. Todos ya existen y están sincronizados.",
                                    "resultados": result_ports
                                }))
                                continue
                            # Si hay streams nuevos o que requieren actualización, solo procesa esos
                            new_entries_to_add = to_add
                        finally:
                            conn.close()
                        # --- FIN BLOQUE NUEVO ---

                        if new_entries_to_add:
                            try:
                                sc.add_streams_sqlite_with_ip_extended(new_entries_to_add)
                                # Importar scdb aquí para evitar error de variable local no asociada
                                from Streams import stream_creation_db as scdb
                                scdb.sync_streams_conf_with_sqlite()

                                # --- CHANGE: Add log before reloading NPM ---
                                ws_info("[WS]", f"Reloading NPM due to stream change...")
                                npmh.reload_npm()
                                # ----------------------------

                                ws_info("[WS]", f"Successfully processed {len(new_entries_to_add)} WG streams")

                            except Exception as e:
                                ws_error("[WS]", f"Error processing WG streams: {e}")
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
                            ws_info("[WS]", f"Removed inactive ports by client request: {removed}")
                            # --- NEW: Synchronize configuration files and reload NGINX/NPM ---
                            from Streams import stream_creation_db as scdb
                            from npm.npm_handler import reload_npm
                            scdb.sync_streams_conf_with_sqlite()
                            ws_info("[WS]", f"Reloading NPM due to port removal...")
                            reload_npm()
                        await websocket.send(json.dumps({"status": "ok", "msg": f"Removed inactive ports: {removed}"}))
                    finally:
                        conn.close()
                    continue

            except json.JSONDecodeError as e:
                ws_error("[WS]", f"Invalid JSON from {peer}: {e}")
                try:
                    await websocket.send(json.dumps({
                        "status": "error",
                        "msg": "Invalid JSON format"
                    }))
                except:
                    pass
            except Exception as e:
                ws_error("[WS]", f"Error processing message from {peer}: {e}")
                try:
                    await websocket.send(json.dumps({
                        "status": "error",
                        "msg": f"Server error: {str(e)}"
                    }))
                except:
                    pass

    except websockets.ConnectionClosed:
        ws_info("[WS]", f"Client {peer} disconnected")
    finally:
        if client_id and client_id in cfg.connected_clients:
            del cfg.connected_clients[client_id]
            await ch.notify_clients_of_conflicts_and_assignments()