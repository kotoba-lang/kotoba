#!/usr/bin/env python3 -I
"""Read-only dry run of the etzhayyim rename map (JUN-842, P0). Changes nothing anywhere.

  etzhayyim-rename-plan.py <map.json> <out-prefix> <org-dir-or-repo-dir>...

Each argument is a repository (has .git) or a directory of repositories. For each repository it runs
`git grep` over the checked-out HEAD commit (tracked text files only, not the working tree), classifies every
token containing the word by the first matching rule of the map, and writes <out-prefix>.json (full) and
<out-prefix>.md (summary). Tokens no rule claims are listed as `unclassified`: that list is how a gap in the
map shows up, so it is never dropped.
"""
import collections
import json
import os
import re
import subprocess
import sys

if len(sys.argv) < 4:
    sys.exit(__doc__)
mapfile, prefix, args = sys.argv[1], sys.argv[2], sys.argv[3:]
spec = json.load(open(mapfile, encoding="utf-8"))
rules = [(r, re.compile(r["match"], re.I)) for r in spec["rules"]]
tok = spec["token"]


def repos(paths):
    for p in paths:
        if os.path.exists(os.path.join(p, ".git")):
            yield p
        else:
            for d in sorted(os.listdir(p)):
                q = os.path.join(p, d)
                if os.path.exists(os.path.join(q, ".git")):
                    yield q


def git(repo, *a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, errors="replace")


by_rule = collections.defaultdict(lambda: {"tokens": 0, "distinct": collections.Counter(), "repos": collections.Counter()})
by_repo = collections.Counter()
files_total = 0
scanned = skipped = 0
for repo in repos(args):
    head = git(repo, "rev-parse", "HEAD")
    if head.returncode != 0:
        skipped += 1
        continue
    scanned += 1
    g = git(repo, "grep", "-I", "-h", "-o", "-i", "-E", tok, "HEAD", "--")
    if g.returncode not in (0, 1):
        skipped += 1
        continue
    for t in g.stdout.splitlines():
        rid = "unclassified"
        for r, rx in rules:
            if rx.search(t):
                rid = r["id"]
                break
        b = by_rule[rid]
        b["tokens"] += 1
        b["distinct"][t] += 1
        b["repos"][repo] += 1
        by_repo[repo] += 1
    files_total += len([l for l in git(repo, "grep", "-I", "-l", "-i", "etzhayyim", "HEAD", "--").stdout.splitlines() if l])

meta = {r["id"]: r for r in spec["rules"]}
out = {"scanned_repos": scanned, "skipped": skipped, "files_with_word": files_total, "rules": {}}
for rid, b in sorted(by_rule.items(), key=lambda kv: -kv[1]["tokens"]):
    r = meta.get(rid, {"kind": "NOT CLAIMED BY ANY RULE", "status": "decide", "to": None})
    ex = []
    for t, n in b["distinct"].most_common(6):
        new = None
        if r.get("to"):
            try:
                new = re.sub(r["match"], r["to"], t, flags=re.I)
            except Exception:
                new = "(preview failed)"
        ex.append({"token": t, "count": n, "preview": new})
    out["rules"][rid] = {"kind": r["kind"], "status": r["status"], "tokens": b["tokens"], "distinct": len(b["distinct"]),
                         "repos": len(b["repos"]), "examples": ex, "top_repos": b["repos"].most_common(8),
                         "blocker": r.get("blocker")}
out["top_repos"] = by_repo.most_common(25)
out["unclassified_top"] = by_rule["unclassified"]["distinct"].most_common(60) if "unclassified" in by_rule else []
json.dump(out, open(prefix + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

L = ["# etzhayyim rename: dry-run report (read-only)", "",
     f"Scanned {scanned} repositories (skipped {skipped}); {files_total} tracked text files contain the word. Source: `git grep` on each repository's local HEAD, so repositories whose checkout is behind their remote are counted at the older commit.", "",
     "| rule | kind | status | tokens | distinct | repos |", "|---|---|---|---:|---:|---:|"]
for rid, v in out["rules"].items():
    L.append(f"| {rid} | {v['kind']} | {v['status']} | {v['tokens']} | {v['distinct']} | {v['repos']} |")
L += ["", "## Examples (token → preview of the rewritten token)", ""]
for rid, v in out["rules"].items():
    L.append(f"### {rid} ({v['status']})" + (f" — blocked by: {v['blocker']}" if v.get("blocker") else ""))
    for e in v["examples"]:
        L.append(f"- `{e['token']}` ×{e['count']}" + (f" → `{e['preview']}`" if e["preview"] else ""))
    L.append("")
L += ["## Repositories with the most tokens", ""] + [f"- {os.path.relpath(r)}: {n}" for r, n in out["top_repos"][:25]]
if out["unclassified_top"]:
    L += ["", "## Unclaimed tokens (the map has a gap here)", ""] + [f"- `{t}` ×{n}" for t, n in out["unclassified_top"]]
open(prefix + ".md", "w", encoding="utf-8").write("\n".join(L) + "\n")
print("scanned", scanned, "skipped", skipped, "files", files_total, "tokens", sum(v["tokens"] for v in out["rules"].values()))
