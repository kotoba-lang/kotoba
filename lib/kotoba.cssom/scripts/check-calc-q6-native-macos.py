#!/usr/bin/env python3
"""Observe the slice-2 Q6 fixed-point modules of the CSSOM (JUN-920 / C2b) with a native Amu CLI.

Slice 2 covers census groups G03 (calc), G06 (line-height and font metrics) and G08 (aspect-ratio and replaced-element
sizing). All with the pinned native macOS Amu binary and no JVM, nbb or babashka (the 2026-11-06 attempt to run the original
.cljk with kbb / nbb is recorded as data, not used here):

  1. DIFFERENTIAL: three native tests compile against a KSL2 source lock and each must print 42 on their spec points and
     on every grid: q6_calc_vs_f64 (34 expression shapes, one binary per shape, every operand from a 16-value catalogue,
     plus refusal programs), q6_line_height_vs_f64, q6_aspect_ratio_vs_f64. The f64 side is a native transcription of the
     .cljk semantics (calc.kotoba, line_height.kotoba, aspect_ratio.kotoba).
  2. PINNED COUNTS: cases compared / justified refusals / edge band / violations, the maximum deviation, and the exact-tie
     report (how often the inexact f64 oracle disagrees with the exact Q6 rule at exact ties and truncation boundaries,
     and that it never disagrees away from them).
  3. NEGATIVE CONTROLS: one or more mutations per module (each anchor must occur exactly once), including the three f64
     references and the shared pack_q6, must make the verdict print 7 and must be seen by a violation counter.
  4. SIZE: the arithmetic core is bundled into one source and compiled with the pinned amu-full-root for
     x86_64-aiueos-kernel-v1 (text bytes pinned, per module and whole) and x86_64-aiueos-user-v1 (exact error codes
     pinned); a six-parameter function must be refused (E7102).
  5. STATIC AUDIT: at most five parameters per function, no floats, strings, records or division except quot.

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
    'cssom.pack-q6': SRC / 'pack_q6.kotoba',
    'cssom.calc': SRC / 'calc.kotoba',
    'cssom.calc-q6': SRC / 'calc_q6.kotoba',
    'cssom.line-height': SRC / 'line_height.kotoba',
    'cssom.line-height-q6': SRC / 'line_height_q6.kotoba',
    'cssom.aspect-ratio': SRC / 'aspect_ratio.kotoba',
    'cssom.aspect-ratio-q6': SRC / 'aspect_ratio_q6.kotoba',
}
CORE = ['pack_q6', 'calc_q6', 'line_height_q6', 'aspect_ratio_q6']
CALC = TESTS / 'q6_calc_vs_f64.kotoba'
LH = TESTS / 'q6_line_height_vs_f64.kotoba'
AR = TESTS / 'q6_aspect_ratio_vs_f64.kotoba'
ENTRY2 = AIUEOS / 'q6_slice2_entry.kotoba'
ENTRY0 = AIUEOS / 'q6_slice2_entry_zero.kotoba'
NEEDS = {
    CALC: ['cssom.calc', 'cssom.calc-q6', 'cssom.pack-q6', 'cssom.length-q6'],
    LH: ['cssom.line-height', 'cssom.line-height-q6', 'cssom.length-q6'],
    AR: ['cssom.aspect-ratio', 'cssom.aspect-ratio-q6', 'cssom.pack-q6', 'cssom.length-q6'],
}
SHAPES = 34
CALC_DENSE = {'mul': (5, 6, 7, 8), 'div': (9, 10, 11, 12)}
LH_MODES = list(range(1, 19))
AR_MODES = list(range(1, 18)) + [22, 23, 24, 25, 26]

# name, module ns, anchor, replacement, runs: (test, mode, slice, kind)
#   kind 'verdict': prints 7;  'count': > 0;  'viol': a calc violation counter (mode 2 packs edge + violations << 21)
MUTANTS = [
    ('calc-q6: product truncates instead of rounding half up', 'cssom.calc-q6',
     '(chk (len/rdiv (* a b) 10000))', '(chk (quot (* a b) 10000))',
     [(CALC, 4, 4, 'verdict'), (CALC, 2, 4, 'viol'), (CALC, 0, None, 'verdict')]),
    ('calc-q6: unit equality dropped from add / sub / min / max', 'cssom.calc-q6',
     '(if (and (>= d 2) (= u0 u1)) (mk (- d 1) (i64-shift-right ub 1) np) -1)',
     '(if (>= d 2) (mk (- d 1) (i64-shift-right ub 1) np) -1)',
     [(CALC, 4, 19, 'verdict'), (CALC, 2, 19, 'viol'), (CALC, 0, None, 'verdict')]),
    ('calc-q6: operand cap removed', 'cssom.calc-q6',
     '(if (and (< d 4) (< np 4))', '(if (< d 4)',
     [(CALC, 0, None, 'verdict')]),
    ('pack-q6: low field bias off by one', 'cssom.pack-q6',
     '(- (bit-and p 4294967295) 1073741825)', '(- (bit-and p 4294967295) 1073741824)',
     [(CALC, 0, None, 'verdict'), (AR, 0, None, 'verdict'), (AR, 20, None, 'verdict')]),
    ('calc f64 reference: subtraction adds', 'cssom.calc',
     '(f64-sub (value-of a) (value-of b))', '(f64-add (value-of a) (value-of b))',
     [(CALC, 4, 3, 'verdict'), (CALC, 2, 3, 'viol')]),
    ('line-height-q6: truncation replaced by rounding', 'cssom.line-height-q6',
     '(quot (* m fs) 640000)', '(len/rdiv (* m fs) 640000)',
     [(LH, 0, None, 'verdict'), (LH, 20, None, 'verdict'), (LH, 4, None, 'count'), (LH, 13, None, 'count')]),
    ('line-height f64 reference: natural leading 1.3', 'cssom.line-height',
     'natural (scaled-px 1.2 fs)', 'natural (scaled-px 1.3 fs)',
     [(LH, 0, None, 'verdict'), (LH, 20, None, 'verdict'), (LH, 13, None, 'count')]),
    ('aspect-ratio-q6: truncation replaced by rounding', 'cssom.aspect-ratio-q6',
     '(finish (* 64 (quot (* bw rd) (* 64 rn))))', '(finish (* 64 (len/rdiv (* bw rd) (* 64 rn))))',
     [(AR, 0, None, 'verdict'), (AR, 20, None, 'verdict'), (AR, 17, None, 'count'), (AR, 5, None, 'count')]),
    ('aspect-ratio f64 reference: ratio inverted in replaced-width', 'cssom.aspect-ratio',
     '(f64-mul dh (f64-div iw ih))', '(f64-mul dh (f64-div ih iw))',
     [(AR, 0, None, 'verdict'), (AR, 20, None, 'verdict'), (AR, 9, None, 'count')]),
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

    # 1 + 2. differential verdicts and pinned counts --------------------------------------------------------------
    # calc: spec points + refusal programs, then per shape the verdict and three count words
    expect(go(CALC, 0) == 42, 'calc spec / refusal points')
    tasks = [(s, m) for s in range(SHAPES) for m in (4, 1, 2, 3)]
    vals = pmap(lambda t: go(CALC, t[1], t[0]), tasks, jobs)
    shapes = {}
    for (s, m), v in zip(tasks, vals):
        row = shapes.setdefault(s, {})
        if m == 4:
            expect(v == 42, 'calc shape %d verdict %r' % (s, v))
            row['verdict'] = v
        elif m == 1:
            c = [v & 0x1FFFFF, (v >> 21) & 0x1FFFFFF, v >> 46]
            row.update({'bothInvalid': v & 0x1FFFFF, 'compared': (v >> 21) & 0x1FFFFF, 'refused': (v >> 42) & 0x1FFFFF})
        elif m == 2:
            row.update({'edge': v & 0x1FFFFF, 'violations': v >> 21})
        else:
            row['maxDeviation1000'] = v
    total = {k: sum(r[k] for r in shapes.values()) for k in ('bothInvalid', 'compared', 'refused', 'edge', 'violations')}
    total['cases'] = sum(total[k] for k in ('bothInvalid', 'compared', 'refused', 'edge', 'violations'))
    expect(total['violations'] == 0, 'calc violations %d' % total['violations'])
    dense = {}
    dtasks = [(k, w) for k, ms in CALC_DENSE.items() for w in range(4)]
    dvals = pmap(lambda t: go(CALC, CALC_DENSE[t[0]][t[1]]), dtasks, jobs)
    for (k, w), v in zip(dtasks, dvals):
        dense.setdefault(k, {})[('pairs', 'ties', 'oracleDiffersAtTie', 'oracleDiffersAwayFromTie')[w]] = v
    measured['calc'] = {'shapes': {str(s): r for s, r in shapes.items()}, 'total': total, 'dense': dense}
    # line height
    expect(go(LH, 0) == 42, 'line-height spec points')
    expect(go(LH, 20) == 42, 'line-height grids')
    lvals = pmap(lambda m: go(LH, m), LH_MODES, jobs)
    measured['lineHeight'] = {str(m): v for m, v in zip(LH_MODES, lvals)}
    # aspect ratio
    expect(go(AR, 0) == 42, 'aspect-ratio spec points')
    expect(go(AR, 20) == 42, 'aspect-ratio grids')
    avals = pmap(lambda m: go(AR, m), AR_MODES, jobs)
    measured['aspectRatio'] = {str(m): v for m, v in zip(AR_MODES, avals)}

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
        for test, mode, slice_, kind in runs:
            v = go(test, mode, slice_, replace={ns: mutant})
            good = {'verdict': v == 7, 'count': v > 0, 'viol': v >= 2097152}[kind]
            expect(good, 'mutant not detected: %s (%s mode %d slice %s printed %r)' % (name, test.name, mode, slice_, v))
            row['results'].append({'test': test.name, 'mode': mode, 'slice': slice_, 'kind': kind, 'printed': v})
        mutation_report.append(row)

    # 4. static audit and size -------------------------------------------------------------------------------------
    audit = static_audit()
    comp = G.AiueosCompiler(full, out)
    size = {}
    for label, entry in (('slice2-main2', ENTRY2), ('slice2-main0', ENTRY0)):
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
    for stem in ('calc', 'line_height', 'aspect_ratio'):
        f64src = (SRC / (stem + '.kotoba')).read_text()
        if f64src.count('(:export [') != 1:
            raise ValueError('f64 export anchor changed: ' + stem)
        f64src = f64src.replace('(:export [', '(:export [main ', 1) + '\n(defn main [] :i64 0)\n'
        for t in ('x86_64-aiueos-kernel-v1', 'x86_64-aiueos-user-v1'):
            size['f64-' + stem + '/' + t] = comp.refusal('f64-' + stem, f64src, t)
            expect(not size['f64-' + stem + '/' + t]['ok'], 'f64 module unexpectedly compiled: ' + stem)
    expect(size['slice2-main2/x86_64-aiueos-kernel-v1']['ok'], 'kernel-v1 compile of the slice-2 core failed')
    expect(size['slice2-main0/x86_64-aiueos-kernel-v1']['ok'], 'kernel-v1 compile of the zero-argument slice-2 core failed')
    expect(size['slice2-main0/x86_64-aiueos-user-v1'].get('error') == 'E7104', 'user-v1 verdict is not the E7104 text limit')
    expect(size['six-parameter-control/x86_64-aiueos-kernel-v1'].get('error') == 'E7102', 'six-parameter control not refused')

    # pins ---------------------------------------------------------------------------------------------------------
    if any(sha(p) != pins[str(p)] for p in tracked):
        raise ValueError('source or compiler changed during gate')
    keep = ('ok', 'textBytes', 'error', 'detail', 'text')
    snapshot = {'measured': measured, 'staticAudit': audit,
                'size': {k: {x: y for x, y in v.items() if x in keep} for k, v in size.items()}}
    receipt = {'status': 'PASS_NATIVE_CSSOM_CALC_LINE_ASPECT_Q6', 'inputs': pins, **snapshot,
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
PINNED = json.loads('''
{
    "measured": {
        "aspectRatio": {
            "1": 16800,
            "10": 7680,
            "11": 5804,
            "12": 1876,
            "13": 0,
            "14": 1180224,
            "15": 332661,
            "16": 2291,
            "17": 0,
            "2": 9076,
            "22": 0,
            "23": 1180224,
            "24": 332661,
            "25": 2475,
            "26": 0,
            "3": 12,
            "4": 7712,
            "5": 0,
            "6": 5760,
            "7": 4526,
            "8": 1234,
            "9": 0
        },
        "calc": {
            "dense": {
                "div": {
                    "oracleDiffersAtTie": 542,
                    "oracleDiffersAwayFromTie": 0,
                    "pairs": 40960000,
                    "ties": 17416
                },
                "mul": {
                    "oracleDiffersAtTie": 805,
                    "oracleDiffersAwayFromTie": 0,
                    "pairs": 40962048,
                    "ties": 31504
                }
            },
            "shapes": {
                "0": {
                    "bothInvalid": 0,
                    "compared": 15,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 1,
                    "verdict": 42,
                    "violations": 0
                },
                "1": {
                    "bothInvalid": 0,
                    "compared": 15,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 1,
                    "verdict": 42,
                    "violations": 0
                },
                "10": {
                    "bothInvalid": 0,
                    "compared": 168,
                    "edge": 40,
                    "maxDeviation1000": 1000,
                    "refused": 48,
                    "verdict": 42,
                    "violations": 0
                },
                "11": {
                    "bothInvalid": 0,
                    "compared": 15,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 1,
                    "verdict": 42,
                    "violations": 0
                },
                "12": {
                    "bothInvalid": 0,
                    "compared": 15,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 1,
                    "verdict": 42,
                    "violations": 0
                },
                "13": {
                    "bothInvalid": 0,
                    "compared": 225,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 31,
                    "verdict": 42,
                    "violations": 0
                },
                "14": {
                    "bothInvalid": 0,
                    "compared": 225,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 31,
                    "verdict": 42,
                    "violations": 0
                },
                "15": {
                    "bothInvalid": 256,
                    "compared": 0,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 0,
                    "verdict": 42,
                    "violations": 0
                },
                "16": {
                    "bothInvalid": 0,
                    "compared": 3375,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 721,
                    "verdict": 42,
                    "violations": 0
                },
                "17": {
                    "bothInvalid": 0,
                    "compared": 3375,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 721,
                    "verdict": 42,
                    "violations": 0
                },
                "18": {
                    "bothInvalid": 4096,
                    "compared": 0,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 0,
                    "verdict": 42,
                    "violations": 0
                },
                "19": {
                    "bothInvalid": 256,
                    "compared": 0,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 0,
                    "verdict": 42,
                    "violations": 0
                },
                "2": {
                    "bothInvalid": 0,
                    "compared": 199,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 57,
                    "verdict": 42,
                    "violations": 0
                },
                "20": {
                    "bothInvalid": 0,
                    "compared": 2163,
                    "edge": 486,
                    "maxDeviation1000": 1000,
                    "refused": 1447,
                    "verdict": 42,
                    "violations": 0
                },
                "21": {
                    "bothInvalid": 0,
                    "compared": 2184,
                    "edge": 734,
                    "maxDeviation1000": 1000,
                    "refused": 1178,
                    "verdict": 42,
                    "violations": 0
                },
                "22": {
                    "bothInvalid": 256,
                    "compared": 2024,
                    "edge": 576,
                    "maxDeviation1000": 1000,
                    "refused": 1240,
                    "verdict": 42,
                    "violations": 0
                },
                "23": {
                    "bothInvalid": 0,
                    "compared": 50625,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 14911,
                    "verdict": 42,
                    "violations": 0
                },
                "24": {
                    "bothInvalid": 0,
                    "compared": 2184,
                    "edge": 936,
                    "maxDeviation1000": 1000,
                    "refused": 976,
                    "verdict": 42,
                    "violations": 0
                },
                "25": {
                    "bothInvalid": 0,
                    "compared": 28194,
                    "edge": 7434,
                    "maxDeviation1000": 1000,
                    "refused": 29908,
                    "verdict": 42,
                    "violations": 0
                },
                "26": {
                    "bothInvalid": 0,
                    "compared": 2173,
                    "edge": 736,
                    "maxDeviation1000": 7446,
                    "refused": 1187,
                    "verdict": 42,
                    "violations": 0
                },
                "27": {
                    "bothInvalid": 256,
                    "compared": 2013,
                    "edge": 764,
                    "maxDeviation1000": 10000000,
                    "refused": 1063,
                    "verdict": 42,
                    "violations": 0
                },
                "28": {
                    "bothInvalid": 256,
                    "compared": 1984,
                    "edge": 748,
                    "maxDeviation1000": 7437,
                    "refused": 1108,
                    "verdict": 42,
                    "violations": 0
                },
                "29": {
                    "bothInvalid": 0,
                    "compared": 37369,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 28167,
                    "verdict": 42,
                    "violations": 0
                },
                "3": {
                    "bothInvalid": 0,
                    "compared": 199,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 57,
                    "verdict": 42,
                    "violations": 0
                },
                "30": {
                    "bothInvalid": 0,
                    "compared": 168,
                    "edge": 40,
                    "maxDeviation1000": 1000,
                    "refused": 48,
                    "verdict": 42,
                    "violations": 0
                },
                "31": {
                    "bothInvalid": 0,
                    "compared": 199,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 57,
                    "verdict": 42,
                    "violations": 0
                },
                "32": {
                    "bothInvalid": 0,
                    "compared": 3375,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 721,
                    "verdict": 42,
                    "violations": 0
                },
                "33": {
                    "bothInvalid": 0,
                    "compared": 15,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 1,
                    "verdict": 42,
                    "violations": 0
                },
                "4": {
                    "bothInvalid": 0,
                    "compared": 168,
                    "edge": 40,
                    "maxDeviation1000": 1000,
                    "refused": 48,
                    "verdict": 42,
                    "violations": 0
                },
                "5": {
                    "bothInvalid": 0,
                    "compared": 168,
                    "edge": 40,
                    "maxDeviation1000": 1000,
                    "refused": 48,
                    "verdict": 42,
                    "violations": 0
                },
                "6": {
                    "bothInvalid": 256,
                    "compared": 0,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 0,
                    "verdict": 42,
                    "violations": 0
                },
                "7": {
                    "bothInvalid": 16,
                    "compared": 156,
                    "edge": 40,
                    "maxDeviation1000": 1000,
                    "refused": 44,
                    "verdict": 42,
                    "violations": 0
                },
                "8": {
                    "bothInvalid": 256,
                    "compared": 0,
                    "edge": 0,
                    "maxDeviation1000": 0,
                    "refused": 0,
                    "verdict": 42,
                    "violations": 0
                },
                "9": {
                    "bothInvalid": 16,
                    "compared": 156,
                    "edge": 40,
                    "maxDeviation1000": 1000,
                    "refused": 44,
                    "verdict": 42,
                    "violations": 0
                }
            },
            "total": {
                "bothInvalid": 5920,
                "cases": 245584,
                "compared": 143144,
                "edge": 12654,
                "refused": 83866,
                "violations": 0
            }
        },
        "lineHeight": {
            "1": 128256,
            "10": 19464,
            "11": 24,
            "12": 5712,
            "13": 0,
            "14": 0,
            "15": 0,
            "16": 0,
            "17": 0,
            "18": 1139727,
            "2": 6716,
            "3": 183,
            "4": 0,
            "5": 38360211,
            "6": 14128,
            "7": 17,
            "8": 0,
            "9": 25200
        }
    },
    "size": {
        "f64-aspect_ratio/x86_64-aiueos-kernel-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'block-height': expected :i64 (byte 1199)"
        },
        "f64-aspect_ratio/x86_64-aiueos-user-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'block-height': expected :i64 (byte 1199)"
        },
        "f64-calc/x86_64-aiueos-kernel-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'value-of': expected :i64 (byte 2426)"
        },
        "f64-calc/x86_64-aiueos-user-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'value-of': expected :i64 (byte 2426)"
        },
        "f64-line_height/x86_64-aiueos-kernel-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'scaled-px': expected :i64 (byte 1777)"
        },
        "f64-line_height/x86_64-aiueos-user-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'scaled-px': expected :i64 (byte 1777)"
        },
        "module-aspect_ratio_q6/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 12251
        },
        "module-calc_q6/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 16833
        },
        "module-line_height_q6/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 9788
        },
        "module-pack_q6/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 1425
        },
        "module0-aspect_ratio_q6/x86_64-aiueos-user-v1": {
            "detail": 11939,
            "error": "E7104",
            "ok": false
        },
        "module0-calc_q6/x86_64-aiueos-user-v1": {
            "detail": 16482,
            "error": "E7104",
            "ok": false
        },
        "module0-line_height_q6/x86_64-aiueos-user-v1": {
            "detail": 9467,
            "error": "E7104",
            "ok": false
        },
        "module0-pack_q6/x86_64-aiueos-user-v1": {
            "ok": true
        },
        "six-parameter-control/x86_64-aiueos-kernel-v1": {
            "detail": 1,
            "error": "E7102",
            "ok": false
        },
        "slice2-main0/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 29789
        },
        "slice2-main0/x86_64-aiueos-user-v1": {
            "detail": 29437,
            "error": "E7104",
            "ok": false
        },
        "slice2-main2/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 29662
        },
        "slice2-main2/x86_64-aiueos-user-v1": {
            "detail": 66,
            "error": "E7102",
            "ok": false
        }
    },
    "staticAudit": {
        "aspect_ratio_q6": {
            "defns": 12,
            "maxParams": 5,
            "multiplications": 10,
            "multiplicationsOfTwoVariables": 4,
            "sourceLines": 44
        },
        "calc_q6": {
            "defns": 16,
            "maxParams": 5,
            "multiplications": 5,
            "multiplicationsOfTwoVariables": 2,
            "sourceLines": 54
        },
        "line_height_q6": {
            "defns": 12,
            "maxParams": 4,
            "multiplications": 4,
            "multiplicationsOfTwoVariables": 2,
            "sourceLines": 36
        },
        "pack_q6": {
            "defns": 4,
            "maxParams": 2,
            "multiplications": 0,
            "multiplicationsOfTwoVariables": 0,
            "sourceLines": 6
        }
    }
}
''')

if __name__ == '__main__':
    main()
