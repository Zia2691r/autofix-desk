"""SQLite ticket store with L1-style notes, SLA due times and escalation."""
import json
import sqlite3
from datetime import datetime, timedelta

from config import DB_PATH, SLA_MINUTES

SCHEMA = """CREATE TABLE IF NOT EXISTS tickets(
    ticket_id TEXT PRIMARY KEY, created_at TEXT, check_key TEXT, category TEXT,
    priority TEXT, summary TEXT, status TEXT, assigned_group TEXT, sla_due TEXT,
    resolved_at TEXT, resolution_notes TEXT, evidence TEXT,
    auto_resolved INTEGER DEFAULT 0, source TEXT DEFAULT 'lab')"""

FMT = "%Y-%m-%d %H:%M:%S"


def connect(path=DB_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def _next_id(conn, now):
    prefix = f"INC{now:%Y%m%d}"
    n = conn.execute("SELECT COUNT(*) FROM tickets WHERE ticket_id LIKE ?", (prefix + "%",)).fetchone()[0]
    return f"{prefix}-{n + 1:04d}"


def open_ticket_for(conn, key):
    """Duplicate suppression: an unresolved Open ticket for the same check."""
    return conn.execute("SELECT ticket_id FROM tickets WHERE check_key=? AND status='Open'", (key,)).fetchone()


def create_ticket(conn, result, source="lab", now=None):
    now = now or datetime.now()
    tid = _next_id(conn, now)
    due = now + timedelta(minutes=SLA_MINUTES[result["priority"]])
    summary = f"{result['label']}: {result['detail']}"
    conn.execute(
        "INSERT INTO tickets(ticket_id,created_at,check_key,category,priority,summary,status,"
        "assigned_group,sla_due,source) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (tid, now.strftime(FMT), result["key"], result["category"], result["priority"], summary,
         "Open", result["group"], due.strftime(FMT), source))
    conn.commit()
    return tid


def resolve_ticket(conn, tid, notes, auto=True, now=None):
    now = now or datetime.now()
    conn.execute("UPDATE tickets SET status='Resolved', resolved_at=?, resolution_notes=?, auto_resolved=? "
                 "WHERE ticket_id=?", (now.strftime(FMT), notes, int(auto), tid))
    conn.commit()


def escalate_ticket(conn, tid, group, notes, evidence):
    conn.execute("UPDATE tickets SET status='Escalated', assigned_group=?, resolution_notes=?, evidence=? "
                 "WHERE ticket_id=?", (group, notes, json.dumps(evidence, indent=2), tid))
    conn.commit()


def l1_note(issue, checks_done, action, outcome):
    """Standard L1 resolution-log format."""
    return f"Issue: {issue} | Troubleshooting: {checks_done} | Action: {action} | Outcome: {outcome}"
