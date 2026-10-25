#!/usr/bin/env python3
"""Verify an install of the kotoba Hermes plugin, without Hermes.

Six cases, in three pairs. Each pair is one distinction the plugin exists to
keep, checked in BOTH directions -- a probe that only asserts the good case
stays green when the bad case has silently become the good one.

    A/B  a listed entry answers 0, an unlisted one answers 1
         (measured-and-present vs measured-and-absent)
    C/D  an absent workspace answers 2, never 1
         (could-not-look must never look like looked-and-found-nothing)
    E/F  the kit reader returns per-kit maps and names what it could not read
         (a kit that failed to parse must not vanish into a clean report)

    HERMES_DID_WORKSPACE-style configuration:
      KOTOBA_WORKSPACE=~/github/com-junkawasaki python3 probe.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
READER = os.path.join(HERE, "read_authority.cljk")


def run(command, workspace, argument=None):
    nbb = os.environ.get("KOTOBA_NBB") or shutil.which("nbb")
    if not nbb:
        print("REFUSED: nbb not found; set KOTOBA_NBB or put it on PATH")
        sys.exit(2)
    argv = [nbb, READER, command, workspace]
    if argument is not None:
        argv.append(argument)
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        payload = {"_unparseable": (proc.stderr or proc.stdout)[:400]}
    return proc.returncode, payload


def main() -> int:
    ws = os.environ.get("KOTOBA_WORKSPACE")
    if not ws:
        print("REFUSED: set KOTOBA_WORKSPACE to a com-junkawasaki checkout.")
        print("A probe that cannot look must not report a healthy plugin.")
        return 2
    ws = os.path.expanduser(ws)

    checks = []

    code, body = run("surface-status", ws, "bool-is-a-type-not-a-number")
    checks.append(("A a listed entry exits 0", code == 0 and body.get("found") is True))
    checks.append(("A …and carries a disposition", bool(body.get("disposition"))))
    checks.append(("A …and the authority's own as-of", bool(body.get("as-of"))))

    code, body = run("surface-status", ws, "no-such-entry-here")
    checks.append(("B an unlisted entry exits 1", code == 1 and body.get("found") is False))
    checks.append(("B …and still says ok (it looked)", body.get("ok") is True))

    code, body = run("surface-status", "/definitely/not/a/workspace", "x")
    checks.append(("C an absent workspace exits 2", code == 2))
    checks.append(("D …and never 1", code != 1))
    checks.append(("D …and says why", body.get("why") == "workspace-absent"))

    code, body = run("capability-kits", ws)
    kits = body.get("kits") or []
    checks.append(("E kits are read", code == 0 and len(kits) > 0))
    checks.append(("E …each with its own map", all("qualification" in k or not k.get("readable") for k in kits)))
    checks.append(("F unreadable kits are counted", "unreadable" in body))

    code, body = run("capability-kits", ws, "no-such-kit")
    checks.append(("F an unknown kit exits 1, not 0", code == 1))

    ok = True
    for label, passed in checks:
        print(("  ok   " if passed else "  FAIL ") + label)
        ok = ok and passed
    print(
        "probe OK — could-not-look and looked-and-found-nothing stay apart"
        if ok
        else "probe FAILED"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
