"""Safe, reversible L1 fixes. Windows only; every function returns (ok, note)."""
import functools
import os
import subprocess
import tempfile

from diagnostics import IS_WIN


def _run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return p.returncode == 0, (p.stdout + p.stderr).strip()[:200]


def _guard(fn):
    @functools.wraps(fn)
    def wrapper():
        if not IS_WIN:
            return False, "Auto-fix is supported on Windows only"
        try:
            return fn()
        except Exception as e:
            return False, f"Fix raised an error: {e}"
    return wrapper


@_guard
def flush_dns():
    ok, out = _run(["ipconfig", "/flushdns"])
    return ok, "Ran ipconfig /flushdns" + ("" if ok else f" (failed: {out})")


@_guard
def renew_ip():
    _run(["ipconfig", "/release"])
    ok, out = _run(["ipconfig", "/renew"])
    return ok, "Ran ipconfig /release and /renew" + ("" if ok else f" (failed: {out})")


@_guard
def restart_spooler():
    _run(["net", "stop", "spooler"])
    ok, out = _run(["net", "start", "spooler"])
    return ok, "Restarted Print Spooler service" + ("" if ok else f" (failed: {out})")


@_guard
def clear_temp():
    freed, skipped = 0, 0
    for root, _, files in os.walk(tempfile.gettempdir()):
        for f in files:
            p = os.path.join(root, f)
            try:
                size = os.path.getsize(p)
                os.remove(p)
                freed += size
            except OSError:
                skipped += 1          # file in use - leave it alone
    return True, f"Cleared temp files, freed {round(freed/1024/1024,1)} MB ({skipped} in use, skipped)"


# check key -> fix. Checks missing here have no safe auto-fix and get escalated.
FIXES = {"dns": flush_dns, "internet": renew_ip, "spooler": restart_spooler,
         "temp": clear_temp, "disk": clear_temp}
