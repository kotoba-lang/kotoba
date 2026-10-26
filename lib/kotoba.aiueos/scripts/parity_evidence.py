#!/usr/bin/env python3
"""linux-parity evidence: amu/aiueos の Linux 並 parity gap を測る（判断を含まない）。

出力: AIUEOS-PARITY.md の gap 表候補と実測値。失敗時は REFUSED バナー + exit 0。
"""
import json
import os
import subprocess
import sys

WORKTREE_DEFAULT = os.path.expanduser("~/.itonami/worktrees/linux-parity")
LEAF = {"amu": "orgs/kotoba-lang/amu", "aiueos": "orgs/kotoba-lang/aiueos"}


def run(cmd, cwd=None, timeout=60):
    try:
        r = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, r.stdout, r.stderr
    except Exception as e:  # noqa: BLE001
        return 1, "", str(e)


def refused(reason):
    print("REFUSED — measurement unavailable, do not claim completion.")
    print(f"reason: {reason}")
    return 0


def main():
    wt = sys.argv[1] if len(sys.argv) > 1 else WORKTREE_DEFAULT
    if not os.path.isdir(wt):
        return refused(f"worktree not found: {wt}")
    rc, out, err = run(["git", "status", "--porcelain"], cwd=wt)
    if rc != 0:
        return refused(f"git status failed in {wt}: {err.strip()[:200]}")
    if out.strip():
        return refused(f"worktree dirty ({len(out.splitlines())} paths) — refusing to measure")

    report = {}
    for leaf in LEAF.values():
        path = os.path.join(wt, leaf)
        if not os.path.isdir(path):
            return refused(f"checkout missing: {path}")
        rc, out, err = run(["git", "status", "--porcelain"], cwd=path)
        if rc != 0:
            return refused(f"git status failed in {path}: {err.strip()[:200]}")
        if out.strip():
            return refused(
                f"leaf checkout dirty ({leaf}, {len(out.splitlines())} paths) — refusing to measure"
            )
        entry = {}
        # 1) テストの存在と件数（観測量）
        rc, out, _ = run(["git", "ls-files", "test/", "fuzz/"], cwd=path)
        entry["test_files"] = len(out.splitlines()) if rc == 0 else None
        # 2) coverage 台帳の有無（aiueos docs/coverage.edn / amu docs/performance.md）
        for cand in ("docs/coverage.edn", "docs/performance.md", "qualification"):
            entry[f"has:{cand}"] = os.path.exists(os.path.join(path, cand))
        # 3) 直近 CI 状態（gh が使える場合のみ、失敗は記録するだけ）
        rc, out, _ = run(
            ["gh", "run", "list", "--limit", "1", "--json", "conclusion,headSha"],
            cwd=path, timeout=30,
        )
        if rc == 0 and out.strip():
            try:
                runs = json.loads(out)
                entry["last_ci"] = runs[0].get("conclusion") if runs else "no-runs"
            except Exception:  # noqa: BLE001
                entry["last_ci"] = "unparseable"
        else:
            entry["last_ci"] = "unavailable"
        # 4) 未閉じ issue 数（amu#611/#612/#614, aiueos#148/#149 の親類）
        rc, out, _ = run(
            ["gh", "issue", "list", "--state", "open", "--limit", "200", "--json", "number"],
            cwd=path, timeout=30,
        )
        if rc == 0 and out.strip():
            try:
                issues = json.loads(out)
                entry["open_issues"] = len(issues) if isinstance(issues, list) else None
            except Exception:  # noqa: BLE001
                entry["open_issues"] = None
        else:
            entry["open_issues"] = None
        report[leaf] = entry

    print(json.dumps({"worktree": wt, "dirty": False, "report": report}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
