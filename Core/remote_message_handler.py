from rich.console import Console
import sys
import os
import json
import time
import sqlite3

# Add the parent directory to sys.path to allow imports from sibling modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg
from Wireguard import wireguard_tools as wg_tools
from Wireguard import wireguard_utils as wg_utils
from Server import ws_server
from ports import conflict_resolution as cr
from Streams import stream_creation as sc
from npm import npm_handler as npmh
from UI.console_handler import ws_info, ws_error, ws_warning

# Initialize Rich console for colored terminal output
console = Console()

# Esta lista almacenará puertos que han sido solicitados para creación de stream desde un servidor remoto.
# El ciclo principal del servidor debe procesar estos puertos como si fueran locales.
pending_remote_ports = (
    []
)  # Lista global para almacenar puertos pendientes de streams remotos (aún no procesados)
# Lista global para almacenar puertos ya procesados y sincronizados con clientes
synced_remote_ports = set()  # set de (incoming_port, proto)

# Cada entrada en pending_remote_ports será una tupla extendida:
# (incoming_port, proto, forwarding_host, forwarding_port, acl_allow_list, acl_deny_list, timestamp)
# Si timestamp no está, se asume que es reciente.

REMOTE_PORT_TIMEOUT = 600  # 10 minutos


def clean_old_pending_remote_ports():
    """Elimina puertos pendientes que sean antiguos (más de REMOTE_PORT_TIMEOUT segundos)."""
    global pending_remote_ports
    now = int(time.time())
    new_pending = []
    for entry in pending_remote_ports:
        # Compatibilidad: si la tupla tiene 6 elementos, agregar timestamp actual
        if len(entry) == 6:
            entry = (*entry, now)
        port, proto, host, fwd_port, allow, deny, ts = entry
        if now - ts <= REMOTE_PORT_TIMEOUT:
            new_pending.append(entry)
        else:
            ws_info("[REMOTE]", f"Limpiando puerto remoto antiguo: {port}/{proto} -> {host}:{fwd_port}")
    pending_remote_ports = new_pending


def remove_remote_port(port, proto):
    """Elimina explícitamente un puerto remoto pendiente."""
    global pending_remote_ports
    before = len(pending_remote_ports)
    pending_remote_ports = [
        entry
        for entry in pending_remote_ports
        if not (entry[0] == port and entry[1] == proto)
    ]
    after = len(pending_remote_ports)
    if before != after:
        ws_info("[REMOTE]", f"Puerto remoto eliminado manualmente: {port}/{proto}")


def get_pending_remote_ports():
    """Devuelve una copia de los puertos pendientes (no procesados aún)."""
    clean_old_pending_remote_ports()
    return list(pending_remote_ports)


def get_all_remote_ports():
    """Devuelve todos los puertos remotos recibidos (pendientes y ya sincronizados)."""
    clean_old_pending_remote_ports()
    return list(pending_remote_ports) + [tuple(x) for x in synced_remote_ports]


def mark_remote_port_synced(port_tuple):
    """Marca un puerto remoto como sincronizado con los clientes."""
    synced_remote_ports.add(port_tuple)


