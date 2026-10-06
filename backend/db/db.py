"""
Database connection + schema setup.

Why raw sqlite3 instead of an ORM (SQLAlchemy etc.):
For a prototype this size, raw SQL keeps the data model fully transparent —
you can open ecoshield.db in any SQLite browser (e.g. "DB Browser for SQLite")
and see exactly what's being stored, with no hidden abstraction to explain
in your viva.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "ecoshield.db")


def get_connection() -> sqlite3.Connection:
    """
    Opens a connection to the EcoShield database.
    check_same_thread=False: FastAPI's background loop and request handlers
    may run on different threads/event loop callbacks — SQLite needs this
    flag to allow that safely for our simple read/write pattern.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # lets us access columns by name, e.g. row["risk_score"]
    return conn


def init_db():
    """
    Creates tables if they don't already exist. Safe to call every time
    the app starts — CREATE TABLE IF NOT EXISTS is idempotent.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            risk_score REAL NOT NULL,
            active_tier TEXT NOT NULL,
            cpu_percent REAL,
            memory_percent REAL,
            process_cpu_percent REAL,
            process_memory_mb REAL,
            estimated_energy_units REAL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tier_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            from_tier TEXT NOT NULL,
            to_tier TEXT NOT NULL
        )
    """)

    # Index on timestamp speeds up "give me the last N readings" queries,
    # which is exactly what the dashboard's history charts will ask for.
    cur.execute("CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON readings(timestamp)")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")