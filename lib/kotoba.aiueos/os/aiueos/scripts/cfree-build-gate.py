#!/usr/bin/env python3
"""cFreeRoute gate: measure the toolchain, do not trust the claim (JUN-31).

The acceptance chain's open item (JUN-64) is that `os/aiueos/kernel/*.c` is
still compiled by a C compiler (`zig cc`).  This gate makes "C-free" a
measured property of a build RUN instead of an assertion in a receipt:

  run    - execute a build command with every foreign compiler on PATH
           replaced by a recording shim (zig cc / zig c++ / cc / gcc /
           clang / c++ / g++ / zig <sub> that compiles).  Every invocation
           appends one JSON line to the invocation log before the real tool
           runs, so the count cannot be lost to shell-echo discipline.
  report - tally the log (and optionally scan an output tree for foreign
           artifacts) and emit the `cFreeRoute` block the chain receipts
           bind: cCompilerInvocations, zigCcInvocations, cUnitsCompiled,
           verdict PASS only when all are zero.

Python here is build orchestration only (the constraint's allowed use); it
is not on any accepted runtime path.

usage:
  cfree-build-gate.py run --log tool-invocations.jsonl -- <build command...>
  cfree-build-gate.py report --log tool-invocations.jsonl [--tree DIR] [--out receipt.json]
"""

import json
import os
import shutil
import subprocess
import sys

# Tools whose invocation means "a C/C++ compilation happened".
CC_TOOLS = ("cc", "gcc", "clang", "c++", "g++", "clang++")
# `zig` subcommands that compile C/C++ (linking `zig ld.lld` is counted
# separately: a linker is not a C compiler, and the gate names both).
ZIG_COMPILE_SUBS = ("cc", "c++")
# Foreign artifacts in an image output tree (the loader smoke's floor).
FOREIGN_SUFFIXES = (".c", ".S", ".s", ".o", ".a", ".so")

SHIM_TEMPLATE = """#!/bin/sh
{
  printf '{"tool":"@TOOL@","argv":['
  sep=''
  for a in "$@"; do
    esc=$(printf '%s' "$a" | sed 's/\\\\/\\\\\\\\/g; s/"/\\\\"/g')
    printf '%s"%s"' "$sep" "$esc"
    sep=','
  done
  printf ']}\\n'
} >> "$AIUEOS_CFREE_LOG"
exec "@REAL@" "$@"
"""


def _shim_script(tool: str, real: str) -> str:
    return SHIM_TEMPLATE.replace("@TOOL@", tool).replace("@REAL@", real)


def cmd_run(argv):
    if "--" not in argv:
        sys.exit("usage: run --log LOG -- <build command...>")
    dash = argv.index("--")
    pre, build_cmd = argv[:dash], argv[dash + 1:]
    log = None
    if "--log" in pre:
        log = pre[pre.index("--log") + 1]
    if not log or not build_cmd:
        sys.exit("usage: run --log LOG -- <build command...>")
    log = os.path.abspath(log)
    os.makedirs(os.path.dirname(log) or ".", exist_ok=True)

    shim_dir = os.path.join(os.environ.get("TMPDIR", "/tmp"), "cfree-gate-shim")
    shutil.rmtree(shim_dir, ignore_errors=True)
    os.makedirs(shim_dir)
    wrapped = []
    for tool in ("zig",) + CC_TOOLS:
        real = shutil.which(tool)
        if real is None:
            continue
        path = os.path.join(shim_dir, tool)
        with open(path, "w") as fh:
            fh.write(_shim_script(tool, real))
        os.chmod(path, 0o755)
        wrapped.append(tool)

    env = dict(os.environ)
    env["AIUEOS_CFREE_LOG"] = log
    env["PATH"] = shim_dir + os.pathsep + env.get("PATH", "")
    open(log, "w").close()
    print("cfree-gate: wrapped tools: %s (log %s)" % (",".join(wrapped), log))
    rc = subprocess.call(build_cmd, env=env)
    print("cfree-gate: build exit %d" % rc)
    return rc


def _tally(log):
    inv = []
    with open(log) as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    inv.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    zig_cc, zig_link, cc_tools, units = 0, 0, 0, set()
    for e in inv:
        tool = os.path.basename(e.get("tool", ""))
        argv = e.get("argv", [])
        if tool == "zig":
            sub = argv[0] if argv else ""
            if sub in ZIG_COMPILE_SUBS:
                zig_cc += 1
                for a in argv:
                    if a.endswith((".c", ".S", ".s")):
                        units.add(a)
            elif "ld" in sub or sub in ("build-lib", "build-exe"):
                zig_link += 1
        elif tool in CC_TOOLS:
            cc_tools += 1
            for a in argv:
                if a.endswith((".c", ".S", ".s")):
                    units.add(a)
    return {
        "totalToolInvocations": len(inv),
        "zigCcInvocations": zig_cc,
        "cCompilerInvocations": cc_tools + zig_cc,
        "zigLinkerInvocations": zig_link,
        "cUnitsCompiled": sorted(units),
        "cUnitCount": len(units),
    }


def cmd_report(argv):
    log = argv[argv.index("--log") + 1] if "--log" in argv else None
    if not log:
        sys.exit("usage: report --log LOG [--tree DIR] [--out receipt.json]")
    r = _tally(log)
    if "--tree" in argv:
        tree = argv[argv.index("--tree") + 1]
        found = []
        for root, _dirs, files in os.walk(tree):
            for f in files:
                if f.endswith(FOREIGN_SUFFIXES):
                    found.append(os.path.relpath(os.path.join(root, f), tree))
        r["foreignArtifactsInTree"] = sorted(found)
    r["verdict"] = "PASS" if r["cCompilerInvocations"] == 0 and \
        not r.get("foreignArtifactsInTree") else "FAIL"
    r["gate"] = "aiueos-cfree-build-gate/v1"
    text = json.dumps(r, indent=2, sort_keys=True)
    if "--out" in argv:
        with open(argv[argv.index("--out") + 1], "w") as fh:
            fh.write(text + "\n")
    print(text)
    return 0 if r["verdict"] == "PASS" else 1


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "run":
        sys.exit(cmd_run(sys.argv[2:]))
    if sys.argv[1] == "report":
        sys.exit(cmd_report(sys.argv[2:]))
    sys.exit(__doc__)


if __name__ == "__main__":
    main()
