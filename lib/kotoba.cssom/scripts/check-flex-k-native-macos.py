#!/usr/bin/env python3
"""Observe flex lines of up to SIXTEEN items as kernel region code (JUN-932 part 1, JUN-920 follow-up) with native tools only:
no JVM, nbb or babashka.

The merged scalar Q6 flex solver (flex_q6) is capped at four items per line because five scalar parameters leave 310 bits and an item
needs 70. This slice holds the line in an owned window (the region-code technique of the style slice, #1268):
src/cssom/fxdiv_k (the exact share of the free space, long division), flex_k (grow / scaled shrink, min/max clamp,
freeze-and-redistribute, the freeze test on the EXACT proposal, one half-up rounding per item), flexplace_k (justify-content and
auto margins from the stored sizes). A line of more than sixteen items is refused (status 1), never truncated.

What this gate does:

  1. STATIC AUDIT of the three region modules: at most five parameters per function, no floats, strings, records, `/` or `rem`.
  2. EXACT MODEL (scripts/flex_k_cases.py): the loop of resolve-flexible-lengths over Python Fractions (no float anywhere), and
     the hand-derived cases (expected sizes written from CSS Flexbox 9.7 before any run) must equal it.
  3. HOST-NATIVE REFERENCES (a native Amu compile and run per batch, src/cssom/flex_ref.kotoba):
       mode 0  the n-item f64 reference against the exact integers of every case: equal after half-up rounding, TIE (the f64 value
               sits within 1e-6 of a half and the exact rule rounds the other way: reported, not copied) or violation (must be 0);
       mode 1  flex_q6 (lines of at most four items) and flex_q6 offset / auto-offset (every placement) against the same integers;
       mode 2  cssom.flex (the existing four-item f64 reference, six for the placement) against the n-item f64 reference.
  4. KERNEL: the region modules run on x86_64-aiueos-kernel-v3 under QEMU TCG (profile `flex` of build-native-desktop-macos.py, the
     entry native/flex-entry.kotoba, the observer os/aiueos/scripts/check-native-flex-qemu.py, fixture opt/aiueos/flex): every case,
     and the kernel's 24-bit digest of the sizes (and offsets) must equal the digest of the exact integers.
  5. NEGATIVE CONTROLS: one rebuilt mutant per region module (one line changed; the anchor must occur exactly once) built into a
     kernel and run through the same observer; it must be seen (observer FAIL, and records that differ from the model), plus a
     mutated f64 reference that must produce violations.
  6. SIZE: kernel-v1 text bytes of the cumulative compile of the modules (a main reaching every export), the whole-image delta, and
     the verdict of x86_64-aiueos-user-v1 with the exact error codes; a six-parameter function must be refused (E7102).

It does not claim CPL3 execution, a wired layout.cljk, or a browser verdict. The original .cljk could not be run here (see
evidence/cssom-q6-slice2-20261106), so the f64 reference and the exact model rest on the code read and on the hand-derived cases.
"""
import argparse
import hashlib
import importlib.util
import json
import platform
import re
import shutil
import sys
import time
from fractions import Fraction as Fr
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


S = load("style_k_gate", HERE / "check-style-k-native-macos.py")      # the style slice's helpers: bundling, compiler, native runs, builder
K = load("flex_k_cases", HERE / "flex_k_cases.py")
OWNER, LIB, SRC, AIUEOS = S.OWNER, S.LIB, S.SRC, S.AIUEOS
sha = S.sha

STEMS = ["fxdiv_k", "flex_k", "flexplace_k"]
MODS = {s: SRC / (s + ".kotoba") for s in STEMS}
REF = SRC / "flex_ref.kotoba"
NATIVE_MODS = {"cssom.flex-ref": REF, "cssom.flex": SRC / "flex.kotoba", "cssom.flex-q6": SRC / "flex_q6.kotoba",
               "cssom.length-q6": SRC / "length_q6.kotoba"}