# This function handles incoming messages from the server and updates the client state accordingly.
# It processes different message types related to port assignments and conflicts.
async def handle_server_message(data, websocket=None):
    """
    Maneja mensajes cuyo type empieza con 'remote_'.
    Este handler asume que el mensaje ya fue validado y autorizado.
    """
    # Si es str, intenta decodificar como JSON
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            ws_info("[REMOTE]", f"Mensaje remoto recibido (texto): {data}")
            return

    message_type = data.get("type")
    remote_target = data.get("remote_target", "server")
    if (
        message_type
        and message_type.startswith("remote_")
        and remote_target != "server"
    ):
        # Ignorar mensajes que no son para el server
        return

    if message_type in ("ping", "remote_ping") and websocket is not None:
        try:
            await websocket.send("ok")
            ws_info("[REMOTE]", f"{message_type} recibido (JSON), respondido con ok.")
        except Exception as e:
            ws_error("[REMOTE]", f"Error al responder {message_type}: {e}")
        return

    elif message_type == "remote_create_stream":
        # Recibe datos para crear un stream manualmente
        stream_data = data.get("stream_data")
        if not stream_data:
            if websocket is not None:
                await websocket.send(
                    json.dumps({"status": "error", "msg": "No stream_data provided"})
                )
            return
        try:
            global pending_remote_ports
            now = int(time.time())
            # acl_allow_list y acl_deny_list se pasan directamente en stream_data
            if int(stream_data.get("tcp_forwarding", 0)):
                key = (int(stream_data["incoming_port"]), "tcp")
                entry = (
                    key[0],
                    key[1],
                    stream_data["forwarding_host"],
                    int(stream_data["forwarding_port"]),
                    stream_data.get("acl_allow_list", []),
                    stream_data.get("acl_deny_list", []),
                    now,
                )
                if not any(
                    e[0] == entry[0] and e[1] == entry[1] for e in pending_remote_ports
                ):
                    pending_remote_ports.append(entry)
            if int(stream_data.get("udp_forwarding", 0)):
                key = (int(stream_data["incoming_port"]), "udp")
                entry = (
                    key[0],
                    key[1],
                    stream_data["forwarding_host"],
                    int(stream_data["forwarding_port"]),
                    stream_data.get("acl_allow_list", []),
                    stream_data.get("acl_deny_list", []),
                    now,
                )
                if not any(
                    e[0] == entry[0] and e[1] == entry[1] for e in pending_remote_ports
                ):
                    pending_remote_ports.append(entry)
            if websocket is not None:
                await websocket.send(
                    json.dumps(
                        {"status": "ok", "msg": "Stream recibido, será procesado"}
                    )
                )
            ws_info("[REMOTE]", f"Stream remoto recibido y encolado para procesamiento.")
        except Exception as e:
            if websocket is not None:
                await websocket.send(json.dumps({"status": "error", "msg": str(e)}))
            ws_error("[REMOTE]", f"Error encolando stream remoto: {e}")

    # Handle regular port data with conflict resolution
    elif message_type == "conflict_resolution_ports":
        ip = data.get("ip")
        hostname = data.get("hostname", "unknown")
        ports = data.get("ports", [])
        ports_pre_approved = data.get(
            "ports_pre_approved", False
        )  # Check if ports are pre-approved

        ws_info("[WS]", f"Received {len(ports)} ports from {hostname} ({ip})")
        ws_info("[WS]", f"Ports pre-approved: {ports_pre_approved}")

        # Check if this is a WireGuard server
        wg_mode = wg_tools.get_local_wg_ip("wg0") is not None

        if not wg_mode:
            # Conflict resolution server (non-WG): Handle conflict resolution
            if ports_pre_approved:
                ws_warning("[WS]", f"Received pre-approved ports on conflict resolution server - this should not happen")
                if websocket is not None:
                    await websocket.send(
                        json.dumps(
                            {
                                "status": "error",
                                "msg": "Pre-approved ports should not be sent to conflict resolution server",
                            }
                        )
                    )
                return

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
                    "assigned_ports": {},
                }

            # Update client information
            port_set = set(
                (entry.get("port"), entry.get("protocol", "tcp"))
                for entry in ports
                if entry.get("port")
            )
            cfg.connected_clients[client_id]["ports"] = port_set
            cfg.connected_clients[client_id]["last_seen"] = time.time()
            cfg.connected_clients[client_id]["ws"] = websocket

            # Process with conflict resolution
            try:
                conflict_resolutions = await cr.process_ports_with_conflict_resolution(
                    ip, hostname, ports, websocket
                )
                ws_info("[WS]", f"Successfully processed ports with {len(conflict_resolutions)} conflicts resolved")
            except Exception as e:
                ws_error("[WS]", f"Error in conflict resolution processing: {e}")
                if websocket is not None:
                    await websocket.send(
                        json.dumps(
                            {"status": "error", "msg": f"Error processing ports: {str(e)}"}
                        )
                    )
        else:
            # WireGuard server: Only process pre-approved ports
            if not ports_pre_approved:
                ws_error("[WS]", f"Received non-pre-approved ports on WG server from {hostname} ({ip})")
                ws_error("[WS]", f"WireGuard servers should only receive pre-approved ports")
                if websocket is not None:
                    await websocket.send(
                        json.dumps(
                            {
                                "status": "error",
                                "msg": "WireGuard servers only accept pre-approved ports. Please process through conflict resolution server first.",
                            }
                        )
                    )
                return

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

                new_entries_to_add.append(
                    (incoming_port, proto, final_ip, forwarding_port)
                )

                result_ports.append(
                    {
                        "puerto": port,
                        "protocolo": proto,
                        "incoming_port": incoming_port,
                        "forwarding_port": forwarding_port,  # Add for clarity
                        "updated": True,
                        "conflict_resolved": conflict_resolved,
                    }
                )

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
                        (incoming_port,),
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
                    if websocket is not None:
                        await websocket.send(
                            json.dumps(
                                {
                                    "status": "ok",
                                    "msg": "No hay cambios en los streams. Todos ya existen y están sincronizados.",
                                    "resultados": result_ports,
                                }
                            )
                        )
                    return
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
                    ws_info("[WS]", f"Error processing WG streams: {e}")
                    if websocket is not None:
                        await websocket.send(
                            json.dumps(
                                {
                                    "status": "error",
                                    "msg": f"Error processing streams: {str(e)}",
                                }
                            )
                        )
                    return

            # Send successful response
            result = {
                "status": "ok",
                "msg": f"WG Streams synchronized for {ip}. {len(new_entries_to_add)} pre-approved entries processed.",
                "resultados": result_ports,
            }
            if websocket is not None:
                await websocket.send(json.dumps(result))


