#!/usr/bin/env python3
"""Verify the kotoba_check memo (iteration 20), without Hermes, in BOTH directions.

    A  first check of a file runs amu and is not a memo hit (but is keyed)
    B  the same file again is a memo hit with the same verdict
    C  a comment / whitespace edit is still a hit (identity is structural)
    D  a body edit is a miss (the file closure changed)
    E  fresh=true bypasses the memo
    F  without an index the check still runs and says why it was NOT keyed
       (could-not-key must never look like keyed)

    KOTOBA_WORKSPACE is not needed: the probe builds its own tiny workspace.
    Needs: kbb (or symbol-index) on PATH, amu at KOTOBA_AMU or
    <superproject>/orgs/kotoba-lang/amu/bin/amu (KOTOBA_SUPERPROJECT).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))


def _import_tools():
    # tools.py imports `tools.registry` from the Hermes tree; stand in for it.
    reg = types.ModuleType("tools.registry")
    reg.tool_error = lambda msg: {"error": msg}
    reg.tool_result = lambda payload: payload
    pkg = types.ModuleType("tools")
    pkg.registry = reg
    sys.modules["tools"] = pkg
    sys.modules["tools.registry"] = reg
    sys.path.insert(0, HERE)
    import importlib.util
    spec = importlib.util.spec_from_file_location("kotoba_plugin_tools", os.path.join(HERE, "tools.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    sp = os.path.expanduser(os.environ.get("KOTOBA_SUPERPROJECT") or "~/github/com-junkawasaki")
    amu = os.environ.get("KOTOBA_AMU") or os.path.join(sp, "orgs/kotoba-lang/amu/bin/amu")
    script = os.path.join(sp, "orgs/kotoba-lang/symbol-index/scripts/symbol-index.cljk")
    kbb = shutil.which("kbb")
    if not (os.path.exists(amu) and kbb and os.path.exists(script)):
        print("REFUSED: need amu, kbb and orgs/kotoba-lang/symbol-index (set KOTOBA_SUPERPROJECT / KOTOBA_AMU)")
        return 2

    ws = tempfile.mkdtemp(prefix="kotoba-check-memo-")
    home = tempfile.mkdtemp(prefix="kotoba-check-memo-home-")
    os.environ["KOTOBA_WORKSPACE"] = ws
    os.environ["KOTOBA_AMU"] = amu
    os.environ["KOTOBA_CHECK_MEMO"] = os.path.join(home, "memo.json")
    script = os.path.expanduser(os.environ.get("KOTOBA_SYMBOL_INDEX") or script)  # file mode needs symbol-index iteration 20
    os.environ["KOTOBA_SYMBOL_INDEX"] = script
    os.environ["HOME"] = home  # symbol-index's roots registry stays out of the real HOME
    src = os.path.join(ws, "src", "hello.kotoba")
    os.makedirs(os.path.dirname(src))

    def write(body):
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(body)

    def build():
        subprocess.run([kbb, "--backend", "sci", script, "build", "--full"], cwd=ws, capture_output=True, text=True, timeout=120, check=True)

    tools = _import_tools()
    checks = []

    write("(ns hello)\n\n(defn add [a b] (+ a b))\n\n(defn main [] (add 40 2))\n")
    build()
    t0 = time.time(); r1 = tools.run_check(ws, src); t_miss = time.time() - t0
    checks.append(("A first check runs amu (exit 0), not a memo hit", r1.get("exit") == 0 and r1["memo"]["hit"] is False))
    checks.append(("A …and is keyed by the file closure", bool(r1["memo"].get("key"))))

    t0 = time.time(); r2 = tools.run_check(ws, src); t_hit = time.time() - t0
    checks.append(("B the same file is a memo hit with the same verdict", r2["memo"]["hit"] is True and r2.get("exit") == 0 and r2["memo"]["key"] == r1["memo"]["key"]))

    write("(ns hello)\n;; a comment\n(defn add [a b]\n  (+ a b))\n\n(defn main [] (add 40 2))\n")
    build()
    r3 = tools.run_check(ws, src)
    checks.append(("C a comment / whitespace edit is still a hit (structural identity)", r3["memo"]["hit"] is True and r3["memo"]["key"] == r1["memo"]["key"]))

    write("(ns hello)\n\n(defn add [a b] (+ a b 1))\n\n(defn main [] (add 40 2))\n")
    build()
    r4 = tools.run_check(ws, src)
    checks.append(("D a body edit is a miss with a new key", r4["memo"]["hit"] is False and r4["memo"].get("key") not in (None, r1["memo"].get("key"))))

    r5 = tools.run_check(ws, src, fresh=True)
    checks.append(("E fresh=true bypasses the memo", r5["memo"]["hit"] is False and r5.get("exit") == 0))

    shutil.rmtree(os.path.join(ws, ".kotoba-cache"))
    r6 = tools.run_check(ws, src)
    checks.append(("F without an index the check still runs…", r6.get("exit") == 0))
    checks.append(("F …and says it was NOT keyed (never a silent hit)", r6["memo"]["hit"] is False and "not_keyed" in r6["memo"]))

    ok = True
    for label, passed in checks:
        print(("  ok   " if passed else "  FAIL ") + label)
        ok = ok and passed
    print(f"  measured: miss {t_miss:.2f}s (amu check) vs hit {t_hit:.2f}s (closure + memo)")
    print("probe-memo OK — a served verdict always says so; an unkeyed check never pretends" if ok else "probe-memo FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
