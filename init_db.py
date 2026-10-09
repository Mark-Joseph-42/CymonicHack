#!/usr/bin/env python3
"""
Initialize and verify the SQLite database for Apex Logistics Claim Engine.
"""
import sqlite3
import sys
from pathlib import Path

DB_FILE = Path(__file__).parent / "apex_claims.db"
SCHEMA_FILE = Path(__file__).parent / "schema.sql"

def init_database():
    if not SCHEMA_FILE.exists():
        print(f"Error: {SCHEMA_FILE} not found.")
        sys.exit(1)

    print(f"Initializing database at: {DB_FILE}")
    conn = sqlite3.connect(DB_FILE)
    try:
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        
        client_count = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        order_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        
        print("Database initialized successfully.")
        print(f"Loaded {client_count} sample clients.")
        print(f"Loaded {order_count} sample orders/claims.")
    finally:
        conn.close()

if __name__ == "__main__":
    init_database()
