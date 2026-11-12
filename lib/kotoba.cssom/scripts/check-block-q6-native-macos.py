#!/usr/bin/env python3
"""Observe the Q6 fixed-point block vertical of the CSSOM (JUN-920 / C2b) with a native Amu CLI.

What it checks, all with the pinned native macOS Amu binary and no JVM, nbb or babashka:

  1. DIFFERENTIAL: five native tests compile against a KSL2 source lock and each must print 42:
     the Q6 modules length_q6, block_width_q6, margin_collapse_q6, block_style_q6 against the existing native f64
     modules (length, block_width, margin_collapse, block_style) over deterministic grids, and the host-only
     number scanner parse_px_q6 against an exact-rational golden table and an f64 grid. The grids are split into
     slices because the host runtime keeps every record; each slice is one binary.
  2. PINNED COUNTS: how many cases were compared, refused by the range guard, invalid on both sides, and the exact-tie
     report (how often the inexact f64 oracle disagrees with the exact Q6 rule at exact .5 ties, and that it never
     disagrees away from ties).
  3. NEGATIVE CONTROLS: one mutation per module (each anchor must occur exactly once) must make the verdict print 7
     and must be seen by the grid itself (violation counts above zero), not only by the hand-written spec points.
  4. SIZE: the arithmetic core (no parse_px_q6) is bundled into one source and compiled with the pinned
     amu-full-root for x86_64-aiueos-kernel-v1 (text bytes pinned) and x86_64-aiueos-user-v1 (the refusal is pinned
     exactly); a six-parameter function must be refused (E7102).
  5. STATIC AUDIT of the arithmetic core: at most five parameters per function, no floats, strings, records or
     division except quot, and the multiplication sites are counted.

It does not claim CPL3 execution, a wired layout.cljk, or a browser verdict. The f64 oracle is inexact at exact ties;
the Q6 rule (round half up, exact) is the specification and the owner must confirm it.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

OWNER = Path(__file__).resolve().parent.parent
SRC = OWNER / 'src/cssom'
TESTS = OWNER / 'test/native'
AIUEOS = OWNER / 'test/aiueos'

AMU_SHA256 = 'e13a20548928cd366c78641edc944e36070f7c5dbbde8cc7c35ef599570e2b02'
AMU_FULL_ROOT_SHA256 = '88623412d4470e7090037ea6b35f2176e5d6edff322e90843b84bce61f17a229'

# namespace -> file; the f64 oracles are the existing native modules
MODULES = {
    'cssom.length': SRC / 'length.kotoba',
    'cssom.block-width': SRC / 'block_width.kotoba',
    'cssom.block-style': SRC / 'block_style.kotoba',
    'cssom.margin-collapse': SRC / 'margin_collapse.kotoba',
    'cssom.length-q6': SRC / 'length_q6.kotoba',
    'cssom.parse-px-q6': SRC / 'parse_px_q6.kotoba',
    'cssom.block-width-q6': SRC / 'block_width_q6.kotoba',
    'cssom.margin-collapse-q6': SRC / 'margin_collapse_q6.kotoba',
    'cssom.block-style-q6': SRC / 'block_style_q6.kotoba',
}
CORE = ['length_q6', 'block_width_q6', 'margin_collapse_q6', 'block_style_q6']   # the arithmetic core

LENGTH = TESTS / 'q6_length_vs_f64.kotoba'
WIDTH = TESTS / 'q6_block_width_vs_f64.kotoba'
MARGIN = TESTS / 'q6_margin_collapse_vs_f64.kotoba'
STYLE = TESTS / 'q6_block_style_vs_f64.kotoba'
PARSE = TESTS / 'q6_parse_px_vs_f64.kotoba'
ENTRY2 = AIUEOS / 'q6_core_entry.kotoba'
ENTRY0 = AIUEOS / 'q6_core_entry_zero.kotoba'

# test -> modules (namespaces) it needs
NEEDS = {
    LENGTH: ['cssom.length', 'cssom.length-q6'],
    WIDTH: ['cssom.block-width', 'cssom.block-width-q6'],
    MARGIN: ['cssom.margin-collapse', 'cssom.margin-collapse-q6'],
    STYLE: ['cssom.length', 'cssom.block-width', 'cssom.block-style', 'cssom.length-q6', 'cssom.block-width-q6',
            'cssom.block-style-q6'],
    PARSE: ['cssom.length-q6', 'cssom.parse-px-q6'],
}
WIDTH_SLICES = {1: 9, 2: 20, 3: 4}   # grid -> slices (modes 10 * grid + which)
STYLE_SLICES = 28

MUTANTS = [
    # name, module ns, anchor, replacement, runs: (test, mode, slice, kind) kind: 'verdict' prints 7, 'count' > 0
    ('block-width: auto-margin half shifted by 2', 'cssom.block-width-q6',
     'half (i64-shift-right remaining 1)', 'half (i64-shift-right remaining 2)',
     [(WIDTH, 0, 0, 'verdict'), (WIDTH, 14, 3, 'verdict'), (WIDTH, 13, 3, 'count')]),
    ('length: round half up replaced by floor', 'cssom.length-q6',
     '(fdiv (+ (* 2 n) d) (* 2 d))', '(fdiv (* 2 n) (* 2 d))',
     [(LENGTH, 0, None, 'verdict'), (LENGTH, 3, None, 'count'), (LENGTH, 7, None, 'count')]),
    ('margin-collapse: negative extremum subtracted', 'cssom.margin-collapse-q6',
     '(+ (positive state) (negative state))', '(- (positive state) (negative state))',
     [(MARGIN, 0, None, 'verdict'), (MARGIN, 5, None, 'count')]),
    ('block-style: has-max flag dropped', 'cssom.block-style-q6',
     '(if (= kmx 1) 32 0)', '(if (= kmx 1) 0 0)',
     [(STYLE, 4, 9, 'verdict'), (STYLE, 3, 9, 'count')]),
    ('parse: round half up replaced by floor', 'cssom.parse-px-q6',
     '(len/rdiv (* n 64) 1000000)', '(len/fdiv (* n 64) 1000000)',
     [(PARSE, 0, None, 'verdict'), (PARSE, 7, None, 'count')]),
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fields(value, n):
    return [(value >> (21 * i)) & 0x1FFFFF for i in range(n)]


class Native:
    def __init__(self, amu, out):
        self.amu = amu
        self.out = out
        self.env = {'PATH': '/nonexistent', 'LANG': 'C'}

    def run(self, tag, entry, mods, mode=None, slice_=None, replace=None):
        """Compile and run one test variant. `mods` maps namespace to path; `mode` / `slice_` rewrite the two def
        lines of the test (each must occur once); `replace` is {ns: (path)} for a mutated module."""
        text = entry.read_text()
        if mode is not None:
            if text.count('(def mode 0)') != 1:
                raise ValueError('mode anchor changed: ' + entry.name)
            text = text.replace('(def mode 0)', '(def mode %d)' % mode)
        if slice_ is not None:
            if text.count('(def slice 0)') != 1:
                raise ValueError('slice anchor changed: ' + entry.name)
            text = text.replace('(def slice 0)', '(def slice %d)' % slice_)
        d = self.out / tag
        d.mkdir(parents=True, exist_ok=False)
        variant = d / entry.name
        variant.write_text(text)
        ns = re.search(r'\(ns\s+([^\s\)]+)', text).group(1)
        paths = dict(mods)
        paths[ns] = variant
        lock = d / 'lock.ksl'
        lock.write_text('KSL2\nentry ' + str(variant.resolve()) + '\n' +
                        ''.join('module %s %s\n' % (n, p.resolve()) for n, p in sorted(paths.items())) +
                        ''.join('file %s %s\n' % (sha(p), p.resolve()) for p in sorted(set(p.resolve() for p in paths.values()))))
        binary = d / 'bin'
        build = subprocess.run([str(self.amu), 'compile', str(variant), '--source-lock', str(lock), '-o', str(binary)],
                               cwd=OWNER, env=self.env, capture_output=True, timeout=300)
        if build.returncode or build.stderr or not binary.is_file():
            raise RuntimeError(('native compile failed', tag, build.returncode, build.stderr[-500:]))
        r = subprocess.run([str(binary)], cwd=OWNER, env=self.env, capture_output=True, timeout=600)
        if r.returncode or r.stderr:
            raise RuntimeError(('native run failed', tag, r.returncode, r.stdout, r.stderr[-300:]))
        return int(r.stdout.decode().strip())


def pmap(fn, items, jobs):
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        return list(ex.map(fn, items))


def static_audit():
    """Source-level audit of the arithmetic core and the scanner."""
    audit = {}
    for stem in CORE + ['parse_px_q6']:
        text = (SRC / (stem + '.kotoba')).read_text()
        code = '\n'.join(l.split(';;')[0] for l in text.split('\n'))
        defns = re.findall(r'\(defn\s+(\S+)\s+\[([^\]]*)\]', code)
        params = {}
        for name, plist in defns:
            toks = plist.split()
            params[name] = len(toks) // 2   # name :type pairs
        worst = max(params.values())
        too_many = [n for n, c in params.items() if c > 5]
        if too_many:
            raise ValueError(('more than five parameters', stem, too_many))
        tokens = TOK.findall(code)
        forbidden = {'/', 'rem', 'mod'}
        bad = sorted({t for t in tokens if t in forbidden or t.startswith('f64') or t == 'record' or t.startswith('record-')
                      or (stem != 'parse_px_q6' and (t == ':string' or t.startswith('string-')))})
        if bad:
            raise ValueError(('forbidden form in the core', stem, bad))
        mult = re.findall(r'\(\*\s+(\S+)\s+(\S+)\)', code)
        two_var = [m for m in mult if not (re.fullmatch(r'-?\d+', m[0]) or re.fullmatch(r'-?\d+', m[1]))]
        audit[stem] = {'defns': len(defns), 'maxParams': worst, 'multiplications': len(mult),
                       'multiplicationsOfTwoVariables': len(two_var), 'sourceLines': len([l for l in code.split('\n') if l.strip()])}
    return audit


# ---- bundling of the arithmetic core into one source (the aiueos compiler takes one file) ----
TOK = re.compile(r'[^\s()\[\]]+')


def strip_comments(t):
    return '\n'.join(l.split(';;')[0].rstrip() for l in t.split('\n'))


def requires(text):
    return {a: m for m, a in re.findall(r'\[cssom\.([\w-]+)\s+:as\s+([\w-]+)\]', text)}


def bundle(entry_text, entry_name='q6-bundle'):
    """Return one source with every required module inlined, names prefixed by the module stem."""
    order, seen = [], set()

    def visit(stem):
        if stem in seen:
            return
        seen.add(stem)
        text = (SRC / (stem + '.kotoba')).read_text()
        for dep in requires(text).values():
            visit(dep.replace('-', '_'))
        order.append(stem)
    for dep in requires(entry_text).values():
        visit(dep.replace('-', '_'))

    def rewrite(body, names, aliases):
        def sub(m):
            tok = m.group(0)
            if tok in names:
                return names[tok]
            if '/' in tok and not tok.startswith('/'):
                a, n = tok.split('/', 1)
                if a in aliases:
                    return aliases[a][n]
            return tok
        return TOK.sub(sub, body)
    defs = {}
    out = ['(ns %s (:export [main]))' % entry_name]
    for stem in order:
        text = (SRC / (stem + '.kotoba')).read_text()
        body = strip_comments(text)
        body = body[body.index('(defn'):]
        own = {n: stem + '_' + n for n in re.findall(r'\(defn\s+(\S+)', body)}
        defs[stem] = own
        aliases = {a: defs[m.replace('-', '_')] for a, m in requires(text).items()}
        out.append(rewrite(body, own, aliases))
    ebody = strip_comments(entry_text)
    ebody = ebody[ebody.index('(defn'):]
    ealiases = {a: defs[m.replace('-', '_')] for a, m in requires(entry_text).items()}
    out.append(rewrite(ebody, {}, ealiases))
    return '\n'.join(out) + '\n'


def module_main(stem):
    """A two-argument main reaching every exported function of one core module with runtime inputs."""
    text = (SRC / (stem + '.kotoba')).read_text()
    exports = re.search(r'\(:export\s+\[([^\]]*)\]', text).group(1).split()
    code = strip_comments(text)
    calls = []
    for name in exports:
        m = re.search(r'\(defn\s+' + re.escape(name) + r'\s+\[([^\]]*)\]', code)
        n = len(m.group(1).split()) // 2
        args = ' '.join(['a', 'b', 'a', 'b', 'a'][:n])
        calls.append('(%s%s)' % ('x/' + name, (' ' + args) if args else ''))
    # exports of boolean type are wrapped so every term is an i64
    terms = []
    for c, name in zip(calls, exports):
        rt = re.search(r'\(defn\s+' + re.escape(name) + r'\s+\[[^\]]*\]\s+(:\w+)', code).group(1)
        terms.append('(if %s 1 0)' % c if rt == ':bool' else c)
    body = terms[0]
    for t in terms[1:]:
        body = '(+ %s %s)' % (body, t)
    alias = stem.replace('_', '-')
    return '(ns m (:require [cssom.%s :as x]) (:export [main]))\n(defn main [a :i64 b :i64] :i64 %s)\n' % (alias, body)


class AiueosCompiler:
    def __init__(self, compiler, work):
        self.compiler = compiler
        self.work = work

    def compile(self, name, source, target):
        d = self.work / (name + '-' + target)
        d.mkdir(parents=True, exist_ok=False)
        (d / 'src.kotoba').write_text(source)
        fd = os.open(str(d), os.O_RDONLY | os.O_DIRECTORY)
        try:
            if fd != 3:
                os.dup2(fd, 3)
            env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'TMPDIR': str(d), 'TMP': str(d), 'TEMP': str(d)}
            r = subprocess.run([str(self.compiler), 'compile', 'src.kotoba', '--target', target, '--output', 'object'],
                               cwd=str(d), env=env, pass_fds=(3,), capture_output=True, timeout=300)
        finally:
            if fd != 3:
                os.close(fd)
        text = (r.stdout + r.stderr).decode(errors='replace').strip()
        res = {'ok': r.returncode == 0, 'output': text, 'sourceSha256': hashlib.sha256(source.encode()).hexdigest()}
        m = re.search(r':text-bytes (\d+)', text)
        if m:
            res['textBytes'] = int(m.group(1))
        m = re.search(r'(E\d{4}) .*detail (\d+)', text)
        if m:
            res['error'] = m.group(1)
            res['detail'] = int(m.group(2))
        return res

    def refusal(self, name, source, target):
        res = self.compile(name, source, target)
        res['text'] = res['output']
        return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--amu', type=Path, required=True, help='amu-cli.macho (native macOS arm64)')
    ap.add_argument('--amu-sha256', default=AMU_SHA256)
    ap.add_argument('--amu-full-root', type=Path, required=True, help='amu-full-root.macho (the --target compiler)')
    ap.add_argument('--amu-full-root-sha256', default=AMU_FULL_ROOT_SHA256)
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
    tracked = [amu, full, Path(__file__).resolve(), ENTRY2, ENTRY0] + sorted(set(MODULES.values())) + sorted(NEEDS)
    pins = {str(p): sha(p) for p in tracked}
    nat = Native(amu, out)
    jobs = args.jobs
    mods = lambda test: {n: MODULES[n] for n in NEEDS[test]}
    measured = {}
    failures = []
    counter = [0]
    lock = threading.Lock()

    def tag(prefix):
        with lock:
            counter[0] += 1
            return '%s-%03d' % (prefix, counter[0])

    def go(test, mode, slice_=None, replace=None):
        m = mods(test)
        if replace:
            m = dict(m)
            m.update(replace)
        return nat.run(tag(test.stem), test, m, mode, slice_)

    def expect(cond, what):
        if not cond:
            failures.append(what)

    # 1 + 2. differential verdicts and pinned counts ------------------------------------------------------------
    # length
    modes = list(range(0, 22))
    vals = pmap(lambda m: go(LENGTH, m), modes, jobs)
    length = dict(zip(modes, vals))
    expect(length[0] == 42, 'length verdict: %r' % length[0])
    measured['length'] = {str(k): v for k, v in length.items() if k}
    # block width
    wtasks = [(g, s, w) for g in (1, 2, 3) for s in range(WIDTH_SLICES[g]) for w in (4, 1, 2)]
    wvals = pmap(lambda t: go(WIDTH, 10 * t[0] + t[2], t[1]), wtasks, jobs)
    wspec = go(WIDTH, 0)
    expect(wspec == 42, 'block-width spec points: %r' % wspec)
    width = {}
    for (g, s, w), v in zip(wtasks, wvals):
        if w == 4:
            expect(v == 42, 'block-width grid %d slice %d verdict %r' % (g, s, v))
        elif w == 1:
            c = fields(v, 3)
            acc = width.setdefault(g, {'cases': 0, 'compared': 0, 'refused': 0, 'bothInvalid': 0, 'halfCases': 0})
            acc['cases'] += c[0]; acc['compared'] += c[1]; acc['refused'] += c[2]
        else:
            c = fields(v, 2)
            acc = width.setdefault(g, {'cases': 0, 'compared': 0, 'refused': 0, 'bothInvalid': 0, 'halfCases': 0})
            acc['bothInvalid'] += c[0]; acc['halfCases'] += c[1]
    measured['blockWidth'] = {str(g): v for g, v in width.items()}
    # margin collapse
    modes = list(range(0, 6))
    mvals = dict(zip(modes, pmap(lambda m: go(MARGIN, m), modes, jobs)))
    expect(mvals[0] == 42, 'margin-collapse verdict: %r' % mvals[0])
    measured['marginCollapse'] = {str(k): v for k, v in mvals.items() if k}
    # block style
    stasks = [(s, w) for s in range(STYLE_SLICES) for w in (4, 1, 2)]
    svals = pmap(lambda t: go(STYLE, t[1], t[0]), stasks, jobs)
    sspec = go(STYLE, 0)
    expect(sspec == 42, 'block-style spec points: %r' % sspec)
    style = {'cases': 0, 'compared': 0, 'refused': 0, 'bothInvalid': 0, 'maxDeviation128': 0}
    for (s, w), v in zip(stasks, svals):
        if w == 4:
            expect(v == 42, 'block-style slice %d verdict %r' % (s, v))
        elif w == 1:
            c = fields(v, 3)
            style['cases'] += c[0]; style['compared'] += c[1]; style['refused'] += c[2]
        else:
            c = fields(v, 2)
            style['bothInvalid'] += c[0]; style['maxDeviation128'] = max(style['maxDeviation128'], c[1])
    measured['blockStyle'] = style
    # parse
    modes = list(range(0, 10))
    pvals = dict(zip(modes, pmap(lambda m: go(PARSE, m), modes, jobs)))
    expect(pvals[0] == 42, 'parse verdict: %r' % pvals[0])
    measured['parse'] = {str(k): v for k, v in pvals.items() if k}

    # 3. negative controls ------------------------------------------------------------------------------------------
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
            good = (v == 7) if kind == 'verdict' else (v > 0)
            expect(good, 'mutant not detected: %s (%s mode %d slice %s printed %r)' % (name, test.name, mode, slice_, v))
            row['results'].append({'test': test.name, 'mode': mode, 'slice': slice_, 'kind': kind, 'printed': v})
        mutation_report.append(row)

    # 4. static audit and size ---------------------------------------------------------------------------------------
    audit = static_audit()
    comp = AiueosCompiler(full, out)
    size = {}
    whole2 = bundle(ENTRY2.read_text())
    whole0 = bundle(ENTRY0.read_text())
    for label, src in (('core-main2', whole2), ('core-main0', whole0)):
        for t in ('x86_64-aiueos-kernel-v1', 'x86_64-aiueos-user-v1'):
            size[label + '/' + t] = comp.compile(label, src, t)
    for stem in CORE:
        src = bundle(module_main(stem))
        size['module-' + stem + '/x86_64-aiueos-kernel-v1'] = comp.compile('module-' + stem, src, 'x86_64-aiueos-kernel-v1')
    six = '(ns six (:export [main]))\n(defn f [a :i64 b :i64 c :i64 d :i64 e :i64 g :i64] :i64 (+ a (+ b (+ c (+ d (+ e g))))))\n(defn main [] :i64 (f 1 2 3 4 5 6))\n'
    size['six-parameter-control/x86_64-aiueos-kernel-v1'] = comp.compile('six', six, 'x86_64-aiueos-kernel-v1')
    # the f64 oracle modules are not an AIUEOS candidate at all: the typed record values are refused at type check
    for stem in ('length', 'margin_collapse', 'block_width'):
        f64src = (SRC / (stem + '.kotoba')).read_text()
        if f64src.count('(:export [') != 1:
            raise ValueError('f64 export anchor changed: ' + stem)
        f64src = f64src.replace('(:export [', '(:export [main ', 1) + '\n(defn main [] :i64 0)\n'
        for t in ('x86_64-aiueos-kernel-v1', 'x86_64-aiueos-user-v1'):
            size['f64-' + stem + '/' + t] = comp.refusal('f64-' + stem, f64src, t)
            expect(not size['f64-' + stem + '/' + t]['ok'], 'f64 module unexpectedly compiled: ' + stem)
    expect(size['core-main2/x86_64-aiueos-kernel-v1']['ok'], 'kernel-v1 compile of the core failed')
    expect(size['core-main0/x86_64-aiueos-kernel-v1']['ok'], 'kernel-v1 compile of the zero-argument core failed')
    expect(size['core-main0/x86_64-aiueos-user-v1'].get('error') == 'E7104', 'user-v1 verdict is not the E7104 text limit')
    expect(size['six-parameter-control/x86_64-aiueos-kernel-v1'].get('error') == 'E7102', 'six-parameter control not refused')

    # pins ------------------------------------------------------------------------------------------------------------
    if any(sha(p) != pins[str(p)] for p in tracked):
        raise ValueError('source or compiler changed during gate')
    receipt = {'status': 'PASS_NATIVE_CSSOM_BLOCK_Q6', 'inputs': pins, 'measured': measured,
               'staticAudit': audit, 'size': size, 'negativeControls': mutation_report,
               'ranOnLiveCpl3': False, 'wiredIntoLayoutCljk': False}
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    if args.print_measurements:
        (out / 'measurements.json').write_text(json.dumps({'measured': measured, 'staticAudit': audit, 'size': {k: {x: y for x, y in v.items() if x in ('ok', 'textBytes', 'error', 'detail', 'text')} for k, v in size.items()}}, indent=2, sort_keys=True))
        print(json.dumps({'measured': measured, 'staticAudit': audit,
                          'size': {k: {x: y for x, y in v.items() if x in ('ok', 'textBytes', 'error', 'detail', 'text')} for k, v in size.items()},
                          'failures': failures}, indent=2))
        return
    pinned = PINNED
    for key, want in pinned.items():
        got = {'measured': measured, 'staticAudit': audit,
               'size': {k: {x: y for x, y in v.items() if x in ('ok', 'textBytes', 'error', 'detail', 'text')} for k, v in size.items()}}[key]
        if got != want:
            failures.append('pinned %s differs: %s != %s' % (key, json.dumps(got, sort_keys=True), json.dumps(want, sort_keys=True)))
    if failures:
        for f in failures:
            print('FAIL ' + f, file=sys.stderr)
        raise SystemExit(1)
    print(receipt['status'])


# Pinned measurements (macOS arm64, pinned compiler, 2026-11-06). Any change in a count, a text size or a refusal fails the gate.
PINNED = json.loads('''
{
    "measured": {
        "blockStyle": {
            "bothInvalid": 768000,
            "cases": 1008000,
            "compared": 192000,
            "maxDeviation128": 2,
            "refused": 48000
        },
        "blockWidth": {
            "1": {
                "bothInvalid": 933120,
                "cases": 2799360,
                "compared": 870976,
                "halfCases": 18816,
                "refused": 995264
            },
            "2": {
                "bothInvalid": 2088960,
                "cases": 5160960,
                "compared": 1638400,
                "halfCases": 49760,
                "refused": 1433600
            },
            "3": {
                "bothInvalid": 0,
                "cases": 1000000,
                "compared": 1000000,
                "halfCases": 17294,
                "refused": 0
            }
        },
        "length": {
            "1": 5376,
            "10": 846,
            "11": 0,
            "12": 1233197,
            "13": 1114,
            "14": 31968,
            "15": 1114,
            "16": 0,
            "17": 122914097,
            "18": 7391,
            "19": 99348,
            "2": 0,
            "20": 7391,
            "21": 0,
            "3": 0,
            "4": 343,
            "5": 30,
            "6": 0,
            "7": 0,
            "8": 61442048,
            "9": 47400
        },
        "marginCollapse": {
            "1": 41371,
            "2": 11111,
            "3": 11510,
            "4": 18750,
            "5": 0
        },
        "parse": {
            "1": 81,
            "2": 1680,
            "3": 1383,
            "4": 12,
            "5": 0,
            "6": 0,
            "7": 0,
            "8": 0,
            "9": 12
        }
    },
    "size": {
        "core-main0/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 23350
        },
        "core-main0/x86_64-aiueos-user-v1": {
            "detail": 22998,
            "error": "E7104",
            "ok": false
        },
        "core-main2/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 22837
        },
        "core-main2/x86_64-aiueos-user-v1": {
            "detail": 56,
            "error": "E7102",
            "ok": false
        },
        "f64-block_width/x86_64-aiueos-kernel-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'solve-constrained': expected :i64 (byte 4657)"
        },
        "f64-block_width/x86_64-aiueos-user-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'solve-constrained': expected :i64 (byte 4657)"
        },
        "f64-length/x86_64-aiueos-kernel-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'resolve': expected :i64 (byte 677)"
        },
        "f64-length/x86_64-aiueos-user-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'resolve': expected :i64 (byte 677)"
        },
        "f64-margin_collapse/x86_64-aiueos-kernel-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'add': expected :i64 (byte 654)"
        },
        "f64-margin_collapse/x86_64-aiueos-user-v1": {
            "ok": false,
            "text": "seed: E2104 type mismatch in 'add': expected :i64 (byte 654)"
        },
        "module-block_style_q6/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 20009
        },
        "module-block_width_q6/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 9753
        },
        "module-length_q6/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 5642
        },
        "module-margin_collapse_q6/x86_64-aiueos-kernel-v1": {
            "ok": true,
            "textBytes": 2344
        },
        "six-parameter-control/x86_64-aiueos-kernel-v1": {
            "detail": 1,
            "error": "E7102",
            "ok": false
        }
    },
    "staticAudit": {
        "block_style_q6": {
            "defns": 12,
            "maxParams": 5,
            "multiplications": 0,
            "multiplicationsOfTwoVariables": 0,
            "sourceLines": 34
        },
        "block_width_q6": {
            "defns": 15,
            "maxParams": 5,
            "multiplications": 4,
            "multiplicationsOfTwoVariables": 0,
            "sourceLines": 55
        },
        "length_q6": {
            "defns": 21,
            "maxParams": 4,
            "multiplications": 5,
            "multiplicationsOfTwoVariables": 3,
            "sourceLines": 39
        },
        "margin_collapse_q6": {
            "defns": 7,
            "maxParams": 2,
            "multiplications": 0,
            "multiplicationsOfTwoVariables": 0,
            "sourceLines": 15
        },
        "parse_px_q6": {
            "defns": 12,
            "maxParams": 4,
            "multiplications": 7,
            "multiplicationsOfTwoVariables": 1,
            "sourceLines": 50
        }
    }
}
''')

if __name__ == '__main__':
    main()
