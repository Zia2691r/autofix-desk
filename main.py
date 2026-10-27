"""AutoFix Desk - automated L1 troubleshooting, ticketing and MIS reporting.

Usage:
  python main.py scan                  # diagnose + log tickets (no fixes)
  python main.py scan --fix            # diagnose, auto-fix, resolve/escalate
  python main.py scan --dry-run        # diagnose + show planned fixes; writes nothing
  python main.py report [--source lab] # build the Excel MIS report
  python main.py stats                 # quick KPIs in the terminal
  python main.py demo --n 50           # seed SYNTHETIC tickets (source=demo) to test the report
"""
import argparse
import random
from datetime import datetime, timedelta

import report as report_mod
from config import GROUPS, SLA_MINUTES
from diagnostics import CHECKS, run_all
from remediation import FIXES
from ticketing import (connect, create_ticket, escalate_ticket, l1_note,
                       open_ticket_for, resolve_ticket)

ICON = {"OK": "[ OK ]", "WARN": "[WARN]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}


def handle(conn, tid, r):
    key = r["key"]
    evidence = {"diagnostic": r, "actions": []}
    if key == "failed_logins":                      # security events are never auto-"fixed"
        notes = l1_note(r["detail"], "Queried Security log (Event ID 4625)",
                        "Routed to SOC L1 for investigation", "Escalated")
        escalate_ticket(conn, tid, GROUPS["soc"], notes, evidence)
        return "Escalated -> SOC L1"
    fix = FIXES.get(key)
    if fix is None:
        notes = l1_note(r["detail"], f"Ran {key} diagnostic", "No safe auto-fix available", "Escalated to L2")
        escalate_ticket(conn, tid, GROUPS["l2"], notes, evidence)
        return "Escalated -> L2 (no safe auto-fix)"
    ok, note = fix()
    evidence["actions"].append(note)
    recheck = CHECKS[key]()
    evidence["recheck"] = recheck
    if recheck["status"] == "OK":
        resolve_ticket(conn, tid, l1_note(r["detail"], f"Ran {key} diagnostic", note,
                                          "Re-test passed, resolved"), auto=True)
        return "Auto-resolved"
    escalate_ticket(conn, tid, GROUPS["l2"],
                    l1_note(r["detail"], f"Ran {key} diagnostic", note, "Re-test failed, escalated to L2"),
                    evidence)
    return "Escalated -> L2 (fix did not work)"


def cmd_scan(a):
    results = run_all()
    for r in results:
        print(f"{ICON[r['status']]} {r['label']:<24} {r['detail']}")
    issues = [r for r in results if r["status"] in ("WARN", "FAIL")]
    if not issues:
        print("\nNo issues found.")
        return
    if a.dry_run:
        print("\nDRY RUN - would raise tickets for:")
        for r in issues:
            print(f"  {r['label']} ({r['priority']}) -> fix: {FIXES[r['key']].__name__ if r['key'] in FIXES else 'escalate'}")
        return
    conn = connect()
    print()
    for r in issues:
        dup = open_ticket_for(conn, r["key"])
        if dup:
            print(f"Skipped duplicate: {r['label']} already open as {dup['ticket_id']}")
            continue
        tid = create_ticket(conn, r, source=a.source)
        outcome = handle(conn, tid, r) if a.fix else "Logged (Open)"
        print(f"{tid} [{r['priority']}] {r['label']} -> {outcome}")


def cmd_report(a):
    path, n = report_mod.build(connect(), source=a.source)
    print(f"Report written: {path} ({n} tickets, source={a.source})")


def cmd_stats(a):
    conn = connect()
    where, args = ("", ()) if a.source == "all" else ("WHERE source=?", (a.source,))
    row = conn.execute(f"""SELECT COUNT(*) t, SUM(status='Resolved') r, SUM(status='Escalated') e,
        SUM(auto_resolved) a, SUM(status='Resolved' AND resolved_at<=sla_due) s FROM tickets {where}""", args).fetchone()
    t = row["t"] or 0
    if not t:
        print("No tickets for that source yet.")
        return
    r = row["r"] or 0
    print(f"Tickets: {t} | Resolved: {r} | Escalated: {row['e'] or 0}")
    print(f"Auto-resolution: {(row['a'] or 0)/t:.0%} | SLA met (resolved): {((row['s'] or 0)/r if r else 0):.0%}")


def cmd_demo(a):
    """SYNTHETIC data to preview the report. Tagged source=demo; never quote these numbers."""
    rnd, conn, now = random.Random(a.seed), connect(), datetime.now()
    pool = [r for r in run_all() if r["key"] in ("dns", "internet", "disk", "temp", "spooler", "resources", "failed_logins")]
    for i in range(a.n):
        r = dict(rnd.choice(pool), detail="synthetic demo scenario")
        t0 = now - timedelta(days=rnd.randint(0, 6), minutes=rnd.randint(0, 600))
        tid = create_ticket(conn, r, source="demo", now=t0)
        if r["key"] in FIXES and rnd.random() < 0.8:
            resolve_ticket(conn, tid, "Demo: synthetic resolution", True, t0 + timedelta(minutes=rnd.randint(2, 500)))
        else:
            escalate_ticket(conn, tid, GROUPS["soc"] if r["key"] == "failed_logins" else GROUPS["l2"],
                            "Demo: synthetic escalation", {"demo": True})
    print(f"Seeded {a.n} synthetic tickets (source=demo).")


def main():
    p = argparse.ArgumentParser(description="AutoFix Desk")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("--fix", action="store_true")
    s.add_argument("--dry-run", action="store_true"); s.add_argument("--source", default="lab")
    s.set_defaults(fn=cmd_scan)
    for name, fn in (("report", cmd_report), ("stats", cmd_stats)):
        x = sub.add_parser(name); x.add_argument("--source", default="lab"); x.set_defaults(fn=fn)
    d = sub.add_parser("demo"); d.add_argument("--n", type=int, default=50)
    d.add_argument("--seed", type=int, default=42); d.set_defaults(fn=cmd_demo)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
