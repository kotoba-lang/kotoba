#!/usr/bin/env python3
"""Observe the draw slice of the CSSOM (JUN-805, ADR-0287) with native tools only: no JVM, nbb or babashka.

The slice: the laid-out box table of the layout slice (flow_k over box_k and the style slice) becomes a DRAW LIST of rect fills and borders
with Q6 coordinates in a shared region (src/cssom/draw_k.kotoba, kernel-dialect region code), in CSS 2.1 Appendix E tree order. The independent
host side is scripts/draw_k_cases.py: its own cascade, colour parser and ordering (`expected`) and a decoder of the raw region words (`decode`).

What this gate does:

  1. STATIC AUDIT of draw_k: at most five parameters per function, no floats, strings, records, `/` or `rem`; the generated property-name table
     `nm`, the colour keyword words and the header magic are regenerated here and compared with the module; every multiplication is listed.
  2. REFERENCE SELF-TEST: the reference reproduces every hand-derived draw list from the hand-derived box table (before the kernel is looked at).
  3. KERNEL: the module runs on x86_64-aiueos-kernel-v3 under QEMU TCG (profile `draw` of build-native-desktop-macos.py, observer
     os/aiueos/scripts/check-native-draw-qemu.py): every case of the grid (scripts/draw_k_cases.py) is run and the raw region words are read back
     from the guest's debug console. The observer checks the structure, the reference on the kernel's own box table, and the hand-derived lists.
     This gate then decodes the receipt AGAIN on the host (second, separate decode and comparison) and reports the census of ops and statuses.
  4. NEGATIVE CONTROLS: one rebuilt mutant per behaviour (one line changed, the anchor occurs exactly once) is built into a kernel and run through
     the same observer; it must be seen (observer FAIL), never silently pass. At most two builds run at a time.
  5. SIZE: kernel-v1 text bytes of the cumulative compile (layout closure, then draw_k), the kernel-v3 whole-image text segment of the `draw` profile
     against the `layout` profile built in the same run, the estimated margin below the compiler cap, and the verdict of x86_64-aiueos-user-v1.

It does not claim CPL3 execution, a mapped (separate) shared region, a wired browser.surface, text or images, or a verdict against a browser. The
region is the two free pages of the owned window; the byte layout is this module's proposal and is not the encoding of the existing kernel
compositor draw list (ADR-0287 still lists the encodings as open).
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
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("style_gate", HERE / "check-style-k-native-macos.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)
spec = importlib.util.spec_from_file_location("layout_gate", HERE / "check-layout-k-native-macos.py")
LG = importlib.util.module_from_spec(spec)
spec.loader.exec_module(LG)
import draw_k_cases as D  # noqa: E402
import layout_k_cases as L  # noqa: E402

SRC, LIB, AIUEOS = G.SRC, G.LIB, G.AIUEOS
MOD = SRC / "draw_k.kotoba"
MODS = {s: SRC / (s + ".kotoba") for s in ["draw_k"] + LG.STEMS + ["intern_k", "selector_k", "match_k", "cascade_k"]}
EXPECTED_MODULES = 63        # 62 + native/update links aiueos.imgsig-prodkeys (JUN-813 amendment 7), as the builder's count for every graph with update.kotoba

# one line per behaviour; each anchor must occur exactly once in draw_k.kotoba
MUTANTS = [
    ("bottom border sits on the box's bottom edge instead of inside it", "(rect! st x (- (+ y h) bb) w bb)", "(rect! st x (+ y h) w bb)"),
    ("right border is placed by the left width", "(rect! st (- (+ x w) br) (+ y bt) br (- h (+ bt bb)))", "(rect! st (- (+ x w) bl) (+ y bt) br (- h (+ bt bb)))"),
    ("left border spans the full height (overlaps the corners)", "(rect! st x (+ y bt) bl (- h (+ bt bb)))", "(rect! st x (+ y bt) bl h)"),
    ("hex digits a-f are one too small", "(- c 87)", "(- c 88)"),
    ("#rgb expands by 16 instead of 17", "(* 17 a)", "(* 16 a)"),
    ("empty-width rectangles are emitted", "(if (or (<= w 0) (<= h 0)) 0", "(if (or (< w 0) (<= h 0)) 0"),
    ("transparent is refused as a bad colour", "(if (word-is st id 11 27426713816363636 1953391986) -2", "(if (word-is st id 11 27426713816363636 1953391986) -1"),
    ("the op limit is 256 (the 256th op overwrites the header slot)", "(if (>= c 255) -21", "(if (>= c 256) -21"),
    ("background-color and border-color are swapped", "pp (+ (+ 1 (pidx st 0 np 0)) (* 256 (+ 1 (pidx st 0 np 1))))",
     "pp (+ (+ 1 (pidx st 0 np 1)) (* 256 (+ 1 (pidx st 0 np 0))))"),
    ("the header carries no document height", "(dw! st 0 4 (hd st 37))", "(dw! st 0 4 0)"),
    ("border-color is read before background-color is checked (a bad background is not refused)",
     "(if (or (= cb -1) (= cc -1))", "(if (= cc -1)"),
]
# names of draw_k and the layout closure it calls, for the cumulative kernel-v1 size
DRAW_ENTRY = ("draw_k", "[cssom.draw-k :as dk]", "(+ (dk/dk-run w n) (dk/dk-word w n 1 2))")


def sha(p):
    return G.sha(p)


def entry_for(include_draw, zero=False):
    ents = list(LG.ENTRIES) + ([DRAW_ENTRY] if include_draw else [])
    req = " ".join([LG.BASE[0]] + [e[1] for e in ents])
    body = LG.BASE[1]
    for e in ents:
        body = "(+ %s %s)" % (body, e[2])
    if zero:
        return "(ns e (:require %s) (:export [main]))\n(defn main [] :i64 (let [w 0 n 0] %s))\n" % (req, body)
    return "(ns e (:require %s) (:export [main]))\n(defn main [w :i64 n :i64] :i64 %s)\n" % (req, body)


def generated_tables():
    """The text of `nm` and the other constants of draw_k, regenerated from the names and keywords."""
    def words(s):
        b = s.encode()
        return [sum(x << (8 * i) for i, x in enumerate(b[7 * k:7 * k + 7])) for k in range(3)]
    arms = []
    for i, name in enumerate(["background-color", "border-color"]):
        for j, v in enumerate([len(name)] + words(name)):
            if v:
                arms.append("%d %d" % (4 * i + j, v))
    nm = "(defn- nm [x :i64] :i64 (case x " + " ".join(arms) + " 0))"
    w = words("transparent")
    return nm, "(word-is st id 11 %d %d)" % (w[0], w[1]), str(int.from_bytes(b"DLv1", "little"))


def static_audit():
    text = MOD.read_text()
    code = G.strip_comments(text)
    defns = re.findall(r"\(defn-?\s+(\S+)\s+\[([^\]]*)\]", code)
    params = {n: len([t for t in p.split() if not t.startswith(":")]) for n, p in defns}
    too_many = [n for n, c in params.items() if c > 5]
    if too_many:
        raise ValueError(("more than five parameters", too_many))
    forbidden = {"/", "rem", "mod", "record", "defrecord"}
    bad = sorted({t for t in G.TOK.findall(code) if t in forbidden or t.startswith(("f64", "f32", "string-", "record-", "document-", "typed-", '"'))})
    if bad:
        raise ValueError(("forbidden form in a region module", bad))
    nm, kw, magic = generated_tables()
    for what, needle in (("property-name table nm", nm), ("transparent keyword words", kw), ("header magic", magic)):
        if needle not in code:
            raise ValueError(("the module differs from the regenerated " + what, needle))
    mult = re.findall(r"\(\*\s+(\S+)\s+(\S+)\)", code)
    two_var = [m for m in mult if not (re.fullmatch(r"-?\d+", m[0]) or re.fullmatch(r"-?\d+", m[1]))]
    return {"defns": len(defns), "maxParams": max(params.values()), "multiplications": len(mult), "multiplicationsOfTwoVariables": two_var,
            "codeLines": len([l for l in code.split("\n") if l.strip()]),
            "productBound": "every product has a literal factor <= 16777216 and a variable of at most 255 (colour channel), 128 (element index) or 4096 (slot): below 2^46"}


def second_decode(cases, records):
    """A separate host-side pass over the receipt: decode every region, rerun the reference, and count what was seen."""
    census = {"cases": len(cases), "opsTotal": 0, "opsMax": 0, "layoutRefused": 0, "drawStatus": {}, "rolesSeen": {}, "casesWithOps": 0, "casesWithBorders": 0,
              "distinctColours": set(), "handDerivedCases": 0}
    for c, rec in zip(cases, records):
        assert rec["name"] == c["name"], (rec["name"], c["name"])
        if rec["status"] != 0:
            census["layoutRefused"] += 1
            continue
        hdr, ops = D.decode(rec["region"], rec["nodes"])
        st, eops, _ = D.expected(c, rec["table"])
        assert (hdr["status"], ops) == (st, eops), c["name"]
        census["drawStatus"][str(st)] = census["drawStatus"].get(str(st), 0) + 1
        census["opsTotal"] += len(ops)
        census["opsMax"] = max(census["opsMax"], len(ops))
        census["casesWithOps"] += 1 if ops else 0
        census["casesWithBorders"] += 1 if any(o[1] for o in ops) else 0
        census["handDerivedCases"] += 1 if c.get("ops") is not None else 0
        for o in ops:
            census["rolesSeen"][str(o[1])] = census["rolesSeen"].get(str(o[1]), 0) + 1
            census["distinctColours"].add(o[6])
    census["distinctColours"] = len(census["distinctColours"])
    return census


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
    ap.add_argument("--reuse-baseline", type=Path, help="an existing builder output of profile draw (skips that build)")
    ap.add_argument("--reuse-layout", type=Path, help="an existing builder output of profile layout (the whole-image delta); built when absent")
    ap.add_argument("--skip-mutants", action="store_true")
    args = ap.parse_args()
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise ValueError("requires native macOS ARM64")
    amu, full = args.amu.resolve(strict=True), args.amu_full_root.resolve(strict=True)
    if sha(amu) != args.amu_sha256 or sha(full) != args.amu_full_root_sha256:
        raise ValueError("Amu digest mismatch")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    receipt = {"status": "RUNNING", "amu": sha(amu), "amuFullRoot": sha(full)}
    cases = D.all_cases()
    receipt["inputs"] = {str(p.relative_to(LIB)): sha(p) for p in
                         [Path(__file__).resolve(), HERE / "draw_k_cases.py", HERE / "layout_k_cases.py", HERE / "style_k_cases.py", *MODS.values(),
                          AIUEOS / "os/aiueos/native/draw-entry.kotoba", AIUEOS / "os/aiueos/scripts/check-native-draw-qemu.py", G.BUILDER,
                          AIUEOS / "os/aiueos/scripts/build-native-kernel-macos.py"]}

    # 1. static audit
    receipt["audit"] = static_audit()
    # 2. reference self-test
    receipt["referenceSelfTest"] = {"handDerivedListsReproduced": D.selftest()}

    # 3. kernel
    base = args.reuse_baseline.resolve() if args.reuse_baseline else out / "kernel-baseline"
    if not args.reuse_baseline:
        code, tail, secs = G.run_builder(args, base, "draw")
        if code:
            raise ValueError(("the baseline kernel build or run failed", tail))
    kr = json.loads((base / "qemu/native-draw-qemu.json").read_text())
    if kr["status"] != "PASS_NATIVE_DRAW_K_QEMU" or len(kr["records"]) != len(cases) or kr["mismatches"]:
        raise ValueError("the baseline observer receipt is missing or not PASS")
    state = json.loads((base / "native-desktop-macos.json").read_text())
    kstate = json.loads((base / "kernel/build-state.json").read_text())
    if kstate["sourceModuleCount"] != EXPECTED_MODULES:
        raise ValueError(("module count", kstate["sourceModuleCount"]))
    census = second_decode(cases, kr["records"])
    for need in ("0", "18", "20", "21"):
        if need not in census["drawStatus"]:
            raise ValueError(("the grid never reached the draw status", need))
    if set(census["rolesSeen"]) != {"0", "1", "2", "3", "4"}:
        raise ValueError(("the grid never emitted every role", census["rolesSeen"]))
    receipt["census"] = census
    receipt["kernel"] = {"profile": "draw", "state": state["state"], "target": "x86_64-aiueos-kernel-v3", "cases": len(cases),
                         "handDerived": census["handDerivedCases"], "textSegmentBytes": state["textMargin"]["textSegmentBytes"],
                         "compilerCapBytes": state["textMargin"]["compilerCapBytes"], "estimatedMarginBytes": state["textMargin"]["estimatedMarginBytes"],
                         "sourceModuleCount": kstate["sourceModuleCount"], "kernelSha256": kstate["kernel"]["sha256"],
                         "cssomModulesLocked": sorted(m for m in kstate["sourceGraph"] if "/cssom/" in m)}

    # 4. negative controls (two builds at a time)
    receipt["mutants"] = []
    if not args.skip_mutants:
        text0 = MOD.read_text()
        for name, anchor, repl in MUTANTS:
            if text0.count(anchor) != 1:
                raise ValueError(("mutation anchor must occur exactly once", name, text0.count(anchor)))

        def mutant(item):
            idx, (name, anchor, repl) = item
            mdir = out / "mutants" / ("m%02d" % idx)
            mdir.mkdir(parents=True)
            for p in sorted(SRC.glob("*.kotoba")):
                shutil.copyfile(p, mdir / p.name)
            (mdir / "draw_k.kotoba").write_text(text0.replace(anchor, repl))
            odir = out / ("kernel-mutant-%02d" % idx)
            code, tail, secs = G.run_builder(args, odir, "draw", env_extra={"AIUEOS_CSSOM_K_SOURCE_PATH": str(mdir)})
            rp = odir / "qemu/native-draw-qemu.json"
            mr = json.loads(rp.read_text()) if rp.is_file() else None
            if code == 0 or (mr is not None and mr["status"] != "FAIL_NATIVE_DRAW_K_QEMU"):
                raise ValueError(("the mutant was not seen by the observer", name, code, tail[-400:]))
            if mr is None and not (odir / "kernel/build-state.json").is_file():
                raise ValueError(("the mutant did not build, so it was not run", name, tail[-400:]))
            differing = [m[0] for m in mr["mismatches"]] if mr is not None else None
            return {"name": name, "anchor": anchor, "replacement": repl, "builderExit": code,
                    "observerReceipt": mr["status"] if mr else "no receipt (the guest did not finish or the build failed)",
                    "casesDifferingFromReference": len(differing) if differing is not None else None,
                    "firstDifferences": (differing or [])[:4], "seconds": round(secs, 1), "builderTail": tail[-300:] if mr is None else None}
        receipt["mutants"] = list(ThreadPoolExecutor(max_workers=2).map(mutant, enumerate(MUTANTS)))

    # 5. sizes and the user-v1 verdict
    comp = G.AiueosCompiler(full, out / "aiueos")
    ik_req, ik_body = G.ENTRIES["intern_k"]
    ik_entry = "(ns e (:require %s) (:export [main]))\n(defn main [w :i64 n :i64] :i64 %s)\n" % (ik_req, ik_body)
    dk_entry = "(ns e (:require %s %s) (:export [main]))\n(defn main [w :i64 n :i64] :i64 (+ %s %s))\n" % (ik_req, DRAW_ENTRY[1], ik_body, DRAW_ENTRY[2])
    src, kept0, total0 = G.reachable(G.bundle(ik_entry))
    r0 = comp.compile("cum-intern", src, "x86_64-aiueos-kernel-v1")
    src, kept1, total1 = G.reachable(G.bundle(dk_entry))
    r1 = comp.compile("cum-intern-draw", src, "x86_64-aiueos-kernel-v1")
    if not (r0["ok"] and r1["ok"]):
        raise ValueError(("kernel-v1 compile failed", r0["output"], r1["output"]))
    lines = receipt["audit"]["codeLines"]
    receipt["sizeKernelV1"] = {"internClosureTextBytes": r0["textBytes"], "internPlusDrawTextBytes": r1["textBytes"],
                               "drawModuleTextBytes": r1["textBytes"] - r0["textBytes"], "functionsReachedAdded": kept1 - kept0,
                               "drawCodeLines": lines, "bytesPerCodeLine": round((r1["textBytes"] - r0["textBytes"]) / lines, 1), "sourceSha256": r1["sourceSha256"]}
    # the layout closure plus draw_k in ONE kernel-v1 object, recorded as it comes
    src, _, _ = G.reachable(G.bundle(entry_for(False)))
    rl = comp.compile("cum-layout", src, "x86_64-aiueos-kernel-v1")
    src, _, _ = G.reachable(G.bundle(entry_for(True)))
    rc = comp.compile("cum-layout-draw", src, "x86_64-aiueos-kernel-v1")
    receipt["sizeKernelV1"]["layoutClosureAlone"] = {"ok": rl["ok"], "textBytes": rl.get("textBytes"), "output": rl["output"][:200]}
    receipt["sizeKernelV1"]["layoutClosurePlusDrawInOneObject"] = {"ok": rc["ok"], "textBytes": rc.get("textBytes"), "output": rc["output"][:300],
                                                                  "note": "recorded as it comes: whether the two closures fit one kernel-v1 object"}
    ldir = args.reuse_layout.resolve() if args.reuse_layout else out / "kernel-layout"
    if not args.reuse_layout:
        code, tail, secs = G.run_builder(args, ldir, "layout")
        if code:
            raise ValueError(("the layout profile build failed", tail))
    lstate = json.loads((ldir / "native-desktop-macos.json").read_text())
    receipt["wholeImage"] = {"drawTextSegmentBytes": state["textMargin"]["textSegmentBytes"], "layoutTextSegmentBytes": lstate["textMargin"]["textSegmentBytes"],
                             "delta": state["textMargin"]["textSegmentBytes"] - lstate["textMargin"]["textSegmentBytes"],
                             "drawEstimatedMarginBytes": state["textMargin"]["estimatedMarginBytes"], "compilerCapBytes": state["textMargin"]["compilerCapBytes"],
                             "drawKernelSha256": kstate["kernel"]["sha256"], "note": "the draw profile also carries the entry's dump glue; the delta is module + glue"}
    user = {}
    for zero in (False, True):
        src, _, _ = G.reachable(G.bundle(entry_for(True, zero)))
        res = comp.compile("user-draw-%s" % ("zero" if zero else "two"), src, "x86_64-aiueos-user-v1")
        if res["ok"]:
            raise ValueError("user-v1 unexpectedly accepted region code")
        user["%s-argument-entry" % ("0" if zero else "2")] = {"error": res.get("error"), "message": res.get("message"), "detail": res.get("detail"), "output": res["output"]}
    receipt["userV1"] = user
    receipt["status"] = "PASS_NATIVE_CSSOM_DRAW_K"
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(receipt["status"], len(cases), "cases", census["opsTotal"], "ops", len(receipt["mutants"]), "mutants seen")
    print(json.dumps({k: receipt[k] for k in ("audit", "referenceSelfTest", "census", "sizeKernelV1", "wholeImage", "kernel", "mutants")}, indent=2))


if __name__ == "__main__":
    main()
