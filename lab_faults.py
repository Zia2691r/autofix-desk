"""Fault injection for YOUR OWN Windows lab VM only. Creates real, reversible faults so you can
measure how AutoFix Desk performs (these are the numbers you can honestly quote).

  python lab_faults.py stop-spooler
  python lab_faults.py fill-temp --mb 400
  python lab_faults.py failed-logins --n 8      (generates Event ID 4625 entries)
  python lab_faults.py cleanup
Run an elevated (Administrator) prompt. Do NOT run on a work or shared machine.
"""
import argparse
import os
import platform
import subprocess
import tempfile

PREFIX = "autofix_fill_"


def stop_spooler(_):
    subprocess.run(["net", "stop", "spooler"], check=False)


def fill_temp(a):
    chunk = b"0" * 1024 * 1024
    for i in range(a.mb // 50 or 1):
        with open(os.path.join(tempfile.gettempdir(), f"{PREFIX}{i}.tmp"), "wb") as f:
            for _ in range(min(50, a.mb)):
                f.write(chunk)
    print(f"Created ~{a.mb} MB of junk in {tempfile.gettempdir()}")


def failed_logins(a):
    for _ in range(a.n):
        subprocess.run(["net", "use", r"\\localhost\IPC$", "/user:labfakeuser", "WrongPass!123"],
                       capture_output=True)
    print(f"Attempted {a.n} bad logons as 'labfakeuser'")


def cleanup(_):
    subprocess.run(["net", "start", "spooler"], check=False)
    for f in os.listdir(tempfile.gettempdir()):
        if f.startswith(PREFIX):
            os.remove(os.path.join(tempfile.gettempdir(), f))
    print("Lab faults cleaned up")


if __name__ == "__main__":
    if platform.system() != "Windows":
        raise SystemExit("Windows lab VM only")
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stop-spooler").set_defaults(fn=stop_spooler)
    f = sub.add_parser("fill-temp"); f.add_argument("--mb", type=int, default=400); f.set_defaults(fn=fill_temp)
    l = sub.add_parser("failed-logins"); l.add_argument("--n", type=int, default=8); l.set_defaults(fn=failed_logins)
    sub.add_parser("cleanup").set_defaults(fn=cleanup)
    a = p.parse_args(); a.fn(a)
