import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time

from rich.console import Console

# Console object for rich output
console = Console()

# Add parent directory to sys.path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg
from npm.npm_handler import reload_npm
from UI.console_handler import ws_error, ws_info, ws_warning


# Main function to synchronize NGINX stream config files with the current SQLite database
def sync_streams_conf_with_sqlite():
    """
    Synchronizes NGINX stream configuration files with the current SQLite database.
    Generates .conf files for each active stream.
    Uses atomic write with backup for safety.
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
    def generate_stream_conf_from_sqlite(
        stream, acl_allow_list_override=None, acl_deny_list_override=None
    ):
        """
        Generates the NGINX configuration for a stream from the database, including access control rules.
        """
        ws_info("[STREAM_MANAGER]", f"Generating config for stream ID: {stream}")

        stream_id = stream["id"]
        incoming_port = stream["incoming_port"]
        forwarding_host = stream["forwarding_host"]
        forwarding_port = stream["forwarding_port"]
        tcp_f = stream["tcp_forwarding"]
        udp_f = stream["udp_forwarding"]
        meta = stream.get("meta", None)

        # Parse metadata for access control
        access_list_config = {"enabled": False, "allowed_ips": [], "denied_ips": []}
        if acl_allow_list_override is not None or acl_deny_list_override is not None:
            access_list_config["enabled"] = bool(acl_allow_list_override or acl_deny_list_override)
            access_list_config["allowed_ips"] = acl_allow_list_override or []
            access_list_config["denied_ips"] = acl_deny_list_override or []
        elif meta:
            try:
                meta_data = json.loads(meta)
                access_list_config = meta_data.get("access_list", access_list_config)
            except Exception:
                pass

        conf_lines = []

        # Header comments
        conf_lines.append("# ------------------------------------------------------------")
        conf_lines.append(
            f"# {incoming_port} TCP: {'true' if tcp_f else 'false'} UDP: {'true' if udp_f else 'false'}"
        )
        conf_lines.append("# ------------------------------------------------------------")
        conf_lines.append("")  # One blank line
        conf_lines.append("")  # Second blank line

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
            conf_lines.append("")  # One blank line
            conf_lines.append("")  # Second blank line

        # Generate UDP configuration block if UDP forwarding is enabled
        if udp_f:
            conf_lines.append("server {")
            conf_lines.append(f"  listen {incoming_port} udp reuseport;")
            conf_lines.append(f"#listen [::]:{incoming_port} udp;")
            conf_lines.append("")
            conf_lines.append(f"  proxy_pass {forwarding_host}:{forwarding_port};")
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
            conf_lines.append("")  # One blank line
            conf_lines.append("")  # Second blank line

        return "\n".join(conf_lines)

    # Read all streams from the database
    streams = read_streams_sqlite()
    # Ensure the NGINX stream config directory exists
    os.makedirs(cfg.NGINX_STREAM_DIR, exist_ok=True)

    # FIX #1: Backup existing configs before deleting
    backup_dir = None
    existing_conf_files = [f for f in os.listdir(cfg.NGINX_STREAM_DIR) if f.endswith(".conf")]
    if existing_conf_files:
        backup_dir = os.path.join(cfg.NGINX_STREAM_DIR, f".backup_{int(time.time())}")
        os.makedirs(backup_dir, exist_ok=True)
        for fname in existing_conf_files:
            src = os.path.join(cfg.NGINX_STREAM_DIR, fname)
            dst = os.path.join(backup_dir, fname)
            shutil.copy2(src, dst)
        ws_info("[STREAM_MANAGER]", f"Backup created at {backup_dir}")

    # Temporary directory for atomic writes
    temp_stream_dir = tempfile.mkdtemp(prefix="npm_streams_")
    temp_stream_path = os.path.join(temp_stream_dir, "streams")
    os.makedirs(temp_stream_path, exist_ok=True)

    # For each stream, generate and write its configuration file to temp directory
    from rich.table import Table

    synced_files = []
    write_errors = []
    for stream in streams:
        conf_content = generate_stream_conf_from_sqlite(stream)
        conf_filename = os.path.join(temp_stream_path, f"{stream['id']}.conf")
        try:
            with open(conf_filename, "w") as f:
                f.write(conf_content)
            synced_files.append(
                {
                    "id": stream["id"],
                    "port": stream["incoming_port"],
                    "tcp": "Yes" if stream["tcp_forwarding"] else "No",
                    "udp": "Yes" if stream["udp_forwarding"] else "No",
                    "destino": f"{stream['forwarding_host']}:{stream['forwarding_port']}",
                }
            )
        except Exception as e:
            write_errors.append((stream["id"], str(e)))
            ws_error("[STREAM_MANAGER]", f"Error writing config for stream {stream['id']}: {e}")

    # FIX #3: Verify all writes succeeded before replacing
    if write_errors:
        ws_error("[STREAM_MANAGER]", f"Failed to write {len(write_errors)} configs, rolling back")
        shutil.rmtree(temp_stream_dir, ignore_errors=True)
        if backup_dir:
            # Restore from backup
            for fname in os.listdir(backup_dir):
                src = os.path.join(backup_dir, fname)
                dst = os.path.join(cfg.NGINX_STREAM_DIR, fname)
                shutil.move(src, dst)
            shutil.rmtree(backup_dir, ignore_errors=True)
        return

    # Atomic replace: remove old and move new
    try:
        for fname in existing_conf_files:
            old_path = os.path.join(cfg.NGINX_STREAM_DIR, fname)
            if os.path.exists(old_path):
                os.remove(old_path)
        for fname in os.listdir(temp_stream_path):
            src = os.path.join(temp_stream_path, fname)
            dst = os.path.join(cfg.NGINX_STREAM_DIR, fname)
            shutil.move(src, dst)
    except Exception as e:
        ws_error("[STREAM_MANAGER]", f"Error replacing configs: {e}")
        # Restore from backup
        if backup_dir:
            for fname in os.listdir(backup_dir):
                src = os.path.join(backup_dir, fname)
                dst = os.path.join(cfg.NGINX_STREAM_DIR, fname)
                shutil.move(src, dst)
    finally:
        shutil.rmtree(temp_stream_dir, ignore_errors=True)
        if backup_dir:
            shutil.rmtree(backup_dir, ignore_errors=True)
    # Show summary with Rich Table
    if synced_files:
        table = Table(title="Synchronized Streams", show_lines=True)
        table.add_column("ID", style="cyan", justify="right")
        table.add_column("Port", style="magenta", justify="right")
        table.add_column("TCP", style="green", justify="center")
        table.add_column("UDP", style="green", justify="center")
        table.add_column("Destination", style="yellow")
        for s in synced_files:
            table.add_row(
                str(s["id"]),
                str(s["port"]),
                s["tcp"],
                s["udp"],
                s["destino"],
            )
        # Imprimir la tabla en consola
        from UI.console_handler import console_handler

        console_handler.console.print(table)
        # Guardar la tabla como string en el log
        ws_info("[STREAM_MANAGER]", str(table))
    else:
        ws_warning("[STREAM_MANAGER]", "No active streams to synchronize.")

    # FIX #5: Verify NGINX reload succeeded
    try:
        reload_result = reload_npm()
        if reload_result:
            ws_info("[STREAM_MANAGER]", "NGINX reloaded successfully")
        else:
            ws_warning("[STREAM_MANAGER]", "NGINX reload may have failed, check logs")
    except Exception as e:
        ws_error("[STREAM_MANAGER]", f"Error reloading NGINX: {e}")