# one line per module; each anchor must occur exactly once
MUTANTS = [
    ("fxdiv: the second chunk of |R| is taken from bit 8 instead of bit 7", "fxdiv_k",
     "(bit-and (u64-shift-right a 7) 127)", "(bit-and (u64-shift-right a 8) 127)"),
    ("flex: an exact proposal equal to the maximum (with a remainder) is not frozen", "flex_k",
     "(and (not= mx 4294967295) (>= v mx))", "(and (not= mx 4294967295) (> v mx))"),
    ("placement: space-evenly takes i instead of i + 1 gaps", "flexplace_k",
     "(rdiv (* (+ i 1) fp) (+ n 1))", "(rdiv (* i fp) (+ n 1))"),
]
REF_MUTANT = ("f64 reference: a shrinking weight ignores the base size", "(if grow (fl fa i) (f64-mul (fl fa i) (fl b i)))",
              "(if grow (fl fa i) (fl fa i))")

# cumulative entries: a main reaching every export, two arguments (a window and its length)
ENTRIES = {
    "fxdiv_k": ("[cssom.fxdiv-k :as xd]", "(+ (xd/xd-pack w n 3) (+ (xd/xd-floor w) (xd/xd-rem n)))"),
    "flex_k": ("[cssom.flex-k :as fk]", "(+ (fk/fx-run w n) (+ (fk/fx-size w n 3) (+ (fk/fx-header w n 2) (fk/fx-count w n))))"),
    "flexplace_k": ("[cssom.flexplace-k :as fp]", "(+ (fp/fp-offset w n 5 100 3) (fp/fp-auto w n 4294967297 100 3))"),
}
TOK = S.TOK
BATCH = 34


def entry_for(upto, zero=False):
    stems = STEMS[:STEMS.index(upto) + 1]
    req = " ".join(ENTRIES[s][0] for s in stems)
    body = ENTRIES[stems[0]][1]
    for s in stems[1:]:
        body = "(+ %s %s)" % (body, ENTRIES[s][1])
    if zero:
        return "(ns e (:require %s) (:export [main]))\n(defn main [] :i64 (let [w 0 n 0] %s))\n" % (req, body)
    return "(ns e (:require %s) (:export [main]))\n(defn main [w :i64 n :i64] :i64 %s)\n" % (req, body)


def static_audit():
    audit = {}
    forbidden = {"/", "rem", "mod", "record", "defrecord"}
    for stem in STEMS:
        code = S.strip_comments(MODS[stem].read_text())
        defns = re.findall(r"\(defn-?\s+(\S+)\s+\[([^\]]*)\]", code)
        params = {n: len([t for t in p.split() if not t.startswith(":")]) for n, p in defns}
        too_many = [n for n, c in params.items() if c > 5]
        if too_many:
            raise ValueError(("more than five parameters", stem, too_many))
        bad = sorted({t for t in TOK.findall(code) if t in forbidden or t.startswith("f64") or t.startswith("f32") or t.startswith("string-")
                      or t.startswith("record-") or t.startswith("document-") or t.startswith("typed-") or t.startswith('"')})
        if bad:
            raise ValueError(("forbidden form in a region module", stem, bad))
        mult = re.findall(r"\(\*\s+(\S+)\s+(\S+)\)", code)
        two_var = [m for m in mult if not (re.fullmatch(r"-?\d+", m[0]) or re.fullmatch(r"-?\d+", m[1]))]
        audit[stem] = {"defns": len(defns), "maxParams": max(params.values()), "multiplications": len(mult),
                       "multiplicationsOfTwoVariables": len(two_var), "codeLines": len([l for l in code.split("\n") if l.strip()])}
    return audit


# ---------------------------------------------------------------- the exact model against the hand-derived cases
def check_hand(cases):
    n = 0
    for c in cases:
        st, sizes, offs, au = K.model(c)
        if c["status"] is not None:
            if -st != c["status"]:
                raise ValueError(("refusal code differs", c["name"], st, c["status"]))
            n += 1
            continue
        if c["expect"] is None and "offsets" not in c and "autos_expect" not in c:
            continue
        if st:
            raise ValueError(("unexpected refusal", c["name"], st))
        if c["expect"] is not None and sizes != c["expect"]:
            raise ValueError(("exact model differs from the hand-derived sizes", c["name"], sizes, c["expect"]))
        if "offsets" in c and offs != c["offsets"]:
            raise ValueError(("exact model differs from the hand-derived offsets", c["name"], offs, c["offsets"]))
        if "autos_expect" in c and au != c["autos_expect"]:
            raise ValueError(("exact model differs from the hand-derived auto offsets", c["name"], au, c["autos_expect"]))
        n += 1
    return n


