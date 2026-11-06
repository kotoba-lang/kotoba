#!/usr/bin/env python3
"""Observe the Q17 / Q6 fixed-point CSS transforms of the CSSOM (JUN-929 / C2b-4, census group G05) with a native Amu CLI.

Slice 4 covers census group G05: the 2D transform matrices of layout.cljk (95 float hits), i.e. sin / cos / tan for rotate and skew
(cssom.trig-q6) and the 2D affine matrix algebra (cssom.transform-q6). All with the pinned native macOS Amu binary and no JVM, nbb or
babashka. THIS SLICE HAS NO NATIVE RUNTIME ORACLE: the native f64 dialect has no sin / cos / tan (and the f64 side would be the inexactness
the Q6 rule replaces). The reference is DATA produced once by Python (a dated one-off oracle run, evidence
cssom-q6-transform-20261106, scripts gen_trig_golden.py / gen_transform_golden.py, which are never run here):

  1. GOLDEN TABLES, PINNED: sha256 of every golden file (TSV for reading, generated .kotoba data modules for the native tests) is pinned
     below and checked before and after the run; the data modules are decoded here and must equal the TSV rows bit for bit.
  2. TRIG: test/native/q6_trig_vs_golden.kotoba compares sin17 / cos17 / tan17 (and sin30 / cos30) with math.sin / cos / tan rounded to Q17
     (12,609 angle rows in deg, grad, rad, turn, 9 outside the domain) and must print 42; the counts and maximum errors are pinned.
  3. MATRIX: test/native/q6_transform_vs_exact.kotoba compares the matrix algebra with an exact-rational (fractions.Fraction) reference
     (1500 cases x 15 functions, 81 x 81 flow pairs, hand-derived spec points, isqrt invariants) and the end-to-end point images with
     ideal real-valued results (rotate*scale and skew*rotate about an origin point, two composition routes); must print 42; counts pinned.
  4. NEGATIVE CONTROLS: one or more mutations of every module (each anchor must occur exactly once) make the verdict print 7, and
     MUTANTS OF THE TABLES THEMSELVES (one leaf changed in the golden data) make it print 7 too.
  5. SIZE: the arithmetic core is bundled into one source and compiled with the pinned amu-full-root for x86_64-aiueos-kernel-v1 (text
     bytes pinned, per module and whole) and x86_64-aiueos-user-v1 (exact error codes pinned); a six-parameter function must be refused.
  6. STATIC AUDIT: at most five parameters per function, no floats, strings, records, loops or division except quot.

It reuses the helpers of check-block-q6-native-macos.py (slice 1). It does not claim CPL3 execution, a wired layout.cljk, or a browser verdict.
"""
import argparse
import hashlib
import importlib.util
import json
import platform
import re
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('block_q6_gate', HERE / 'check-block-q6-native-macos.py')
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)

OWNER, SRC, TESTS, AIUEOS = G.OWNER, G.SRC, G.TESTS, G.AIUEOS
sha, pmap, Native = G.sha, G.pmap, G.Native
EVIDENCE = OWNER.parent / 'kotoba.aiueos/90-docs/evidence/cssom-q6-transform-20261106'

MODULES = {
    'cssom.length-q6': SRC / 'length_q6.kotoba',
    'cssom.pack-q6': SRC / 'pack_q6.kotoba',
    'cssom.trig-q6': SRC / 'trig_q6.kotoba',
    'cssom.transform-q6': SRC / 'transform_q6.kotoba',
    'cssom.trig-golden': EVIDENCE / 'trig_golden.kotoba',
    'cssom.transform-golden-a': EVIDENCE / 'transform_golden_a.kotoba',
    'cssom.transform-golden-b': EVIDENCE / 'transform_golden_b.kotoba',
    'cssom.transform-golden-c': EVIDENCE / 'transform_golden_c.kotoba',
}
CORE = ['trig_q6', 'transform_q6']
TRIG = TESTS / 'q6_trig_vs_golden.kotoba'
TRANS = TESTS / 'q6_transform_vs_exact.kotoba'
ENTRY2 = AIUEOS / 'q6_transform_entry.kotoba'
ENTRY0 = AIUEOS / 'q6_transform_entry_zero.kotoba'
NEEDS = {
    TRIG: ['cssom.length-q6', 'cssom.trig-q6', 'cssom.trig-golden'],
    TRANS: ['cssom.length-q6', 'cssom.pack-q6', 'cssom.trig-q6', 'cssom.transform-q6', 'cssom.transform-golden-a',
            'cssom.transform-golden-b', 'cssom.transform-golden-c'],
}
TRIG_MODES = list(range(1, 27))
TRANS_MODES = list(range(1, 25))
E2E_MODES = [30 + 20 * pl + 10 * route + w for pl in (0, 1) for route in (0, 1) for w in range(9)]

