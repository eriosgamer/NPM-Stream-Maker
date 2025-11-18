from Config import config as cfg
import os
import sqlite3
import sys

# Add the parent directory to sys.path to allow imports from parent modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from UI.console_handler import ws_info, ws_error, ws_warning

def clean_streams_database():
    """
    Removes all streams from the SQLite database robustly.
    Marks as deleted and then deletes the records.
    Resets the auto-increment counter.
    """
    try:
        # Check if the SQLite database file exists
        if not os.path.exists(cfg.SQLITE_DB_PATH):
            ws_info("[WS]", "SQLite database not found - skipping database cleanup")
            return False

        # Use 'with' to ensure the connection is closed properly
        with sqlite3.connect(cfg.SQLITE_DB_PATH) as conn:
            cur = conn.cursor()
            # Check if the 'stream' table exists in the database
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='stream'")
            if not cur.fetchone():
                ws_warning("[WS]", "Table 'stream' does not exist in the database")
                return False

            # Count active streams (not marked as deleted)
            cur.execute("SELECT COUNT(*) FROM stream WHERE is_deleted=0")
            active_streams = cur.fetchone()[0]

            # Count total streams in the table
            cur.execute("SELECT COUNT(*) FROM stream")
            total_streams = cur.fetchone()[0]

            if total_streams == 0:
                ws_info("[WS]", "Database stream table is already empty")
                return True

            ws_info("[WS]", f"Found {active_streams} active streams, {total_streams} total streams in database")

            try:
                # Mark all active streams as deleted and disable them
                cur.execute(
                    "UPDATE stream SET is_deleted=1, enabled=0 WHERE is_deleted=0")
                marked_deleted = cur.rowcount

                # Permanently remove all streams from the table
                cur.execute("DELETE FROM stream")
                deleted_count = cur.rowcount

                # Reset the auto-increment counter for the 'stream' table
                cur.execute("DELETE FROM sqlite_sequence WHERE name='stream'")

                conn.commit()
            except sqlite3.DatabaseError as db_err:
                ws_error("[WS]", f"SQLite error during cleanup: {db_err}")
                conn.rollback()
                return False

            if marked_deleted > 0:
                ws_info("[WS]", f"Marked {marked_deleted} active streams as deleted")
            if deleted_count > 0:
                ws_info("[WS]", f"Permanently removed {deleted_count} streams from database")
                ws_info("[WS]", "Reset stream table auto-increment counter")
            else:
                ws_info("[WS]", "No streams to remove from database")
            return True

    except Exception as e:
        ws_error("[WS]", f"Error cleaning streams database: {e}")
        return False
