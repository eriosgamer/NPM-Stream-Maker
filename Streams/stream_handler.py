import os
import sys
from rich.table import Table
from rich.console import Console
from rich.prompt import Prompt

# Add the parent directory to sys.path to allow importing configuration
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg

console = Console()

# -------------------------------
# Stream Management Functions
# -------------------------------

def show_streams():
    """
    Displays the list of existing streams in the database.
    Presents the information in a table with details for each stream.
    """
    console.rule("[bold blue]Existing Streams")
    try:
        import sqlite3

        if not os.path.exists(cfg.SQLITE_DB_PATH):
            console.print("[bold red]NPM database not found[/bold red]")
            input("\nPress Enter to continue...")
            return

        conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
        try:
            cur = conn.cursor()
            # Query all non-deleted streams
            cur.execute(
                "SELECT id, incoming_port, forwarding_host, forwarding_port, tcp_forwarding, udp_forwarding, enabled FROM stream WHERE is_deleted=0"
            )
            streams = cur.fetchall()

            if streams:
                table = Table(title="Active Streams", show_lines=True)
                table.add_column("ID", style="cyan", justify="center")
                table.add_column("Incoming Port", style="magenta")
                table.add_column("Forwarding", style="green")
                table.add_column("Protocols", style="yellow")
                table.add_column("Status", style="blue")

                for stream_id, incoming_port, forwarding_host, forwarding_port, tcp_f, udp_f, enabled in streams:
                    protocols = []
                    if tcp_f:
                        protocols.append("TCP")
                    if udp_f:
                        protocols.append("UDP")
                    proto_str = "/".join(protocols)

                    status = "✅ Enabled" if enabled else "❌ Disabled"

                    table.add_row(
                        str(stream_id),
                        str(incoming_port),
                        f"{forwarding_host}:{forwarding_port}",
                        proto_str,
                        status
                    )

                console.print(table)
                console.print(
                    f"\n[bold cyan]Total streams: {len(streams)}[/bold cyan]")
            else:
                console.print("[bold yellow]No streams found.[/bold yellow]")
                console.print(
                    "[bold cyan]💡 You can add streams using option 2 or start WebSocket client (option 6) to auto-discover services.[/bold cyan]")
        finally:
            conn.close()

    except Exception as e:
        console.print(f"[bold red]Error displaying streams: {e}[/bold red]")

    input("\nPress Enter to continue...")


# Copied
async def handle_create_stream_menu(remote):
    """
    Handles the menu for creating a stream remotely.
    Allows selecting the server, configuring the stream, and applying access control.
    """
    console.rule("[bold blue]Create Stream Remotely")

    # Select target server
    server_keys = list(remote.connections.keys())
    if not server_keys:
        console.print("[bold red][REMOTE][/bold red] No servers connected")
        return

    console.print("[bold cyan]Available servers:[/bold cyan]")
    for i, server_key in enumerate(server_keys, 1):
        server_type = remote.server_capabilities.get(
            server_key, {}).get("server_type", "unknown")
        console.print(
            f"[bold white]  {i}. {server_key} ({server_type})[/bold white]")

    try:
        server_choice = Prompt.ask("[bold cyan]Select target server", choices=[
                                   str(i) for i in range(1, len(server_keys)+1)])
        server_key = server_keys[int(server_choice) - 1]
    except (ValueError, IndexError):
        console.print("[bold red][REMOTE][/bold red] Invalid server selection")
        return

    # Get stream configuration from user
    try:
        incoming_port = int(Prompt.ask("[bold cyan]Enter incoming port"))
        forwarding_host = Prompt.ask(
            "[bold cyan]Enter forwarding host/IP", default="127.0.0.1")
        forwarding_port = int(Prompt.ask(
            "[bold cyan]Enter forwarding port", default=str(incoming_port)))
        protocol = Prompt.ask("[bold cyan]Enter protocol", choices=[
                              "tcp", "udp", "both"], default="tcp")

        # IP Access Control Configuration
        console.print(
            "\n[bold yellow]🔒 IP Access Control Configuration[/bold yellow]")
        enable_access_control = Prompt.ask(
            "[bold cyan]Enable IP access control?[/bold cyan]",
            choices=["yes", "no"],
            default="no"
        )

        allowed_ips = []
        denied_ips = []

        if enable_access_control == "yes":
            allowed_ips_input = Prompt.ask(
                "[bold green]Enter allowed IPs (comma-separated)[/bold green]",
                default=""
            )
            if allowed_ips_input.strip():
                allowed_ips = [ip.strip()
                               for ip in allowed_ips_input.split(",") if ip.strip()]

            denied_ips_input = Prompt.ask(
                "[bold red]Enter denied IPs (comma-separated)[/bold red]",
                default=""
            )
            if denied_ips_input.strip():
                denied_ips = [ip.strip()
                              for ip in denied_ips_input.split(",") if ip.strip()]

        # Build stream configuration dictionary
        stream_config = {
            "incoming_port": incoming_port,
            "forwarding_host": forwarding_host,
            "forwarding_port": forwarding_port,
            "protocol": protocol,
            "access_control": {
                "enabled": enable_access_control == "yes",
                "allowed_ips": allowed_ips,
                "denied_ips": denied_ips
            }
        }

        # Show summary to user
        console.print(
            f"\n[bold cyan]📋 Stream Configuration Summary:[/bold cyan]")
        console.print(
            f"[bold white]• Target Server: {server_key}[/bold white]")
        console.print(
            f"[bold white]• Port: {incoming_port} → {forwarding_host}:{forwarding_port}[/bold white]")
        console.print(
            f"[bold white]• Protocol: {protocol.upper()}[/bold white]")
        if enable_access_control == "yes":
            console.print(
                f"[bold white]• Access Control: Enabled[/bold white]")
            if allowed_ips:
                console.print(
                    f"[bold white]• Allowed IPs: {', '.join(allowed_ips)}[/bold white]")
            if denied_ips:
                console.print(
                    f"[bold white]• Denied IPs: {', '.join(denied_ips)}[/bold white]")
        else:
            console.print(
                f"[bold white]• Access Control: Disabled[/bold white]")

        confirm = Prompt.ask(
            "\n[bold yellow]Create this stream?[/bold yellow]", choices=["yes", "no"], default="no")

        if confirm == "yes":
            result = await remote.create_remote_stream(server_key, stream_config)
            if result and result.get("status") == "ok":
                console.print(
                    "[bold green]🎉 Stream created successfully![/bold green]")
            else:
                console.print("[bold red]❌ Failed to create stream[/bold red]")
        else:
            console.print("[bold yellow]Operation cancelled[/bold yellow]")

    except ValueError:
        console.print("[bold red][REMOTE][/bold red] Invalid port number")
    except Exception as e:
        console.print(
            f"[bold red][REMOTE][/bold red] Error in stream creation: {e}")