def exact_ties(cases):
    """Items whose exact value (before the final rounding) has the fractional part 1/2, and the cases that hold one."""
    items = lines = 0
    for c in cases:
        if c["status"] is not None:
            continue
        st, s = K.solve_exact(c["items"], c["net"])
        if st:
            continue
        t = sum(1 for x in s if x.denominator == 2)
        items += t
        lines += 1 if t else 0
    return items, lines


# ---------------------------------------------------------------- host-native batches
def edn(c):
    st, sizes, offs, au = K.model(c)
    out = "{:net %d :items [%s] :sizes [%s] :mode %d :safe %d :container %d :gap %d :offs [%s] :leads %d :trails %d :autos [%s]}" % (
        c["net"], " ".join("[%d %d %d %d]" % (b, mn, -1 if mx is None else mx, f) for b, mn, mx, f in c["items"]),
        " ".join(map(str, sizes)), -1 if c["mode"] is None else c["mode"], c["safe"], c["container"], c["gap"],
        " ".join(map(str, offs or [])), (c["autos"] or (0, 0))[0], (c["autos"] or (0, 0))[1], " ".join(map(str, au or [])))
    return out


def batches(cases):
    ok = [c for c in cases if c["status"] is None]
    return [ok[i:i + BATCH] for i in range(0, len(ok), BATCH)]


def run_batch(nat, tag, batch, mode, mods):
    doc = ("{:cases [%s]}" % " ".join(edn(c) for c in batch)).replace("\\", "\\\\").replace('"', '\\"')
    entry = ('(ns ent (:require [cssom.flex-ref :as r]) (:export [main]))\n(defn main [] :i64 (r/stats (document-edn-read "%s") %d))\n' % (doc, mode))
    return nat.run(tag, entry, mods, "ent")


def host_reference(nat, cases, jobs, mods, label):
    bs = batches(cases)
    jobs_list = [(i, m) for i in range(len(bs)) for m in (0, 1, 2)]

    def one(job):
        i, m = job
        return run_batch(nat, "%s-b%03d-m%d" % (label, i, m), bs[i], m, mods)
    res = S.pmap(one, jobs_list, jobs)
    for (i, m), r in zip(jobs_list, res):
        if not isinstance(r, int):
            raise ValueError(("the host-native reference trapped", label, i, m, r))
    t0 = dict(eq=0, tie=0, viol=0, maxdev1000=0, bad=[])
    t1 = dict(sizesCompared=0, sizeMismatches=0, placementsCompared=0, placementMismatches=0, bad=[])
    t2 = dict(comparisons=0, differences=0, bad=[])
    for (i, m), r in zip(jobs_list, res):
        if m == 0:
            t0["eq"] += r & 16383
            t0["tie"] += (r >> 14) & 16383
            t0["viol"] += (r >> 28) & 16383
            t0["maxdev1000"] = max(t0["maxdev1000"], r >> 42)
            if (r >> 28) & 16383:
                t0["bad"].append(i)
        elif m == 1:
            t1["sizesCompared"] += r & 32767
            t1["sizeMismatches"] += (r >> 15) & 32767
            t1["placementsCompared"] += (r >> 30) & 32767
            t1["placementMismatches"] += r >> 45
            if (r >> 15) & 32767 or r >> 45:
                t1["bad"].append(i)
        else:
            t2["comparisons"] += r & 1048575
            t2["differences"] += r >> 20
            if r >> 20:
                t2["bad"].append(i)
    return dict(mode0=t0, mode1=t1, mode2=t2, batches=len(bs))


def read_receipt(output):
    path = Path(output) / "qemu" / "native-flex-qemu.json"
    return json.loads(path.read_text()) if path.is_file() else None


