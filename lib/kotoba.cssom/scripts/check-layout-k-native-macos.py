#!/usr/bin/env python3
"""Observe the layout slice of the CSSOM (JUN-134/135/920, ADR-0287) with native tools only: no JVM, nbb or babashka.

The slice: normal block flow of the styled node table of the style slice into a box table (position, border-box size, content size, margins
with 8.3.1 collapsing, padding, border) in Q6 fixed point, as kernel-dialect REGION code (src/cssom/box_k, flow_k) on top of the style slice
(intern_k .. cascade_k) and the merged Q6 scalar modules (length_q6, block_width_q6, block_style_q6, margin_collapse_q6).

What this gate does:

  1. STATIC AUDIT of the two new region modules (box_k, flow_k): at most five parameters per function, no floats, strings, records, `/` or `rem`;
     the generated name table `nt` of box_k is regenerated from the supported / refused names, from `inline-level-tags` and `non-rendered-tags`
     of layout.cljk, and compared; the refused names are compared with the independent reference's list.
  2. KERNEL: the region modules run on x86_64-aiueos-kernel-v3 under QEMU TCG (profile `layout` of build-native-desktop-macos.py, observer
     os/aiueos/scripts/check-native-layout-qemu.py): every case of the grid (src: scripts/layout_k_cases.py) and the whole box table of every case is
     read back from the guest's debug console. The observer checks the hand-derived cases word for word.
  3. REFERENCE: the independent host-native f64 implementation (src/cssom/layout_ref.kotoba, native Amu compile and run per case) takes each case
     together with the kernel's table. It must (a) reproduce every hand-derived table (run with the hand-derived table as the "kernel"), (b) refuse
     with the status the kernel answers, (c) for every case that runs, report the largest deviation in Q6 units between the kernel's integers and
     its f64 values, and the tie report (round half up: fields whose f64 value is an exact .5 of a Q6 unit and whether the kernel rounded up).
  4. NEGATIVE CONTROLS: one rebuilt mutant per module (box_k, flow_k and the four Q6 modules the slice calls; one line changed, the anchor occurs
     exactly once) is built into a kernel and run through the same observer; it must be seen (observer FAIL), never silently pass.
  5. SIZE: kernel-v1 text bytes of the cumulative compile (a main reaching every export), the kernel-v3 whole-image text segment and its delta against
     the `style` profile, and the verdict of x86_64-aiueos-user-v1 with the exact error; a six-parameter function must be refused (E7102).

It does not claim CPL3 execution, a wired layout.cljk, or a browser verdict. The reference transcribes layout.cljk block flow; the original .cljk
could not be run here (see evidence/cssom-q6-slice2-20261106), so its fidelity rests on the hand-derived cases and on the code read.
"""
import argparse
import importlib.util
import json
import platform
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("style_gate", HERE / "check-style-k-native-macos.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)         # bundle, reachable, AiueosCompiler, Native, run_builder, sha, strip_comments, TOK, constants
spec2 = importlib.util.spec_from_file_location("layout_k_cases", HERE / "layout_k_cases.py")
K = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(K)

SRC, LIB, AIUEOS, OWNER = G.SRC, G.LIB, G.AIUEOS, G.OWNER
NEW = ["box_k", "flow_k"]
Q6 = ["length_q6", "block_width_q6", "block_style_q6", "margin_collapse_q6"]
STEMS = NEW + Q6
MODS = {s: SRC / (s + ".kotoba") for s in NEW + Q6 + ["intern_k", "selector_k", "match_k", "cascade_k"]}
REF = SRC / "layout_ref.kotoba"
REFMODS = {"cssom.layout-ref": REF, "cssom.style-ref": SRC / "style_ref.kotoba", "cssom.length": SRC / "length.kotoba",
           "cssom.block-style": SRC / "block_style.kotoba", "cssom.block-width": SRC / "block_width.kotoba",
           "cssom.margin-collapse": SRC / "margin_collapse.kotoba"}

MUTANTS = [
    ("box: border-box is ignored by the solver", "box_k", "(bs/p0-of cb sel bb 0)", "(bs/p0-of cb sel 0 0)"),
    ("flow: sibling margins add instead of collapsing", "flow_k", "(cm2 pm mts))", "(+ pm mts))"),
    ("margin-collapse-q6: negative margins are ignored", "margin_collapse_q6",
     "n (if (< value (negative state)) value (negative state))", "n (negative state)"),
    ("block-width-q6: auto margins split by a quarter", "block_width_q6", "half (i64-shift-right remaining 1)", "half (i64-shift-right remaining 2)"),
    ("length-q6: percentages are halved", "length_q6", "(rdiv (* h basis) 10000))", "(rdiv (* h basis) 20000))"),
    ("block-style-q6: max-width is never applied", "block_style_q6", "(if (= kmx 1) 32 0)", "(if (= kmx 1) 0 0)"),
]

# cumulative entries for kernel-v1 sizes: the style slice first (its own gate sizes it), then the Q6 modules, then the new ones
BASE = ("[cssom.cascade-k :as ck]", "(+ (ck/ck-run w n 100) (ck/ck-nodes w n))")
ENTRIES = [
    ("length_q6", "[cssom.length-q6 :as len]", "(+ (len/percent-of 5 7) (+ (len/resolve-value 1 2 3 4) (len/rdiv 3 2)))"),
    ("block_width_q6", "[cssom.block-width-q6 :as bw]", "(bw/solve-constrained-pick 1 2 3 4 5)"),
    ("margin_collapse_q6", "[cssom.margin-collapse-q6 :as mc]", "(mc/finish (mc/add 0 5))"),
    ("block_style_q6", "[cssom.block-style-q6 :as bs]", "(+ (bs/solve-pick 1 2 3 4 5) (+ (bs/slot 1 2) (+ (bs/pair 1 2) (+ (bs/border-field 1 2) (bs/p0-of 1 2 3 4)))))"),
    ("box_k", "[cssom.box-k :as bk]", "(bk/bk-run w n 64000)"),
    ("flow_k", "[cssom.flow-k :as fk]", "(+ (fk/fk-run w n 100 64000) (+ (fk/fk-height w n) (+ (fk/fk-off w n) (fk/fk-word w n 1 2))))"),
]
EXPECTED_MODULES = 61


def sha(p):
    return G.sha(p)


def entry_for(upto, zero=False):
    k = [e[0] for e in ENTRIES].index(upto) + 1
    req = " ".join([BASE[0]] + [e[1] for e in ENTRIES[:k]])
    body = BASE[1]
    for e in ENTRIES[:k]:
        body = "(+ %s %s)" % (body, e[2])
    if zero:
        return "(ns e (:require %s) (:export [main]))\n(defn main [] :i64 (let [w 0 n 0] %s))\n" % (req, body)
    return "(ns e (:require %s) (:export [main]))\n(defn main [w :i64 n :i64] :i64 %s)\n" % (req, body)


def base_entry():
    return "(ns e (:require %s) (:export [main]))\n(defn main [w :i64 n :i64] :i64 %s)\n" % BASE


def name_table():
    """The generated text of `nt` in box_k, from the lists the module documents and layout.cljk."""
    core = (SRC / "layout.cljk").read_text()
    def kws(var):
        m = re.search(r"\(def \^:private %s\b.*?#\{([^}]*)\}" % var, core, re.S)
        return [x.lstrip(":") for x in m.group(1).split()]
    inline, hidden = kws("inline-level-tags"), kws("non-rendered-tags")
    refm = re.search(r'\(def refused-names "([^"]*)"\)', REF.read_text())
    refused = refm.group(1).split("|")
    sys.path.insert(0, str(HERE))
    supported = K.SUPPORTED
    names = supported + refused + inline + hidden

    def words(s):
        b = s.encode()
        return [sum(x << (8 * i) for i, x in enumerate(b[7 * k:7 * k + 7])) for k in range(3)]
    arms = []
    for i, n in enumerate(names):
        for j, v in enumerate([len(n)] + words(n)):
            if v:
                arms.append("%d %d" % (4 * i + j, v))
    return {"supported": len(supported), "refused": len(refused), "inline": len(inline), "hidden": len(hidden), "total": len(names)}, \
        "(defn- nt [x :i64] :i64 (case x " + " ".join(arms) + " 0))"


def static_audit():
    audit = {}
    forbidden = {"/", "rem", "mod", "record", "defrecord"}
    for stem in NEW:
        text = MODS[stem].read_text()
        code = G.strip_comments(text)
        defns = re.findall(r"\(defn-?\s+(\S+)\s+\[([^\]]*)\]", code)
        params = {n: len([t for t in p.split() if not t.startswith(":")]) for n, p in defns}
        too_many = [n for n, c in params.items() if c > 5]
        if too_many:
            raise ValueError(("more than five parameters", stem, too_many))
        tokens = G.TOK.findall(code)
        bad = sorted({t for t in tokens if t in forbidden or t.startswith("f64") or t.startswith("f32") or t.startswith("string-")
                      or t.startswith("record-") or t.startswith("document-") or t.startswith("typed-") or t.startswith('"')})
        if bad:
            raise ValueError(("forbidden form in a region module", stem, bad))
        mult = re.findall(r"\(\*\s+(\S+)\s+(\S+)\)", code)
        two_var = [m for m in mult if not (re.fullmatch(r"-?\d+", m[0]) or re.fullmatch(r"-?\d+", m[1]))]
        audit[stem] = {"defns": len(defns), "maxParams": max(params.values()), "multiplications": len(mult),
                       "multiplicationsOfTwoVariables": len(two_var), "codeLines": len([l for l in code.split("\n") if l.strip()])}
    return audit


def edn_case(c, table, knn, kdh, masks, docmask):
    base = G.K.edn_case(c)
    return base[:-1] + " :vw %d :knn %d :kdh %d :fmask %d :fmasks [%s] :kernel [%s]}" % (
        c["vw"], knn, kdh, docmask, " ".join(map(str, masks)), " ".join(map(str, table)))


def ref_run(nat, tag, c, table, knn, kdh, masks, docmask):
    edn = edn_case(c, table, knn, kdh, masks, docmask).replace("\\", "\\\\").replace('"', '\\"')
    entry = '(ns ent (:require [cssom.layout-ref :as r]) (:export [main]))\n(defn main [] :i64 (r/run-case (document-edn-read "%s")))\n' % edn
    return nat.run(tag, entry, REFMODS, "ent")


def decode(r):
    """(refusal status or 0, deviation in thousandths of a Q6 unit, ties, tie disagreements)"""
    if r < 0:
        return -r, None, 0, 0
    return 0, r & 0xFFFFFFFF, (r >> 32) & 0xFFF, r >> 44


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--amu", type=Path, required=True)
    ap.add_argument("--amu-sha256", default=G.AMU_SHA256)
    ap.add_argument("--amu-full-root", type=Path, required=True)
    ap.add_argument("--amu-full-root-sha256", default=G.AMU_FULL_ROOT_SHA256)
    ap.add_argument("--amu-source", type=Path, required=True)
    ap.add_argument("--owner-repo-root", type=Path, required=True)
    ap.add_argument("--qemu", type=Path, required=True)
    ap.add_argument("--qemu-sha256", required=True)
    ap.add_argument("--firmware", type=Path, required=True)
    ap.add_argument("--firmware-sha256", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--reuse-baseline", type=Path, help="an existing builder output of profile layout (skips the baseline build)")
    ap.add_argument("--reuse-style", type=Path, help="an existing builder output of profile style (the whole-image delta); built when absent")
    ap.add_argument("--skip-mutants", action="store_true")
    ap.add_argument("--max-deviation", type=float, default=None, help="fail when a deviation exceeds this many Q6 units (default: report only)")
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
                         [Path(__file__).resolve(), HERE / "layout_k_cases.py", HERE / "style_k_cases.py", REF, SRC / "style_ref.kotoba", *MODS.values(),
                          AIUEOS / "os/aiueos/native/layout-entry.kotoba", AIUEOS / "os/aiueos/scripts/check-native-layout-qemu.py", G.BUILDER,
                          AIUEOS / "os/aiueos/scripts/build-native-kernel-macos.py"]}
    nat = G.Native(amu, out / "native")

    # 1. static audit and the generated name table
    receipt["audit"] = static_audit()
    counts, table_text = name_table()
    if table_text not in MODS["box_k"].read_text():
        raise ValueError("the name table nt of box_k.kotoba differs from the one regenerated from layout.cljk and the reference (regenerate it)")
    receipt["nameTable"] = counts

    # 2. kernel
    base = args.reuse_baseline.resolve() if args.reuse_baseline else out / "kernel-baseline"
    if not args.reuse_baseline:
        code, tail, secs = G.run_builder(args, base, "layout")
        if code:
            raise ValueError(("the baseline kernel build or run failed", tail))
    kr = json.loads((base / "qemu/native-layout-qemu.json").read_text())
    if kr["status"] != "PASS_NATIVE_LAYOUT_K_QEMU" or len(kr["records"]) != len(cases):
        raise ValueError("the baseline observer receipt is missing or not PASS")
    state = json.loads((base / "native-desktop-macos.json").read_text())
    kstate = json.loads((base / "kernel/build-state.json").read_text())
    if kstate["sourceModuleCount"] != EXPECTED_MODULES:
        raise ValueError(("module count", kstate["sourceModuleCount"]))
    recs = kr["records"]

    # 3. reference: (a) hand-derived tables, (b) the kernel's tables
    def hand_job(c):
        words, masks, dm = K.hand_table(c)
        n = len(K.flat(c["doc"]))
        return ref_run(nat, "hand-" + c["name"], c, words, n, K.Q(c["doch"]) if c["doch"] is not None else 0, masks, dm)
    hand = [c for c in cases if c.get("boxes")]
    started = time.monotonic()
    hres = list(zip(hand, ThreadPoolExecutor(args.jobs).map(hand_job, hand)))
    bad_hand = [(c["name"], r) for c, r in hres if not isinstance(r, int) or r < 0 or decode(r)[1] != 0]
    if bad_hand:
        raise ValueError(("the reference does not reproduce the hand-derived tables", bad_hand[:5]))
    hand_tie = sum(decode(r)[2] for _, r in hres)

    def kern_job(i):
        c, rec = cases[i], recs[i]
        if rec["status"] == 0:
            n = rec["nodes"]
            return ref_run(nat, "k-%03d" % i, c, rec["table"], n, rec["dh"], [(1 << 22) - 2] * n, 1 << 22)
        return ref_run(nat, "k-%03d" % i, c, [], 0, 0, [], 0)
    kres = list(ThreadPoolExecutor(args.jobs).map(kern_job, range(len(cases))))
    receipt["reference"] = {"handCases": len(hand), "handReproduced": len(hand), "seconds": round(time.monotonic() - started, 1), "handTies": hand_tie}
    traps = [(cases[i]["name"], r) for i, r in enumerate(kres) if not isinstance(r, int)]
    if traps:
        raise ValueError(("the reference trapped", traps[:5]))
    status_diff, expect_diff, devs, run_cases, refused = [], [], [], 0, 0
    ties = disagree = 0
    tie_cases = []
    for i, (c, rec, r) in enumerate(zip(cases, recs, kres)):
        rs, dev, t, d = decode(r)
        if c["ref"] and rs != rec["status"]:
            status_diff.append((c["name"], rec["status"], rs))
        if c["status"] is not None and rec["status"] != c["status"]:
            expect_diff.append((c["name"], rec["status"], c["status"]))
        if rec["status"] == 0 and rs == 0:
            run_cases += 1
            devs.append((dev / 1000.0, c["name"]))
            ties += t
            disagree += d
            if t:
                tie_cases.append({"case": c["name"], "tieFields": t, "kernelDidNotRoundHalfUp": d})
        elif rec["status"]:
            refused += 1
    if status_diff or expect_diff:
        raise ValueError(("status disagreements", status_diff[:6], expect_diff[:6]))
    devs.sort(reverse=True)
    structural = [n for d, n in devs if d >= 4294967.0]
    if structural:
        raise ValueError(("kernel and reference tables differ structurally (kinds or element count)", structural[:5]))
    worst = devs[0] if devs else (0.0, None)
    if args.max_deviation is not None and worst[0] > args.max_deviation:
        raise ValueError(("deviation above the allowed", worst))
    hist = {}
    for d, _ in devs:
        key = "<=0.5" if d <= 0.5 else "<=1" if d <= 1 else "<=2" if d <= 2 else "<=4" if d <= 4 else "<=16" if d <= 16 else ">16"
        hist[key] = hist.get(key, 0) + 1
    receipt["kernel"] = {"profile": "layout", "state": state["state"], "target": "x86_64-aiueos-kernel-v3", "cases": len(cases),
                         "run": run_cases, "refused": refused, "comparedWithReference": sum(1 for c in cases if c["ref"]),
                         "handDerived": len(hand), "textSegmentBytes": state["textMargin"]["textSegmentBytes"],
                         "estimatedMarginBytes": state["textMargin"]["estimatedMarginBytes"], "sourceModuleCount": kstate["sourceModuleCount"],
                         "kernelSha256": kstate["kernel"]["sha256"], "cssomModulesLocked": sorted(m for m in kstate["sourceGraph"] if "/cssom/" in m)}
    receipt["deviation"] = {"maxQ6Units": worst[0], "worstCase": worst[1], "top": [(n, d) for d, n in devs[:8]], "histogramOfCases": hist,
                            "casesAtZero": sum(1 for d, _ in devs if d == 0.0)}
    receipt["ties"] = {"roundingRule": "round half up: floor(x + 1/2)", "tieFields": ties, "kernelDidNotRoundHalfUp": disagree, "cases": tie_cases}
    receipt["statusHistogram"] = {str(s): sum(1 for r in recs if r["status"] == s) for s in sorted({r["status"] for r in recs})}

    # 4. negative controls
    receipt["mutants"] = []
    if not args.skip_mutants:
        def mutant(item):
            name, stem, anchor, repl = item
            text0 = MODS[stem].read_text()
            if text0.count(anchor) != 1:
                raise ValueError(("mutation anchor must occur exactly once", name, text0.count(anchor)))
            mdir = out / "mutants" / stem
            mdir.mkdir(parents=True)
            for s in MODS:
                shutil.copyfile(MODS[s], mdir / (s + ".kotoba"))
            (mdir / (stem + ".kotoba")).write_text(text0.replace(anchor, repl))
            code, tail, secs = G.run_builder(args, out / ("kernel-mutant-" + stem), "layout", env_extra={"AIUEOS_CSSOM_K_SOURCE_PATH": str(mdir)})
            rp = out / ("kernel-mutant-" + stem) / "qemu/native-layout-qemu.json"
            mr = json.loads(rp.read_text()) if rp.is_file() else None
            if code == 0 or (mr is not None and mr["status"] != "FAIL_NATIVE_LAYOUT_K_QEMU"):
                raise ValueError(("the mutant was not seen by the observer", name, code, tail[-400:]))
            if mr is None and not (out / ("kernel-mutant-" + stem) / "kernel/build-state.json").is_file():
                raise ValueError(("the mutant did not build, so it was not run", name, tail[-400:]))
            differing = [m[0] if isinstance(m, (list, tuple)) else m for m in mr["mismatches"]] if mr is not None else None
            return {"name": name, "module": stem, "anchor": anchor, "replacement": repl, "builderExit": code,
                    "observerReceipt": mr["status"] if mr else "no receipt (the guest did not finish or the build failed)",
                    "casesDifferingFromTable": len(differing) if differing is not None else None,
                    "firstDifferences": (differing or [])[:4], "seconds": round(secs, 1), "builderTail": tail[-300:] if mr is None else None}
        receipt["mutants"] = list(ThreadPoolExecutor(max_workers=3).map(mutant, MUTANTS))

    # 5. sizes and the user-v1 verdict
    comp = G.AiueosCompiler(full, out / "aiueos")
    src, kept, total = G.reachable(G.bundle(base_entry()))
    res = comp.compile("cum-style", src, "x86_64-aiueos-kernel-v1")
    if not res["ok"]:
        raise ValueError(("kernel-v1 compile failed", "style base", res["output"]))
    prev = res["textBytes"]
    sizes = {"styleSliceBase": {"cumulativeTextBytes": prev}}
    for stem, _req, _body in ENTRIES:
        src, kept, total = G.reachable(G.bundle(entry_for(stem)))
        res = comp.compile("cum-" + stem, src, "x86_64-aiueos-kernel-v1")
        if not res["ok"]:
            raise ValueError(("kernel-v1 compile failed", stem, res["output"]))
        sizes[stem] = {"cumulativeTextBytes": res["textBytes"], "moduleTextBytes": res["textBytes"] - prev, "functionsReached": kept,
                       "functionsInBundle": total, "sourceSha256": res["sourceSha256"]}
        prev = res["textBytes"]
    sizes["layoutDeltaOverStyleBase"] = prev - sizes["styleSliceBase"]["cumulativeTextBytes"]
    lines = sum(a["codeLines"] for a in receipt["audit"].values())
    sizes["newModulesBytesPerCodeLine"] = round((sizes["box_k"]["moduleTextBytes"] + sizes["flow_k"]["moduleTextBytes"]) / lines, 1)
    receipt["sizeKernelV1"] = sizes
    sdir = args.reuse_style.resolve() if args.reuse_style else out / "kernel-style"
    if not args.reuse_style:
        code, tail, secs = G.run_builder(args, sdir, "style")
        if code:
            raise ValueError(("the style profile build failed", tail))
    sstate = json.loads((sdir / "native-desktop-macos.json").read_text())
    receipt["wholeImage"] = {"layoutTextSegmentBytes": state["textMargin"]["textSegmentBytes"], "styleTextSegmentBytes": sstate["textMargin"]["textSegmentBytes"],
                             "delta": state["textMargin"]["textSegmentBytes"] - sstate["textMargin"]["textSegmentBytes"],
                             "layoutKernelSha256": kstate["kernel"]["sha256"]}
    user = {}
    for stem in ("box_k", "flow_k"):
        for zero in (False, True):
            src, _, _ = G.reachable(G.bundle(entry_for(stem, zero)))
            res = comp.compile("user-%s-%s" % (stem, "zero" if zero else "two"), src, "x86_64-aiueos-user-v1")
            if res["ok"]:
                raise ValueError(("user-v1 unexpectedly accepted region code", stem))
            user["%s/%s-argument-entry" % (stem, "0" if zero else "2")] = {"error": res.get("error"), "message": res.get("message"),
                                                                         "detail": res.get("detail"), "output": res["output"]}
    receipt["userV1"] = user
    six = ("(ns m (:export [main]))\n(defn f [a b c d e g] (+ a (+ b (+ c (+ d (+ e g))))))\n(defn main [a :i64 b :i64] :i64 (f a b a b a b))\n")
    res = comp.compile("six-params", six, "x86_64-aiueos-kernel-v1")
    if res["ok"] or res.get("error") != "E7102":
        raise ValueError(("six parameters must be refused with E7102", res["output"]))
    receipt["sixParameterRefusal"] = {"error": res["error"], "detail": res["detail"]}
    receipt["status"] = "PASS_NATIVE_CSSOM_LAYOUT_K"
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(receipt["status"], len(cases), "cases", run_cases, "run", refused, "refused", "max deviation", worst[0], "Q6 units;", len(receipt["mutants"]), "mutants seen")
    print(json.dumps({k: receipt[k] for k in ("audit", "sizeKernelV1", "wholeImage", "kernel", "deviation", "ties", "mutants", "reference", "statusHistogram")}, indent=2))


if __name__ == "__main__":
    main()
