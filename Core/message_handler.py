from rich.console import Console
import sys
import os

# Add the parent directory to sys.path to allow imports from sibling modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg
from Client import ws_client

# Initialize Rich console for colored terminal output
console = Console()

# This function handles incoming messages from the server and updates the client state accordingly.
# It processes different message types related to port assignments and conflicts.
async def handle_server_message(data):
    """
    Handle incoming server messages and update client state accordingly.
    """
    try:
        message_type = data.get("type")

        if message_type == "port_assignments":
            assignments = data.get("assignments", [])
            conflicts = data.get("conflicts", [])

            # Print the number of received port assignments
            console.print(f"[bold green][WS_CLIENT][/bold green] Received port assignments: {len(assignments)} ports")

            for assignment in assignments:
                port = assignment.get("port")
                protocol = assignment.get("protocol", "tcp")
                assigned = assignment.get("assigned", False)
                incoming_port = assignment.get("incoming_port", port)

                if port:
                    # Update the client's port assignments with the received data
                    ws_client.client_assignments[(port, protocol)] = {
                        "assigned": assigned,
                        "incoming_port": incoming_port
                    }

            if conflicts:
                # Print the number of detected port conflicts
                console.print(f"[bold yellow][WS_CLIENT][/bold yellow] Port conflicts detected: {len(conflicts)}")
                for conflict in conflicts:
                    # Print details about each port conflict
                    console.print(f"[bold yellow]  → Port {conflict.get('port')} ({conflict.get('protocol')}) - assigned to: {conflict.get('assigned_to')}[/bold yellow]")

            # Save the updated client assignments to persistent storage
            ws_client.save_client_assignments()

        elif message_type == "port_assignment_update":
            port = data.get("port")
            protocol = data.get("protocol", "tcp")
            assigned = data.get("assigned", False)
            incoming_port = data.get("incoming_port", port)

            if port:
                # Update a single port assignment
                ws_client.client_assignments[(port, protocol)] = {
                    "assigned": assigned,
                    "incoming_port": incoming_port
                }
                # Print update information
                console.print(f"[bold cyan][WS_CLIENT][/bold cyan] Port assignment updated: {port} ({protocol}) - assigned: {assigned}")
                ws_client.save_client_assignments()

        elif message_type == "port_conflict_resolution":
            port = data.get("port")
            protocol = data.get("protocol", "tcp")
            conflicting_clients = data.get("conflicting_clients", [])
            assigned_to = data.get("assigned_to")

            # Print information about the resolved port conflict
            console.print(f"[bold yellow][WS_CLIENT][/bold yellow] Port conflict resolution: {port} ({protocol}) assigned to {assigned_to}")
            console.print(f"[bold yellow]  → Conflicting clients: {conflicting_clients}[/bold yellow]")

        elif message_type == "port_conflict_resolutions":
            # Handle broadcast of conflict resolutions from the conflict resolution server
            conflicts = data.get("conflicts", [])
            # Print the number of conflict resolutions received
            console.print(f"[bold cyan][WS_CLIENT][/bold cyan] Received {len(conflicts)} conflict resolutions from server")

            for conflict in conflicts:
                original_port = conflict.get("original_port")
                alternative_port = conflict.get("alternative_port")
                protocol = conflict.get("protocol")
                client_ip = conflict.get("client_ip")

                # Print details about each conflict resolution
                console.print(f"[bold blue][WS_CLIENT][/bold blue] Conflict resolution: {original_port} ({protocol}) → {alternative_port} for {client_ip}")

        else:
            # Print a warning for unknown message types
            console.print(f"[bold blue][WS_CLIENT][/bold blue] Unknown message type: {message_type}")

    except Exception as e:
        # Print error details if message handling fails
        console.print(f"[bold red][WS_CLIENT][/bold red] Error handling server message: {e}")