# Copied


async def handle_delete_stream_menu(remote):
    """
    Handles the menu for deleting a stream remotely.
    Allows selecting the server and stream to delete.
    """
    console.rule("[bold blue]Delete Stream Remotely")

    # Select target server
    server_keys = list(remote.connections.keys())
    if not server_keys:
        console.print("[bold red][REMOTE][/bold red] No servers connected")
        return

    console.print("[bold cyan]Available servers:[/bold cyan]")
    for i, server_key in enumerate(server_keys, 1):
        server_type = remote.server_capabilities.get(
            server_key, {}).get("server_type", "unknown")
        console.print(
            f"[bold white]  {i}. {server_key} ({server_type})[/bold white]")

    try:
        server_choice = Prompt.ask("[bold cyan]Select target server", choices=[
                                   str(i) for i in range(1, len(server_keys)+1)])
        server_key = server_keys[int(server_choice) - 1]
    except (ValueError, IndexError):
        console.print("[bold red][REMOTE][/bold red] Invalid server selection")
        return

    # Show existing streams from the selected server
    console.print(
        f"\n[bold cyan]Getting streams from {server_key}...[/bold cyan]")
    streams = await remote.list_remote_streams(server_key)

    if not streams:
        console.print(
            "[bold yellow][REMOTE][/bold yellow] No streams found or failed to retrieve streams")
        return

    # Display streams in a table
    table = Table(title=f"Streams on {server_key}", show_lines=True)
    table.add_column("Index", style="cyan", justify="center")
    table.add_column("Incoming Port", style="magenta")
    table.add_column("Forwarding", style="green")
    table.add_column("Protocols", style="yellow")
    table.add_column("Status", style="blue")

    stream_list = []
    for i, stream in enumerate(streams, 1):
        protocols = []
        if stream.get("tcp_forwarding"):
            protocols.append("TCP")
        if stream.get("udp_forwarding"):
            protocols.append("UDP")
        proto_str = "/".join(protocols)

        status = "✅ Enabled" if stream.get("enabled") else "❌ Disabled"

        table.add_row(
            str(i),
            str(stream.get("incoming_port")),
            f"{stream.get('forwarding_host')}:{stream.get('forwarding_port')}",
            proto_str,
            status
        )

        stream_list.append({
            "incoming_port": stream.get("incoming_port"),
            "protocols": protocols
        })

    console.print(table)

    # Select stream to delete
    try:
        stream_choice = Prompt.ask(
            "[bold cyan]Select stream to delete",
            choices=[str(i) for i in range(1, len(stream_list)+1)]
        )
        selected_stream = stream_list[int(stream_choice) - 1]

        # Select protocol if both TCP and UDP are present
        protocols = selected_stream["protocols"]
        if len(protocols) > 1:
            protocol_choice = Prompt.ask(
                "[bold cyan]Select protocol to delete",
                choices=[p.lower() for p in protocols] + ["both"]
            )
        else:
            protocol_choice = protocols[0].lower()

        port = selected_stream["incoming_port"]

        console.print(
            f"\n[bold red]⚠️  This will delete stream: Port {port} ({protocol_choice})[/bold red]")
        confirm = Prompt.ask(
            "[bold yellow]Are you sure?[/bold yellow]", choices=["yes", "no"], default="no")

        if confirm == "yes":
            if protocol_choice == "both":
                # Delete both TCP and UDP
                for proto in protocols:
                    result = await remote.delete_remote_stream(server_key, port, proto.lower())
                    if result and result.get("status") == "ok":
                        console.print(
                            f"[bold green]✅ Deleted {proto} stream for port {port}[/bold green]")
                    else:
                        console.print(
                            f"[bold red]❌ Failed to delete {proto} stream for port {port}[/bold red]")
            else:
                result = await remote.delete_remote_stream(server_key, port, protocol_choice)
                if result and result.get("status") == "ok":
                    console.print(
                        f"[bold green]✅ Deleted {protocol_choice.upper()} stream for port {port}[/bold green]")
                else:
                    console.print(
                        f"[bold red]❌ Failed to delete stream[/bold red]")
        else:
            console.print("[bold yellow]Operation cancelled[/bold yellow]")

    except (ValueError, IndexError):
        console.print("[bold red][REMOTE][/bold red] Invalid selection")
    except Exception as e:
        console.print(
            f"[bold red][REMOTE][/bold red] Error in stream deletion: {e}")