# the golden files: sha256 pinned (the one-time Python oracle run, 2026-11-06, Python 3.15.0, macOS arm64)
GOLDEN_PINS = {
    'trig-golden.tsv': 'd87da8699a9ba78dd34c2938fecb770eb8b13944259a26739b733d4a112acd7f',
    'trig_golden.kotoba': '0e18b7f513f2204ac426ba63bc2718bebd40dd74491f8e876babcc3f6c39bcb8',
    'transform-golden.tsv': '68381d0251a86aa78e1cc9b18cfa030c06dda7a880a9bc3b1155ac5ac05e73d3',
    'transform-golden-c.tsv': '9fd2519499c85211b2f29667f239c7c08557d6ae520324b8f3b56579eb839eb9',
    'transform_golden_a.kotoba': '874a07c3293629a2f95058ed74228c5bd6dad74b1d722f4727534c52c5b512a4',
    'transform_golden_b.kotoba': '395388cd95b08e74c5e8e4d03b401ef6c542825c9622adc52d1044d92c9e1b59',
    'transform_golden_c.kotoba': 'bdb47d9bf77596c35cf2ea1dea2f9227b1941c430f06e82932574112684b6d3d',
}
INV = -4611686018427387904


# ---- decoding the generated data modules back to the TSV (consistency of the two golden forms) --------------------------------
PREFIX = re.compile(r'\(if \(< i \d+\) |(-?\d+|X)')


def tree_leaves(text, name):
    line = [l for l in text.split('\n') if l.startswith('(defn %s [' % name)]
    if len(line) != 1:
        raise ValueError('data function not found exactly once: ' + name)
    body = line[0].split(':i64 ', 1)[1]
    out = []
    for m in PREFIX.finditer(body):
        if m.group(1) is not None:
            out.append(INV if m.group(1) == 'X' else int(m.group(1)))
    return out


def tsv_rows(path):
    rows = [l.split('\t') for l in path.read_text().split('\n') if l]
    return rows[0], rows[1:]


def check_golden_consistency():
    """Decode the data modules and compare with the TSV tables; returns counts. Raises on any difference."""
    inv = lambda s: None if s == 'INV' else int(s)
    # trig
    _, rows = tsv_rows(EVIDENCE / 'trig-golden.tsv')
    text = (EVIDENCE / 'trig_golden.kotoba').read_text()
    g_in, g_q, g_s, g_c = (tree_leaves(text, n) for n in ('g-in', 'g-q17', 'g-s30', 'g-c30'))
    exp_in, exp_q, exp_s, exp_c = [], [], [], []
    for r in rows:
        u, v, s17, c17, t17, s30, c30 = int(r[1]), int(r[2]), inv(r[3]), inv(r[4]), inv(r[5]), inv(r[6]), inv(r[7])
        exp_in.append(u + 8 * (v + 2 ** 35))
        exp_q.append(0 if s17 is None else (s17 + 2 ** 18) + ((c17 + 2 ** 18) << 19) + ((0 if t17 is None else t17 + 2 ** 23) << 38))
    for k in range(0, len(rows), 4):
        s30, c30 = inv(rows[k][6]), inv(rows[k][7])
        exp_s.append(0 if s30 is None else s30 + 2 ** 30 + 1)
        exp_c.append(0 if c30 is None else c30 + 2 ** 30 + 1)
    if (g_in, g_q, g_s, g_c) != (exp_in, exp_q, exp_s, exp_c):
        raise ValueError('trig data module differs from trig-golden.tsv')
    # transform P1
    head, prow = tsv_rows(EVIDENCE / 'transform-golden.tsv')
    ta = (EVIDENCE / 'transform_golden_a.kotoba').read_text()
    tb = (EVIDENCE / 'transform_golden_b.kotoba').read_text()
    for f in range(15):
        leaves = tree_leaves(ta if f < 8 else tb, 'g1-%d' % f)
        col = [INV if r[1 + f] == 'INV' else int(r[1 + f]) for r in prow]
        if leaves != col:
            raise ValueError('transform data module differs from transform-golden.tsv, function %d' % f)
    # transform flow / e2e
    _, crow = tsv_rows(EVIDENCE / 'transform-golden-c.tsv')
    tc = (EVIDENCE / 'transform_golden_c.kotoba').read_text()
    sections = {}
    for sec, idx, val in crow:
        sections.setdefault(sec, []).append(INV if val == 'INV' else int(val))
    for sec, fn in (('flow', 'g-flow'), ('flow-ab', 'g-flow-ab'), ('flow-cd', 'g-flow-cd'), ('e2e-x-0', 'g-e2e-x-0'),
                    ('e2e-x-1', 'g-e2e-x-1'), ('e2e-y-0', 'g-e2e-y-0'), ('e2e-y-1', 'g-e2e-y-1')):
        if tree_leaves(tc, fn) != sections[sec]:
            raise ValueError('transform data module differs from transform-golden-c.tsv: ' + sec)
    return {'trigRows': len(rows), 'trigQ30Rows': len(exp_s), 'transformCases': len(prow), 'transformColumns': 15,
            'flowPairs': len(sections['flow']), 'e2eWords': sum(len(v) for k, v in sections.items() if k.startswith('e2e'))}


