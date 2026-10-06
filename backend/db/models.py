"""
Data access functions.

This is the ONLY file that should contain SQL. Everywhere else in the app
(main.py, future API routes) calls these functions instead of writing
queries directly — keeps the database logic in one place, easy to change
later (e.g. if you ever move off SQLite).
"""

import time
from db.db import get_connection


def insert_reading(
    risk_score: float,
    active_tier: str,
    cpu_percent: float,
    memory_percent: float,
    process_cpu_percent: float,
    process_memory_mb: float,
    estimated_energy_units: float,
    timestamp: float = None,
) -> int:
    """
    Stores one monitoring-loop tick: the risk score, active tier, and
    resource usage at that instant. Returns the new row's id.
    """
    if timestamp is None:
        timestamp = time.time()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO readings (
            timestamp, risk_score, active_tier,
            cpu_percent, memory_percent,
            process_cpu_percent, process_memory_mb, estimated_energy_units
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        timestamp, risk_score, active_tier,
        cpu_percent, memory_percent,
        process_cpu_percent, process_memory_mb, estimated_energy_units,
    ))
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def insert_tier_event(from_tier: str, to_tier: str, timestamp: float = None) -> int:
    """Records a tier switch (only called when the tier actually changes)."""
    if timestamp is None:
        timestamp = time.time()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO tier_events (timestamp, from_tier, to_tier)
        VALUES (?, ?, ?)
    """, (timestamp, from_tier, to_tier))
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_recent_readings(limit: int = 100) -> list[dict]:
    """
    Returns the most recent `limit` readings, oldest first — exactly the
    shape a dashboard line chart wants (left = past, right = now).
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM readings
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return list(reversed(rows))  # flip back to chronological order


def get_recent_tier_events(limit: int = 50) -> list[dict]:
    """Returns the most recent tier-switch events, oldest first."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM tier_events
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return list(reversed(rows))


def get_readings_between(start_ts: float, end_ts: float) -> list[dict]:
    """
    Returns all readings between two timestamps.
    This is what your Config A vs Config B experiment scripts will use —
    run a scenario, note the start/end time, then pull exactly that window
    for analysis.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM readings
        WHERE timestamp BETWEEN ? AND ?
        ORDER BY timestamp ASC
    """, (start_ts, end_ts))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def clear_all_data():
    """
    Wipes both tables. Useful between experiment runs so Config A and
    Config B data don't mix together in the same database.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM readings")
    cur.execute("DELETE FROM tier_events")
    conn.commit()
    conn.close()