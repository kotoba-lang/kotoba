#!/usr/bin/env python3
"""sec-sentinel hourly throttle wrapper.

Cron fires every hour; the real iteration for one scope runs once per
cooldown window. Scope rotation is built in: each hour the NEXT scope in
the ladder is due, so all five scopes cycle daily at one audit per hour
max. A scope whose cooldown has not expired prints [SILENT]/THROTTLED and
exits 0 — the bot runs and is told 'not due', never silently skipped.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from throttle import gate, mark  # noqa: E402

SCOPES = ["kotoba", "amu", "kotobase", "kototama", "net-kotobase"]
SUPER = os.path.expanduser("~/github/com-junkawasaki")
STATE = os.path.join(os.path.expanduser("~"), ".hermes", "cron-throttle")


def due_scope():
    """The first scope whose cooldown expired, in fixed rotation order."""
    from throttle import _read_last
    import time
    now = time.time()
    best = None
    for s in SCOPES:
        last = _read_last(f"sec-sentinel-{s}")
        age = now - last if last else float("inf")
        if best is None or age > best[1]:
            best = (s, age)
    return best[0]


def main():
    scope = due_scope()
    gate(f"sec-sentinel-{scope}", hours=24)
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "vuln_state.sh")
    proc = subprocess.run(["bash", script, scope], cwd=SUPER,
                          capture_output=True, text=True, timeout=600)
    out = proc.stdout.strip()
    print(f"scope\t{scope}")
    print(f"gate\tbash vuln_state.sh {scope} (exit {proc.returncode})")
    print(out)
    if proc.returncode != 0:
        print("REFUSED — the audit surface could not be measured. Report the "
              "refusal and stop; do not propose fixes from nothing.")
        return 0  # bot must RUN and be told it is blind
    if "MEASURED" not in out:
        print("REFUSED — no MEASURED line: the output cannot be distinguished "
              "from a truncated run.")
        return 0
    mark(f"sec-sentinel-{scope}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