def mutate_leaf(text, name, which, f):
    """Return `text` with the `which`-th leaf of data function `name` replaced by f(old). The leaf is located by position in the line."""
    out, pos = [], 0
    lines = text.split('\n')
    for li, l in enumerate(lines):
        if l.startswith('(defn %s [' % name):
            start = l.index(':i64 ') + 5
            n = -1
            for m in PREFIX.finditer(l, start):
                if m.group(1) is not None:
                    n += 1
                    if (n == which) if isinstance(which, int) else which(INV if m.group(1) == 'X' else int(m.group(1))):
                        new = f(INV if m.group(1) == 'X' else int(m.group(1)))
                        lines[li] = l[:m.start(1)] + ('X' if new == INV else str(new)) + l[m.end(1):]
                        return '\n'.join(lines)
    raise ValueError('leaf not found: %s %d' % (name, which))


# name, module ns, anchor, replacement, runs: (test, mode, kind)  kind 'verdict': the mutant prints 7;  'count': the mode prints > 0
MUTANTS = [
    ('trig-q6: sin polynomial divisor 6 -> 7', 'cssom.trig-q6', 'w2 (lv u w3 6)', 'w2 (lv u w3 7)',
     [(TRIG, 0, 'verdict'), (TRIG, 6, 'count')]),
    ('trig-q6: cos quadrant 1 loses its sign', 'cssom.trig-q6', '(= k 1) (- 0 (psi-sin n theta))', '(= k 1) (psi-sin n theta)',
     [(TRIG, 0, 'verdict'), (TRIG, 9, 'count')]),
    ('trig-q6: the Q17 rounding floors', 'cssom.trig-q6', '(defn to17 [x :i64] :i64 (len/rdiv x 8192))',
     '(defn to17 [x :i64] :i64 (len/fdiv x 8192))', [(TRIG, 0, 'verdict'), (TRIG, 5, 'count')]),
    ('trig-q6: the degree domain edge moved by one micro-degree', 'cssom.trig-q6', '(= unit 1) 11520000000', '(= unit 1) 11520000001',
     [(TRIG, 0, 'verdict'), (TRIG, 3, 'count')]),
    ('trig-q6: tan refusal threshold doubled', 'cssom.trig-q6', '(> m 8388607) (invalid)', '(> m 16777215) (invalid)',
     [(TRIG, 0, 'verdict'), (TRIG, 19, 'count')]),
    ('trig-q6: rad residual divisor 15625 -> 15626', 'cssom.trig-q6', '(len/rdiv (* r16 256) 15625)', '(len/rdiv (* r16 256) 15626)',
     [(TRIG, 0, 'verdict'), (TRIG, 23, 'count')]),
    ('trig-q6: degree constant off by 1e-7 relative', 'cssom.trig-q6', '(= unit 1) 628821134', '(= unit 1) 628821234',
     [(TRIG, 0, 'verdict'), (TRIG, 23, 'count')]),
    ('transform-q6: mul-ab reads the wrong factor', 'cssom.transform-q6',
     '(len/rdiv (+ (* (pk/hi ab1) (pk/hi ab2)) (* (pk/hi cd1) (pk/lo ab2))) 131072)',
     '(len/rdiv (+ (* (pk/hi ab1) (pk/hi ab2)) (* (pk/hi cd1) (pk/hi ab2))) 131072)', [(TRANS, 0, 'verdict'), (TRANS, 2, 'count')]),
    ('transform-q6: about-ef adds the product instead of subtracting it', 'cssom.transform-q6',
     '(len/rdiv (- (* (+ (pk/hi ef) (pk/hi cxy)) 131072)', '(len/rdiv (+ (* (+ (pk/hi ef) (pk/hi cxy)) 131072)',
     [(TRANS, 0, 'verdict'), (TRANS, 5, 'count')]),
    ('transform-q6: isqrt step uses < instead of <=', 'cssom.transform-q6',
     '(if (<= (* (+ r b) (+ r b)) n) (+ r b) r)', '(if (< (* (+ r b) (+ r b)) n) (+ r b) r)', [(TRANS, 0, 'verdict'), (TRANS, 23, 'count')]),
    ('transform-q6: uniform-scale truncates its root', 'cssom.transform-q6',
     '(let [r (isqrt n)] (if (> (- n (* r r)) r) (+ r 1) r))', '(let [r (isqrt n)] r)', [(TRANS, 0, 'verdict'), (TRANS, 12, 'count')]),
    ('transform-q6: flow-rotation inverse loses a sign', 'cssom.transform-q6',
     'ib (* det (- 0 (dig parent 1)))', 'ib (* det (dig parent 1))', [(TRANS, 0, 'verdict'), (TRANS, 18, 'count')]),
    ('transform-q6: number divisor 15625 -> 15626', 'cssom.transform-q6',
     '(len/rdiv (* v6 2048) 15625)', '(len/rdiv (* v6 2048) 15626)', [(TRANS, 0, 'verdict'), (TRANS, 1, 'count')]),
    ('transform-q6: map-x floors instead of rounding half up', 'cssom.transform-q6',
     '(let [r (len/rdiv (+ (+ (* (pk/hi ab) x) (* (pk/hi cd) y)) (* (pk/hi ef) 131072)) 131072)]',
     '(let [r (len/fdiv (+ (+ (* (pk/hi ab) x) (* (pk/hi cd) y)) (* (pk/hi ef) 131072)) 131072)]', [(TRANS, 0, 'verdict'), (TRANS, 6, 'count')]),
    ('transform-q6: origin centre truncates', 'cssom.transform-q6', '(= kind 0) (len/rdiv basis 2)', '(= kind 0) (quot basis 2)',
     [(TRANS, 0, 'verdict'), (TRANS, 15, 'count')]),
    ('transform-q6: max of the four corners is the minimum', 'cssom.transform-q6',
     '(if (> m1 m2) m1 m2)', '(if (> m1 m2) m2 m1)', [(TRANS, 0, 'verdict'), (TRANS, 9, 'count')]),
    ('transform-q6: skew-y sign flipped', 'cssom.transform-q6',
     '(mk-lin 131072 (tg/tan17 uy vy))', '(mk-lin 131072 (- 0 (tg/tan17 uy vy)))', [(TRANS, 0, 'verdict'), (TRANS, 52, 'count')]),
    ('length-q6 (shared): round half up replaced by floor', 'cssom.length-q6',
     '(fdiv (+ (* 2 n) d) (* 2 d))', '(fdiv (* 2 n) (* 2 d))', [(TRIG, 0, 'verdict'), (TRANS, 0, 'verdict')]),
    ('pack-q6 (shared): low field offset by one', 'cssom.pack-q6',
     '(- (bit-and p 4294967295) 1073741825)', '(- (bit-and p 4294967295) 1073741824)', [(TRANS, 0, 'verdict'), (TRANS, 2, 'count')]),
]
# mutants of the TABLES: (name, ns, data function, leaf index, change, runs)
TABLE_MUTANTS = [
    ('golden trig: sin17 of row 0 off by 2', 'cssom.trig-golden', 'g-q17', 0, lambda v: v + 2, [(TRIG, 0, 'verdict'), (TRIG, 6, 'count')]),
    ('golden trig: tan17 of row 1 off by 50', 'cssom.trig-golden', 'g-q17', 1, lambda v: v + (50 << 38), [(TRIG, 0, 'verdict'), (TRIG, 15, 'count')]),
    ('golden trig: row 0 marked invalid', 'cssom.trig-golden', 'g-q17', 0, lambda v: 0, [(TRIG, 0, 'verdict'), (TRIG, 3, 'count')]),
    ('golden trig: angle of row 1 moved by half a degree', 'cssom.trig-golden', 'g-in', 1, lambda v: v + 8 * 500000,
     [(TRIG, 0, 'verdict'), (TRIG, 6, 'count')]),
    ('golden trig: Q30 sin of a row off by 5', 'cssom.trig-golden', 'g-s30', 1, lambda v: v + 5, [(TRIG, 0, 'verdict'), (TRIG, 23, 'count')]),
    ('golden transform: mul-ef word of case 0 changed', 'cssom.transform-golden-a', 'g1-3', 0, lambda v: 12345 if v == INV else v + 7,
     [(TRANS, 0, 'verdict'), (TRANS, 4, 'count')]),
    ('golden transform: isqrt word of case 3 changed', 'cssom.transform-golden-b', 'g1-13', 3, lambda v: 12345 if v == INV else v + 1,
     [(TRANS, 0, 'verdict'), (TRANS, 14, 'count')]),
    ('golden transform: a flow pair changed', 'cssom.transform-golden-c', 'g-flow', 0, lambda v: 5 if v == INV else INV,
     [(TRANS, 0, 'verdict'), (TRANS, 18, 'count')]),
    ('golden transform: one ideal end-to-end image moved', 'cssom.transform-golden-c', 'g-e2e-x-0', lambda v: v != 0 and v != INV, lambda v: v + 100000,
     [(TRANS, 0, 'verdict'), (TRANS, 32, 'count')]),
]


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
        tokens = G.TOK.findall(code)
        bad = sorted({t for t in tokens if t in ('/', 'rem', 'mod', 'loop', 'recur') or t.startswith('f64') or t == 'record'
                      or t.startswith('record-') or t == ':string' or t.startswith('string-')})
        if bad:
            raise ValueError(('forbidden form in the core', stem, bad))
        mult = re.findall(r'\(\*\s+(\S+)\s+(\S+)\)', code)
        two_var = [m for m in mult if not (re.fullmatch(r'-?\d+', m[0]) or re.fullmatch(r'-?\d+', m[1]))]
        audit[stem] = {'defns': len(defns), 'maxParams': max(params.values()), 'multiplications': len(mult),
                       'multiplicationsOfTwoVariables': len(two_var), 'sourceLines': len([l for l in code.split('\n') if l.strip()])}
    return audit


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
    # 1. golden pins (before anything runs)
    for name, want in GOLDEN_PINS.items():
        if sha(EVIDENCE / name) != want:
            raise ValueError('golden table changed: %s' % name)
    golden = check_golden_consistency()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    tracked = [amu, full, Path(__file__).resolve(), ENTRY2, ENTRY0] + sorted(set(MODULES.values())) + sorted(NEEDS)
    pins = {str(p): sha(p) for p in tracked}
    nat = Native(amu, out)
    jobs = args.jobs
    mods = lambda test: {n: MODULES[n] for n in NEEDS[test]}
    measured = {'golden': golden}
    failures = []
    counter = [0]
    lock = threading.Lock()

    def tag(prefix):
        with lock:
            counter[0] += 1
            return '%s-%03d' % (prefix, counter[0])

    def go(test, mode, replace=None):
        m = mods(test)
        if replace:
            m = dict(m)
            m.update(replace)
        return nat.run(tag(test.stem), test, m, mode, None)

    def expect(cond, what):
        if not cond:
            failures.append(what)

    # 2 + 3. differential verdicts and pinned counts -------------------------------------------------------------
    tasks = [(TRIG, m) for m in [0] + TRIG_MODES] + [(TRANS, m) for m in [0] + TRANS_MODES + E2E_MODES]
    vals = pmap(lambda t: go(t[0], t[1]), tasks, jobs)
    res = {(t[0].stem, t[1]): v for t, v in zip(tasks, vals)}
    expect(res[(TRIG.stem, 0)] == 42, 'trig verdict: %r' % res[(TRIG.stem, 0)])
    expect(res[(TRANS.stem, 0)] == 42, 'transform verdict: %r' % res[(TRANS.stem, 0)])
    measured['trig'] = {str(m): res[(TRIG.stem, m)] for m in TRIG_MODES}
    measured['transform'] = {str(m): res[(TRANS.stem, m)] for m in TRANS_MODES}
    measured['endToEnd'] = {str(m): res[(TRANS.stem, m)] for m in E2E_MODES}

    # 4. negative controls -------------------------------------------------------------------------------------------
    mutation_report = []
    jobs_list = []
    for name, ns, anchor, replacement, runs in MUTANTS:
        src = MODULES[ns]
        text = src.read_text()
        if text.count(anchor) != 1:
            raise ValueError('mutation anchor changed: ' + name)
        mdir = out / ('mutant-' + re.sub(r'\W+', '-', name))
        mdir.mkdir()
        mutant = mdir / src.name
        mutant.write_text(text.replace(anchor, replacement))
        jobs_list.append((name, ns, mutant, runs))
    for name, ns, fn, which, change, runs in TABLE_MUTANTS:
        src = MODULES[ns]
        mdir = out / ('mutant-' + re.sub(r'\W+', '-', name))
        mdir.mkdir()
        mutant = mdir / src.name
        mutant.write_text(mutate_leaf(src.read_text(), fn, which, change))
        if sha(mutant) == sha(src):
            raise ValueError('table mutation changed nothing: ' + name)
        jobs_list.append((name, ns, mutant, runs))
    flat = [(name, ns, mutant, test, mode, kind) for name, ns, mutant, runs in jobs_list for test, mode, kind in runs]
    mvals = pmap(lambda r: go(r[3], r[4], replace={r[1]: r[2]}), flat, jobs)
    rows = {}
    for (name, ns, mutant, test, mode, kind), v in zip(flat, mvals):
        good = (v == 7) if kind == 'verdict' else (v > 0)
        expect(good, 'mutant not detected: %s (%s mode %d printed %r)' % (name, test.name, mode, v))
        rows.setdefault(name, {'mutation': name, 'module': ns, 'results': []})['results'].append(
            {'test': test.name, 'mode': mode, 'kind': kind, 'printed': v})
    mutation_report = list(rows.values())

    # 5. static audit and size ---------------------------------------------------------------------------------------
    audit = static_audit()
    comp = G.AiueosCompiler(full, out)
    size = {}
    whole2 = G.bundle(ENTRY2.read_text())
    whole0 = G.bundle(ENTRY0.read_text())
    for label, src in (('core-main2', whole2), ('core-main0', whole0)):
        for t in ('x86_64-aiueos-kernel-v1', 'x86_64-aiueos-user-v1'):
            size[label + '/' + t] = comp.compile(label, src, t)
    for stem in CORE:
        src = G.bundle(G.module_main(stem))
        size['module-' + stem + '/x86_64-aiueos-kernel-v1'] = comp.compile('module-' + stem, src, 'x86_64-aiueos-kernel-v1')
    six = '(ns six (:export [main]))\n(defn f [a :i64 b :i64 c :i64 d :i64 e :i64 g :i64] :i64 (+ a (+ b (+ c (+ d (+ e g))))))\n(defn main [] :i64 (f 1 2 3 4 5 6))\n'
    size['six-parameter-control/x86_64-aiueos-kernel-v1'] = comp.compile('six', six, 'x86_64-aiueos-kernel-v1')
    expect(size['core-main2/x86_64-aiueos-kernel-v1']['ok'], 'kernel-v1 compile of the core failed')
    expect(size['core-main0/x86_64-aiueos-kernel-v1']['ok'], 'kernel-v1 compile of the zero-argument core failed')
    expect(size['core-main0/x86_64-aiueos-user-v1'].get('error') == 'E7104', 'user-v1 verdict is not the E7104 text limit')
    expect(size['six-parameter-control/x86_64-aiueos-kernel-v1'].get('error') == 'E7102', 'six-parameter control not refused')

    # pins ------------------------------------------------------------------------------------------------------------
    if any(sha(p) != pins[str(p)] for p in tracked) or any(sha(EVIDENCE / n) != w for n, w in GOLDEN_PINS.items()):
        raise ValueError('source, golden table or compiler changed during gate')
    size_view = {k: {x: y for x, y in v.items() if x in ('ok', 'textBytes', 'error', 'detail', 'text')} for k, v in size.items()}
    receipt = {'status': 'PASS_NATIVE_CSSOM_TRANSFORM_Q6', 'inputs': pins, 'goldenPins': GOLDEN_PINS, 'measured': measured,
               'staticAudit': audit, 'size': size, 'negativeControls': mutation_report,
               'ranOnLiveCpl3': False, 'wiredIntoLayoutCljk': False, 'nativeRuntimeOracleForTrig': False}
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    view = {'measured': measured, 'staticAudit': audit, 'size': size_view}
    if args.print_measurements:
        (out / 'measurements.json').write_text(json.dumps(view, indent=2, sort_keys=True))
        print(json.dumps({**view, 'failures': failures}, indent=2, sort_keys=True))
        return
    for key, want in PINNED.items():
        if view[key] != want:
            failures.append('pinned %s differs: %s != %s' % (key, json.dumps(view[key], sort_keys=True), json.dumps(want, sort_keys=True)))
    if failures:
        for f in failures:
            print('FAIL ' + f, file=sys.stderr)
        raise SystemExit(1)
    print(receipt['status'])


