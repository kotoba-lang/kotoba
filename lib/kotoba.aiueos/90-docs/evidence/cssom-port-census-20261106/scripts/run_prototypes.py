#!/usr/bin/env python3
"""Run the host-native (macOS arm64) differential gates: existing f64 cssom native tests, the Q6 block-width gate with a
negative control, the percent-rounding oracle comparison, and the Q6 px parser. usage: run_prototypes.py OUT.txt"""
import os, subprocess, sys, tempfile, re
HERE = os.path.dirname(os.path.abspath(__file__)); EV = os.path.dirname(HERE)
LIB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(EV))))  # evidence -> 90-docs -> kotoba.aiueos -> lib
CSSOM = os.path.join(LIB, 'kotoba.cssom'); PROTO = os.path.join(EV, 'prototype')
tmp = tempfile.mkdtemp(prefix='proto-')
log = []
def run(label, entry, mods):
    out = os.path.join(tmp, re.sub(r'\W', '_', label))
    r = subprocess.run([sys.executable, os.path.join(HERE, 'runnative.py'), out, entry] + ['%s=%s' % kv for kv in mods.items()], capture_output=True, text=True)
    last = [l for l in r.stdout.strip().split('\n') if l.startswith('run rc')]
    res = last[0] if last else r.stdout.strip()[-200:]
    log.append('%-62s %s' % (label, res)); print(log[-1])
    m = re.search(r"stdout=b'(-?\d+)", res); return int(m.group(1)) if m else None
def variant(src, name, edits):
    s = open(src).read()
    for a, b in edits: s = s.replace(a, b)
    p = os.path.join(tmp, name); open(p, 'w').write(s); return p
# 1. existing f64 native tests
run('existing f64 test/native/block_width.kotoba (expect 42)', CSSOM + '/test/native/block_width.kotoba', {'cssom.block-width': CSSOM + '/src/cssom/block_width.kotoba'})
run('existing f64 test/native/margin_collapse.kotoba (expect 42)', CSSOM + '/test/native/margin_collapse.kotoba', {'cssom.margin-collapse': CSSOM + '/src/cssom/margin_collapse.kotoba'})
run('existing f64 test/native/block_style.kotoba (expect 42)', CSSOM + '/test/native/block_style.kotoba', {'cssom.block-style': CSSOM + '/src/cssom/block_style.kotoba', 'cssom.block-width': CSSOM + '/src/cssom/block_width.kotoba', 'cssom.length': CSSOM + '/src/cssom/length.kotoba'})
# 2. Q6 vs f64 block width, 1,000,000 random Q6-grid samples
f64w = CSSOM + '/src/cssom/block_width.kotoba'; q6 = PROTO + '/block_width_q6.kotoba'
T = PROTO + '/q6_vs_f64_test.kotoba'
for m, what in ((0, 'violations of |q6-f64|<=1/128px (42 = none)'), (1, 'max |q6-f64| in 1/128px units'), (2, 'samples valid on both sides')):
    t = variant(T, 'q6_m%d.kotoba' % m, [('(def mode 0)', '(def mode %d)' % m), ('(ns q6-vs-f64-test', '(ns q6-vs-f64-test-m%d' % m)])
    run('Q6 vs f64 block-width, 1e6 samples: ' + what, t, {'cssom.block-width': f64w, 'cssom.block-width-q6': q6})
mut = variant(PROTO + '/block_width_q6_mut.kotoba', 'block_width_q6_mut.kotoba', [])
t = variant(PROTO + '/q6_vs_f64_test_mutant.kotoba', 'q6_mut_test.kotoba', [])
run('NEGATIVE CONTROL mutant (half = remaining>>2): violations', t, {'cssom.block-width': f64w, 'cssom.block-width-q6-mut': mut})
# 3. percent rounding: f64 oracle vs exact rational
P = PROTO + '/pct_oracle.kotoba'
run('percent: H 0..30000 (0.01%) x basis 0..4096: pairs differing', P, {})
step100 = variant(P, 'pct_int.kotoba', [('(ns pct-oracle ', '(ns pct-oracle-int '), ('(scan (inc h) 0 n k)', '(scan (+ h 100) 0 n k)')])
run('percent: integer percent 0..300 x basis 0..4096: pairs differing', step100, {})
for k in (0, 1, 2):
    ex = variant(step100, 'pct_ex%d.kotoba' % k, [('(def mode 0)', '(def mode 1)'), ('(def skip 0)', '(def skip %d)' % k), ('(ns pct-oracle-int ', '(ns pct-oracle-ex%d ' % k)])
    v = run('percent: integer-percent mismatch #%d as H*100000+basis' % k, ex, {})
    if v is not None: log.append('    -> %.2f%% of %d px' % ((v // 100000) / 100.0, v % 100000)); print(log[-1])
# 4. px parser, host twin
run('Q6 px parser host twin, 15 cases (expect 42)', PROTO + '/px_parse_q6_host.kotoba', {})
open(sys.argv[1], 'w').write('\n'.join(log) + '\n')
