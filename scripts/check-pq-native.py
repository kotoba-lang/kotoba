#!/usr/bin/env python3
"""Run the native post-quantum known-answer gates (JUN-352 P1b) and their mutants.

Each gate is one unity source: the library bodies with their `ns` forms removed, the
`sha3/` alias dropped, then the gate body. The gate's main returns a bitmask; a pass is
every bit set. Each mutant changes one line of a library body and must not pass.
Runs on Linux x86_64 (KX64 under the native runner) and on Apple Silicon (Mac root and
packager), through lib/kotoba.hata/scripts/native_gate.py.
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib/kotoba.hata/scripts'))
from native_gate import NativeGate  # noqa: E402

SHA3 = 'lib/gov.nist.sha3/kotoba/sha3/core.kotoba'
GATES = {
    'sha3': dict(bodies=[SHA3], gate='lib/gov.nist.sha3/kotoba/sha3/native_gate.kotoba', passing=63, mutants={
        'constant': (SHA3, '0x0000000000008082', '0x0000000000008083'),
        'suffix': ('lib/gov.nist.sha3/kotoba/sha3/core.kotoba', '(sponge bytes 136 6 32))', '(sponge bytes 136 1 32))'),
    }),
    'mlkem': dict(bodies=[SHA3, 'lib/gov.nist.mlKem/kotoba/mlkem/core.kotoba'],
                  gate='lib/gov.nist.mlKem/kotoba/mlkem/native_gate.kotoba', passing=63, mutants={
        'zeta': ('lib/gov.nist.mlKem/kotoba/mlkem/core.kotoba', '(vector-i64 1 1729 ', '(vector-i64 1 1730 '),
        'mask': ('lib/gov.nist.mlKem/kotoba/mlkem/core.kotoba', '(if (= differ 0) 0 255)', '(if (= differ 0) 255 0)'),
        'cbd': ('lib/gov.nist.mlKem/kotoba/mlkem/core.kotoba', '(md (- x y))', '(md (- y x))'),
    }),
    'mldsa': dict(bodies=[SHA3, 'lib/gov.nist.mlDsa/kotoba/mldsa/core.kotoba'],
                  gate='lib/gov.nist.mlDsa/kotoba/mldsa/native_gate.kotoba', passing=31, mutants={
        'ctx': ('lib/gov.nist.mlDsa/kotoba/mldsa/core.kotoba', '(vector-i64 0 (vector-count ctx))', '(vector-i64 1 (vector-count ctx))'),
        'hint': ('lib/gov.nist.mlDsa/kotoba/mldsa/core.kotoba',
                 '(and (> p idx) (>= (vector-at hb (- p 1)) (vector-at hb p))) -1', 'false -1'),
        'znorm': ('lib/gov.nist.mlDsa/kotoba/mldsa/core.kotoba',
                  '(if (or (= (vector-count h) 0) (>= (vnorm z) 524092)) false', '(if (= (vector-count h) 0) false'),
    }),
}

def strip_ns(text):
    return re.sub(r'^\(ns [^\n]*\n(?:[^\n]*\n)*?[^\n]*\)\)\n', '', text, count=1, flags=re.M)

def unity(name, spec, change=None):
    parts = [f'(ns pq.{name}-gate (:export [main]))\n']
    for path in spec['bodies'] + [spec['gate']]:
        text = (ROOT / path).read_text()
        if change and change[0] == path:
            assert text.count(change[1]) == 1, (name, change)
            text = text.replace(change[1], change[2])
        parts.append(strip_ns(text).replace('sha3/', '') if path != spec['gate'] else strip_ns(text))
    return ''.join(parts).encode()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--compiler-sha256', required=True)
    parser.add_argument('--runner', type=Path, help='Linux: the native runner')
    parser.add_argument('--packager', type=Path, help='macOS: the Mac packager')
    parser.add_argument('--packager-sha256')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    gate = NativeGate(args)
    results = {}
    for name, spec in GATES.items():
        entry = f'pq/{name}_gate.kotoba'
        image = gate.build(name, entry, {entry: unity(name, spec)})
        gate.run(name + '-pass', image, spec['passing'])
        results[name] = dict(passing=spec['passing'], mutants={})
        for label, change in spec['mutants'].items():
            mutant = gate.build(f'{name}-{label}', entry, {entry: unity(name, spec, change)})
            try:
                gate.run(f'{name}-{label}-detected', mutant, spec['passing'])
                detected = False
            except AssertionError:
                detected = True
            results[name]['mutants'][label] = detected
            assert detected, (name, label, 'mutant passed the gate')
    gate.finish('PASS_PQ_NATIVE_GATES', gates=results)

if __name__ == '__main__':
    main()
