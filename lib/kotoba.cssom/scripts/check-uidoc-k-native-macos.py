#!/usr/bin/env python3
"""Observe the UI-document front end of the CSSOM render chain (JUN-856, ADR-0287) with native tools only: no JVM, nbb or babashka.

The slice: a compact UI document in a region (src/cssom/uidoc_k.kotoba, kernel-dialect region code; the layout is a PROPOSAL documented in
90-docs/evidence/cssom-uidoc-slice-20261107/README.md) becomes the wire stream of the style slice; the existing style, layout and draw slices then run on
it unchanged, so the full chain is document -> style -> layout -> draw list. The independent host side is scripts/uidoc_k_cases.py: its own encoder,
its own reference decoder `ref_expand`, the canonical wire encoder of style_k_cases, and (from draw_k_cases) the cascade, colour parser and Appendix E
ordering that check the draw list on the kernel's own box table.

What this gate does:

  1. STATIC AUDIT of uidoc_k: at most five parameters per function, no floats, strings, records, `/` or `rem`; the magic is regenerated here and
     compared; every multiplication is listed.
  2. REFERENCE SELF-TEST: the reference decodes every case as the case table says (refusals carry hand-written statuses), an expanding document equals the
     canonical wire stream byte for byte, and the reference reproduces the hand-derived draw list of the tokei window from its hand-derived box table.
  3. KERNEL: the module runs on x86_64-aiueos-kernel-v3 under QEMU TCG (profile `uidoc` of build-native-desktop-macos.py, observer
     os/aiueos/scripts/check-native-uidoc-qemu.py). Every case runs the expanded stream (path A) and the canonical stream (path B, the existing input of
     the draw gate) through the same kernel; the observer compares the front end with the reference, the stream byte for byte, A with B, and the draw list
     with the reference on the kernel's own box table. This gate decodes the receipt AGAIN on the host and reports the census.
  4. NEGATIVE CONTROLS: one rebuilt mutant per behaviour (one line changed, the anchor occurs exactly once) is built into a kernel and run through the same
     observer; it must be seen (observer FAIL or no receipt because the guest did not finish), never silently pass. At most two builds run at a time.
  5. SIZE: kernel-v1 text bytes of the module alone and in one object with the layout and draw closures, the kernel-v3 whole-image text segment of the
     `uidoc` profile against the `draw` profile built in the same run, the estimated margin below the compiler cap, and the verdict of x86_64-aiueos-user-v1.

It does not claim CPL3 execution, a mapped (separate) UI-document region, a wired browser.surface, text or images, the style attribute, or a verdict
against a browser. The document region is the two free pages of the owned window that the draw list reuses afterwards.
"""
import argparse
import os
import signal
import subprocess
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
import uidoc_k_cases as U  # noqa: E402

SRC, LIB, AIUEOS = G.SRC, G.LIB, G.AIUEOS
MOD = SRC / "uidoc_k.kotoba"
MODS = {s: SRC / (s + ".kotoba") for s in ["uidoc_k", "draw_k"] + LG.STEMS + ["intern_k", "selector_k", "match_k", "cascade_k"]}
EXPECTED_MODULES = 64        # draw 63 (62 + native/update links aiueos.imgsig-prodkeys, JUN-813 amendment 7) + cssom.uidoc-k

