import os
import sqlite3
import subprocess

NGINX_STREAM_DIR = os.path.join("data", "nginx", "stream")
NGINX_PROXY_HOST_DIR = os.path.join("data", "nginx", "proxy_host")
SQLITE_DB_PATH = os.path.join("data", "database.sqlite")

def clean_stream_conf():
    if os.path.isdir(NGINX_STREAM_DIR):
        for fname in os.listdir(NGINX_STREAM_DIR):
            if fname.endswith('.conf'):
                os.remove(os.path.join(NGINX_STREAM_DIR, fname))
        print("Stream .conf files deleted.")
    else:
        print("Stream directory not found.")

def clean_proxy_host_conf():
    if os.path.isdir(NGINX_PROXY_HOST_DIR):
        for fname in os.listdir(NGINX_PROXY_HOST_DIR):
            if fname.endswith('.conf'):
                os.remove(os.path.join(NGINX_PROXY_HOST_DIR, fname))
        print("proxy_host .conf files deleted.")
    else:
        print("proxy_host directory not found.")

def clean_streams_sqlite():
    if not os.path.exists(SQLITE_DB_PATH):
        print("SQLite database not found.")
        return
    conn = sqlite3.connect(SQLITE_DB_PATH)
    try:
        cur = conn.cursor()
        # Check if the 'stream' table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stream';")
        if not cur.fetchone():
            print("The 'stream' table does not exist in the database.")
            return
        cur.execute("DELETE FROM stream")
        conn.commit()
        print("'stream' table cleaned in the SQLite database.")
    finally:
        conn.close()

def clean_proxy_host_sqlite():
    if not os.path.exists(SQLITE_DB_PATH):
        print("SQLite database not found.")
        return
    conn = sqlite3.connect(SQLITE_DB_PATH)
    try:
        cur = conn.cursor()
        # Check if the 'proxy_host' table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='proxy_host';")
        if not cur.fetchone():
            print("The 'proxy_host' table does not exist in the database.")
            return
        # Safe cleanup: only mark as deleted (is_deleted=1) and disable (enabled=0)
        cur.execute("UPDATE proxy_host SET is_deleted=1, enabled=0")
        conn.commit()
        print("'proxy_host' records marked as deleted and disabled in the SQLite database.")
    finally:
        conn.close()

def restart_npm():
    print("Restarting Nginx Proxy Manager with docker-compose...")
    subprocess.run(["docker-compose", "down"], check=True)
    subprocess.run(["docker-compose", "up", "-d"], check=True)
    print("Container restarted.")

if __name__ == "__main__":
    if os.environ.get("RUN_FROM_PANEL") != "1":
        print("This script must be run from Control_Panel.py")
        import sys
        sys.exit(1)
    clean_stream_conf()
    clean_proxy_host_conf()
    clean_streams_sqlite()
    clean_proxy_host_sqlite()
    restart_npm()
