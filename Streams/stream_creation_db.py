import os
import sqlite3
import json
import sys
from rich.console import Console

# Console object for rich output
console = Console()

# Add parent directory to sys.path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg
from npm.npm_handler import reload_npm


# Main function to synchronize NGINX stream config files with the current SQLite database
def sync_streams_conf_with_sqlite():
    """
    Synchronizes NGINX stream configuration files with the current SQLite database.
    Generates .conf files for each active stream.
    """

    # Reads active streams from the SQLite database and returns a list of dictionaries with stream data
    def read_streams_sqlite():
        """
        Reads active streams from the SQLite database.
        Returns a list of dictionaries with each stream's data.
        """
        streams = []
        if not os.path.exists(cfg.SQLITE_DB_PATH):
            return streams
        conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, incoming_port, forwarding_host, forwarding_port, tcp_forwarding, udp_forwarding, enabled FROM stream WHERE is_deleted=0"
            )
            for row in cur.fetchall():
                streams.append(
                    {
                        "id": row[0],
                        "incoming_port": row[1],
                        "forwarding_host": row[2],
                        "forwarding_port": row[3],
                        "tcp_forwarding": row[4],
                        "udp_forwarding": row[5],
                        "enabled": row[6],
                    }
                )
        finally:
            conn.close()
        return streams

    # Generates the NGINX configuration for a stream from the database, including access control rules
    def generate_stream_conf_from_sqlite(stream):
        """
        Generates the NGINX configuration for a stream from the database, including access control rules.
        """
        console.print(f"Generating config for stream ID: {stream}")

        stream_id = stream["id"]
        incoming_port = stream["incoming_port"]
        forwarding_host = stream["forwarding_host"]
        forwarding_port = stream["forwarding_port"]
        tcp_f = stream["tcp_forwarding"]
        udp_f = stream["udp_forwarding"]
        meta = stream.get("meta", None)

        # Parse metadata for access control
        access_list_config = {"enabled": False, "allowed_ips": [], "denied_ips": []}
        if meta:
            try:
                meta_data = json.loads(meta)
                access_list_config = meta_data.get("access_list", access_list_config)
            except Exception:
                pass

        conf_lines = []

        # Header comments
        conf_lines.append(
            "# ------------------------------------------------------------"
        )
        conf_lines.append(
            f"# {incoming_port} TCP: {'true' if tcp_f else 'false'} UDP: {'true' if udp_f else 'false'}"
        )
        conf_lines.append(
            "# ------------------------------------------------------------"
        )
        conf_lines.append("")  # Una línea en blanco
        conf_lines.append("")  # Segunda línea en blanco

        # Generate TCP configuration block if TCP forwarding is enabled
        if tcp_f:
            conf_lines.append("server {")
            conf_lines.append(f"  listen {incoming_port};")
            conf_lines.append(f"#listen [::]:{incoming_port};")
            conf_lines.append("")
            conf_lines.append(f"  proxy_pass {forwarding_host}:{forwarding_port};")
            # Add access control rules if enabled
            if access_list_config.get("enabled", False):
                conf_lines.append("")
                conf_lines.append("  # Access control rules")
                allowed_ips = access_list_config.get("allowed_ips", [])
                for ip in allowed_ips:
                    conf_lines.append(f"  allow {ip};")
                denied_ips = access_list_config.get("denied_ips", [])
                for ip in denied_ips:
                    conf_lines.append(f"  deny {ip};")
                if allowed_ips:
                    conf_lines.append("  deny all;")
            conf_lines.append("")
            conf_lines.append("  # Custom")
            conf_lines.append("  include /data/nginx/custom/server_stream[.]conf;")
            conf_lines.append("  include /data/nginx/custom/server_stream_tcp[.]conf;")
            conf_lines.append("}")
            conf_lines.append("")  # Una línea en blanco
            conf_lines.append("")  # Segunda línea en blanco

        # Generate UDP configuration block if UDP forwarding is enabled
        if udp_f:
            conf_lines.append("server {")
            conf_lines.append(f"  listen {incoming_port} udp reuseport;")
            conf_lines.append(f"#listen [::]:{incoming_port} udp;")
            conf_lines.append("")
            conf_lines.append(f"  proxy_pass {forwarding_host}:{forwarding_port};")
            #conf_lines.append("  proxy_timeout 600s;")
            #conf_lines.append("  proxy_buffer_size 64k;")
            #conf_lines.append("  proxy_socket_keepalive on;")
            #conf_lines.append("  proxy_bind $remote_addr transparent;")
            # Add access control rules if enabled (same as TCP)
            if access_list_config.get("enabled", False):
                conf_lines.append("")
                conf_lines.append("  # Access control rules")
                allowed_ips = access_list_config.get("allowed_ips", [])
                for ip in allowed_ips:
                    conf_lines.append(f"  allow {ip};")
                denied_ips = access_list_config.get("denied_ips", [])
                for ip in denied_ips:
                    conf_lines.append(f"  deny {ip};")
                if allowed_ips:
                    conf_lines.append("  deny all;")
            conf_lines.append("")
            conf_lines.append("  # Custom")
            conf_lines.append("  include /data/nginx/custom/server_stream[.]conf;")
            conf_lines.append("  include /data/nginx/custom/server_stream_udp[.]conf;")
            conf_lines.append("}")
            conf_lines.append("")  # Una línea en blanco
            conf_lines.append("")  # Segunda línea en blanco

        return "\n".join(conf_lines)

    # Read all streams from the database
    streams = read_streams_sqlite()
    # Ensure the NGINX stream config directory exists
    os.makedirs(cfg.NGINX_STREAM_DIR, exist_ok=True)
    # Remove all existing .conf files in the NGINX stream config directory
    for fname in os.listdir(cfg.NGINX_STREAM_DIR):
        if fname.endswith(".conf"):
            os.remove(os.path.join(cfg.NGINX_STREAM_DIR, fname))
    # For each stream, generate and write its configuration file
    from rich.table import Table

    synced_files = []
    for stream in streams:
        conf_content = generate_stream_conf_from_sqlite(stream)
        conf_filename = os.path.join(cfg.NGINX_STREAM_DIR, f"{stream['id']}.conf")
        with open(conf_filename, "w") as f:
            f.write(conf_content)
        synced_files.append(
            {
                "id": stream["id"],
                "port": stream["incoming_port"],
                "tcp": "Sí" if stream["tcp_forwarding"] else "No",
                "udp": "Sí" if stream["udp_forwarding"] else "No",
                "destino": f"{stream['forwarding_host']}:{stream['forwarding_port']}",
            }
        )
    # Mostrar resumen con Rich Table
    if synced_files:
        table = Table(title="Streams sincronizados", show_lines=True)
        table.add_column("ID", style="cyan", justify="right")
        table.add_column("Puerto", style="magenta", justify="right")
        table.add_column("TCP", style="green", justify="center")
        table.add_column("UDP", style="green", justify="center")
        table.add_column("Destino", style="yellow")
        for s in synced_files:
            table.add_row(
                str(s["id"]),
                str(s["port"]),
                s["tcp"],
                s["udp"],
                s["destino"],
            )
        console.print(table)
    else:
        console.print("[yellow]No hay streams activos para sincronizar.[/yellow]")

    # Recargar NGINX usando la función existente del npm_handler
    reload_npm()