# Copied


async def handle_list_streams_menu(remote):
    """
    Handles the menu for listing streams from a remote server.
    Shows details and access control for each stream.
    """
    console.rule("[bold blue]List Streams from Server")

    # Select target server
    server_keys = list(remote.connections.keys())
    if not server_keys:
        console.print("[bold red][REMOTE][/bold red] No servers connected")
        return

    console.print("[bold cyan]Available servers:[/bold cyan]")
    for i, server_key in enumerate(server_keys, 1):
        server_type = remote.server_capabilities.get(
            server_key, {}).get("server_type", "unknown")
        console.print(
            f"[bold white]  {i}. {server_key} ({server_type})[/bold white]")

    try:
        server_choice = Prompt.ask("[bold cyan]Select server", choices=[
                                   str(i) for i in range(1, len(server_keys)+1)])
        server_key = server_keys[int(server_choice) - 1]
    except (ValueError, IndexError):
        console.print("[bold red][REMOTE][/bold red] Invalid server selection")
        return

    # Get streams from server
    console.print(
        f"\n[bold cyan]Getting streams from {server_key}...[/bold cyan]")
    streams = await remote.list_remote_streams(server_key)

    if not streams:
        console.print(
            "[bold yellow][REMOTE][/bold yellow] No streams found or failed to retrieve streams")
        return

    # Display streams in a table
    table = Table(
        title=f"Streams on {server_key} ({len(streams)} total)", show_lines=True)
    table.add_column("ID", style="cyan", justify="center")
    table.add_column("Incoming Port", style="magenta")
    table.add_column("Forwarding", style="green")
    table.add_column("Protocols", style="yellow")
    table.add_column("Status", style="blue")
    table.add_column("Access Control", style="red")

    for stream in streams:
        protocols = []
        if stream.get("tcp_forwarding"):
            protocols.append("TCP")
        if stream.get("udp_forwarding"):
            protocols.append("UDP")
        proto_str = "/".join(protocols)

        status = "✅ Enabled" if stream.get("enabled") else "❌ Disabled"

        # Check for access control in stream metadata
        meta = stream.get("meta", "{}")
        access_control = "❌ None"
        try:
            import json
            meta_data = json.loads(meta) if isinstance(meta, str) else meta
            access_list = meta_data.get("access_list", {})
            if access_list.get("enabled", False):
                allowed_count = len(access_list.get("allowed_ips", []))
                denied_count = len(access_list.get("denied_ips", []))
                access_control = f"🔒 A:{allowed_count} D:{denied_count}"
        except:
            pass

        table.add_row(
            str(stream.get("id", "N/A")),
            str(stream.get("incoming_port")),
            f"{stream.get('forwarding_host')}:{stream.get('forwarding_port')}",
            proto_str,
            status,
            access_control
        )

    console.print(table)
    console.print(f"\n[bold cyan]💡 Access Control Legend:[/bold cyan]")
    console.print(
        f"[bold white]  🔒 A:X D:Y = X allowed IPs, Y denied IPs[/bold white]")
    console.print(
        f"[bold white]  ❌ None = No access restrictions[/bold white]")

# Copied

async def update_forwarding_ips(ip_mappings):
    """
    Update forwarding IPs for specified ports.
    """
    try:
        from Streams import stream_creation
        from Streams import stream_creation_db as scdb
        from npm import npm_handler as npm

        updated_count = 0
        for port, new_ip in ip_mappings.items():
            if stream_creation.update_stream_forwarding_ip(int(port), new_ip):
                updated_count += 1

        if updated_count > 0:
            scdb.sync_streams_conf_with_sqlite()
            npm.reload_npm()

        console.print(f"[bold green][WS][/bold green] Updated forwarding IPs for {updated_count} ports")
        return True

    except Exception as e:
        console.print(f"[bold red][WS][/bold red] Error updating forwarding IPs: {e}")
        return False

# -------------------------------
# End of stream_handler.py
# -------------------------------