# Pinned measurements (macOS arm64, pinned compiler, 2026-11-06). Any change in a count, a text size or a refusal fails the gate.
PINNED = json.loads('''
{
    "measured": {
        "endToEnd": {
            "30": 888,
            "31": 594,
            "32": 0,
            "33": 32,
            "34": 15,
            "35": 16,
            "36": 29,
            "37": 132,
            "38": 594,
            "40": 888,
            "41": 594,
            "42": 0,
            "43": 32,
            "44": 15,
            "45": 16,
            "46": 29,
            "47": 132,
            "48": 594,
            "50": 844,
            "51": 827,
            "52": 0,
            "53": 36,
            "54": 15,
            "55": 16,
            "56": 41,
            "57": 384,
            "58": 827,
            "60": 844,
            "61": 827,
            "62": 0,
            "63": 36,
            "64": 15,
            "65": 16,
            "66": 41,
            "67": 384,
            "68": 827
        },
        "golden": {
            "e2eWords": 4000,
            "flowPairs": 6561,
            "transformCases": 1500,
            "transformColumns": 15,
            "trigQ30Rows": 3153,
            "trigRows": 12609
        },
        "transform": {
            "1": 0,
            "10": 0,
            "11": 0,
            "12": 0,
            "13": 0,
            "14": 0,
            "15": 0,
            "16": 16967,
            "17": 5533,
            "18": 0,
            "19": 0,
            "2": 0,
            "20": 5473,
            "21": 40,
            "22": 0,
            "23": 0,
            "24": 16000,
            "3": 0,
            "4": 0,
            "5": 0,
            "6": 0,
            "7": 0,
            "8": 0,
            "9": 0
        },
        "trig": {
            "1": 12609,
            "10": 12327,
            "11": 1,
            "12": 1,
            "13": 1,
            "14": 1,
            "15": 0,
            "16": 273,
            "17": 0,
            "18": 0,
            "19": 0,
            "2": 9,
            "20": 3151,
            "21": 1,
            "22": 1,
            "23": 0,
            "24": 2,
            "25": 0,
            "26": 4097,
            "3": 0,
            "4": 12600,
            "5": 0,
            "6": 0,
            "7": 12600,
            "8": 0,
            "9": 0
        }
    },
    "size": {
        "core-main0/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 50956
        },
        "core-main0/x86_64-aiueos-user-v1": {
            "detail": 50604,
            "error": "E7104",
            "ok": false
        },
        "core-main2/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 50619
        },
        "core-main2/x86_64-aiueos-user-v1": {
            "detail": 121,
            "error": "E7102",
            "ok": false
        },
        "module-transform_q6/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 49363
        },
        "module-trig_q6/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 18360
        },
        "six-parameter-control/x86_64-aiueos-kernel-v1": {
            "detail": 1,
            "error": "E7102",
            "ok": false
        }
    },
    "staticAudit": {
        "transform_q6": {
            "defns": 54,
            "maxParams": 5,
            "multiplications": 39,
            "multiplicationsOfTwoVariables": 36,
            "sourceLines": 157
        },
        "trig_q6": {
            "defns": 41,
            "maxParams": 3,
            "multiplications": 11,
            "multiplicationsOfTwoVariables": 3,
            "sourceLines": 79
        }
    }
}
''')

if __name__ == '__main__':
    main()