# one line per behaviour; each anchor must occur exactly once in uidoc_k.kotoba. No mutant may loop: a hang would wait for the observer's timeout.
MUTANTS = [
    ("the magic's last byte is 50", "(= (ib st 3) 49)", "(= (ib st 3) 50)"),
    ("the section sum ignores the tree length", "(not (= (+ 12 (+ s (+ g t))) dlen))", "(not (= (+ 12 (+ s g)) dlen))"),
    ("more than 256 strings are allowed", "(> n 255)", "(> n 256)"),
    ("the document region is 8193 bytes", "(> dlen 8192)", "(> dlen 8193)"),
    ("a string table with slack after its entries is accepted", "(if (not (= (tbl-end st gs n) ts)) -31", "(if (< (tbl-end st gs n) 0) -31"),
    ("string index N + 1 is accepted", "(> idx (hd st 73))", "(> idx (+ (hd st 73) 1))"),
    ("the string walk skips one byte too few", "(walk st (+ pos (+ 1 (ib st pos))) (- k 1))", "(walk st (+ pos (ib st pos)) (- k 1))"),
    ("the id operand is read from the tag's position", "ip (if (= hi 1) (sp-of st (ib st (+ pos 2))) -1)", "ip (if (= hi 1) (sp-of st (ib st (+ pos 1))) -1)"),
    ("the class operand is read from the id's position", "kp (if (= hk 1) (sp-of st (ib st (+ pos (+ 2 hi)))) -1)", "kp (if (= hk 1) (sp-of st (ib st (+ pos 2))) -1)"),
    ("an element record starts with F", "(ob! st dst 69)", "(ob! st dst 70)"),
    ("the close marker is a dot", "(ob! st dst 47)", "(ob! st dst 46)"),
    ("the sheet terminator is 1", "e (ob! st s 0)", "e (ob! st s 1)"),
    ("a text op advances two bytes", "(defn- adv [b] (if (= b 64) 3", "(defn- adv [b] (if (= b 64) 2"),
    ("an unclosed tree is accepted", "(if (= depth 0) (+ dst (+ 1 (* 0 (ob! st dst 0)))) -35)", "(if (>= depth 0) (+ dst (+ 1 (* 0 (ob! st dst 0)))) -35)"),
    ("text outside the root is accepted", "(defn- text-dst [st pos dst depth]\n  (if (= depth 0) -35", "(defn- text-dst [st pos dst depth]\n  (if (= depth -1) -35"),
    ("text bytes count one per node", "(hd! st 75 (+ (hd st 75) n))", "(hd! st 75 (+ (hd st 75) 1))"),
    ("text nodes count two each", "(hd! st 74 (+ (hd st 74) 1))", "(hd! st 74 (+ (hd st 74) 2))"),
    ("the element limit is three bytes lower (the exact 16384-byte stream is refused)", "(if (> (+ dst n) 16383) -34", "(if (> (+ dst n) 16380) -34"),
    ("the element limit is gone (a far over-long stream is written past the window)", "(if (> (+ dst n) 16383) -34", "(if (> (+ dst n) 99999) -34"),
    ("the close limit is one byte higher (the 16385-byte stream is accepted)", "(if (> (+ dst 1) 16383) -34", "(if (> (+ dst 1) 16384) -34"),
]
# names of draw_k, uidoc_k and the layout closure, for the cumulative kernel-v1 size
DRAW_ENTRY = ("draw_k", "[cssom.draw-k :as dk]", "(+ (dk/dk-run w n) (dk/dk-word w n 1 2))")
UIDOC_ENTRY = ("uidoc_k", "[cssom.uidoc-k :as ud]", "(+ (ud/ud-run w n 100) (ud/ud-word w n 2))")


def sha(p):
    return G.sha(p)


def run_builder_timeout(args, output, profile, env_extra, limit=480):
    """G.run_builder with a wall-clock limit: a mutant whose guest stops (a fault, a halt) leaves the observer waiting, so the whole process group is
    killed after `limit` seconds and the run is reported as exit 124."""
    cmd = [sys.executable, "-I", str(G.BUILDER), "--amu-source", str(args.amu_source), "--owner-repo-root", str(args.owner_repo_root),
           "--qemu", str(args.qemu), "--qemu-sha256", args.qemu_sha256, "--firmware", str(args.firmware), "--firmware-sha256", args.firmware_sha256,
           "--profile", profile, "--output", str(output)]
    env = {"PATH": "/usr/bin:/bin:/opt/homebrew/bin", "LANG": "C"}
    env.update(env_extra or {})
    started = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=AIUEOS, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=limit)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, _ = proc.communicate()
        code = 124
        out = b"TIMEOUT after %d s (the guest stopped before the marker)\n" % limit + out
    return code, out.decode(errors="replace")[-1500:], time.monotonic() - started


