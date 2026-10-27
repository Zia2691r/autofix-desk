"""Diagnostic checks. Every check returns a dict (see _r) and never raises."""
import os
import platform
import re
import shutil
import socket
import subprocess
import tempfile
from collections import Counter

from config import GROUPS, THRESHOLDS as T

IS_WIN = platform.system() == "Windows"


def _r(key, label, status, detail, category, priority, group=None):
    return {"key": key, "label": label, "status": status, "detail": detail,
            "category": category, "priority": priority,
            "group": group or GROUPS["l1"]}


def check_internet():
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=3).close()
        return _r("internet", "Internet connectivity", "OK", "Reached 1.1.1.1:53", "Network", "P2")
    except OSError as e:
        return _r("internet", "Internet connectivity", "FAIL", f"Cannot reach 1.1.1.1:53 ({e})", "Network", "P2")


def check_dns():
    try:
        ip = socket.gethostbyname("www.microsoft.com")
        return _r("dns", "DNS resolution", "OK", f"www.microsoft.com -> {ip}", "Network", "P3")
    except OSError as e:
        return _r("dns", "DNS resolution", "FAIL", f"Name resolution failed ({e})", "Network", "P3")


def check_disk():
    path = "C:\\" if IS_WIN else "/"
    u = shutil.disk_usage(path)
    free_pct = round(u.free / u.total * 100, 1)
    detail = f"{free_pct}% free on {path}"
    if free_pct < T["disk_fail_pct_free"]:
        status = "FAIL"
    elif free_pct < T["disk_warn_pct_free"]:
        status = "WARN"
    else:
        status = "OK"
    return _r("disk", "Disk space", status, detail, "Hardware/Storage", "P3")


def _dir_size_mb(path):
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return round(total / 1024 / 1024, 1)


def check_temp():
    size = _dir_size_mb(tempfile.gettempdir())
    status = "WARN" if size > T["temp_warn_mb"] else "OK"
    return _r("temp", "Temp folder size", status, f"{size} MB in {tempfile.gettempdir()}",
              "Hardware/Storage", "P4")


def check_resources():
    try:
        import psutil
    except ImportError:
        return _r("resources", "CPU / memory", "SKIP", "psutil not installed", "Performance", "P3")
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory().percent
    bad = cpu >= T["cpu_warn_pct"] or mem >= T["mem_warn_pct"]
    return _r("resources", "CPU / memory", "WARN" if bad else "OK",
              f"CPU {cpu}% | RAM {mem}%", "Performance", "P3")


def check_spooler():
    if not IS_WIN:
        return _r("spooler", "Print Spooler service", "SKIP", "Windows only", "Printing", "P3")
    try:
        out = subprocess.run(["sc", "query", "Spooler"], capture_output=True, text=True, timeout=10).stdout
        running = "RUNNING" in out
        return _r("spooler", "Print Spooler service", "OK" if running else "FAIL",
                  "Service running" if running else "Service not running", "Printing", "P3")
    except Exception as e:
        return _r("spooler", "Print Spooler service", "SKIP", f"Could not query: {e}", "Printing", "P3")


def check_failed_logins():
    """Counts Windows failed logons (Event ID 4625). Needs an elevated prompt."""
    label = "Failed logon attempts"
    if not IS_WIN:
        return _r("failed_logins", label, "SKIP", "Windows only", "Security", "P2", GROUPS["soc"])
    window_ms = T["failed_logins_window_min"] * 60 * 1000
    query = f"*[System[(EventID=4625) and TimeCreated[timediff(@SystemTime) <= {window_ms}]]]"
    try:
        p = subprocess.run(["wevtutil", "qe", "Security", f"/q:{query}", "/c:500", "/f:xml"],
                           capture_output=True, text=True, timeout=30)
        if p.returncode != 0:
            return _r("failed_logins", label, "SKIP", "Run as Administrator to read Security log",
                      "Security", "P2", GROUPS["soc"])
        count = p.stdout.count("<EventID>4625</EventID>")
        users = Counter(re.findall(r"<Data Name='TargetUserName'>(.*?)</Data>", p.stdout))
        top = ", ".join(f"{u} ({n})" for u, n in users.most_common(3)) or "n/a"
        status = "WARN" if count >= T["failed_logins_warn"] else "OK"
        return _r("failed_logins", label, status,
                  f"{count} failed logons in {T['failed_logins_window_min']} min; top accounts: {top}",
                  "Security", "P2", GROUPS["soc"])
    except Exception as e:
        return _r("failed_logins", label, "SKIP", f"Could not read log: {e}", "Security", "P2", GROUPS["soc"])


CHECKS = {
    "internet": check_internet, "dns": check_dns, "disk": check_disk, "temp": check_temp,
    "resources": check_resources, "spooler": check_spooler, "failed_logins": check_failed_logins,
}


def run_all():
    return [fn() for fn in CHECKS.values()]
