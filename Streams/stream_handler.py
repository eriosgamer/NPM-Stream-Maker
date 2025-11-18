import os
import sys
from rich.table import Table
from rich.console import Console
from rich.prompt import Prompt

# Add the parent directory to sys.path to allow importing configuration
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg
from UI.console_handler import ws_error, ws_info, ws_warning

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
            ws_error("[STREAM_MANAGER]", "NPM database not found")
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

                # Sort streams by ID to ensure consistent ordering
                sorted_streams = sorted(streams, key=lambda x: x[0])  # x[0] is stream_id

                for stream_id, incoming_port, forwarding_host, forwarding_port, tcp_f, udp_f, enabled in sorted_streams:
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

                from UI.console_handler import console_handler
                console_handler.console.print(table)
                # Guardar la tabla en el log en formato legible
                import io
                log_buffer = io.StringIO()
                from rich.console import Console as RichConsole
                log_console = RichConsole(file=log_buffer, force_terminal=True, color_system=None)
                log_console.print(table)
                table_text = log_buffer.getvalue()
                ws_info("[STREAM_MANAGER]", table_text)
                ws_info("[STREAM_MANAGER]", f"Total streams: {len(streams)}")
            else:
                ws_warning("[STREAM_MANAGER]", "No streams found.")
                ws_info("[STREAM_MANAGER]", "💡 You can add streams using option 2 or start WebSocket client (option 6) to auto-discover services.")
        finally:
            conn.close()

    except Exception as e:
        ws_error("[STREAM_MANAGER]", f"Error displaying streams: {e}")

    input("\nPress Enter to continue...")


# -------------------------------
# End of stream_handler.py
# -------------------------------
