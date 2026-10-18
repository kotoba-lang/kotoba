#!/usr/bin/env python3
"""growth_gate.py - the mechanical gate that stands in for human judgment.

accountability-steward grows without a person approving each step. What
replaces the person is this gate: a PR is merged by the bot only if every
rule below holds, and the rules are code, not prose. Anything the gate
cannot verify mechanically is class C and is never merged by the bot; the
bot moves on to the next independent item instead of waiting.

  class A  docs / markdown only, or comment-only lines in source
  class B  ADDITIVE pure-algebra: new src/ + new test/ files in
           kotoba-protocol (plus test-runner registration and docs).
           Needs passing tests, at least one new test, and a soak period
           with no human hold.
  class C  anything else (crypto primitives, existing code, other repos'
           source, config, CI, the bot's own profile). Never auto-merged.

This file is part of the charter: the bot's PRs are never allowed to touch
the profile that contains it (see PROTECTED_REPO_PATHS), and the gate checks
its targets by allowlist.

Usage:
  growth_gate.py check <target> <pr>          decide, print, change nothing
  growth_gate.py sweep [--merge]              every open bot PR; merge only with --merge
  growth_gate.py status                       pause state, budget, recent outcomes

Fails closed: any doubt is HOLD or DENY, never ALLOW.
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HOME = os.path.expanduser("~")
WORK = os.environ.get("STEWARD_WORK") or os.path.join(HOME, ".itonami/agent/profiles/accountability-steward/workspace")
LEDGER = os.path.join(WORK, "gate-ledger.jsonl")
PAUSE = os.path.join(WORK, "PAUSE")
MIRRORS = os.path.join(WORK, "mirrors")

BOT_BRANCH = re.compile(r"^bot/accountability-steward-[0-9A-Za-z._-]+$")

# target key -> repo, allowed classes, test command (None = no tests => no B)
TARGETS = {
    "protocol": {"repo": "kotoba-lang/kotoba-protocol", "classes": "AB",
                 "test": ["kbb", "--backend", "sci", "--classpath", "src:test", "test/run_portable.cljk"]},
    "adr": {"repo": "kotoba-lang/kotoba", "classes": "A", "test": None},
    "messenger": {"repo": "kotoba-lang/kotobase-messenger", "classes": "A", "test": None},
    "server": {"repo": "kotoba-lang/kotoba-server", "classes": "A", "test": None},
}

DOC_RE = re.compile(r"(^docs/.*|.*\.md)$")
COMMENT_EXT = {".cljk": ";", ".cljc": ";", ".clj": ";", ".cljs": ";", ".edn": ";", ".rs": "//", ".py": "#"}

B_SRC = re.compile(r"^src/kotoba/protocol/[a-z0-9_]+\.cljk$")
B_TEST = re.compile(r"^test/kotoba/protocol/[a-z0-9_]+_test\.cljk$")
B_RUNNER = "test/run_portable.cljk"
RUNNER_LINE = re.compile(r"^\s*(\(t/run-tests\s+)?'\[?kotoba\.protocol\.[a-z0-9-]+-test\]?\)?\s*$|^\s*$")

# Added lines in class B must not look like cryptographic or secret handling.
# A tripwire, not a proof: real crypto is class C by policy, whatever this says.
DENY_ADDED = re.compile(
    r"crypto\.subtle|js/crypto|javax?\.(security|crypto)|MessageDigest|SecureRandom|"
    r"getRandomValues|urandom|\.env\b|API_?KEY|BEGIN [A-Z ]*PRIVATE|password", re.I)

# L0 forms that may never change in any merged PR. (file, def name)
PINNED_FORMS = [
    ("src/kotoba/protocol/accountability.cljk", n) for n in
    ("version", "l0-version", "tier-order", "tiers", "externalities", "disclosure-floor",
     "invariants", "l0-param-keys", "owner-only-receipt-fields")
] + [
    ("src/kotoba/protocol/ratelimit.cljk", "linkable-fields-allowed"),
    ("src/kotoba/protocol/pairwise.cljk", "hkdf-salt"),
    ("src/kotoba/protocol/pairwise.cljk", "seed-length"),
]

PROTECTED_REPO_PATHS = ("hermes/profiles/accountability-steward/", "CHARTER.md")

SOAK_HOURS = {"A": 0, "B": 24}
MAX_CHANGED_LINES = 400
MAX_MERGES_PER_REPO_PER_DAY = 1


# ── pure core (unit-tested; no I/O) ─────────────────────────────────────────

def parse_diff(patch):
    """Unified diff -> [{path, status, added[], removed[]}]."""
    files, cur = [], None
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/(.*) b/(.*)$", line)
            if not m:
                # An unreadable header must not be skipped silently: record it
                # as an opaque path so classification sends it to class C.
                cur = {"path": "<unparsed:" + line[:60] + ">", "status": "M", "added": [], "removed": []}
            else:
                cur = {"path": m.group(2), "status": "M", "added": [], "removed": []}
            files.append(cur)
        elif cur is None:
            continue
        elif line.startswith("new file mode"):
            cur["status"] = "A"
        elif line.startswith("deleted file mode"):
            cur["status"] = "D"
        elif line.startswith("rename from"):
            cur["status"] = "R"
        elif line.startswith("+++") or line.startswith("---"):
            continue
        elif line.startswith("+"):
            cur["added"].append(line[1:])
        elif line.startswith("-"):
            cur["removed"].append(line[1:])
    return files


def _comment_only(f):
    ext = os.path.splitext(f["path"])[1]
    mark = COMMENT_EXT.get(ext)
    if not mark or f["status"] != "M":
        return False
    return all(l.strip() == "" or l.lstrip().startswith(mark)
               for l in f["added"] + f["removed"])


def classify(files):
    """-> (class, reasons). The strictest class any file forces wins."""
    reasons = []
    for f in files:
        if any(f["path"].startswith(p) or f["path"] == p for p in PROTECTED_REPO_PATHS):
            return "C", [f"touches the charter/profile: {f['path']}"]
    if not files:
        return "C", ["empty diff"]
    if all(DOC_RE.match(f["path"]) or _comment_only(f) for f in files):
        return "A", reasons
    new_tests = [f for f in files if B_TEST.match(f["path"]) and f["status"] == "A"]
    ok = True
    for f in files:
        p = f["path"]
        if B_SRC.match(p) and f["status"] == "A":
            continue
        if B_TEST.match(p) and f["status"] == "A":
            continue
        if p == B_RUNNER and all(RUNNER_LINE.match(l) for l in f["added"] + f["removed"]):
            continue
        if DOC_RE.match(p):
            continue
        ok = False
        reasons.append(f"not additive algebra: {f['status']} {p}")
    if ok and new_tests and any(B_SRC.match(f["path"]) for f in files):
        return "B", reasons
    if ok:
        reasons.append("class B needs a new src file and a new test file")
    return "C", reasons


def _form(text, name):
    """Text of the top-level `(def name ...)` form, by balanced scan. None if absent."""
    m = re.search(r"^\(def\s+%s[\s\n)]" % re.escape(name), text, re.M)
    if not m:
        return None
    i, depth, n = m.start(), 0, len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 2 if text[i] == "\\" else 1
        elif c == ";":
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return re.sub(r"\s+", " ", text[m.start():i + 1])
        i += 1
    return None


def pinned_changes(read_base, read_head):
    """Names of pinned L0 forms whose text differs between base and head."""
    changed = []
    for path, name in PINNED_FORMS:
        b, h = read_base(path), read_head(path)
        if b is None and h is None:
            continue
        if (None if b is None else _form(b, name)) != (None if h is None else _form(h, name)):
            changed.append(f"{path}:{name}")
    return changed


def decide(info):
    """info -> {verdict: ALLOW|HOLD|DENY, class, reasons[]}. Fail closed."""
    reasons = []
    t = TARGETS.get(info["target"])
    if t is None:
        return {"verdict": "DENY", "class": "C", "reasons": ["unknown target"]}
    if not BOT_BRANCH.match(info.get("branch", "")):
        return {"verdict": "DENY", "class": "C", "reasons": ["not a bot/accountability-steward-* branch"]}
    klass, why = classify(info["files"])
    if klass == "C" or klass not in t["classes"]:
        return {"verdict": "DENY", "class": klass,
                "reasons": why or [f"class {klass} is not allowed for target {info['target']}"]}
    if info.get("paused"):
        reasons.append("PAUSE is set")
    if info.get("draft"):
        reasons.append("draft")
    if info.get("changes_requested"):
        reasons.append("changes requested")
    if any(l.lower() in ("hold", "do-not-merge", "wip") for l in info.get("labels", [])):
        reasons.append("human hold label")
    if klass == "B" and not (info.get("read_base") and info.get("read_head")):
        reasons.append("cannot read base/head to check the pinned L0 forms")
    pins = pinned_changes(info.get("read_base") or (lambda _p: None), info.get("read_head") or (lambda _p: None))
    if pins:
        return {"verdict": "DENY", "class": "C", "reasons": ["changes pinned L0 form(s): " + ", ".join(pins)]}
    if klass == "B":
        hits = [l for f in info["files"] for l in f["added"] if DENY_ADDED.search(l)]
        if hits:
            return {"verdict": "DENY", "class": "C", "reasons": [f"crypto/secret tripwire: {hits[0].strip()[:80]}"]}
    lines = sum(len(f["added"]) + len(f["removed"]) for f in info["files"])
    if lines > MAX_CHANGED_LINES:
        return {"verdict": "DENY", "class": "C", "reasons": [f"{lines} changed lines > {MAX_CHANGED_LINES}"]}
    if klass == "B":
        tr = info.get("tests")
        if not tr:
            reasons.append("tests not run")
        elif not tr["ok"]:
            return {"verdict": "DENY", "class": klass, "reasons": ["tests fail: " + tr.get("detail", "")]}
        elif tr["head_n"] <= tr["base_n"]:
            return {"verdict": "DENY", "class": klass,
                    "reasons": [f"no new tests ({tr['base_n']} -> {tr['head_n']})"]}
    if info.get("age_hours", 0) < SOAK_HOURS[klass]:
        reasons.append(f"soak {info.get('age_hours', 0):.1f}h < {SOAK_HOURS[klass]}h since last commit")
    if info.get("merged_24h", 0) >= MAX_MERGES_PER_REPO_PER_DAY:
        reasons.append("daily merge budget used")
    return {"verdict": "HOLD" if reasons else "ALLOW", "class": klass, "reasons": reasons}


# ── plumbing ────────────────────────────────────────────────────────────────

def run(cmd, cwd=None, timeout=600):
    env = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout, env=env)


def gh_json(args):
    p = run(["gh", *args])
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:200] or "gh failed")
    return json.loads(p.stdout)


def ledger_rows():
    if not os.path.exists(LEDGER):
        return []
    rows = []
    for l in open(LEDGER):
        try:
            rows.append(json.loads(l))
        except ValueError:
            pass
    return rows


def log(row):
    os.makedirs(WORK, exist_ok=True)
    row["ts"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    with open(LEDGER, "a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def merged_24h(repo):
    cut = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
    return sum(1 for r in ledger_rows() if r.get("event") == "merged" and r.get("repo") == repo
               and datetime.datetime.fromisoformat(r["ts"]) > cut)


def mirror(repo):
    path = os.path.join(MIRRORS, repo.replace("/", "__") + ".git")
    os.makedirs(MIRRORS, exist_ok=True)
    if not os.path.isdir(path):
        p = run(["gh", "repo", "clone", repo, path, "--", "--bare"])
        if p.returncode != 0:
            raise RuntimeError("clone failed: " + p.stderr.strip()[:200])
    return path


def run_suite(cmd, ref, mirror_path):
    tmp = tempfile.mkdtemp(prefix="steward-")
    try:
        p = run(["git", "-C", mirror_path, "worktree", "add", "--detach", tmp, ref])
        if p.returncode != 0:
            return None, p.stderr.strip()[:200]
        q = run(cmd, cwd=tmp, timeout=900)
        m = re.search(r"Ran (\d+) tests containing (\d+) assertions\.\s*(\d+) failures, (\d+) errors", q.stdout + q.stderr)
        if not m:
            return None, "no test summary in output"
        return {"n": int(m.group(1)), "fail": int(m.group(3)) + int(m.group(4))}, ""
    finally:
        run(["git", "-C", mirror_path, "worktree", "remove", "--force", tmp])
        shutil.rmtree(tmp, ignore_errors=True)


def gather(target, number):
    t = TARGETS[target]
    repo = t["repo"]
    pr = gh_json(["pr", "view", str(number), "--repo", repo, "--json",
                  "headRefName,headRefOid,baseRefName,isDraft,labels,reviewDecision,state,commits"])
    if pr["state"] != "OPEN":
        return None
    patch = run(["gh", "pr", "diff", str(number), "--repo", repo]).stdout
    files = parse_diff(patch)
    last = pr["commits"][-1]["committedDate"] if pr.get("commits") else None
    age = 0.0
    if last:
        age = (datetime.datetime.now(datetime.timezone.utc)
               - datetime.datetime.fromisoformat(last.replace("Z", "+00:00"))).total_seconds() / 3600
    info = {"target": target, "repo": repo, "number": number, "branch": pr["headRefName"],
            "head_sha": pr["headRefOid"], "files": files, "draft": pr["isDraft"],
            "labels": [l["name"] for l in pr.get("labels", [])],
            "changes_requested": pr.get("reviewDecision") == "CHANGES_REQUESTED",
            "age_hours": age, "paused": os.path.exists(PAUSE), "merged_24h": merged_24h(repo)}
    klass, _ = classify(files)
    if klass == "B" and t["test"]:
        mp = mirror(repo)
        run(["git", "-C", mp, "fetch", "origin", f"+refs/heads/{pr['baseRefName']}:refs/heads/{pr['baseRefName']}",
             f"+refs/pull/{number}/head:refs/pull/{number}/head"])
        info["read_head"] = lambda p, mp=mp, n=number: _show(mp, f"refs/pull/{n}/head", p)
        info["read_base"] = lambda p, mp=mp, b=pr["baseRefName"]: _show(mp, f"refs/heads/{b}", p)
        h, eh = run_suite(t["test"], f"refs/pull/{number}/head", mp)
        b, eb = run_suite(t["test"], f"refs/heads/{pr['baseRefName']}", mp)
        if h and b:
            info["tests"] = {"ok": h["fail"] == 0, "head_n": h["n"], "base_n": b["n"],
                             "detail": f"{h['fail']} failing"}
        else:
            info["tests"] = None
            print(f"  tests could not run: head={eh or 'ok'} base={eb or 'ok'}")
    return info


def _show(mp, ref, path):
    p = run(["git", "-C", mp, "show", f"{ref}:{path}"])
    return p.stdout if p.returncode == 0 else None


def check_reverts():
    """A bot-merged commit that was later reverted pauses all merging."""
    for r in ledger_rows():
        if r.get("event") != "merged" or not r.get("sha"):
            continue
        try:
            mp = mirror(r["repo"])
            run(["git", "-C", mp, "fetch", "origin", "+refs/heads/*:refs/heads/*"])
            q = run(["git", "-C", mp, "log", "--all", "--oneline", f"--grep=This reverts commit {r['sha']}"])
        except Exception:
            continue
        if q.stdout.strip():
            os.makedirs(WORK, exist_ok=True)
            open(PAUSE, "w").write(f"revert of {r['repo']}@{r['sha']} detected {q.stdout.strip()[:80]}\n")
            return f"{r['repo']}@{r['sha'][:9]}"
    return None


def cmd_check(target, number, merge=False):
    info = gather(target, number)
    if info is None:
        print(f"{target}#{number}: not open")
        return None
    d = decide(info)
    print(f"{target}#{number} {info['branch']}: {d['verdict']} class={d['class']} "
          f"{'; '.join(d['reasons'])}")
    if d["verdict"] == "ALLOW" and merge:
        p = run(["gh", "pr", "merge", str(number), "--repo", info["repo"], "--squash",
                 "--match-head-commit", info["head_sha"]])
        if p.returncode == 0:
            log({"event": "merged", "repo": info["repo"], "pr": number, "class": d["class"],
                 "sha": info["head_sha"]})
            print(f"  MERGED {info['repo']}#{number}")
        else:
            log({"event": "merge-failed", "repo": info["repo"], "pr": number, "error": p.stderr.strip()[:160]})
            print(f"  MERGE-FAILED {p.stderr.strip()[:120]}")
    elif d["verdict"] == "DENY":
        log({"event": "denied", "repo": info["repo"], "pr": number, "reasons": d["reasons"]})
    return d


def cmd_sweep(merge):
    rev = check_reverts()
    if rev:
        print(f"PAUSED: a bot merge was reverted ({rev}); delete {PAUSE} to resume")
    n = 0
    for target, t in TARGETS.items():
        try:
            prs = gh_json(["pr", "list", "--repo", t["repo"], "--state", "open", "--json", "number,headRefName"])
        except Exception as e:
            print(f"{target}: cannot list PRs ({e})")
            continue
        for pr in prs:
            if BOT_BRANCH.match(pr["headRefName"]):
                n += 1
                try:
                    cmd_check(target, pr["number"], merge=merge and not os.path.exists(PAUSE))
                except Exception as e:
                    print(f"{target}#{pr['number']}: HOLD (gate error: {e})")
    print(f"swept {n} bot PR(s)")


def cmd_status():
    print("PAUSE:", open(PAUSE).read().strip() if os.path.exists(PAUSE) else "no")
    rows = ledger_rows()
    for r in rows[-8:]:
        print(" ", json.dumps(r, ensure_ascii=False))
    for t in TARGETS.values():
        print(f"{t['repo']}: merged in last 24h = {merged_24h(t['repo'])}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["check"] and len(a) == 3:
        cmd_check(a[1], int(a[2]))
    elif a[:1] == ["sweep"]:
        cmd_sweep("--merge" in a)
    elif a[:1] == ["status"]:
        cmd_status()
    else:
        print(__doc__)
        sys.exit(2)
