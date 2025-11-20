from rich.console import Console
import sys
import os
import asyncio
import json

# Add the parent directory to sys.path to allow imports from sibling modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Client import ws_client
from UI.console_handler import ws_info, ws_error


# Initialize Rich console for colored terminal output
console = Console()


async def handle_server_message(data, websocket=None):
    """
    Handle incoming client messages (type starts with 'client_').
    """
    try:
        message_type = None

        if isinstance(data, str):
            try:
                data_json = json.loads(data)
                message_type = data_json.get("type")
                if not (message_type and message_type.startswith("client_")):
                    return
                data = data_json
            except Exception:
                return

        if isinstance(data, dict):
            message_type = data.get("type")
            if not (message_type and message_type.startswith("client_")):
                return
        else:
            return

        message_type = data.get("type")

        # NUEVO: Manejar solicitud de clientes conectados
        if message_type == "client_get_connected_clients":
            ws_info("[WS_CLIENT]", "Received request for connected clients list")
            from Config import config as cfg
            # Construir lista de clientes conectados
            clients = []
            for cid, info in cfg.connected_clients.items():
                clients.append({
                    "client_id": cid,
                    "ip": info.get("ip"),
                    "hostname": info.get("hostname"),
                    "last_seen": info.get("last_seen"),
                    "ports": list(info.get("ports", [])),
                })
            response = {
                "type": "connected_clients_list",
                "clients": clients
            }
            if websocket:
                await websocket.send(json.dumps(response))
            else:
                return response
            return
        
        if message_type == "client_port_get_assignments":
            ws_info("[WS_CLIENT]", "Received request for port assignments")
            # Consultar la base de datos de streams activos
            import sqlite3
            from Config import config as cfg
            assignments = []
            if not os.path.exists(cfg.SQLITE_DB_PATH):
                ws_error("[WS_CLIENT]", "NPM database not found")
            else:
                try:
                    conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT id, incoming_port, forwarding_host, forwarding_port, tcp_forwarding, udp_forwarding, enabled FROM stream WHERE is_deleted=0"
                    )
                    streams = cur.fetchall()
                    for (
                        stream_id,
                        incoming_port,
                        forwarding_host,
                        forwarding_port,
                        tcp_f,
                        udp_f,
                        enabled,
                    ) in streams:
                        protocols = []
                        if tcp_f:
                            protocols.append("TCP")
                        if udp_f:
                            protocols.append("UDP")
                        for proto in protocols:
                            assignments.append({
                                "id": stream_id,
                                "incoming_port": incoming_port,
                                "forwarding_host": forwarding_host,
                                "forwarding_port": forwarding_port,
                                "protocol": proto,
                                "enabled": bool(enabled),
                            })
                except Exception as e:
                    ws_error("[WS_CLIENT]", f"Error reading streams from DB: {e}")
                finally:
                    try:
                        conn.close()
                    except:
                        pass
            response = {
                "type": "client_port_assignments_response",
                "assignments": assignments
            }
            if websocket:
                ws_info("[WS_CLIENT]", "Sending port assignments response")
                ws_info("[WS_CLIENT]", f"Response data: {response}")
                await websocket.send(json.dumps(response))
            else:
                return response
            return
        
        if message_type == "client_add_stream":
            ws_info("[WS_CLIENT]", "Received request to add stream")
            from UI.stream_menu_manager import create_stream_from_remote
            stream_data = data.get("stream_data", {})
            ws_info("[WS_CLIENT]", f"Stream data: {stream_data}")
            if stream_data:
                # Ejecutar la función async correctamente según el estado del event loop
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        success = await create_stream_from_remote(stream_data)
                    else:
                        success = asyncio.run(create_stream_from_remote(stream_data))
                except RuntimeError:
                    # Si no hay event loop, usar asyncio.run
                    success = asyncio.run(create_stream_from_remote(stream_data))
                ws_info("[WS_CLIENT]", f"Stream creation success: {success}")
                if success:
                    ws_info("[WS_CLIENT]", "Stream added successfully")
                    response = {
                        "type": "client_add_stream_response",
                        "status": "success"
                    }
                    if websocket:
                        await websocket.send(json.dumps(response))
                else:
                    ws_error("[WS_CLIENT]", "Failed to add stream")
                    response = {
                        "type": "client_add_stream_response",
                        "status": "failure"
                    }
                    if websocket:
                        await websocket.send(json.dumps(response))
            else:
                ws_error("[WS_CLIENT]", "No stream data provided")
            return
        
        if message_type == "client_remove_stream":
            ws_info("[WS_CLIENT]", "Received request to remove stream")
            from UI.stream_menu_manager import remove_stream_from_remote
            stream_id = data.get("stream_id")
            if stream_id is not None:
                success = remove_stream_from_remote(stream_id)
                if success:
                    ws_info("[WS_CLIENT]", f"Stream with ID {stream_id} removed successfully")
                    response = {
                        "type": "client_remove_stream_response",
                        "status": "success"
                    }
                    if websocket:
                        await websocket.send(json.dumps(response))
                else:
                    ws_error("[WS_CLIENT]", f"Failed to remove stream with ID {stream_id}")
                    response = {
                        "type": "client_remove_stream_response",
                        "status": "failure"
                    }
                    if websocket:
                        await websocket.send(json.dumps(response))
            else:
                ws_error("[WS_CLIENT]", "No stream ID provided")
            return
        
        if message_type == "client_port_assignments":
            assignments = data.get("assignments", [])
            conflicts = data.get("conflicts", [])

            # Print the number of received port assignments
            ws_info(
                "[WS_CLIENT]", f"Received port assignments: {len(assignments)} ports"
            )

            for assignment in assignments:
                port = assignment.get("port")
                protocol = assignment.get("protocol", "tcp")
                assigned = assignment.get("assigned", False)
                incoming_port = assignment.get("incoming_port", port)

                if port:
                    # Update the client's port assignments with the received data
                    ws_client.client_assignments[(port, protocol)] = {
                        "assigned": assigned,
                        "incoming_port": incoming_port,
                    }

            if conflicts:
                # Print the number of detected port conflicts
                ws_error("[WS_CLIENT]", f"Port conflicts detected: {len(conflicts)}")
                for conflict in conflicts:
                    # Print details about each port conflict
                    ws_info(
                        "[WS_CLIENT]",
                        f"  → Port {conflict.get('port')} ({conflict.get('protocol')}) - assigned to: {conflict.get('assigned_to')}",
                    )

            # Save the updated client assignments to persistent storage
            ws_client.save_client_assignments()

        elif message_type == "client_port_assignment_update":
            port = data.get("port")
            protocol = data.get("protocol", "tcp")
            assigned = data.get("assigned", False)
            incoming_port = data.get("incoming_port", port)

            if port:
                # Update a single port assignment
                ws_client.client_assignments[(port, protocol)] = {
                    "assigned": assigned,
                    "incoming_port": incoming_port,
                }
                # Print update information
                ws_info(
                    "[WS_CLIENT]",
                    f"Port assignment updated: {port} ({protocol}) - assigned: {assigned}",
                )
                ws_client.save_client_assignments()

        elif message_type == "client_port_conflict_resolution":
            port = data.get("port")
            protocol = data.get("protocol", "tcp")
            conflicting_clients = data.get("conflicting_clients", [])
            assigned_to = data.get("assigned_to")

            # Print information about the resolved port conflict
            ws_info(
                "[WS_CLIENT]",
                f"Port conflict resolution: {port} ({protocol}) assigned to {assigned_to}",
            )
            ws_info("[WS_CLIENT]", f"  → Conflicting clients: {conflicting_clients}")

        elif message_type == "client_port_conflict_resolutions":
            # Handle broadcast of conflict resolutions from the conflict resolution server
            conflicts = data.get("conflicts", [])
            # Print the number of conflict resolutions received
            ws_info(
                "[WS_CLIENT]",
                f"Received {len(conflicts)} conflict resolutions from server",
            )

            for conflict in conflicts:
                original_port = conflict.get("original_port")
                alternative_port = conflict.get("alternative_port")
                protocol = conflict.get("protocol")
                client_ip = conflict.get("client_ip")

                # Print details about each conflict resolution
                ws_info(
                    "[WS_CLIENT]",
                    f"Conflict resolution: {original_port} ({protocol}) → {alternative_port} for {client_ip}",
                )

        else:
            # Print a warning for unknown message types
            ws_error("[WS_CLIENT]", f"Unknown message type: {message_type}")

    except Exception as e:
        # Print error details if message handling fails
        ws_error("[WS_CLIENT]", f"Error handling server message: {e}")
