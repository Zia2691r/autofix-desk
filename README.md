# AutoFix Desk - Automated L1 Troubleshooting & Ticket Triage

A home-lab project that mimics a service desk agent's workflow: **diagnose -> fix -> log -> escalate -> report**,
plus a security-aware triage step (failed-logon detection routed to a SOC queue).

> Lab project, not production software. Fixes run on Windows only. Test on your own VM.

## What it does
| Stage | Behaviour |
|---|---|
| Diagnose | Internet, DNS, disk, temp folder, CPU/RAM, Print Spooler, failed logons (Event ID 4625) |
| Fix | Flush DNS, renew IP, restart Spooler, clear temp. Each fix is followed by a **re-test** |
| Ticket | SQLite ticket with ID, category, priority, SLA due time, L1-format resolution note |
| Escalate | Fix failed or no safe fix -> L2 with evidence JSON. Failed logons -> SOC L1 (never auto-"fixed") |
| De-duplicate | Won't open a second ticket while one is still Open for the same check |
| Report | Excel MIS: formula-driven KPIs (auto-resolution %, SLA met %, escalation %, avg resolution time) + chart |

## Setup (Windows lab VM, Python 3.9+)
```
pip install -r requirements.txt
python main.py scan --dry-run      # see what it would do, writes nothing
```

## Measure real results (this is what you quote in interviews)
Open an **Administrator** prompt in a lab VM, then for each run: inject fault -> scan -> note result.
```
python lab_faults.py stop-spooler
python main.py scan --fix
python lab_faults.py fill-temp --mb 400
python main.py scan --fix
python lab_faults.py failed-logins --n 8
python main.py scan --fix
python lab_faults.py cleanup
```
Repeat 10+ times per fault (include a few you expect to fail), then:
```
python main.py stats
python main.py report
```
`python main.py demo` seeds **synthetic** tickets (source=demo) only to preview the report. Never quote those numbers.

## Project layout
`diagnostics.py` checks | `remediation.py` fixes | `ticketing.py` SQLite + SLA + notes | `report.py` Excel MIS |
`main.py` CLI | `lab_faults.py` fault injection | `config.py` SLA targets and thresholds (assumptions, editable)

## Resume bullet (fill in YOUR measured numbers)
- Built AutoFix Desk, a Python/SQLite service desk automation toolkit that diagnoses common L1 faults, applies
  safe fixes with re-test validation, logs SLA-tracked tickets and escalates with evidence; in [N] lab fault-injection
  runs, auto-resolved [X]% with [Y]% SLA compliance and routed failed-logon spikes to a SOC queue.

## Interview questions to prepare
- Why re-test after a fix? (Confirms resolution before closing; avoids false closures.)
- Why isn't the security alert auto-fixed? (Needs human investigation; auto-actions could destroy evidence.)
- What's the SLA/TAT logic? (Priority -> minutes in config.py; "SLA met" = resolved before due time.)
- What would you add for production? (ITSM integration like ServiceNow API, RBAC, audit logging, approvals for fixes.)
- What are the limits? (Local machine only, Windows fixes only, thresholds not tuned to a real client.)
