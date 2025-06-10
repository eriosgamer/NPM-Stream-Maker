# conflict_cleaner.py
# This module provides utility functions to clear conflict resolution data
# from both files and the database in the Stream Manager application.
# It is intended to help maintain a clean state by removing records and files
# related to port conflicts in streaming configurations.

import json
import os
import sys
import sqlite3
from dotenv import load_dotenv
load_dotenv()
from rich.console import Console

# Add the parent directory to sys.path to allow importing the config module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg

console = Console()

# Copied
def clear_all_conflict_resolution_data():
    """
    Removes all conflict resolution data from files and the database.
    Returns the number of items removed.
    """
    console.print(
        "[bold cyan][STREAM_MANAGER][/bold cyan] Clearing all conflict resolution data...")

    cleared_count = 0

    # Iterate over all conflict files defined in the config and remove them if they exist
    for file_path in cfg.CONFLICT_FILES:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                cleared_count += 1
                console.print(
                    f"[bold green][STREAM_MANAGER][/bold green] Cleared: {file_path}")
        except Exception as e:
            console.print(
                f"[bold red][STREAM_MANAGER][/bold red] Error clearing {file_path}: {e}")

    # Clear conflict resolution streams from the database
    try:
        if os.path.exists(cfg.SQLITE_DB_PATH):
            conn = sqlite3.connect(cfg.SQLITE_DB_PATH)
            try:
                cur = conn.cursor()

                # Find and remove conflict resolution streams (where incoming_port != forwarding_port)
                cur.execute(
                    "SELECT COUNT(*) FROM stream WHERE incoming_port != forwarding_port AND is_deleted=0"
                )
                conflict_streams = cur.fetchone()[0]

                if conflict_streams > 0:
                    cur.execute(
                        "UPDATE stream SET is_deleted=1, enabled=0 WHERE incoming_port != forwarding_port AND is_deleted=0"
                    )
                    conn.commit()
                    cleared_count += conflict_streams
                    console.print(
                        f"[bold green][STREAM_MANAGER][/bold green] Cleared {conflict_streams} conflict resolution streams from database")

            finally:
                conn.close()
    except Exception as e:
        console.print(
            f"[bold red][STREAM_MANAGER][/bold red] Error clearing database conflict resolutions: {e}")

    console.print(
        f"[bold cyan][STREAM_MANAGER][/bold cyan] Total items cleared: {cleared_count}")
    return cleared_count


# Copied
def clear_ws_ports_file():
    """
    Clears the WebSocket ports file by writing an empty list to it.
    Uses a lock to ensure thread safety.
    """
    with cfg.ws_ports_lock:
        try:
            with open(cfg.WS_PORTS_FILE, "w") as f:
                json.dump([], f)
        except Exception as e:
            console.print(f"[bold red][WS][/bold red] Error clearing ws_ports file: {e}")
