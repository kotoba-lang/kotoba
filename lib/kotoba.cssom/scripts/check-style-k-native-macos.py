#!/usr/bin/env python3
"""Observe the style slice of the CSSOM (JUN-134/135/920, ADR-0287) with native tools only: no JVM, nbb or babashka.

The slice: selector matching (type, *, #id, .class; descendant, child, adjacent and general sibling), specificity, cascade order
(important, origin, specificity, source order) and inheritance of the engine's inherited properties, as kernel-dialect REGION code
(src/cssom/intern_k, selector_k, match_k, cascade_k: a bounded string table, rule table and node table in one 61440-byte owned window).

What this gate does:

  1. STATIC AUDIT of the four region modules: at most five parameters per function, no floats, strings, records, `/` or `rem`,
     counted multiplications, the generated inherited-property predicate regenerated from the list in core.cljk and compared.
  2. SHEET EQUIVALENCE: the author sheet fed to the slice is the sheet css_sheet.kotoba renders for ui_components_sheet.kotoba;
     a native program hashes (styles) and the hash must equal the one of the text the case grid is built from.
  3. REFERENCE: the independent host-native implementation (src/cssom/style_ref.kotoba, maps and strings allowed) runs every case it
     can (a native Amu compile and run per case). Its sums must equal the hand-derived expectations of the hand cases, and its
     refusals must be the expected ones.
  4. KERNEL: the region modules run on x86_64-aiueos-kernel-v3 under QEMU TCG (profile `style` of build-native-desktop-macos.py,
     observer os/aiueos/scripts/check-native-style-qemu.py): every case of the grid, including every document the shared UI
     components emit with the real component sheet, one case on each side of every capacity bound, refusals and malformed streams.
     The kernel's sum (or refusal) must equal the reference's for every case the reference ran, and the observer's own checks
     (status, element count, hand-derived sum) must pass.
  5. NEGATIVE CONTROLS: one rebuilt mutant per module (one line changed; the anchor must occur exactly once) is built into a
     kernel and run through the same observer; it must be seen (observer FAIL receipt, and records that differ from the case table
     or the reference), never silently pass.
  6. SIZE: kernel-v1 text bytes of the cumulative compile of the modules (a main reaching every export), and the verdict of
     x86_64-aiueos-user-v1 with the exact error; a six-parameter function must be refused (E7102).

It does not claim CPL3 execution, a wired layout.cljk, or a browser verdict. The reference transcribes core.cljk; the original .cljk
could not be run here (see evidence/cssom-q6-slice2-20261106), so its fidelity rests on the hand-derived cases and on the code read.
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

spec = importlib.util.spec_from_file_location("style_k_cases", HERE / "style_k_cases.py")
K = importlib.util.module_from_spec(spec)
spec.loader.exec_module(K)

STEMS = ["intern_k", "selector_k", "match_k", "cascade_k"]
REF = SRC / "style_ref.kotoba"
MODS = {s: SRC / (s + ".kotoba") for s in STEMS}

# one line per module; each anchor must occur exactly once
MUTANTS = [
    ("intern: ASCII fold adds 33 instead of 32", "intern_k", "(+ b 32)", "(+ b 33)"),
    ("selector: a class counts as a tag in the specificity", "selector_k", "(sp! st (+ (sp st) 65536))", "(sp! st (+ (sp st) 1))"),
    ("match: the descendant combinator reads the sibling mask", "match_k",
     "(if (= c 1) (bit (mm st (+ 2176 n)) (- k 1))", "(if (= c 1) (bit (mm st (+ 2304 n)) (- k 1))"),
    ("cascade: source order reversed", "cascade_k", "(+ d 1))]", "(- 4095 d))]"),
]

# cumulative entries: a main reaching every export, two arguments (a window and its length)
ENTRIES = {
    "intern_k": ("[cssom.intern-k :as ik]",
                 "(+ (ik/ik-reset w n) (+ (ik/ik-intern w n 3 4 0) (+ (ik/ik-len w n 5) (+ (ik/ik-byte w n 5 2) (ik/ik-word w n 5 0 1)))))"),
    "selector_k": ("[cssom.selector-k :as sk]", "(+ (sk/sk-reset w n) (sk/sk-sheet w n 0))"),
    "match_k": ("[cssom.match-k :as mk]", "(+ (mk/mk-doc w n 0) (mk/mk-match w n 1))"),
    "cascade_k": ("[cssom.cascade-k :as ck]", "(+ (ck/ck-run w n 100) (ck/ck-nodes w n))"),
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


def hash_text(t):
    x = 5381
    for b in t.encode():
        x = (x * 257 + b + 1) & 0xFFFFFFFF
    return x


def inherited_predicate():
    """The (defn- inh? ...) text of cascade_k, regenerated from the list in core.cljk (inherited-properties)."""
    core = (SRC / "core.cljk").read_text()
    m = re.search(r'\(def \^:private inherited-properties\s+"(?:[^"\\]|\\.)*"\s+"(\|[^"]*\|)"\)', core, re.S)
    names = [n for n in m.group(1).split("|") if n]

    def words(s):
        b = s.encode()
        return [sum(x << (8 * i) for i, x in enumerate(b[7 * k:7 * k + 7])) for k in range(3)]
    terms = []
    for n in names:
        w, need = words(n), (len(n) + 6) // 7
        t = "(= n %d)" % len(n)
        for i in range(need):
            t = "(and %s (= w%d %d))" % (t, i, w[i])
        terms.append(t)

    def nest(ts):
        return ts[0] if len(ts) == 1 else "(or %s %s)" % (ts[0], nest(ts[1:]))
    return names, "(defn- inh? [n w0 w1 w2]\n  " + nest(terms) + ")\n"


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


def run_builder(args, output, profile="style", env_extra=None):
    cmd = [sys.executable, "-I", str(BUILDER), "--amu-source", str(args.amu_source), "--owner-repo-root", str(args.owner_repo_root),
           "--qemu", str(args.qemu), "--qemu-sha256", args.qemu_sha256, "--firmware", str(args.firmware),
           "--firmware-sha256", args.firmware_sha256, "--profile", profile, "--output", str(output)]
    env = {"PATH": "/usr/bin:/bin:/opt/homebrew/bin", "LANG": "C"}
    env.update(env_extra or {})
    started = time.monotonic()
    r = subprocess.run(cmd, cwd=AIUEOS, env=env, capture_output=True, timeout=7200)
    return r.returncode, (r.stdout + r.stderr).decode(errors="replace")[-1500:], time.monotonic() - started


def read_receipt(output):
    path = Path(output) / "qemu" / "native-style-qemu.json"
    return json.loads(path.read_text()) if path.is_file() else None


def compare(cases, receipt, ref):
    """Disagreements between the kernel records and the case table and, for the cases the reference ran, the reference."""
    table, against_ref, compared = [], [], 0
    for i, (c, rec) in enumerate(zip(cases, receipt["records"])):
        assert rec["name"] == c["name"], (rec["name"], c["name"])
        ok = rec["status"] == c["status"]
        if ok and rec["status"] == 0:
            ok = rec["nodes"] == (len(K.flat(c["doc"])) if c["doc"] is not None else 0) and (c["styles"] is None or rec["sum"] == K.case_sum(c["styles"]))
        if not ok:
            table.append(c["name"])
        r = ref.get(i)
        if isinstance(r, int):
            compared += 1
            if not ((r < 0 and rec["status"] == -r) or (r >= 0 and rec["status"] == 0 and rec["sum"] == r)):
                against_ref.append((c["name"], rec["status"], rec["sum"], r))
    return table, against_ref, compared


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
    ap.add_argument("--reuse-baseline", type=Path, help="an existing builder output of profile style (skips the baseline build)")
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
                         [Path(__file__).resolve(), HERE / "style_k_cases.py", REF, *MODS.values(), K.SHEET_SRC, K.HTML_TEST,
                          LIB / "kotoba.css/kotoba/css_sheet.kotoba", AIUEOS / "os/aiueos/native/style-entry.kotoba",
                          AIUEOS / "os/aiueos/scripts/check-native-style-qemu.py", BUILDER]}
    nat = Native(amu, out / "native")

    # 1. static audit and the generated predicate
    receipt["audit"] = static_audit()
    names, predicate = inherited_predicate()
    if predicate not in MODS["cascade_k"].read_text():
        raise ValueError("the inherited-property predicate of cascade_k.kotoba differs from the list in core.cljk (regenerate it)")
    receipt["inheritedProperties"] = len(names)

    # 2. sheet equivalence
    rules, text = K.real_sheet()
    probe = ("(ns shmain (:require [ui-components-sheet :as s]) (:export [main]))\n"
             "(defn hsh [t :string] :i64 (loop [i 0 h 5381] (if (>= i (string-length t)) h "
             "(recur (+ i 1) (bit-and (+ (* h 257) (+ (string-code-point-at t i) 1)) 4294967295)))))\n"
             "(defn main [] :i64 (hsh (option-value-of [:option :string] (s/styles) \"\")))\n")
    got = nat.run("sheet", probe, {"ui-components-sheet": K.SHEET_SRC, "css-sheet": LIB / "kotoba.css/kotoba/css_sheet.kotoba"}, "shmain")
    if got != hash_text(text):
        raise ValueError(("the sheet of the grid is not the sheet css_sheet renders", got, hash_text(text)))
    receipt["sheet"] = {"rules": len(rules), "textBytes": len(text.encode()), "hash": got}

    # 3. reference
    ref_ids = [i for i, c in enumerate(cases) if c["ref"] and c.get("raw") is None]

    def ref_case(i):
        c = cases[i]
        edn = K.edn_case(c).replace("\\", "\\\\").replace('"', '\\"')
        entry = '(ns ent (:require [cssom.style-ref :as r]) (:export [main]))\n(defn main [] :i64 (r/run-case (document-edn-read "%s")))\n' % edn
        return nat.run("ref-%03d" % i, entry, {"cssom.style-ref": REF}, "ent")
    started = time.monotonic()
    ref = dict(zip(ref_ids, pmap(ref_case, ref_ids, args.jobs)))
    receipt["reference"] = {"cases": len(ref), "seconds": round(time.monotonic() - started, 1)}
    traps = [(cases[i]["name"], r) for i, r in ref.items() if not isinstance(r, int)]
    if traps:
        raise ValueError(("the reference trapped", traps[:5]))
    wrong = []
    for i, r in ref.items():
        c = cases[i]
        if c["status"] != 0:
            if r != -c["status"]:
                wrong.append((c["name"], r, -c["status"]))
        elif c["styles"] is not None and r != K.case_sum(c["styles"]):
            wrong.append((c["name"], r, K.case_sum(c["styles"])))
        elif r < 0:
            wrong.append((c["name"], r, "a sum"))
    if wrong:
        raise ValueError(("the reference disagrees with the hand-derived expectations", wrong[:5]))
    receipt["reference"]["handDerivedAgree"] = sum(1 for i in ref if cases[i]["styles"] is not None)
    receipt["reference"]["refusalsAgree"] = sum(1 for i in ref if cases[i]["status"] != 0)

    # 4. kernel: baseline build and QEMU run
    base = args.reuse_baseline.resolve() if args.reuse_baseline else out / "kernel-baseline"
    if not args.reuse_baseline:
        code, tail, secs = run_builder(args, base)
        if code:
            raise ValueError(("the baseline kernel build or run failed", tail))
    base_receipt = read_receipt(base)
    if base_receipt is None or base_receipt["status"] != "PASS_NATIVE_STYLE_K_QEMU":
        raise ValueError("the baseline observer receipt is missing or not PASS")
    table, against_ref, compared = compare(cases, base_receipt, ref)
    if table or against_ref:
        raise ValueError(("kernel and reference disagree", table[:5], against_ref[:5]))
    state = json.loads((base / "native-desktop-macos.json").read_text())
    kstate = json.loads((base / "kernel/build-state.json").read_text())
    receipt["kernel"] = {"profile": "style", "state": state["state"], "target": "x86_64-aiueos-kernel-v3", "cases": len(cases),
                         "comparedWithReference": compared, "statusZero": sum(1 for r in base_receipt["records"] if r["status"] == 0),
                         "refused": sum(1 for r in base_receipt["records"] if r["status"] != 0),
                         "textSegmentBytes": state["textMargin"]["textSegmentBytes"], "estimatedMarginBytes": state["textMargin"]["estimatedMarginBytes"],
                         "sourceModuleCount": kstate["sourceModuleCount"], "kernelSha256": kstate["kernel"]["sha256"],
                         "cssomModulesLocked": sorted(m for m in kstate["sourceGraph"] if "/cssom/" in m)}

    # 5. negative controls
    receipt["mutants"] = []
    if not args.skip_mutants:
        for name, stem, anchor, repl in MUTANTS:
            text0 = MODS[stem].read_text()
            if text0.count(anchor) != 1:
                raise ValueError(("mutation anchor must occur exactly once", name, text0.count(anchor)))
            mdir = out / "mutants" / stem
            mdir.mkdir(parents=True)
            for s in STEMS:
                shutil.copyfile(MODS[s], mdir / (s + ".kotoba"))
            (mdir / (stem + ".kotoba")).write_text(text0.replace(anchor, repl))
            code, tail, secs = run_builder(args, out / ("kernel-mutant-" + stem), env_extra={"AIUEOS_CSSOM_K_SOURCE_PATH": str(mdir)})
            mr = read_receipt(out / ("kernel-mutant-" + stem))
            if code == 0 or mr is None or mr["status"] != "FAIL_NATIVE_STYLE_K_QEMU":
                raise ValueError(("the mutant was not seen by the observer", name, code, tail[-400:]))
            mtable, magainst, _ = compare(cases, mr, ref)
            if not mtable or not magainst:
                raise ValueError(("the mutant is not seen both by the case table and by the reference", name, len(mtable), len(magainst)))
            receipt["mutants"].append({"name": name, "module": stem, "anchor": anchor, "replacement": repl, "builderExit": code,
                                       "casesDifferingFromTable": len(mtable), "casesDifferingFromReference": len(magainst),
                                       "firstDifferences": [x[0] for x in magainst[:3]]})

    # 6. sizes and the user-v1 verdict
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
    receipt["status"] = "PASS_NATIVE_CSSOM_STYLE_K"
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(receipt["status"], len(cases), "cases", compared, "compared with the reference", len(receipt["mutants"]), "mutants seen")
    if args.print_measurements:
        print(json.dumps({k: receipt[k] for k in ("audit", "sizeKernelV1", "kernel", "mutants", "reference")}, indent=2))


if __name__ == "__main__":
    main()
