"""AutoFix Desk configuration. Adjust to match your lab's policy."""
from pathlib import Path

BASE = Path(__file__).parent
DB_PATH = BASE / "data" / "tickets.db"
REPORT_DIR = BASE / "reports"

# SLA / TAT targets in minutes per priority.
# ASSUMPTION: typical L1 service-desk targets, not Wipro's real policy.
SLA_MINUTES = {"P1": 60, "P2": 240, "P3": 480, "P4": 1440}

THRESHOLDS = {
    "disk_warn_pct_free": 20,     # WARN below this % free
    "disk_fail_pct_free": 10,     # FAIL below this % free
    "temp_warn_mb": 300,          # WARN if temp folder exceeds this size
    "cpu_warn_pct": 90,
    "mem_warn_pct": 90,
    "failed_logins_warn": 5,      # failed logons inside the window
    "failed_logins_window_min": 15,
}

GROUPS = {"l1": "L1 Service Desk", "l2": "L2 Support", "soc": "SOC L1 (Security)"}