def entry_for(include_draw, include_uidoc=False, zero=False):
    ents = list(LG.ENTRIES) + ([DRAW_ENTRY] if include_draw else []) + ([UIDOC_ENTRY] if include_uidoc else [])
    req = " ".join([LG.BASE[0]] + [e[1] for e in ents])
    body = LG.BASE[1]
    for e in ents:
        body = "(+ %s %s)" % (body, e[2])
    if zero:
        return "(ns e (:require %s) (:export [main]))\n(defn main [] :i64 (let [w 0 n 0] %s))\n" % (req, body)
    return "(ns e (:require %s) (:export [main]))\n(defn main [w :i64 n :i64] :i64 %s)\n" % (req, body)


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
    magic_ok = all(("(= (ib st %d) %d)" % (i, v)) in code for i, v in enumerate(U.MAGIC))
    if not magic_ok:
        raise ValueError(("the module differs from the regenerated magic", U.MAGIC))
    mult = re.findall(r"\(\*\s+(\S+)\s+(\S+)\)", code)
    two_var = [m for m in mult if not (re.fullmatch(r"-?\d+", m[0]) or re.fullmatch(r"-?\d+", m[1]))]
    return {"defns": len(defns), "maxParams": max(params.values()), "multiplications": len(mult), "multiplicationsOfTwoVariables": two_var,
            "codeLines": len([l for l in code.split("\n") if l.strip()]),
            "productBound": "every product has a literal factor (4, 256 or 0) and a variable of at most 255 (an input byte) or 8192 (an offset): below 2^46"}


