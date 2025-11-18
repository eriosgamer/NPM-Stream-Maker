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
