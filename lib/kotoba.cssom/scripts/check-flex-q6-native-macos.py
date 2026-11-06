#!/usr/bin/env python3
"""Observe the slice-3 Q6 fixed-point modules of the CSSOM (JUN-920 / C2b) with a native Amu CLI.

Slice 3 covers census groups G07 (flex solver and main-axis placement, multi-column geometry), G11 (opacity and flex factors),
G09 (vertical-align shifts of inline fragments) and G04 (colour arithmetic of domGpu host/color.cljk). All with the pinned native
macOS Amu binary and no JVM, nbb or babashka (the 2026-11-06 attempt to run the original .cljk with kbb / nbb is recorded as
data in the slice-2 evidence and not used here):

  1. DIFFERENTIAL: five native tests compile against a KSL2 source lock and each must print 42 on their spec points (derived by
     hand from the documented tables and comments of layout.cljk) and on every grid: q6_flex_vs_f64 (8 slices of 125,000
     pseudo-random lines, exact share formula, placement and auto-margin grids), q6_multicol_vs_f64, q6_style_num_vs_f64,
     q6_inline_vs_f64, q6_color_vs_f64. The f64 side is a native transcription of the .cljk semantics (flex.kotoba,
     multicol.kotoba, style_num.kotoba, inline.kotoba, color.kotoba).
  2. PINNED COUNTS: cases compared, equal / tie / cascade classes, the maximum deviation, and the exact-tie report (how often
     the inexact f64 oracle disagrees with the exact Q6 rule at exact ties, and that it never disagrees away from them).
  3. NEGATIVE CONTROLS: one or more mutations per module (each anchor must occur exactly once), including the f64
     references, must make the verdict print 7 (or a violation counter rise).
  4. SIZE: the arithmetic core is bundled into one source and compiled with the pinned amu-full-root for
     x86_64-aiueos-kernel-v1 (text bytes pinned, per module and whole) and x86_64-aiueos-user-v1 (exact error codes
     pinned); a six-parameter function must be refused (E7102).
  5. STATIC AUDIT: at most five parameters per function, no floats, strings, records, loops or division except quot.

It reuses the helpers of check-block-q6-native-macos.py (slice 1). It does not claim CPL3 execution, a wired layout.cljk,
or a browser verdict.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import platform
import re
import sys
import threading

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('block_q6_gate', HERE / 'check-block-q6-native-macos.py')
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)

SRC, TESTS, AIUEOS = G.SRC, G.TESTS, G.AIUEOS
sha, fields, pmap = G.sha, G.fields, G.pmap

MODULES = {
    'cssom.length-q6': SRC / 'length_q6.kotoba',
    'cssom.flex': SRC / 'flex.kotoba',
    'cssom.flex-q6': SRC / 'flex_q6.kotoba',
    'cssom.multicol': SRC / 'multicol.kotoba',
    'cssom.multicol-q6': SRC / 'multicol_q6.kotoba',
    'cssom.style-num': SRC / 'style_num.kotoba',
    'cssom.style-num-q6': SRC / 'style_num_q6.kotoba',
    'cssom.parse-d4-q6': SRC / 'parse_d4_q6.kotoba',
    'cssom.inline': SRC / 'inline.kotoba',
    'cssom.inline-q6': SRC / 'inline_q6.kotoba',
    'cssom.color': SRC / 'color.kotoba',
    'cssom.color-q6': SRC / 'color_q6.kotoba',
}
CORE = ['flex_q6', 'multicol_q6', 'style_num_q6', 'inline_q6', 'color_q6']
F64_REFS = ['flex', 'multicol', 'style_num', 'inline', 'color']
FLEX = TESTS / 'q6_flex_vs_f64.kotoba'
MC = TESTS / 'q6_multicol_vs_f64.kotoba'
SN = TESTS / 'q6_style_num_vs_f64.kotoba'
IL = TESTS / 'q6_inline_vs_f64.kotoba'
CO = TESTS / 'q6_color_vs_f64.kotoba'
ENTRY2 = AIUEOS / 'q6_slice3_entry.kotoba'
ENTRY0 = AIUEOS / 'q6_slice3_entry_zero.kotoba'
NEEDS = {
    FLEX: ['cssom.flex', 'cssom.flex-q6', 'cssom.length-q6'],
    MC: ['cssom.multicol', 'cssom.multicol-q6', 'cssom.length-q6'],
    SN: ['cssom.style-num', 'cssom.style-num-q6', 'cssom.parse-d4-q6', 'cssom.length-q6'],
    IL: ['cssom.inline', 'cssom.inline-q6', 'cssom.length-q6'],
    CO: ['cssom.color', 'cssom.color-q6', 'cssom.length-q6'],
}
FLEX_SLICES = list(range(1, 9))
MC_MODES = list(range(1, 16))
SN_MODES = [5, 6, 7, 8, 9, 100, 101, 102]
SN_MUL = [10 * s + w for s in (1, 2, 3, 4) for w in (1, 2, 3, 4)]
IL_MODES = list(range(1, 15))
CO_MODES = list(range(1, 14))
FLEX_MODES = [100, 101, 102, 110, 111, 112, 113, 120, 121, 122]

# name, module ns, anchor, replacement, runs: (test, mode, kind)
#   kind 'verdict': prints 7;  'count': > 0;  'pack42': a field at bit 42 of a packed counter is > 0 (violations)
#   'pack0': bits 0..20 of a packed counter are > 0 (violations in mode 2 of the flex sweep)
MUTANTS = [
    ('flex-q6: share() rounds down instead of half up', 'cssom.flex-q6',
     '(+ (dvf d) (if (>= (* 2 (dvr d)) tw) 1 0))', '(dvf d)',
     [(FLEX, 101, 'count')]),
    ('flex-q6: the solver rounds down instead of half up', 'cssom.flex-q6',
     '(+ v (if (>= (* 2 f) tw) 1 0))', 'v',
     [(FLEX, 0, 'verdict'), (FLEX, 14, 'verdict')]),
    ('flex-q6: the freeze test uses the ROUNDED proposal instead of the exact one', 'cssom.flex-q6',
     'ch (if (> f 0) (if (or (< v (f-min p)) (and (not= mx 262143) (>= v mx))) 1 0) (if (= c v) 0 1))]',
     'ch (if (= (clampv p (+ v (if (>= (* 2 f) tw) 1 0))) (+ v (if (>= (* 2 f) tw) 1 0))) 0 1)]',
     [(FLEX, 0, 'verdict'), (FLEX, 14, 'verdict'), (FLEX, 12, 'pack0')]),
    ('flex-q6: shrink weight not scaled by the base size', 'cssom.flex-q6',
     '(* (factor p l k) (f-base p))', '(factor p l k)',
     [(FLEX, 0, 'verdict'), (FLEX, 14, 'verdict')]),
    ('flex-q6: space-around lead uses n instead of 2n', 'cssom.flex-q6',
     '(* (+ (* 2 i) 1) fp) (* 2 n))', '(* (+ (* 2 i) 1) fp) n)',
     [(FLEX, 20, 'verdict'), (FLEX, 111, 'count')]),
    ('flex-q6: auto-margin share not capped at zero free space', 'cssom.flex-q6',
     '(imax 0 (- container totalg))', '(- container totalg)',
     [(FLEX, 20, 'verdict'), (FLEX, 121, 'count')]),
    ('flex f64 reference: weight ratio inverted', 'cssom.flex',
     '(f64-mul rem (f64-div w tw))', '(f64-mul rem (f64-div tw w))',
     [(FLEX, 0, 'verdict'), (FLEX, 14, 'verdict')]),
    ('flex f64 reference: space-evenly unit uses n instead of n + 1', 'cssom.flex',
     '(= mode 5) (f64-div freep (f64-add nf 1.0))\n                    :else 0.0)]', '(= mode 5) (f64-div freep nf)\n                    :else 0.0)]',
     [(FLEX, 20, 'verdict'), (FLEX, 111, 'count')]),
    ('multicol-q6: column pitch floors instead of rounding half up', 'cssom.multicol-q6',
     '(* 64 (len/rdiv (* k (+ (num cw gap n) (* n gap))) (* 64 n)))', '(* 64 (len/fdiv (* k (+ (num cw gap n) (* n gap))) (* 64 n)))',
     [(MC, 0, 'verdict'), (MC, 9, 'count')]),
    ('multicol f64 reference: gap counted once', 'cssom.multicol',
     '(f64-sub cw (f64-mul (i64-to-f64-rounded (- n 1)) gap))', '(f64-sub cw gap)',
     [(MC, 20, 'verdict'), (MC, 4, 'count')]),
    ('style-num-q6: opacity product truncates', 'cssom.style-num-q6',
     '(len/rdiv (* a b) 10000)', '(quot (* a b) 10000)',
     [(SN, 0, 'verdict'), (SN, 14, 'count')]),
    ('parse-d4-q6: below-one adjustment dropped', 'cssom.parse-d4-q6',
     '(if (and (>= r 10000) (< m 1000000)) 9999 (sn/opacity-clamp r))', '(sn/opacity-clamp r)',
     [(SN, 0, 'verdict'), (SN, 100, 'count')]),
    ('style-num f64 reference: opacity upper bound 2', 'cssom.style-num',
     '(if (f64-gt x 1.0) 1.0 x)', '(if (f64-gt x 2.0) 2.0 x)',
     [(SN, 20, 'verdict'), (SN, 8, 'count')]),
    ('inline-q6: sub shifts upwards', 'cssom.inline-q6',
     '(len/rdiv (- 0 (+ fs 320)) 5)', '(len/rdiv (+ fs 320) 5)',
     [(IL, 0, 'verdict'), (IL, 4, 'count')]),
    ('inline f64 reference: super divides by 4', 'cssom.inline',
     '(f64-add (f64-div fs 3.0) 64.0)', '(f64-add (f64-div fs 4.0) 64.0)',
     [(IL, 20, 'verdict'), (IL, 4, 'count')]),
    ('color-q6: unit-byte floors', 'cssom.color-q6',
     '(len/rdiv (* b 65536) 255)', '(quot (* b 65536) 255)',
     [(CO, 0, 'verdict'), (CO, 1, 'pack42')]),
    ('color-q6: blue offset 5 instead of 4', 'cssom.color-q6',
     '(if (= which 1) 8 4)', '(if (= which 1) 8 5)',
     [(CO, 0, 'verdict'), (CO, 20, 'verdict')]),
    ('color f64 reference: hsl clamp uses 8 - k', 'cssom.color',
     '(f64-sub 9.0 k)', '(f64-sub 8.0 k)',
     [(CO, 20, 'verdict'), (CO, 8, 'pack42')]),
    ('length-q6: round half up replaced by floor (shared)', 'cssom.length-q6',
     '(fdiv (+ (* 2 n) d) (* 2 d))', '(fdiv (* 2 n) (* 2 d))',
     [(MC, 0, 'verdict'), (SN, 0, 'verdict'), (IL, 0, 'verdict')]),
]

TOK = G.TOK


def static_audit():
    audit = {}
    for stem in CORE:
        text = (SRC / (stem + '.kotoba')).read_text()
        code = '\n'.join(l.split(';;')[0] for l in text.split('\n'))
        defns = re.findall(r'\(defn\s+(\S+)\s+\[([^\]]*)\]', code)
        params = {name: len(plist.split()) // 2 for name, plist in defns}
        too_many = [n for n, c in params.items() if c > 5]
        if too_many:
            raise ValueError(('more than five parameters', stem, too_many))
        bad = sorted({t for t in TOK.findall(code)
                      if t in {'/', 'rem', 'mod'} or t.startswith('f64') or t == 'record' or t.startswith('record-')
                      or t == ':string' or t.startswith('string-') or t in {'loop', 'recur', 'vector', 'conj', 'assoc'}})
        if bad:
            raise ValueError(('forbidden form in the core', stem, bad))
        mult = re.findall(r'\(\*\s+(\S+)\s+(\S+)\)', code)
        two_var = [m for m in mult if not (re.fullmatch(r'-?\d+', m[0]) or re.fullmatch(r'-?\d+', m[1]))]
        audit[stem] = {'defns': len(defns), 'maxParams': max(params.values()), 'multiplications': len(mult),
                       'multiplicationsOfTwoVariables': len(two_var),
                       'sourceLines': len([l for l in code.split('\n') if l.strip()])}
    return audit


def module_main0(stem):
    """Zero-argument main reaching every export of one core module with literal inputs (the user-v1 entry shape)."""
    text = (SRC / (stem + '.kotoba')).read_text()
    exports = re.search(r'\(:export\s+\[([^\]]*)\]', text).group(1).split()
    code = G.strip_comments(text)
    lits = ['7', '13', '7', '13', '7']
    terms = []
    for name in exports:
        m = re.search(r'\(defn\s+' + re.escape(name) + r'\s+\[([^\]]*)\]\s+(:\w+)', code)
        n = len(m.group(1).split()) // 2
        call = '(x/%s%s)' % (name, (' ' + ' '.join(lits[:n])) if n else '')
        terms.append('(if %s 1 0)' % call if m.group(2) == ':bool' else call)
    body = terms[0]
    for t in terms[1:]:
        body = '(+ %s %s)' % (body, t)
    alias = stem.replace('_', '-')
    return '(ns m (:require [cssom.%s :as x]) (:export [main]))\n(defn main [] :i64 %s)\n' % (alias, body)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--amu', type=Path, required=True, help='amu-cli.macho (native macOS arm64)')
    ap.add_argument('--amu-sha256', default=G.AMU_SHA256)
    ap.add_argument('--amu-full-root', type=Path, required=True, help='amu-full-root.macho (the --target compiler)')
    ap.add_argument('--amu-full-root-sha256', default=G.AMU_FULL_ROOT_SHA256)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--print-measurements', action='store_true', help='print the measured table instead of enforcing pins')
    args = ap.parse_args()
    if (platform.system(), platform.machine()) != ('Darwin', 'arm64'):
        raise ValueError('requires native macOS ARM64')
    amu = args.amu.resolve(strict=True)
    full = args.amu_full_root.resolve(strict=True)
    if sha(amu) != args.amu_sha256:
        raise ValueError('Amu digest mismatch')
    if sha(full) != args.amu_full_root_sha256:
        raise ValueError('amu-full-root digest mismatch')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    tracked = [amu, full, Path(__file__).resolve(), HERE / 'check-block-q6-native-macos.py', ENTRY2, ENTRY0] + \
        sorted(set(MODULES.values())) + sorted(NEEDS)
    pins = {str(p): sha(p) for p in tracked}
    nat = G.Native(amu, out)
    jobs = args.jobs
    measured, failures, counter, lock = {}, [], [0], threading.Lock()

    def tag(prefix):
        with lock:
            counter[0] += 1
            return '%s-%03d' % (prefix, counter[0])

    def go(test, mode, slice_=None, replace=None):
        m = {n: MODULES[n] for n in NEEDS[test]}
        if replace:
            m.update(replace)
        return nat.run(tag(test.stem), test, m, mode, slice_)

    def expect(cond, what):
        if not cond:
            failures.append(what)

    def batch(test, modes):
        vals = pmap(lambda m: go(test, m), modes, jobs)
        return dict(zip(modes, vals))

    # 1 + 2. differential verdicts and pinned counts --------------------------------------------------------------
    # flex
    expect(go(FLEX, 0) == 42, 'flex spec points')
    expect(go(FLEX, 20) == 42, 'flex placement grids')
    ftasks = [(s, w) for s in FLEX_SLICES for w in (1, 2, 3, 4)]
    fvals = pmap(lambda t: go(FLEX, 10 * t[0] + t[1]), ftasks, jobs)
    flex = {'lines': 0, 'comparisons': 0, 'equal': 0, 'tie': 0, 'cascade': 0, 'violations': 0, 'maxDeviation1000': 0,
            'onBound': 0}
    for (s, w), v in zip(ftasks, fvals):
        if w == 1:
            c = fields(v, 3)
            flex['equal'] += c[0]; flex['tie'] += c[1]; flex['cascade'] += c[2]
        elif w == 2:
            c = fields(v, 3)
            flex['violations'] += c[0]; flex['maxDeviation1000'] = max(flex['maxDeviation1000'], c[1]); flex['onBound'] += c[2]
        elif w == 3:
            flex['comparisons'] += v
            flex['lines'] += 125000
        else:
            expect(v == 42, 'flex slice %d verdict %r' % (s, v))
    expect(flex['violations'] == 0, 'flex violations %d' % flex['violations'])
    expect(flex['equal'] + flex['tie'] + flex['cascade'] == flex['comparisons'], 'flex classes do not add up')
    extra = batch(FLEX, FLEX_MODES)
    measured['flex'] = {'sweep': flex, 'grids': {str(k): v for k, v in extra.items()}}
    # multicol
    expect(go(MC, 0) == 42, 'multicol spec points')
    expect(go(MC, 20) == 42, 'multicol grids')
    measured['multicol'] = {str(k): v for k, v in batch(MC, MC_MODES).items()}
    # style numbers
    expect(go(SN, 0) == 42, 'style-num spec points')
    expect(go(SN, 20) == 42, 'style-num grids')
    svals = batch(SN, SN_MODES + SN_MUL)
    mul = {'pairs': 0, 'ties': 0, 'oracleDiffersAtTie': 0, 'oracleDiffersAwayFromTie': 0}
    for s in (1, 2, 3, 4):
        for w, k in zip((1, 2, 3, 4), ('pairs', 'ties', 'oracleDiffersAtTie', 'oracleDiffersAwayFromTie')):
            mul[k] += svals[10 * s + w]
    measured['styleNum'] = {'multiply': mul, 'other': {str(k): svals[k] for k in SN_MODES}}
    # inline
    expect(go(IL, 0) == 42, 'inline spec points')
    expect(go(IL, 20) == 42, 'inline grids')
    measured['inline'] = {str(k): v for k, v in batch(IL, IL_MODES).items()}
    # colour
    expect(go(CO, 0) == 42, 'colour spec points')
    expect(go(CO, 20) == 42, 'colour grids')
    cvals = batch(CO, CO_MODES)
    col = {}
    for k, v in cvals.items():
        if k in (1, 4, 5, 6, 7, 12):
            c = fields(v, 3)
            col[str(k)] = {'cases': c[0], 'maxDeviation1000': c[1], 'violations': v >> 42}
        elif k == 8:
            col[str(k)] = {'cases': v & 0x1FFFFF, 'maxDeviation1000': (v >> 21) & 0x1FFFFF, 'violations': v >> 42}
        else:
            col[str(k)] = v
    measured['colour'] = col

    # 3. negative controls -----------------------------------------------------------------------------------------
    mutation_report = []
    for name, ns, anchor, replacement, runs in MUTANTS:
        src = MODULES[ns]
        text = src.read_text()
        if text.count(anchor) != 1:
            raise ValueError('mutation anchor changed: ' + name)
        mdir = out / ('mutant-' + re.sub(r'\W+', '-', name))
        mdir.mkdir()
        mutant = mdir / src.name
        mutant.write_text(text.replace(anchor, replacement))
        row = {'mutation': name, 'module': ns, 'results': []}
        for test, mode, kind in runs:
            v = go(test, mode, None, replace={ns: mutant})
            good = {'verdict': v == 7, 'count': v > 0, 'pack42': (v >> 42) > 0, 'pack0': (v & 0x1FFFFF) > 0}[kind]
            expect(good, 'mutant not detected: %s (%s mode %d printed %r)' % (name, test.name, mode, v))
            row['results'].append({'test': test.name, 'mode': mode, 'kind': kind, 'printed': v})
        mutation_report.append(row)

    # 4. static audit and size -------------------------------------------------------------------------------------
    audit = static_audit()
    comp = G.AiueosCompiler(full, out)
    size = {}
    for label, entry in (('slice3-main2', ENTRY2), ('slice3-main0', ENTRY0)):
        src = G.bundle(entry.read_text())
        for t in ('x86_64-aiueos-kernel-v1', 'x86_64-aiueos-user-v1'):
            size[label + '/' + t] = comp.compile(label, src, t)
    for stem in CORE:
        size['module-' + stem + '/x86_64-aiueos-kernel-v1'] = comp.compile(
            'module-' + stem, G.bundle(G.module_main(stem)), 'x86_64-aiueos-kernel-v1')
        size['module0-' + stem + '/x86_64-aiueos-user-v1'] = comp.compile(
            'module0-' + stem, G.bundle(module_main0(stem)), 'x86_64-aiueos-user-v1')
    six = '(ns six (:export [main]))\n(defn f [a :i64 b :i64 c :i64 d :i64 e :i64 g :i64] :i64 (+ a (+ b (+ c (+ d (+ e g))))))\n(defn main [] :i64 (f 1 2 3 4 5 6))\n'
    size['six-parameter-control/x86_64-aiueos-kernel-v1'] = comp.compile('six', six, 'x86_64-aiueos-kernel-v1')
    for stem in F64_REFS:
        f64src = (SRC / (stem + '.kotoba')).read_text()
        if f64src.count('(:export [') != 1:
            raise ValueError('f64 export anchor changed: ' + stem)
        f64src = f64src.replace('(:export [', '(:export [main ', 1) + '\n(defn main [] :i64 0)\n'
        for t in ('x86_64-aiueos-kernel-v1', 'x86_64-aiueos-user-v1'):
            size['f64-' + stem + '/' + t] = comp.refusal('f64-' + stem, f64src, t)
            expect(not size['f64-' + stem + '/' + t]['ok'], 'f64 module unexpectedly compiled: ' + stem)
    expect(size['slice3-main2/x86_64-aiueos-kernel-v1']['ok'], 'kernel-v1 compile of the slice-3 core failed')
    expect(size['slice3-main0/x86_64-aiueos-kernel-v1']['ok'], 'kernel-v1 compile of the zero-argument slice-3 core failed')
    expect(size['slice3-main0/x86_64-aiueos-user-v1'].get('error') == 'E7104', 'user-v1 verdict is not the E7104 text limit')
    expect(size['six-parameter-control/x86_64-aiueos-kernel-v1'].get('error') == 'E7102', 'six-parameter control not refused')

    # pins ---------------------------------------------------------------------------------------------------------
    if any(sha(p) != pins[str(p)] for p in tracked):
        raise ValueError('source or compiler changed during gate')
    keep = ('ok', 'textBytes', 'error', 'detail', 'text')
    snapshot = {'measured': measured, 'staticAudit': audit,
                'size': {k: {x: y for x, y in v.items() if x in keep} for k, v in size.items()}}
    receipt = {'status': 'PASS_NATIVE_CSSOM_FLEX_COLOUR_Q6', 'inputs': pins, **snapshot,
               'negativeControls': mutation_report, 'ranOnLiveCpl3': False, 'wiredIntoLayoutCljk': False}
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    if args.print_measurements:
        (out / 'measurements.json').write_text(json.dumps(snapshot, indent=2, sort_keys=True))
        print(json.dumps({**snapshot, 'failures': failures}, indent=2, sort_keys=True))
        return
    for key, want in PINNED.items():
        if snapshot[key] != want:
            failures.append('pinned %s differs: %s != %s' % (key, json.dumps(snapshot[key], sort_keys=True), json.dumps(want, sort_keys=True)))
    if failures:
        for f in failures:
            print('FAIL ' + f, file=sys.stderr)
        raise SystemExit(1)
    print(receipt['status'])


# Pinned measurements (macOS arm64, pinned compiler, 2026-11-06). Any change in a count, a text size or a refusal fails the gate.
PINNED = json.loads(r'''
{
    "measured": {
        "colour": {
            "1": {
                "cases": 256,
                "maxDeviation1000": 498,
                "violations": 0
            },
            "10": 0,
            "11": 0,
            "12": {
                "cases": 27248,
                "maxDeviation1000": 500,
                "violations": 0
            },
            "13": 0,
            "2": 0,
            "3": 0,
            "4": {
                "cases": 8777,
                "maxDeviation1000": 499,
                "violations": 0
            },
            "5": {
                "cases": 8777,
                "maxDeviation1000": 499,
                "violations": 0
            },
            "6": {
                "cases": 8777,
                "maxDeviation1000": 483,
                "violations": 0
            },
            "7": {
                "cases": 8777,
                "maxDeviation1000": 499,
                "violations": 0
            },
            "8": {
                "cases": 871926,
                "maxDeviation1000": 1560,
                "violations": 0
            },
            "9": 31048
        },
        "flex": {
            "grids": {
                "100": 5520,
                "101": 0,
                "102": 59,
                "110": 168264,
                "111": 0,
                "112": 500,
                "113": 68,
                "120": 672384,
                "121": 0,
                "122": 60
            },
            "sweep": {
                "cascade": 0,
                "comparisons": 2500000,
                "equal": 2500000,
                "lines": 1000000,
                "maxDeviation1000": 500,
                "onBound": 1655847,
                "tie": 0,
                "violations": 0
            }
        },
        "inline": {
            "1": 80002,
            "10": 341432,
            "11": 0,
            "12": 0,
            "13": 0,
            "14": 119652,
            "2": 0,
            "3": 0,
            "4": 0,
            "5": 327184,
            "6": 163592,
            "7": 0,
            "8": 0,
            "9": 682864
        },
        "multicol": {
            "1": 11466,
            "10": 1279,
            "11": 9,
            "12": 1474560,
            "13": 0,
            "14": 12,
            "15": 90513,
            "2": 0,
            "3": 1386,
            "4": 0,
            "5": 73728,
            "6": 0,
            "7": 0,
            "8": 430080,
            "9": 0
        },
        "styleNum": {
            "multiply": {
                "oracleDiffersAtTie": 11364,
                "oracleDiffersAwayFromTie": 0,
                "pairs": 100020001,
                "ties": 84000
            },
            "other": {
                "100": 0,
                "101": 2,
                "102": 0,
                "5": 10111,
                "6": 0,
                "7": 50001,
                "8": 0,
                "9": 23
            }
        }
    },
    "size": {
        "f64-color/x86_64-aiueos-kernel-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'unit': expected :i64 (byte 1493)"
        },
        "f64-color/x86_64-aiueos-user-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'unit': expected :i64 (byte 1493)"
        },
        "f64-flex/x86_64-aiueos-kernel-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'item': expected :i64 (byte 1989)"
        },
        "f64-flex/x86_64-aiueos-user-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'item': expected :i64 (byte 1989)"
        },
        "f64-inline/x86_64-aiueos-kernel-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'shift-keyword': expected :i64 (byte 916)"
        },
        "f64-inline/x86_64-aiueos-user-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'shift-keyword': expected :i64 (byte 916)"
        },
        "f64-multicol/x86_64-aiueos-kernel-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'ncols': expected :i64 (byte 1099)"
        },
        "f64-multicol/x86_64-aiueos-user-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'ncols': expected :i64 (byte 1099)"
        },
        "f64-style_num/x86_64-aiueos-kernel-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'clamp01': expected :i64 (byte 632)"
        },
        "f64-style_num/x86_64-aiueos-user-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'clamp01': expected :i64 (byte 632)"
        },
        "module-color_q6/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 11492
        },
        "module-flex_q6/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 26743
        },
        "module-inline_q6/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 7012
        },
        "module-multicol_q6/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 10254
        },
        "module-style_num_q6/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 6288
        },
        "module0-color_q6/x86_64-aiueos-user-v1": {
            "detail": 11183,
            "error": "E7104",
            "ok": false
        },
        "module0-flex_q6/x86_64-aiueos-user-v1": {
            "detail": 26470,
            "error": "E7104",
            "ok": false
        },
        "module0-inline_q6/x86_64-aiueos-user-v1": {
            "detail": 6679,
            "error": "E7104",
            "ok": false
        },
        "module0-multicol_q6/x86_64-aiueos-user-v1": {
            "detail": 9945,
            "error": "E7104",
            "ok": false
        },
        "module0-style_num_q6/x86_64-aiueos-user-v1": {
            "detail": 5937,
            "error": "E7104",
            "ok": false
        },
        "six-parameter-control/x86_64-aiueos-kernel-v1": {
            "detail": 1,
            "error": "E7102",
            "ok": false
        },
        "slice3-main0/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 44234
        },
        "slice3-main0/x86_64-aiueos-user-v1": {
            "detail": 43882,
            "error": "E7104",
            "ok": false
        },
        "slice3-main2/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 43993
        },
        "slice3-main2/x86_64-aiueos-user-v1": {
            "detail": 96,
            "error": "E7102",
            "ok": false
        }
    },
    "staticAudit": {
        "color_q6": {
            "defns": 17,
            "maxParams": 4,
            "multiplications": 6,
            "multiplicationsOfTwoVariables": 4,
            "sourceLines": 37
        },
        "flex_q6": {
            "defns": 36,
            "maxParams": 5,
            "multiplications": 17,
            "multiplicationsOfTwoVariables": 8,
            "sourceLines": 114
        },
        "inline_q6": {
            "defns": 5,
            "maxParams": 4,
            "multiplications": 1,
            "multiplicationsOfTwoVariables": 0,
            "sourceLines": 21
        },
        "multicol_q6": {
            "defns": 11,
            "maxParams": 5,
            "multiplications": 7,
            "multiplicationsOfTwoVariables": 2,
            "sourceLines": 29
        },
        "style_num_q6": {
            "defns": 5,
            "maxParams": 2,
            "multiplications": 1,
            "multiplicationsOfTwoVariables": 1,
            "sourceLines": 11
        }
    }
}
''')

if __name__ == '__main__':
    main()
