import os
import sys
import sqlite3
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg
from UI.console_handler import ws_info, ws_error, ws_warning


def generate_proxy_host_conf(
    proxy_id,
    domains,
    destination_ip,
    destination_port,
    proxy_type="https",
    listen_port=None,
    ssl_cert_path="/etc/letsencrypt/live/npm-1/fullchain.pem",
    ssl_key_path="/etc/letsencrypt/live/npm-1/privkey.pem",
):

    domain_line = ", ".join(domains)
    server_name_line = " ".join(domains)
    conf_lines = []
    conf_lines.append("# ------------------------------------------------------------")
    conf_lines.append(f"# {domain_line}")
    conf_lines.append("# ------------------------------------------------------------")
    conf_lines.append("")
    conf_lines.append("map $scheme $hsts_header {")
    conf_lines.append('    https   "max-age=63072000; preload";')
    conf_lines.append("}")
    conf_lines.append("")
    conf_lines.append("server {")
    conf_lines.append("  set $forward_scheme https;")
    conf_lines.append(f'  set $server         "{destination_ip}";')
    conf_lines.append(f"  set $port           {destination_port};")
    conf_lines.append("")

    # Determinar puerto de escucha
    if listen_port is None:
        listen_port = 443 if proxy_type == "https" else 80

    if proxy_type == "https":
        conf_lines.append(f"  listen {listen_port} ssl;")
        conf_lines.append("#listen [::]:{} ssl;".format(listen_port))
    else:
        conf_lines.append(f"  listen {listen_port};")
        conf_lines.append("#listen [::]:{};".format(listen_port))

    conf_lines.append("")
    conf_lines.append(f"  server_name {server_name_line};")
    conf_lines.append("  http2 off;")
    conf_lines.append("")

    if proxy_type == "https":
        conf_lines.append("  # Let's Encrypt SSL")
        conf_lines.append("  include conf.d/include/letsencrypt-acme-challenge.conf;")
        conf_lines.append("  include conf.d/include/ssl-cache.conf;")
        conf_lines.append("  include conf.d/include/ssl-ciphers.conf;")
        conf_lines.append(f"  ssl_certificate {ssl_cert_path};")
        conf_lines.append(f"  ssl_certificate_key {ssl_key_path};")
        conf_lines.append("")
        conf_lines.append("  # Force SSL")
        conf_lines.append("  include conf.d/include/force-ssl.conf;")
        conf_lines.append("")

    conf_lines.append(
        f"  access_log /data/logs/proxy-host-{proxy_id}_access.log proxy;"
    )
    conf_lines.append(f"  error_log /data/logs/proxy-host-{proxy_id}_error.log warn;")
    conf_lines.append("")
    conf_lines.append("  proxy_set_header X-Real-IP $remote_addr;")
    conf_lines.append("  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;")
    conf_lines.append("  proxy_set_header X-Forwarded-Proto $scheme;")
    conf_lines.append("")
    conf_lines.append("  location / {")
    conf_lines.append("    # Proxy!")
    conf_lines.append("    include conf.d/include/proxy.conf;")
    conf_lines.append("  }")
    conf_lines.append("")
    conf_lines.append("  # Custom")
    conf_lines.append("  include /data/nginx/custom/server_proxy[.]conf;")
    conf_lines.append("}")
    conf_lines.append("")
    return "\n".join(conf_lines)


def add_proxy_host_sqlite(
    domains,
    forward_host,
    forward_port,
    forward_scheme="http",
    certificate_id=0,
    ssl_forced=0,
    caching_enabled=0,
    block_exploits=0,
    advanced_config="",
    meta=None,
    allow_websocket_upgrade=0,
    http2_support=0,
    enabled=1,
    locations=None,
    hsts_enabled=0,
    hsts_subdomains=0,
    access_list_id=0,
):

    if not os.path.exists(cfg.SQLITE_DB_PATH):
        ws_error("[WS]", "NPM SQLite database not found.")
        return False

    conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='proxy_host';"
        )
        if not cur.fetchone():
            ws_error("[WS]", "La tabla 'proxy_host' no existe en la base de datos.")
            return False

        cur.execute("SELECT id FROM user ORDER BY id LIMIT 1")
        user_row = cur.fetchone()
        if not user_row:
            ws_error("[WS]", "No hay usuario en la base de datos.")
            return False
        owner_user_id = user_row[0]

        domain_names_json = json.dumps(domains)
        meta_json = json.dumps(meta) if meta else json.dumps({})
        locations_json = json.dumps(locations) if locations else None

        cur.execute(
            """
            INSERT INTO proxy_host (
                created_on, modified_on, owner_user_id, is_deleted,
                domain_names, forward_host, forward_port, access_list_id,
                certificate_id, ssl_forced, caching_enabled, block_exploits,
                advanced_config, meta, allow_websocket_upgrade, http2_support,
                forward_scheme, enabled, locations, hsts_enabled, hsts_subdomains
            ) VALUES (
                datetime('now'), datetime('now'), ?, 0,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )
        """,
            (
                owner_user_id,
                domain_names_json,
                forward_host,
                forward_port,
                access_list_id,
                certificate_id,
                ssl_forced,
                caching_enabled,
                block_exploits,
                advanced_config,
                meta_json,
                allow_websocket_upgrade,
                http2_support,
                forward_scheme,
                enabled,
                locations_json,
                hsts_enabled,
                hsts_subdomains,
            ),
        )
        conn.commit()
        ws_info("[WS]", f"Proxy Host creado para dominios: {', '.join(domains)}")
        return True
    except Exception as e:
        ws_error("[WS]", f"Error al crear proxy_host: {e}")
        return False
    finally:
        conn.close()


# No changes needed for menu integration.
