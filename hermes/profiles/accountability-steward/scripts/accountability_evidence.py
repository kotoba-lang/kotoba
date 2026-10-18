#!/usr/bin/env python3
"""accountability_evidence.py - ADR-2610081200 rollout evidence.

Read-only measurement of how far the accountability-tiered anonymity
rollout has got, from each repository's remote `main` (git show / git grep;
no checkout, no writes except the append-only ledger). It first runs a
read-only `git fetch <remote> main`, which updates only the remote-tracking
ref; if that fails the run says STALE and does not report SMOKE-OK, so an
old picture is never mistaken for a current one.

The agent never recomputes this. Prints SMOKE-OK as the last line only if
every repository could be read; otherwise SMOKE-FAIL and a non-zero exit.

Usage:
  accountability_evidence.py [--root DIR] [--ledger FILE] [--no-ledger]

Env: none (paths derive from HOME unless overridden).
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

REPOS = {
    "protocol": "kotoba-lang/kotoba-protocol",
    "adr": "kotoba-lang/kotoba",
    "messenger": "kotoba-lang/kotobase-messenger",
    "server": "kotoba-lang/kotoba-server",
}

ADR_PATH = "docs/ADR-accountability-tiered-anonymity.md"
PROTO = "src/kotoba/protocol/"

# phase -> list of (label, repo, kind, arg, mode)
#   kind: file | grep (any non-doc, non-test file in the repo, case-insensitive)
#   mode: "-"  already part of the merged baseline
#         "B"  additive pure algebra the bot may build and merge itself
#              (gate class B: new src + new test files in kotoba-protocol)
#         "C"  needs the owner: cryptographic primitives, existing code, other
#              repos' source. The bot never builds these; it moves on.
PHASES = [
    ("R0", [("tier vocabulary + policy/profile schema", "protocol", "file", PROTO + "accountability.cljk", "-"),
            ("govern tier check", "protocol", "grep", "accountability/decide", "-")]),
    ("R1", [("pairwise DIDs", "protocol", "file", PROTO + "pairwise.cljk", "-"),
            ("policy composition", "protocol", "grep", "compose-policies", "-"),
            ("receipt visibility rule", "protocol", "grep", "receipt-visibility", "-"),
            ("messenger mailbox id", "messenger", "grep", "mailbox-id", "-"),
            ("server owner-only receipts", "server", "grep", "OwnerOnly", "-")]),
    ("R2", [("rate-limit token algebra", "protocol", "file", PROTO + "ratelimit.cljk", "-"),
            ("blind-signature issuer/verifier implementation", "server", "grep", "blind_rsa", "C"),
            ("gateway token check", "server", "grep", "ratelimit_token", "C")]),
    ("R3", [("credential predicate algebra", "protocol", "file", PROTO + "credential.cljk", "B"),
            ("context nullifier algebra", "protocol", "file", PROTO + "nullifier.cljk", "B"),
            ("BBS+ selective-disclosure primitive", "protocol", "grep", "bbs", "C")]),
    ("R4", [("RLN share-accounting algebra", "protocol", "file", PROTO + "rln.cljk", "B"),
            ("anonymous stake and forfeiture algebra", "protocol", "file", PROTO + "stake.cljk", "B"),
            ("RLN secret-recovery primitive", "protocol", "grep", "shamir", "C")]),
    ("R5", [("transparency log chain algebra", "protocol", "file", PROTO + "translog.cljk", "B"),
            ("threshold escrow opening", "protocol", "grep", "threshold-escrow-open", "C"),
            ("message franking", "messenger", "grep", "franking", "C")]),
]


def git(repo, *args):
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    return p.returncode, p.stdout


def main_ref(repo):
    rc, out = git(repo, "for-each-ref", "--format=%(refname:short)", "refs/remotes/*/main")
    refs = [r for r in out.split() if rc == 0]
    if not refs:
        return None
    return "origin/main" if "origin/main" in refs else sorted(refs)[0]


def fetch_main(repo, ref):
    """Refresh the remote-tracking ref. Returns an error string, or None."""
    remote = ref.split("/", 1)[0]
    try:
        p = subprocess.run(["git", "-C", repo, "fetch", "--quiet", remote, "main"],
                           capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return "fetch timed out"
    return None if p.returncode == 0 else (p.stderr.strip()[:120] or "fetch failed")


def has_file(repo, ref, path):
    return git(repo, "cat-file", "-e", f"{ref}:{path}")[0] == 0


def has_grep(repo, ref, needle):
    """Implementation evidence only: docs and tests mentioning a name do not
    count (a sentence in a doc is not an implementation)."""
    rc, _ = git(repo, "grep", "-qiF", needle, ref, "--", ".",
                ":(exclude)docs", ":(exclude)*.md", ":(exclude)test", ":(exclude)*/tests/*",
                ":(exclude)*_test.*")
    return rc == 0


def read_file(repo, ref, path):
    rc, out = git(repo, "show", f"{ref}:{path}")
    return out if rc == 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.expanduser("/Users/junkawasaki/github"))
    ap.add_argument("--ledger", default=os.path.join(
        os.environ.get("STEWARD_WORK") or os.path.expanduser("/Users/junkawasaki/.itonami/agent/profiles/accountability-steward/workspace"),
        "ledger.jsonl"))
    ap.add_argument("--no-ledger", action="store_true")
    a = ap.parse_args()

    ctx, problems = {}, []
    for key, path in REPOS.items():
        repo = os.path.join(a.root, path)
        ref = main_ref(repo) if os.path.isdir(repo) else None
        if ref is None:
            problems.append(f"cannot read {path} (no checkout or no remote main)")
            continue
        err = fetch_main(repo, ref)
        if err:
            problems.append(f"STALE {path}: {err}")
            print(f"repo {path}: could not refresh ({err}); using the last fetched state")
        ctx[key] = (repo, ref)
        rc, d = git(repo, "log", "-1", "--format=%cs", ref)
        print(f"repo {path:34s} {ref:16s} last-commit {d.strip()}")

    out = {"phases": {}, "drift": [], "adr": None}

    if "adr" in ctx:
        repo, ref = ctx["adr"]
        out["adr"] = has_file(repo, ref, ADR_PATH)
        print(f"adr  {ADR_PATH}: {'present' if out['adr'] else 'MISSING on main'}")

    queue_b, owner_c, awaiting = [], [], []
    print("--- phases")
    for name, checks in PHASES:
        done, missing = [], []
        for label, rk, kind, arg, mode in checks:
            if rk not in ctx:
                missing.append(f"{label} (repo unreadable)")
                continue
            repo, ref = ctx[rk]
            ok = has_file(repo, ref, arg) if kind == "file" else has_grep(repo, ref, arg)
            if ok:
                done.append(label)
            else:
                missing.append(label)
                {"B": queue_b, "C": owner_c}.get(mode, awaiting).append((name, label, arg if kind == "file" else None))
        status = "done" if not missing else ("partial" if done else "open")
        out["phases"][name] = {"status": status, "done": done, "missing": missing}
        print(f"{name}: {status}")
        for m in missing:
            print(f"     missing: {m}")

    print("--- drift")
    if "protocol" in ctx:
        repo, ref = ctx["protocol"]
        src = read_file(repo, ref, PROTO + "accountability.cljk") or ""
        m = re.search(r"\(def invariants(.*?)\n\n\(def ", src, re.S)
        declared = set(re.findall(r":l0/[a-z0-9-]+", m.group(1))) if m else set()
        rc, grep_out = git(repo, "grep", "-hoE", r":l0/[a-z0-9-]+", ref, "--", "src", "test")
        used = set(grep_out.split()) if rc == 0 else set()
        undeclared = sorted(used - declared)
        if not declared:
            out["drift"].append("L0 `invariants` map not found in accountability.cljk")
        for u in undeclared:
            out["drift"].append(f"{u} is referenced but not declared in `invariants`")
        rc, stale = git(repo, "grep", "-l", "kotoba-auth", ref, "--", "src", "docs")
        for line in stale.split():
            out["drift"].append(f"retired `kotoba-auth` still referenced in {line.split(':', 1)[-1]}")
    for d in out["drift"]:
        print(f"drift: {d}")
    if not out["drift"]:
        print("drift: none")

    order = ["R0", "R1", "R2", "R3", "R4", "R5"]
    nxt = next((p for p in order if out["phases"].get(p, {}).get("status") != "done"), None)
    print(f"--- next open phase: {nxt}")
    print("--- awaiting a merge to main (baseline items; the bot does not redo them)")
    for ph, label, _f in awaiting:
        print(f"awaiting: {ph} {label}")
    if not awaiting:
        print("awaiting: none")
    print("--- autonomous queue (class B: build it, open a bot PR, the gate merges it)")
    for ph, label, f_ in queue_b:
        print(f"queue-b: {ph} {label}  -> new file {f_} + test/kotoba/protocol/{os.path.basename(f_ or '').replace('.cljk', '_test.cljk')}")
    if not queue_b:
        print("queue-b: empty")
    print("--- owner-only (class C: the bot does not build these, and does not wait for them)")
    for ph, label, _f in owner_c:
        print(f"owner-c: {ph} {label}")
    work = os.environ.get("STEWARD_WORK") or os.path.expanduser("/Users/junkawasaki/.itonami/agent/profiles/accountability-steward/workspace")
    pause = os.path.join(work, "PAUSE")
    print(f"--- gate: PAUSE = {open(pause).read().strip() if os.path.exists(pause) else 'no'}")
    gl = os.path.join(work, "gate-ledger.jsonl")
    if os.path.exists(gl):
        for line in open(gl).read().splitlines()[-5:]:
            print(f"gate-event: {line[:200]}")

    row = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "adr_on_main": out["adr"],
           "phases": {k: v["status"] for k, v in out["phases"].items()},
           "drift": len(out["drift"]), "next": nxt, "queue_b": [q[1] for q in queue_b],
           "owner_c": [c[1] for c in owner_c], "problems": problems}
    seq = 0
    if not a.no_ledger:
        os.makedirs(os.path.dirname(a.ledger), exist_ok=True)
        if os.path.exists(a.ledger):
            with open(a.ledger) as f:
                seq = sum(1 for _ in f)
        with open(a.ledger, "a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        seq += 1
    print(f"ledger seq: {seq if not a.no_ledger else 'not written'}")

    if problems:
        for p in problems:
            print(f"SMOKE-FAIL: {p}")
        return 1
    print("SMOKE-OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
