#!/usr/bin/env python3
"""Decision-free measurement for the kotoba-vm-evm bot.

Prints the current state of the kotoba-vm EVM/FEVM implementation so the
bot can pick the next slice. On any failure prints a REFUSED banner and
exits 0 (the bot must learn it is blind, never that the work is done).
"""
import json
import os
import subprocess
import sys

WORKTREE_CANDIDATES = [
    os.environ.get("KOTOBA_VM_EVM_WORKTREE", ""),
    os.path.expanduser("~/.itonami-fleet/worktrees/bot-kotoba-vm-evm"),
    os.path.expanduser("~/.gftd/worktrees/kotoba-vm-evm"),
]
WORKTREE = next((p for p in WORKTREE_CANDIDATES if p and os.path.isdir(p)), WORKTREE_CANDIDATES[-1])


def run(cmd, cwd=None, timeout=120):
    try:
        r = subprocess.run(
            cmd, cwd=cwd or WORKTREE, capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:  # noqa: BLE001
        return 127, f"EXC {e}"


def refused(why):
    print("REFUSED: " + why)
    print(json.dumps({"state": "refused", "reason": why}))
    sys.exit(0)


def main():
    if not os.path.isdir(WORKTREE):
        refused(f"worktree missing: {WORKTREE}")
    rc, out = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if rc != 0:
        refused(f"git failed in worktree: {out.strip()[:200]}")
    head = out.strip()
    rc, out = run(["git", "status", "--porcelain"])
    dirty = len([l for l in out.splitlines() if l.strip()])

    def exists(p):
        return os.path.isfile(os.path.join(WORKTREE, p))

    # kotoba-vm uses the .cljk extension; keep these in sync with main.
    files = {
        "u256": "src/kotoba/vm/evm/u256.cljk",
        "u256_test": "test/kotoba/vm/evm/u256_test.cljk",
        "core": "src/kotoba/vm/evm/core.cljk",
        "core_test": "test/kotoba/vm/evm/core_test.cljk",
        "storage_env": "src/kotoba/vm/evm/env.cljk",
        "calls": "src/kotoba/vm/evm/calls.cljk",
        "fvm_map": "src/kotoba/vm/fvm/mapping.cljk",
        "fvm_test": "test/kotoba/vm/fvm/mapping_test.cljk",
    }
    present = {k: exists(p) for k, p in files.items()}

    rc, out = run(["clojure", "-M:test"], timeout=420)
    test_tail = "\n".join(out.strip().splitlines()[-4:]) if out.strip() else ""
    tests_ok = rc == 0 and "0 failures, 0 errors" in out

    rc2, out2 = run(["clojure", "-M:lint"], timeout=180)
    lint_ok = rc2 == 0

    profile = os.path.join(WORKTREE, "kototama-profile.edn")
    evm_status = "?"
    try:
        with open(profile) as f:
            txt = f.read()
        if ":evm/v1" in txt:
            import re
            m = re.search(r":evm/v1\s+.*?:status\s+:(\S+)", txt)
            if m:
                evm_status = m.group(1)
            else:
                m2 = re.search(r"\{:evm/v1\s*\{[^}]*:status\s+:(\S+?)\s", txt)
                evm_status = m2.group(1) if m2 else "present-unparsed"
    except OSError:
        pass

    # slice selection (mechanical, in SOUL-defined order)
    # fevm-mapping is done when src/kotoba/vm/fvm/mapping.cljk exists
    if not present["u256"]:
        nxt = "evm-u256"
    elif not present["core"]:
        nxt = "evm-core"
    elif not present["storage_env"]:
        nxt = "evm-storage+env"
    elif not present["calls"]:
        nxt = "evm-calls"
    elif not present["fvm_map"]:
        nxt = "fevm-mapping"
    elif evm_status not in ("partial",):
        nxt = "profile-update"
    else:
        nxt = "done"

    print(
        json.dumps(
            {
                "state": "ok",
                "worktree": WORKTREE,
                "head": head,
                "dirty_files": dirty,
                "files_present": present,
                "tests_ok": tests_ok,
                "test_tail": test_tail,
                "lint_ok": lint_ok,
                "profile_evm_status": evm_status,
                "next_slice": nxt,
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