# Función utilitaria para crear el stream usando la lógica de stream_creation_db.py
async def create_stream_from_remote(stream_data):
    """
    Crea un stream en la base de datos usando la lógica del cliente y sincroniza con otros servidores si corresponde.
    """
    import sys
    import os
    import json
    import asyncio

    # Importar módulos necesarios
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from Streams import stream_creation
    from WebSockets import diagnostics
    from Client import server_querys

    # 1. Crear el stream en la base de datos local usando la función extendida
    # El cliente agrupa por puerto, pero aquí solo es uno, así que adaptamos la entrada
    new_entries = []
    incoming_port = int(stream_data["incoming_port"])
    forwarding_host = stream_data["forwarding_host"]
    forwarding_port = int(stream_data["forwarding_port"])
    tcp_forwarding = int(stream_data.get("tcp_forwarding", 1))
    udp_forwarding = int(stream_data.get("udp_forwarding", 0))
    # Por compatibilidad, se agregan ambos protocolos si están activos
    if tcp_forwarding:
        new_entries.append((incoming_port, "tcp", forwarding_host, forwarding_port))
    if udp_forwarding:
        new_entries.append((incoming_port, "udp", forwarding_host, forwarding_port))

    # Llama a la función de creación extendida (sincroniza con la DB local)
    stream_creation.add_streams_sqlite_with_ip_extended(new_entries)

    # 2. Sincronizar con otros servidores si corresponde (ejemplo: WireGuard)
    # Buscar servidores WireGuard configurados
    uri_token_pairs = diagnostics.get_ws_uris_and_tokens()
    wg_servers = []
    for uri, token in uri_token_pairs:
        caps = await server_querys.query_server_capabilities(uri, token)
        if caps and caps.get("has_wireguard", False):
            wg_servers.append((uri, token))

    # Si hay servidores WG, reenviar la información del nuevo stream
    if wg_servers:
        # Construir la estructura de puertos aprobados (como hace el cliente)
        approved_ports = []
        if tcp_forwarding:
            approved_ports.append(
                {
                    "port": incoming_port,
                    "protocol": "tcp",
                    "incoming_port": incoming_port,
                    "conflict_resolved": False,
                }
            )
        if udp_forwarding:
            approved_ports.append(
                {
                    "port": incoming_port,
                    "protocol": "udp",
                    "incoming_port": incoming_port,
                    "conflict_resolved": False,
                }
            )
        # Enviar a cada servidor WG
        for wg_uri, wg_token in wg_servers:
            try:
                import websockets

                async with websockets.connect(wg_uri, ping_timeout=30) as wg_ws:
                    await wg_ws.send(json.dumps({"token": wg_token}))
                    wg_token_resp = await asyncio.wait_for(wg_ws.recv(), timeout=10)
                    wg_token_result = json.loads(wg_token_resp)
                    if wg_token_result.get("status") != "ok":
                        continue
                    wg_data = {
                        "type": "conflict_resolution_ports",
                        "ip": forwarding_host,
                        "hostname": "remote_manual",
                        "token": wg_token,
                        "timestamp": int(__import__("time").time()),
                        "ports": approved_ports,
                        "ports_pre_approved": True,
                    }
                    await wg_ws.send(json.dumps(wg_data))
                    # Esperar respuesta (opcional)
                    try:
                        wg_response_msg = await asyncio.wait_for(
                            wg_ws.recv(), timeout=15
                        )
                        wg_response = json.loads(wg_response_msg)
                    except Exception:
                        pass
            except Exception as e:
                ws_error("[WS_REMOTE]", f"Error sending to WG {wg_uri}: {e}")

    # No se retorna un stream_id específico porque la función de creación múltiple no lo devuelve
    return True
    # No se retorna un stream_id específico porque la función de creación múltiple no lo devuelve
    return True
