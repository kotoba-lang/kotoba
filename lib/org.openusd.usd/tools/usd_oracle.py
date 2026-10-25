#!/usr/bin/env python3
"""Real Pixar USD oracle for kotoba-lang/org-openusd's usd.core tests (ADR-2607101525 D3).

This is not app code (kotoba's runtime priority order — kotoba wasm >
clojurewasm > cljs > nbb > jvm/bb — governs how *this repo's own* .cljc/
.kotoba is written, not how a third-party validation oracle is invoked):
it is a thin, deliberately dumb driver around the `pxr` Python bindings
(`pip install usd-core`), played the same role usdcat/usdchecker CLIs
would if they shipped standalone binaries for `usd-core` (they don't —
only the Python module does). Called as a subprocess from a JVM-only
Clojure test namespace (`usd.oracle-test`), never imported as a library.

Usage:
  usd_oracle.py compliance <path.usda>          # -> one "ERROR: "/"WARNING: " line per
                                                 #    finding (no output at all = clean)
  usd_oracle.py roundtrip  <path.usda>          # -> the file re-exported through Usd.Stage (stdout)
  usd_oracle.py convert    <in> <out>           # -> writes <out>, format inferred from its
                                                 #    extension (.usda/.usdc/.usdz) by Usd itself

`convert` is ADR-2607101525 M3's binary bridge: usd.core's own parser/emitter
stay ASCII-text-only (D1, deliberately no native .usdc/.usdz support) --
reading/writing binary goes through this real oracle instead of a from-
scratch crate-format implementation, exactly as D1 always intended once a
concrete need for it showed up.

No JSON/extra deps on either side of the pipe on purpose (matches usd.core's
own zero-external-dependency ethos) — line-prefixed plain text is enough for
what usd.oracle-test needs to assert.
"""
import sys


def compliance(path):
    from pxr import UsdUtils

    checker = UsdUtils.ComplianceChecker()
    checker.CheckCompliance(path)
    for e in checker.GetErrors():
        print(f"ERROR: {e}")
    for w in checker.GetWarnings():
        print(f"WARNING: {w}")


def roundtrip(path):
    from pxr import Usd

    stage = Usd.Stage.Open(path)
    sys.stdout.write(stage.GetRootLayer().ExportToString())


def convert(in_path, out_path):
    from pxr import Usd

    stage = Usd.Stage.Open(in_path)
    if not stage.GetRootLayer().Export(out_path):
        sys.stderr.write(f"convert: Usd.Stage export to {out_path!r} failed\n")
        sys.exit(1)


COMMANDS = {"compliance": compliance, "roundtrip": roundtrip, "convert": convert}
ARITY = {"compliance": 1, "roundtrip": 1, "convert": 2}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    args = sys.argv[2:]
    if cmd not in COMMANDS or len(args) != ARITY[cmd]:
        sys.stderr.write(
            f"usage: {sys.argv[0]} compliance <path.usda> | "
            f"roundtrip <path.usda> | convert <in> <out>\n"
        )
        sys.exit(2)
    COMMANDS[cmd](*args)
