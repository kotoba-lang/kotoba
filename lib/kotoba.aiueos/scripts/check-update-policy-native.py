#!/usr/bin/env python3 -I
"""Run the update-policy test natively and prove it fails for each mutant (JUN-813).

usage: check-update-policy-native.py AMU_HOME

Runs test/aiueos/update_policy_test.kotoba against os/aiueos/kotoba/aiueos/update_policy.kotoba
with `AMU_HOME/bin/amu run ENTRY --source-lock LOCK` (a KSL2 lock over the two files, as
session-page.py writes for the session page). The unmodified policy must print main's value 0.
Each mutant below changes one rule in a temporary copy; the test must then print a nonzero
value, so a test that cannot tell the rule apart fails this script. Host-side, one-shot: it
builds nothing into an image and is not wired into a workflow (the Amu build it needs is
fetched only by the native lanes). Prints the Amu binary's SHA-256 so a run can be recorded.
"""
import hashlib
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
POLICY = ROOT / "os/aiueos/kotoba/aiueos/update_policy.kotoba"
TEST = ROOT / "test/aiueos/update_policy_test.kotoba"

# (name, anchor in update_policy.kotoba, replacement). Each anchor must occur exactly once.
MUTANTS = [
    ("notify raises a download prompt", "(>= mode 2) (= stage 1) ok has-endpoint))", "(>= mode 1) (= stage 1) ok has-endpoint))"),
    ("manual raises a check prompt", "(= event 1) (>= mode 1) (= stage 0)", "(= event 1) (>= mode 0) (= stage 0)"),
    ("a tick raises an install prompt", "(and (= event 2) (= mode 3) (= stage 2) ok)", "(and (>= event 1) (= mode 3) (= stage 2) ok)"),
    ("install prompt in auto-stage", "(= event 2) (= mode 3) (= stage 2) ok)", "(= event 2) (>= mode 2) (= stage 2) ok)"),
    ("download button without an endpoint", "(b (and (= stage 1) ok has-endpoint))", "(b (and (= stage 1) ok))"),
    ("install button for an unadmitted image", "(b (and (= stage 2) ok))", "(b (= stage 2))"),
    ("may-run ignores freshness", "(b (and (= fresh 1) (= approved-op op)", "(b (and (= approved-op op)"),
    ("may-run ignores which operation was approved", "(= fresh 1) (= approved-op op) (> op 0)", "(= fresh 1) (> approved-op 0) (> op 0)"),
    ("may-run ignores the offered state", "(> op 0) (> offered 0)))", "(> op 0)))"),
    ("floor equal to version admitted", "(<= version floor) 9", "(< version floor) 9"),
    ("unreadable floor treated as 0", "(< floor 0) 10", "(< floor -9) 10"),
    ("one signer admitted", "(< signers 2) 1", "(< signers 1) 1"),
    ("expired record reported as fresh", "(= verdict 1) (if (> latest installed) 2 1)", "(<= verdict 2) (if (> latest installed) 2 1)"),
    ("refused record reported as data", "(not (= record 1)) 3", "(< record 0) 3"),
]


def lock(entry, policy, path):
    mods = {"aiueos.update-policy": policy, "aiueos.update-policy-test": entry}
    text = "KSL2\nentry %s\n" % entry
    text += "".join("module %s %s\n" % (n, p) for n, p in sorted(mods.items()))
    text += "".join("file %s %s\n" % (hashlib.sha256(p.read_bytes()).hexdigest(), p) for p in sorted(mods.values(), key=str))
    path.write_text(text, encoding="utf-8")


def run(amu, policy, tmp, tag):
    work = tmp / tag
    work.mkdir()
    work = work.resolve()
    entry = (work / TEST.name).resolve()
    entry.write_bytes(TEST.read_bytes())
    path = work / "lock.ksl"
    lock(entry.resolve(), policy.resolve(), path)
    r = subprocess.run([str(amu), "run", str(entry), "--source-lock", str(path)], capture_output=True, timeout=300)
    return r.returncode, r.stdout.decode("utf-8", "replace").strip(), r.stderr.decode("utf-8", "replace").strip()


def fail(msg):
    print("AIUEOS_UPDATE_POLICY_NATIVE_FAIL " + msg)
    sys.exit(1)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    amu = pathlib.Path(sys.argv[1]).resolve() / "bin" / "amu"
    if not amu.is_file():
        fail("%s not found" % amu)
    print("amu sha256 " + hashlib.sha256(amu.resolve().read_bytes()).hexdigest())
    src = POLICY.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        code, out, err = run(amu, POLICY, tmp, "base")
        if code != 0 or out != "0":
            fail("unmodified policy: exit %d, stdout %r, stderr %r" % (code, out, err[:200]))
        print("base: test prints 0")
        for i, (name, anchor, repl) in enumerate(MUTANTS):
            if src.count(anchor) != 1:
                fail("mutant %r: anchor occurs %d times" % (name, src.count(anchor)))
            (tmp / ("m%d-src" % i)).mkdir()
            mp = tmp / ("m%d-src" % i) / POLICY.name
            mp.write_text(src.replace(anchor, repl, 1), encoding="utf-8")
            code, out, err = run(amu, mp, tmp, "m%d" % i)
            # A failing test prints its nonzero check code and exits 0; anything else (a lock or
            # compile error) is not a detection and fails the script.
            if code != 0 or not out.isdigit():
                fail("mutant %r did not run (exit %d, stdout %r, stderr %r)" % (name, code, out[:40], err[:200]))
            if out == "0":
                fail("mutant %r was NOT detected (test still prints 0)" % name)
            print("mutant detected (%s): test failed with check code %s" % (name, out))
    print("AIUEOS_UPDATE_POLICY_NATIVE_OK mutants=%d" % len(MUTANTS))


main()