def second_decode(cases, records):
    """A separate host-side pass over the receipt: rerun the front-end reference, decode every draw region and count what was seen."""
    census = {"cases": len(cases), "expanded": 0, "frontEndStatus": {}, "layoutRefused": 0, "layoutStatus": {}, "drawStatus": {}, "opsTotal": 0, "opsMax": 0,
              "rolesSeen": {}, "distinctColours": set(), "handDerivedCases": 0, "textNodes": 0, "textBytes": 0, "pathsEqual": 0, "apps": {}}
    for c, rec in zip(cases, records):
        assert rec["name"] == c["name"], (rec["name"], c["name"])
        st, wire, tx, tb = U.ref_expand(c["blob"])
        assert rec["front"] == st, (c["name"], rec["front"], st)
        if st < 0:
            census["frontEndStatus"][str(st)] = census["frontEndStatus"].get(str(st), 0) + 1
            assert rec["a"] is None and rec["b"] is None
            continue
        census["expanded"] += 1
        assert (rec["texts"], rec["textBytes"]) == (tx, tb)
        census["textNodes"] += tx
        census["textBytes"] += tb
        a = rec["a"]
        assert rec["b"] == "equal to a" or rec["b"] == a, c["name"]
        census["pathsEqual"] += 1
        census["layoutStatus"][str(a["status"])] = census["layoutStatus"].get(str(a["status"]), 0) + 1
        if a["status"] != 0:
            census["layoutRefused"] += 1
            continue
        hdr, ops = D.decode(a["region"], a["nodes"])
        dst, eops, _ = D.expected(c, a["table"])
        assert (hdr["status"], ops) == (dst, eops), c["name"]
        census["drawStatus"][str(dst)] = census["drawStatus"].get(str(dst), 0) + 1
        census["opsTotal"] += len(ops)
        census["opsMax"] = max(census["opsMax"], len(ops))
        census["handDerivedCases"] += 1 if c.get("ops") is not None else 0
        for o in ops:
            census["rolesSeen"][str(o[1])] = census["rolesSeen"].get(str(o[1]), 0) + 1
            census["distinctColours"].add(o[6])
        if c["name"].startswith("uidoc-app-"):
            census["apps"][c["name"][10:]] = {"elements": a["nodes"], "ops": len(ops), "documentHeightPx": a["dh"] / 64, "compactBytes": len(c["blob"]),
                                              "wireBytes": len(wire), "textNodes": tx, "textBytes": tb, "drawStatus": dst}
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
    ap.add_argument("--reuse-baseline", type=Path, help="an existing builder output of profile uidoc (skips that build)")
    ap.add_argument("--reuse-draw", type=Path, help="an existing builder output of profile draw (the whole-image delta); built when absent")
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
    cases = U.all_cases()
    receipt["inputs"] = {str(p.relative_to(LIB)): sha(p) for p in
                         [Path(__file__).resolve(), HERE / "uidoc_k_cases.py", HERE / "draw_k_cases.py", HERE / "layout_k_cases.py", HERE / "style_k_cases.py", *MODS.values(),
                          AIUEOS / "os/aiueos/native/uidoc-entry.kotoba", AIUEOS / "os/aiueos/scripts/check-native-uidoc-qemu.py", G.BUILDER,
                          AIUEOS / "os/aiueos/scripts/build-native-kernel-macos.py", U.INDEX_HTML]}

    # 1. static audit
    receipt["audit"] = static_audit()
    # 2. reference self-test (also runs the draw reference's own hand-derived lists)
    receipt["referenceSelfTest"] = {"uidoc": U.selftest(), "drawHandDerivedListsReproduced": D.selftest()}

    # 3. kernel
    base = args.reuse_baseline.resolve() if args.reuse_baseline else out / "kernel-baseline"
    if not args.reuse_baseline:
        code, tail, secs = G.run_builder(args, base, "uidoc")
        if code:
            raise ValueError(("the baseline kernel build or run failed", tail))
    kr = json.loads((base / "qemu/native-uidoc-qemu.json").read_text())
    if kr["status"] != "PASS_NATIVE_UIDOC_K_QEMU" or len(kr["records"]) != len(cases) or kr["mismatches"]:
        raise ValueError("the baseline observer receipt is missing or not PASS")
    state = json.loads((base / "native-desktop-macos.json").read_text())
    kstate = json.loads((base / "kernel/build-state.json").read_text())
    if kstate["sourceModuleCount"] != EXPECTED_MODULES:
        raise ValueError(("module count", kstate["sourceModuleCount"]))
    census = second_decode(cases, kr["records"])
    for need in ("-30", "-31", "-32", "-33", "-34", "-35"):
        if need not in census["frontEndStatus"]:
            raise ValueError(("the grid never reached the front-end status", need))
    for need in ("0", "20"):
        if need not in census["drawStatus"]:
            raise ValueError(("the grid never reached the draw status", need))
    if set(census["rolesSeen"]) != {"0", "1", "2", "3", "4"}:
        raise ValueError(("the grid never emitted every role", census["rolesSeen"]))
    if set(census["apps"]) != set(U.APPS):
        raise ValueError(("not every dapp window ran the whole chain", sorted(set(U.APPS) - set(census["apps"]))))
    receipt["census"] = census
    receipt["kernel"] = {"profile": "uidoc", "state": state["state"], "target": "x86_64-aiueos-kernel-v3", "cases": len(cases),
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
            (mdir / "uidoc_k.kotoba").write_text(text0.replace(anchor, repl))
            odir = out / ("kernel-mutant-%02d" % idx)
            code, tail, secs = run_builder_timeout(args, odir, "uidoc", {"AIUEOS_CSSOM_K_SOURCE_PATH": str(mdir)})
            rp = odir / "qemu/native-uidoc-qemu.json"
            mr = json.loads(rp.read_text()) if rp.is_file() else None
            if code == 0 or (mr is not None and mr["status"] != "FAIL_NATIVE_UIDOC_K_QEMU"):
                raise ValueError(("the mutant was not seen by the observer", name, code, tail[-400:]))
            if mr is None and not (odir / "kernel/build-state.json").is_file():
                raise ValueError(("the mutant did not build, so it was not run", name, tail[-400:]))
            differing = [m[0] for m in mr["mismatches"]] if mr is not None else None
            res = {"name": name, "anchor": anchor, "replacement": repl, "builderExit": code,
                   "observerReceipt": mr["status"] if mr else ("no receipt: killed after the time limit, the guest stopped" if code == 124 else "no receipt (the guest did not finish or the observer could not parse the console)"),
                   "casesDifferingFromReference": len(differing) if differing is not None else None,
                   "firstDifferences": (differing or [])[:4], "seconds": round(secs, 1), "builderTail": tail[-300:] if mr is None else None}
            shutil.rmtree(odir, ignore_errors=True)          # disk is tight: the receipt fields above are what is kept
            return res
        receipt["mutants"] = list(ThreadPoolExecutor(max_workers=2).map(mutant, enumerate(MUTANTS)))

    # 5. sizes and the user-v1 verdict
    comp = G.AiueosCompiler(full, out / "aiueos")
    ud_entry = "(ns e (:require %s) (:export [main]))\n(defn main [w :i64 n :i64] :i64 %s)\n" % (UIDOC_ENTRY[1], UIDOC_ENTRY[2])
    src, kept, total = G.reachable(G.bundle(ud_entry))
    r1 = comp.compile("uidoc-alone", src, "x86_64-aiueos-kernel-v1")
    if not r1["ok"]:
        raise ValueError(("kernel-v1 compile failed", r1["output"]))
    lines = receipt["audit"]["codeLines"]
    receipt["sizeKernelV1"] = {"uidocModuleAloneTextBytes": r1["textBytes"], "functionsReached": kept, "uidocCodeLines": lines,
                               "bytesPerCodeLine": round(r1["textBytes"] / lines, 1), "sourceSha256": r1["sourceSha256"]}
    src, _, _ = G.reachable(G.bundle(entry_for(True, False)))
    rd = comp.compile("cum-layout-draw", src, "x86_64-aiueos-kernel-v1")
    src, _, _ = G.reachable(G.bundle(entry_for(True, True)))
    rc = comp.compile("cum-layout-draw-uidoc", src, "x86_64-aiueos-kernel-v1")
    receipt["sizeKernelV1"]["layoutPlusDrawInOneObject"] = {"ok": rd["ok"], "textBytes": rd.get("textBytes"), "output": rd["output"][:200]}
    receipt["sizeKernelV1"]["layoutPlusDrawPlusUidocInOneObject"] = {"ok": rc["ok"], "textBytes": rc.get("textBytes"), "output": rc["output"][:300],
                                                                    "note": "recorded as it comes: whether the closures fit one kernel-v1 object"}
    ddir = args.reuse_draw.resolve() if args.reuse_draw else out / "kernel-draw"
    if not args.reuse_draw:
        code, tail, secs = G.run_builder(args, ddir, "draw")
        if code:
            raise ValueError(("the draw profile build failed", tail))
    dstate = json.loads((ddir / "native-desktop-macos.json").read_text())
    receipt["wholeImage"] = {"uidocTextSegmentBytes": state["textMargin"]["textSegmentBytes"], "drawTextSegmentBytes": dstate["textMargin"]["textSegmentBytes"],
                             "delta": state["textMargin"]["textSegmentBytes"] - dstate["textMargin"]["textSegmentBytes"],
                             "uidocEstimatedMarginBytes": state["textMargin"]["estimatedMarginBytes"], "compilerCapBytes": state["textMargin"]["compilerCapBytes"],
                             "uidocKernelSha256": kstate["kernel"]["sha256"],
                             "note": "the uidoc profile also carries the entry's dump glue (two PATH dumps, the stream dump, the document loader); the delta is module + glue"}
    user = {}
    for zero in (False, True):
        src, _, _ = G.reachable(G.bundle(entry_for(True, True, zero)))
        res = comp.compile("user-uidoc-%s" % ("zero" if zero else "two"), src, "x86_64-aiueos-user-v1")
        if res["ok"]:
            raise ValueError("user-v1 unexpectedly accepted region code")
        user["%s-argument-entry" % ("0" if zero else "2")] = {"error": res.get("error"), "message": res.get("message"), "detail": res.get("detail"), "output": res["output"]}
    receipt["userV1"] = user
    receipt["status"] = "PASS_NATIVE_CSSOM_UIDOC_K"
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(receipt["status"], len(cases), "cases", census["opsTotal"], "ops", len(receipt["mutants"]), "mutants seen")
    print(json.dumps({k: receipt[k] for k in ("audit", "referenceSelfTest", "census", "sizeKernelV1", "wholeImage", "kernel", "mutants")}, indent=2))


if __name__ == "__main__":
    main()