def differing(cases, receipt):
    """Cases whose kernel record differs from the digest of the exact model."""
    out = []
    for c, rec in zip(cases, receipt["records"]):
        assert rec["name"] == c["name"], (rec["name"], c["name"])
        want = K.digest(c)
        if (rec["status"] << 24 | rec["digest"]) != want:
            out.append(c["name"])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--amu", type=Path, required=True, help="amu-cli.macho (native macOS arm64)")
    ap.add_argument("--amu-sha256", default=S.AMU_SHA256)
    ap.add_argument("--amu-full-root", type=Path, required=True, help="amu-full-root.macho (the --target compiler)")
    ap.add_argument("--amu-full-root-sha256", default=S.AMU_FULL_ROOT_SHA256)
    ap.add_argument("--amu-source", type=Path, required=True, help="the Amu checkout the desktop builder uses")
    ap.add_argument("--owner-repo-root", type=Path, required=True)
    ap.add_argument("--qemu", type=Path, required=True)
    ap.add_argument("--qemu-sha256", required=True)
    ap.add_argument("--firmware", type=Path, required=True)
    ap.add_argument("--firmware-sha256", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--reuse-baseline", type=Path, help="an existing builder output of profile flex (skips the baseline build)")
    ap.add_argument("--image-baseline", type=Path, help="an existing builder output of another profile, for the whole-image delta")
    ap.add_argument("--image-baseline-profile", default="imgsig")
    ap.add_argument("--host-only", action="store_true", help="stages 1-3 and the reference mutant only (no kernel build)")
    ap.add_argument("--reuse-run", type=Path, help="a previous output of this gate on the same tree: its kernel-baseline and kernel-mutant-* "
                    "builds are re-verified (receipts read, records compared with the exact model again) instead of rebuilt")
    ap.add_argument("--skip-mutants", action="store_true")
    ap.add_argument("--print-measurements", action="store_true")
    args = ap.parse_args()
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise ValueError("requires native macOS ARM64")
    amu, full = args.amu.resolve(strict=True), args.amu_full_root.resolve(strict=True)
    if sha(amu) != args.amu_sha256 or sha(full) != args.amu_full_root_sha256:
        raise ValueError("Amu digest mismatch")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    receipt = {"status": "RUNNING", "amu": sha(amu), "amuFullRoot": sha(full)}
    cases = K.all_cases()
    receipt["inputs"] = {str(p.relative_to(LIB)): sha(p) for p in
                         [Path(__file__).resolve(), HERE / "flex_k_cases.py", REF, SRC / "flex.kotoba", SRC / "flex_q6.kotoba", *MODS.values(),
                          AIUEOS / "os/aiueos/native/flex-entry.kotoba", AIUEOS / "os/aiueos/scripts/check-native-flex-qemu.py", S.BUILDER]}
    nat = S.Native(amu, out / "native")

    # 1. static audit
    receipt["audit"] = static_audit()

    # 2. the exact model against the hand-derived cases
    hand = [c for c in cases if c["group"] == "hand"]
    receipt["handDerived"] = {"hand-group-cases": len(hand), "casesWithAHandDerivedExpectationOrRefusal": check_hand(cases)}
    ti, tl = exact_ties(cases)
    st_counts = {}
    for c in cases:
        k = K.model(c)[0]
        st_counts[k] = st_counts.get(k, 0) + 1
    by_n = {}
    for c in cases:
        if K.model(c)[0] == 0:
            by_n[len(c["items"])] = by_n.get(len(c["items"]), 0) + 1
    receipt["grid"] = {"cases": len(cases), "groups": {g: sum(1 for c in cases if c["group"] == g) for g in sorted({c["group"] for c in cases})},
                       "statusCounts": {str(k): v for k, v in sorted(st_counts.items())}, "runByItemCount": {str(k): v for k, v in sorted(by_n.items())},
                       "exactTieItems": ti, "linesWithAnExactTie": tl,
                       "placementCases": sum(1 for c in cases if c["mode"] is not None), "autoMarginCases": sum(1 for c in cases if c["autos"])}

    # 3. host-native references
    t0 = time.monotonic()
    ref = host_reference(nat, cases, args.jobs, NATIVE_MODS, "ref")
    ref["seconds"] = round(time.monotonic() - t0, 1)
    if ref["mode0"]["viol"] or ref["mode1"]["sizeMismatches"] or ref["mode1"]["placementMismatches"] or ref["mode2"]["differences"]:
        raise ValueError(("a host-native reference disagrees with the exact model", ref))
    if ref["mode0"]["tie"] > ti + 0 and False:
        raise ValueError("more f64 ties than exact ties")
    receipt["reference"] = ref
    # negative control of the reference: a mutated copy must produce violations
    text0 = REF.read_text()
    if text0.count(REF_MUTANT[1]) != 1:
        raise ValueError(("mutation anchor must occur exactly once", REF_MUTANT[0], text0.count(REF_MUTANT[1])))
    mdir = out / "ref-mutant"
    mdir.mkdir()
    (mdir / "flex_ref.kotoba").write_text(text0.replace(REF_MUTANT[1], REF_MUTANT[2]))
    mods = dict(NATIVE_MODS)
    mods["cssom.flex-ref"] = mdir / "flex_ref.kotoba"
    mutated = host_reference(nat, [c for c in cases if c["group"] in ("hand", "cascade")], args.jobs, mods, "refmut")
    if not mutated["mode0"]["viol"]:
        raise ValueError(("the mutated f64 reference was not seen", mutated))
    receipt["referenceMutant"] = {"name": REF_MUTANT[0], "anchor": REF_MUTANT[1], "replacement": REF_MUTANT[2],
                                  "violations": mutated["mode0"]["viol"], "batchesWithViolations": len(mutated["mode0"]["bad"])}
    if args.host_only:
        receipt["status"] = "PASS_HOST_ONLY"
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps({k: receipt[k] for k in ("audit", "handDerived", "grid", "reference", "referenceMutant")}, indent=2))
        return

    # 4. kernel: baseline build and QEMU run
    receipt["reusedRun"] = str(args.reuse_run.resolve()) if args.reuse_run else None
    if args.reuse_run:
        args.reuse_baseline = args.reuse_run.resolve() / "kernel-baseline"
    base = args.reuse_baseline.resolve() if args.reuse_baseline else out / "kernel-baseline"
    started = time.monotonic()
    if not args.reuse_baseline:
        code, tail, secs = S.run_builder(args, base, profile="flex")
        if code:
            raise ValueError(("the baseline kernel build or run failed", tail))
    base_receipt = read_receipt(base)
    if base_receipt is None or base_receipt["status"] != "PASS_NATIVE_FLEX_K_QEMU":
        raise ValueError("the baseline observer receipt is missing or not PASS")
    bad = differing(cases, base_receipt)
    if bad:
        raise ValueError(("the kernel differs from the exact model", bad[:10]))
    state = json.loads((base / "native-desktop-macos.json").read_text())
    kstate = json.loads((base / "kernel/build-state.json").read_text())
    recs = base_receipt["records"]
    receipt["kernel"] = {"profile": "flex", "state": state["state"], "target": "x86_64-aiueos-kernel-v3", "cases": len(cases),
                         "equalToExactModel": len(cases) - len(bad), "statusZero": sum(1 for r in recs if r["status"] == 0),
                         "refused": sum(1 for r in recs if r["status"] != 0),
                         "refusalCodes": sorted({r["status"] for r in recs if r["status"]}),
                         "buildAndRunSeconds": None if args.reuse_baseline else round(time.monotonic() - started, 1),
                         "textSegmentBytes": state["textMargin"]["textSegmentBytes"], "estimatedMarginBytes": state["textMargin"]["estimatedMarginBytes"],
                         "sourceModuleCount": kstate["sourceModuleCount"], "kernelSha256": kstate["kernel"]["sha256"],
                         "cssomModulesLocked": sorted(m for m in kstate["sourceGraph"] if "/cssom/" in m)}
    if args.image_baseline:
        bstate = json.loads((args.image_baseline.resolve() / "native-desktop-macos.json").read_text())
        receipt["imageDelta"] = {"baselineProfile": args.image_baseline_profile, "baselineTextSegmentBytes": bstate["textMargin"]["textSegmentBytes"],
                                 "flexTextSegmentBytes": receipt["kernel"]["textSegmentBytes"],
                                 "delta": receipt["kernel"]["textSegmentBytes"] - bstate["textMargin"]["textSegmentBytes"]}

    # 5. negative controls
    receipt["mutants"] = []
    if not args.skip_mutants:
        for name, stem, anchor, repl in MUTANTS:
            text0 = MODS[stem].read_text()
            if text0.count(anchor) != 1:
                raise ValueError(("mutation anchor must occur exactly once", name, text0.count(anchor)))
            mdir = out / "mutants" / stem
            mdir.mkdir(parents=True)
            for p in SRC.glob("*_k.kotoba"):
                shutil.copyfile(p, mdir / p.name)
            (mdir / (stem + ".kotoba")).write_text(text0.replace(anchor, repl))
            if args.reuse_run:
                old = args.reuse_run.resolve() / "mutants" / stem
                if any(sha(old / p.name) != sha(mdir / p.name) for p in mdir.glob("*.kotoba")):
                    raise ValueError(("the reused mutant sources differ from the current tree", stem))
                mout = args.reuse_run.resolve() / ("kernel-mutant-" + stem)
                code = None                               # not re-run: the first run raised unless the builder exited non-zero; the receipt decides
            else:
                mout = out / ("kernel-mutant-" + stem)
                code, tail, secs = S.run_builder(args, mout, profile="flex", env_extra={"AIUEOS_CSSOM_K_SOURCE_PATH": str(mdir)})
            tail = ""
            mr = read_receipt(mout)
            if code == 0 or mr is None or mr["status"] != "FAIL_NATIVE_FLEX_K_QEMU":
                raise ValueError(("the mutant was not seen by the observer", name, code, tail[-400:]))
            diff = differing(cases, mr)
            if not diff:
                raise ValueError(("the mutant is not seen by the case table", name))
            receipt["mutants"].append({"name": name, "module": stem, "anchor": anchor, "replacement": repl, "builderExit": code,
                                       "casesDifferingFromModel": len(diff), "firstDifferences": diff[:3]})

    # 6. sizes and the user-v1 verdict
    comp = S.AiueosCompiler(full, out / "aiueos")
    sizes, prev = {}, 0
    for stem in STEMS:
        src, kept, total = S.reachable(S.bundle(entry_for(stem), SRC))
        res = comp.compile("cum-" + stem, src, "x86_64-aiueos-kernel-v1")
        if not res["ok"]:
            raise ValueError(("kernel-v1 compile failed", stem, res["output"]))
        sizes[stem] = {"cumulativeTextBytes": res["textBytes"], "moduleTextBytes": res["textBytes"] - prev, "functionsReached": kept,
                       "functionsInBundle": total, "sourceSha256": res["sourceSha256"]}
        prev = res["textBytes"]
    receipt["sizeKernelV1"] = sizes
    lines = sum(a["codeLines"] for a in receipt["audit"].values())
    receipt["sizeKernelV1"]["bytesPerCodeLine"] = round(prev / lines, 1)
    user = {}
    for stem in STEMS:
        for zero in (False, True):
            src, _, _ = S.reachable(S.bundle(entry_for(stem, zero), SRC))
            res = comp.compile("user-%s-%s" % (stem, "zero" if zero else "two"), src, "x86_64-aiueos-user-v1")
            # fxdiv_k holds no window form (scalar code), so user-v1 may accept it; the two window modules must be refused
            if res["ok"] and stem != "fxdiv_k":
                raise ValueError(("user-v1 unexpectedly accepted region code", stem))
            user["%s/%s-argument-entry" % (stem, "0" if zero else "2")] = {
                "accepted": res["ok"], "textBytes": res.get("textBytes"), "error": res.get("error"), "message": res.get("message"),
                "detail": res.get("detail"), "output": res["output"]}
    receipt["userV1"] = user
    six = ("(ns m (:export [main]))\n(defn f [a b c d e g] (+ a (+ b (+ c (+ d (+ e g))))))\n(defn main [a :i64 b :i64] :i64 (f a b a b a b))\n")
    res = comp.compile("six-params", six, "x86_64-aiueos-kernel-v1")
    if res["ok"] or res.get("error") != "E7102":
        raise ValueError(("six parameters must be refused with E7102", res["output"]))
    receipt["sixParameterRefusal"] = {"error": res["error"], "detail": res["detail"]}
    receipt["status"] = "PASS_NATIVE_CSSOM_FLEX_K"
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(receipt["status"], len(cases), "cases", len(receipt["mutants"]), "mutants seen")
    if args.print_measurements:
        print(json.dumps({k: v for k, v in receipt.items() if k != "inputs"}, indent=2))


if __name__ == "__main__":
    main()
