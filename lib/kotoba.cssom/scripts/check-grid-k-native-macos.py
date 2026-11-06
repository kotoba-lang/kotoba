#!/usr/bin/env python3
"""Observe the grid track sizing and table column width slice of the CSSOM (JUN-932 part 2, JUN-920, ADR-0287) with native tools only:
no JVM, nbb or babashka.

The slice: layout.cljk track-sizes (fixed, fr, minmax(px, px), minmax(px, Nfr), auto; the equal-share growth with caps; the stretch of
auto tracks), distribute-fr, grid-track-intrinsics (single-track items) and span-width, as src/cssom/grid_k.kotoba; and
table-column-widths, table-fixed-column-widths, distribute-excess and the caption widening of layout-table as src/cssom/table_k.kotoba.
Both are kernel-dialect REGION code over bounded tables in one 61440-byte owned window (16 tracks, 32 items, 16 columns, 64 cells).

What this gate does:

  1. STATIC AUDIT of the two region modules: at most five parameters per function, no floats, strings, records, `/` or `rem`.
  2. MODELS: grid_k_cases.py holds an exact integer model and an f64 model of the source (independent of the region modules); the 25
     hand-derived expectations (written from the CSS text and the docstrings of layout.cljk) must equal the exact model.
  3. REFERENCE: the host-native f64 transcriptions src/cssom/grid_ref.kotoba and table_ref.kotoba run every accepted case (a native Amu
     compile and run per case); each result must equal the f64 model's, and where the case has no tie the exact model's.
  4. KERNEL: the region modules run on x86_64-aiueos-kernel-v3 under QEMU TCG (profile `grid` of build-native-desktop-macos.py,
     observer os/aiueos/scripts/check-native-grid-qemu.py): every case of the grid, one case on each side of every bound, the
     refusals. The kernel must equal the exact model on every case (observer), and the reference except at exact ties.
  5. TIE REPORT: every case where kernel and reference differ is listed with the step; each must be an exact-integer quotient that
     the double evaluation puts one below (anything else fails the gate).
  6. NEGATIVE CONTROLS: rebuilt mutants (one line changed per module, the anchor must occur exactly once) built into a kernel and run
     through the same observer; each must be seen by the observer and differ from the case table and the reference.
  7. SIZE: kernel-v1 text bytes per module (cumulative compile), the whole-image text segment against the imgsig profile, and the
     verdict of x86_64-aiueos-user-v1 with the exact error; a six-parameter function must be refused (E7102).

It does not claim CPL3 execution, a wired layout.cljk, or a browser verdict. The references transcribe layout.cljk; the original .cljk
could not be run here (see evidence/cssom-q6-slice2-20261106), so their fidelity rests on the hand-derived cases and the code read.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
OWNER = HERE.parent
LIB = OWNER.parent
SRC = OWNER / "src/cssom"
AIUEOS = LIB / "kotoba.aiueos"
BUILDER = AIUEOS / "os/aiueos/scripts/build-native-desktop-macos.py"

AMU_SHA256 = "e13a20548928cd366c78641edc944e36070f7c5dbbde8cc7c35ef599570e2b02"
AMU_FULL_ROOT_SHA256 = "88623412d4470e7090037ea6b35f2176e5d6edff322e90843b84bce61f17a229"

spec = importlib.util.spec_from_file_location("grid_k_cases", HERE / "grid_k_cases.py")
K = importlib.util.module_from_spec(spec)
spec.loader.exec_module(K)

STEMS = ["grid_k", "table_k"]
MODS = {s: SRC / (s + ".kotoba") for s in STEMS}
REFS = {"grid": ("cssom.grid-ref", SRC / "grid_ref.kotoba"), "table": ("cssom.table-ref", SRC / "table_ref.kotoba")}

# one line per mutant; each anchor must occur exactly once
MUTANTS = [
    ("grid: the fr share divides by W + 1", "grid_k", "(quot (* (gq st 7) wi) (gq st 4))", "(quot (* (gq st 7) wi) (+ (gq st 4) 1))"),
    ("grid: auto tracks stretch although an fr track competes", "grid_k", "(if (and (= (gw st 3) 1) (= hf 0))", "(if (= (gw st 3) 1)"),
    ("table: the colspan shortfall rounds down", "table_k", "(quot (+ short (- sp 1)) sp)", "(quot short sp)"),
    ("table: the surplus is shared over total + 1", "table_k", "(quot (* (gq st 6) v) tb)", "(quot (* (gq st 6) v) (+ tb 1))"),
]

# cumulative entries: a main reaching every export, two arguments (a window and its length)
ENTRIES = {
    "grid_k": ("[cssom.grid-k :as gk]", "(+ (gk/gk-run w n 8) (+ (gk/gk-sum w n) (gk/gk-count w n)))"),
    "table_k": ("[cssom.table-k :as tk]", "(+ (tk/tk-run w n 8) (+ (tk/tk-sum w n) (tk/tk-count w n)))"),
}

TOK = re.compile(r"[^\s()\[\]]+")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def strip_comments(t):
    return "\n".join(l.split(";;")[0].rstrip() for l in t.split("\n"))


# ---- bundling of the region modules into one source (the aiueos object compiler takes one file) ----
def requires(text):
    return {a: m for m, a in re.findall(r"\[cssom\.([\w-]+)\s+:as\s+([\w-]+)\]", text)}


def bundle(entry_text, src_dir=SRC, name="sty"):
    order, seen = [], set()

    def visit(stem):
        if stem in seen:
            return
        seen.add(stem)
        for dep in requires((src_dir / (stem + ".kotoba")).read_text()).values():
            visit(dep.replace("-", "_"))
        order.append(stem)
    for dep in requires(entry_text).values():
        visit(dep.replace("-", "_"))

    def rewrite(body, names, aliases):
        def sub(m):
            tok = m.group(0)
            if tok in names:
                return names[tok]
            if "/" in tok and not tok.startswith("/"):
                a, n = tok.split("/", 1)
                if a in aliases:
                    return aliases[a][n]
            return tok
        return TOK.sub(sub, body)
    defs, out = {}, ["(ns %s (:export [main]))" % name]
    for stem in order:
        text = (src_dir / (stem + ".kotoba")).read_text()
        body = strip_comments(text)
        body = body[body.index("(defn"):]
        own = {n: stem + "_" + n for n in re.findall(r"\(defn-?\s+(\S+)", body)}
        defs[stem] = own
        aliases = {a: defs[m.replace("-", "_")] for a, m in requires(text).items()}
        out.append(rewrite(body, own, aliases))
    ebody = strip_comments(entry_text)
    ebody = ebody[ebody.index("(defn"):]
    ealiases = {a: defs[m.replace("-", "_")] for a, m in requires(entry_text).items()}
    out.append(rewrite(ebody, {}, ealiases))
    return "\n".join(out) + "\n"


def entry_for(upto, zero=False):
    stems = STEMS[:STEMS.index(upto) + 1]
    req = " ".join(ENTRIES[s][0] for s in stems)
    body = ENTRIES[stems[0]][1]
    for s in stems[1:]:
        body = "(+ %s %s)" % (body, ENTRIES[s][1])
    if zero:
        return "(ns e (:require %s) (:export [main]))\n(defn main [] :i64 (let [w 0 n 0] %s))\n" % (req, body)
    return "(ns e (:require %s) (:export [main]))\n(defn main [w :i64 n :i64] :i64 %s)\n" % (req, body)


def reachable(src):
    """Keep only the functions main reaches: a function nothing calls has no rooted caller and is refused by the extent proof."""
    forms = re.split(r"\n(?=\(defn)", src)
    head, fs = forms[0], forms[1:]
    names = {re.match(r"\(defn-?\s+(\S+)", f).group(1): f for f in fs}
    keep, stack = set(), ["main"]
    while stack:
        n = stack.pop()
        if n in keep:
            continue
        keep.add(n)
        stack += [t for t in TOK.findall(names[n]) if t in names and t not in keep]
    return head + "\n" + "\n".join(f for f in fs if re.match(r"\(defn-?\s+(\S+)", f).group(1) in keep) + "\n", len(keep), len(fs)


class AiueosCompiler:
    def __init__(self, compiler, work):
        self.compiler, self.work = compiler, work

    def compile(self, name, source, target):
        d = self.work / (name + "-" + target)
        d.mkdir(parents=True, exist_ok=False)
        (d / "src.kotoba").write_text(source)
        fd = os.open(str(d), os.O_RDONLY | os.O_DIRECTORY)
        try:
            if fd != 3:
                os.dup2(fd, 3)
            env = {"PATH": "/usr/bin:/bin", "LANG": "C", "TMPDIR": str(d), "TMP": str(d), "TEMP": str(d)}
            r = subprocess.run([str(self.compiler), "compile", "src.kotoba", "--target", target, "--output", "object"],
                               cwd=str(d), env=env, pass_fds=(3,), capture_output=True, timeout=600)
        finally:
            if fd != 3:
                os.close(fd)
        text = (r.stdout + r.stderr).decode(errors="replace").strip()
        res = {"ok": r.returncode == 0, "output": text, "sourceSha256": hashlib.sha256(source.encode()).hexdigest()}
        m = re.search(r":text-bytes (\d+)", text)
        if m:
            res["textBytes"] = int(m.group(1))
        m = re.search(r"(E\d{4}) (.*?)(?:; detail (\d+))?$", text)
        if m and not res["ok"]:
            res["error"] = m.group(1)
            res["message"] = m.group(2)
            res["detail"] = int(m.group(3)) if m.group(3) else None
        return res


# ---- native host runs ----
class Native:
    def __init__(self, amu, out):
        self.amu, self.out = amu, out
        self.env = {"PATH": "/nonexistent", "LANG": "C"}

    def run(self, tag, entry_text, mods, entry_ns):
        d = self.out / tag
        d.mkdir(parents=True)
        entry = d / "entry.kotoba"
        entry.write_text(entry_text)
        paths = dict(mods)
        paths[entry_ns] = entry
        lock = d / "lock.ksl"
        lock.write_text("KSL2\nentry %s\n" % entry.resolve() + "".join("module %s %s\n" % (n, p.resolve()) for n, p in sorted(paths.items()))
                        + "".join("file %s %s\n" % (sha(p), p.resolve()) for p in sorted(set(p.resolve() for p in paths.values()))))
        binary = d / "bin"
        b = subprocess.run([str(self.amu), "compile", str(entry), "--source-lock", str(lock), "-o", str(binary)], cwd=OWNER, env=self.env,
                           capture_output=True, timeout=600)
        if b.returncode or b.stderr or not binary.is_file():
            raise RuntimeError(("native compile failed", tag, b.returncode, b.stdout[-300:], b.stderr[-300:]))
        r = subprocess.run([str(binary)], cwd=OWNER, env=self.env, capture_output=True, timeout=900)
        if r.returncode or r.stderr:
            return {"trap": r.returncode, "stderr": r.stderr[-200:].decode(errors="replace")}
        return int(r.stdout.decode().strip())


def static_audit():
    audit = {}
    forbidden = {"/", "rem", "mod", "record", "defrecord"}
    for stem in STEMS:
        text = MODS[stem].read_text()
        code = strip_comments(text)
        defns = re.findall(r"\(defn-?\s+(\S+)\s+\[([^\]]*)\]", code)
        params = {n: len([t for t in p.split() if not t.startswith(":")]) for n, p in defns}
        too_many = [n for n, c in params.items() if c > 5]
        if too_many:
            raise ValueError(("more than five parameters", stem, too_many))
        tokens = TOK.findall(code)
        bad = sorted({t for t in tokens if t in forbidden or t.startswith("f64") or t.startswith("f32") or t.startswith("string-")
                      or t.startswith("record-") or t.startswith("document-") or t.startswith("typed-") or t.startswith('"')})
        if bad:
            raise ValueError(("forbidden form in a region module", stem, bad))
        mult = re.findall(r"\(\*\s+(\S+)\s+(\S+)\)", code)
        two_var = [m for m in mult if not (re.fullmatch(r"-?\d+", m[0]) or re.fullmatch(r"-?\d+", m[1]))]
        audit[stem] = {"defns": len(defns), "maxParams": max(params.values()), "multiplications": len(mult),
                       "multiplicationsOfTwoVariables": len(two_var), "codeLines": len([l for l in code.split("\n") if l.strip()])}
    return audit


def pmap(fn, items, jobs):
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        return list(ex.map(fn, items))


def run_builder(args, output, profile="grid", env_extra=None):
    cmd = [sys.executable, "-I", str(BUILDER), "--amu-source", str(args.amu_source), "--owner-repo-root", str(args.owner_repo_root),
           "--qemu", str(args.qemu), "--qemu-sha256", args.qemu_sha256, "--firmware", str(args.firmware),
           "--firmware-sha256", args.firmware_sha256, "--profile", profile, "--output", str(output)]
    env = {"PATH": "/usr/bin:/bin:/opt/homebrew/bin", "LANG": "C"}
    env.update(env_extra or {})
    started = time.monotonic()
    r = subprocess.run(cmd, cwd=AIUEOS, env=env, capture_output=True, timeout=7200)
    return r.returncode, (r.stdout + r.stderr).decode(errors="replace")[-1500:], time.monotonic() - started


def read_receipt(output):
    path = Path(output) / "qemu" / "native-grid-qemu.json"
    return json.loads(path.read_text()) if path.is_file() else None


def f64_expect(c):
    ties = K.Ties()
    r = K.model(c["words"], c["kind"], "f64", ties)
    return r, ties.log


def compare(cases, receipt, ref):
    """Disagreements between the kernel records and the exact model (the table) and, for the cases the reference ran, the reference."""
    table, against_ref = [], []
    for c, rec in zip(cases, receipt["records"]):
        assert rec["name"] == c["name"], (rec["name"], c["name"])
        e = K.expected(c)
        if e[0] < 0:
            ok = rec["status"] == -e[0]
        else:
            outs = K.model(c["words"], c["kind"], "exact")[0]
            ok = rec["status"] == 0 and (rec["count"], rec["hash"], rec["sum"]) == (len(outs), e[1], e[2])
        if not ok:
            table.append(c["name"])
        r = ref.get(c["name"])
        if isinstance(r, int) and not (rec["status"] == 0 and rec["hash"] == r):
            against_ref.append((c["name"], rec["status"], rec["hash"], r))
    return table, against_ref


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--amu", type=Path, required=True, help="amu-cli.macho (native macOS arm64)")
    ap.add_argument("--amu-sha256", default=AMU_SHA256)
    ap.add_argument("--amu-full-root", type=Path, required=True, help="amu-full-root.macho (the --target compiler)")
    ap.add_argument("--amu-full-root-sha256", default=AMU_FULL_ROOT_SHA256)
    ap.add_argument("--amu-source", type=Path, required=True, help="the Amu checkout the desktop builder uses")
    ap.add_argument("--owner-repo-root", type=Path, required=True)
    ap.add_argument("--qemu", type=Path, required=True)
    ap.add_argument("--qemu-sha256", required=True)
    ap.add_argument("--firmware", type=Path, required=True)
    ap.add_argument("--firmware-sha256", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--reuse-baseline", type=Path, help="an existing builder output of profile grid (skips the baseline build)")
    ap.add_argument("--reuse-imgsig", type=Path, help="an existing builder output of profile imgsig (skips that build)")
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
                         [Path(__file__).resolve(), HERE / "grid_k_cases.py", *MODS.values(), *[r[1] for r in REFS.values()],
                          AIUEOS / "os/aiueos/native/grid-entry.kotoba", AIUEOS / "os/aiueos/scripts/check-native-grid-qemu.py", BUILDER]}

    # 1. static audit
    receipt["audit"] = static_audit()

    # 2. models: the hand-derived expectations equal the exact model; the accepted/refused status of every case is the table's
    hand = 0
    for c in cases:
        e = K.expected(c)
        if e[0] != c["status"]:
            raise ValueError(("the exact model disagrees with the case status", c["name"], e[0], c["status"]))
        if c["expect"] is not None:
            if K.model(c["words"], c["kind"], "exact")[0] != c["expect"]:
                raise ValueError(("the exact model disagrees with a hand-derived expectation", c["name"]))
            hand += 1
    receipt["models"] = {"cases": len(cases), "handDerived": hand, "refusals": sum(1 for c in cases if c["status"] != 0),
                         "grid": sum(1 for c in cases if c["kind"] == "grid"), "table": sum(1 for c in cases if c["kind"] == "table")}

    # 3. references: the native f64 transcriptions
    nat = Native(amu, out / "native")
    run_ids = [c for c in cases if c["status"] == 0]

    def ref_case(c):
        ns, path = REFS[c["kind"]]
        edn = "[" + " ".join(str(x) for x in c["words"]) + "]"
        entry = '(ns ent (:require [%s :as r]) (:export [main]))\n(defn main [] :i64 (r/run (document-edn-read "%s")))\n' % (ns, edn)
        return nat.run("ref-" + c["name"], entry, {ns: path}, "ent")
    started = time.monotonic()
    ref = dict(zip([c["name"] for c in run_ids], pmap(ref_case, run_ids, args.jobs)))
    receipt["reference"] = {"cases": len(ref), "seconds": round(time.monotonic() - started, 1)}
    traps = [(n, r) for n, r in ref.items() if not isinstance(r, int)]
    if traps:
        raise ValueError(("the reference trapped", traps[:5]))
    ties_total, tie_cases = 0, []
    for c in run_ids:
        f64res, log = f64_expect(c)
        exact = K.model(c["words"], c["kind"], "exact")
        if K.hash_out(f64res[0]) != ref[c["name"]]:
            raise ValueError(("the native f64 reference differs from the f64 model", c["name"], ref[c["name"]], K.hash_out(f64res[0])))
        if c["expect"] is not None and not log and f64res[0] != c["expect"]:
            raise ValueError(("the f64 model disagrees with a hand-derived expectation", c["name"]))
        ties_total += len(log)
        if log:
            tie_cases.append((c, exact, f64res, log))
    receipt["reference"]["equalToF64Model"] = len(ref)
    receipt["reference"]["tieSteps"] = ties_total

    # 4. kernel: baseline build and QEMU run (the imgsig control image is built alongside)
    base = args.reuse_baseline.resolve() if args.reuse_baseline else out / "kernel-baseline"
    imgsig = args.reuse_imgsig.resolve() if args.reuse_imgsig else out / "kernel-imgsig"
    jobs = []
    if not args.reuse_baseline:
        jobs.append(("baseline", base, "grid", None))
    if not args.reuse_imgsig:
        jobs.append(("imgsig", imgsig, "imgsig", None))
    if not args.skip_mutants:
        for name, stem, anchor, repl in MUTANTS:
            text0 = MODS[stem].read_text()
            if text0.count(anchor) != 1:
                raise ValueError(("mutation anchor must occur exactly once", name, text0.count(anchor)))
            mdir = out / "mutants" / (stem + "-" + str(MUTANTS.index((name, stem, anchor, repl))))
            mdir.mkdir(parents=True)
            for s in STEMS:
                shutil.copyfile(MODS[s], mdir / (s + ".kotoba"))
            (mdir / (stem + ".kotoba")).write_text(text0.replace(anchor, repl))
            jobs.append((name, out / ("kernel-mutant-" + mdir.name), "grid", {"AIUEOS_CSSOM_K_SOURCE_PATH": str(mdir)}))
    results = dict(zip([j[0] for j in jobs], pmap(lambda j: run_builder(args, j[1], j[2], j[3]), jobs, 4)))
    if "baseline" in results and results["baseline"][0]:
        raise ValueError(("the baseline kernel build or run failed", results["baseline"][1]))
    if "imgsig" in results and results["imgsig"][0]:
        raise ValueError(("the imgsig control build or run failed", results["imgsig"][1]))
    base_receipt = read_receipt(base)
    if base_receipt is None or base_receipt["status"] != "PASS_NATIVE_GRID_K_QEMU":
        raise ValueError("the baseline observer receipt is missing or not PASS")
    table, against_ref = compare(cases, base_receipt, ref)
    if table:
        raise ValueError(("kernel and exact model disagree", table[:5]))
    # 5. tie report: the kernel (exact) differs from the reference (doubles) only at exact ties
    ties = []
    for name, status, h, r in against_ref:
        c = next(x for x in cases if x["name"] == name)
        f64res, log = f64_expect(c)
        if not log:
            raise ValueError(("kernel and reference differ and no tie step explains it", name))
        exact = K.model(c["words"], c["kind"], "exact")
        ties.append({"case": name, "kernel": exact[0], "reference": f64res[0],
                     "steps": [{"step": t[0], "numerator": t[1], "denominator": t[2], "exactFloor": t[3], "doubleResult": t[4]} for t in log]})
    state = json.loads((base / "native-desktop-macos.json").read_text())
    kstate = json.loads((base / "kernel/build-state.json").read_text())
    receipt["kernel"] = {"profile": "grid", "state": state["state"], "target": "x86_64-aiueos-kernel-v3", "cases": len(cases),
                         "statusZero": sum(1 for r in base_receipt["records"] if r["status"] == 0),
                         "refused": sum(1 for r in base_receipt["records"] if r["status"] != 0),
                         "equalToExactModel": len(cases), "equalToReference": len(run_ids) - len(against_ref), "differFromReference": len(against_ref),
                         "textSegmentBytes": state["textMargin"]["textSegmentBytes"], "estimatedMarginBytes": state["textMargin"]["estimatedMarginBytes"],
                         "sourceModuleCount": kstate["sourceModuleCount"], "kernelSha256": kstate["kernel"]["sha256"],
                         "cssomModulesLocked": sorted(m for m in kstate["sourceGraph"] if "/cssom/" in m)}
    receipt["ties"] = {"tieSteps": ties_total, "casesWithATieStep": len(tie_cases), "casesWhereKernelAndReferenceDiffer": ties}
    img = json.loads((imgsig / "native-desktop-macos.json").read_text())
    receipt["imageDelta"] = {"gridProfileTextSegmentBytes": state["textMargin"]["textSegmentBytes"],
                             "imgsigProfileTextSegmentBytes": img["textMargin"]["textSegmentBytes"],
                             "deltaBytes": state["textMargin"]["textSegmentBytes"] - img["textMargin"]["textSegmentBytes"]}

    # 6. negative controls
    receipt["mutants"] = []
    if not args.skip_mutants:
        for name, stem, anchor, repl in MUTANTS:
            mname = stem + "-" + str(MUTANTS.index((name, stem, anchor, repl)))
            code = results[name][0]
            mr = read_receipt(out / ("kernel-mutant-" + mname))
            if code == 0 or mr is None or mr["status"] != "FAIL_NATIVE_GRID_K_QEMU":
                raise ValueError(("the mutant was not seen by the observer", name, code, results[name][1][-400:]))
            mtable, magainst = compare(cases, mr, ref)
            baseline_ties = {t["case"] for t in ties}
            magainst = [x for x in magainst if x[0] not in baseline_ties]      # the exact-tie differences exist in the baseline too
            if not mtable or not magainst:
                raise ValueError(("the mutant is not seen both by the case table and by the reference", name, len(mtable), len(magainst)))
            receipt["mutants"].append({"name": name, "module": stem, "anchor": anchor, "replacement": repl, "builderExit": code,
                                       "casesDifferingFromTable": len(mtable), "casesDifferingFromReferenceBeyondTheTies": len(magainst),
                                       "firstDifferences": mtable[:3]})

    # 7. sizes and the user-v1 verdict
    comp = AiueosCompiler(full, out / "aiueos")
    sizes, prev = {}, 0
    for stem in STEMS:
        src, kept, total = reachable(bundle(entry_for(stem)))
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
            src, _, _ = reachable(bundle(entry_for(stem, zero)))
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
    receipt["status"] = "PASS_NATIVE_CSSOM_GRID_K"
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(receipt["status"], len(cases), "cases", len(run_ids), "run through the references", len(ties), "kernel/reference tie differences",
          len(receipt["mutants"]), "mutants seen")
    if args.print_measurements:
        print(json.dumps({k: receipt[k] for k in ("audit", "sizeKernelV1", "kernel", "ties", "imageDelta", "mutants", "reference")}, indent=2))


if __name__ == "__main__":
    main()
