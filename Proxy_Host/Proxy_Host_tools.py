import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Config import config as cfg
import sqlite3
import json


def list_certificates_from_db():
    certs = []
    db_path = cfg.SQLITE_DB_PATH
    if not os.path.exists(db_path):
        return certs

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nice_name, domain_names, provider, expires_on, meta FROM certificate WHERE is_deleted=0"
        )
        for row in cur.fetchall():
            try:
                domains = json.loads(row[2]) if row[2] else []
            except Exception:
                domains = []
            try:
                meta = json.loads(row[5]) if row[5] else {}
            except Exception:
                meta = {}
            certs.append(
                {
                    "id": row[0],
                    "nice_name": row[1],
                    "domain_names": domains,
                    "provider": row[3],
                    "expires_on": row[4],
                    "meta": meta,
                }
            )
    finally:
        conn.close()
    return certs


# No changes needed, function list_certificates_from_db() already returns a list of certificates.
