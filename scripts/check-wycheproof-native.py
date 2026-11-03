#!/usr/bin/env python3
"""Run the Wycheproof X25519, ChaCha20-Poly1305 and XChaCha20-Poly1305 vectors through
the native modules, with mutants (AWAI-117).

The vectors are vendored from C2SP/wycheproof at the commit in WYCHEPROOF, and each
file's sha256 is checked before use. Every test case runs natively:

* X25519 (xdh_comp, 518 cases, valid and acceptable): x25519-bytes(private, public)
  equals shared. That includes the low-order, twist and non-canonical public keys.
* (X)ChaCha20-Poly1305 (aead_test, 325 and 315 cases): for a valid case, seal gives
  ct || tag and open gives msg back; for an invalid case (modified tag, wrong nonce
  size), open refuses with [-1].

One image holds only a few X25519 multiplications or AEAD operations before its heap
runs out, so each suite is cut into chunks; each chunk is its own entry module whose
main returns the number of passing cases, and a pass is every case of the chunk. A
mutant (the same one-line library changes check-pq-native.py uses) must fail at least
one chunk; chunks run in order and stop at the first failure, and the evidence records
which chunk caught it. Poly1305's final-reduction mutant is left out: no Wycheproof case
reaches that branch (RFC 8439 A.3 in check-pq-native.py does).

Runs where check-pq-native.py runs its arm64 and Mac gates: Linux arm64 (the payload
packed into the runner from --runner-source) and Apple Silicon (Mac root and packager).
The vectors are hex in JSON; the generated sources carry them as vector literals.
"""
import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import os
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('pq_native', ROOT / 'scripts/check-pq-native.py')
pq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pq)

WYCHEPROOF = dict(repository='https://github.com/C2SP/wycheproof',
                  commit='d17cc89fa5c8f4f4d378b5385ebf75da5d0926c9', files={
    'lib/org.ietf.x25519/test/wycheproof/x25519_test.json':
        '35c3f5231cf25cc640b524d403461deee9e49441d5d915a3a25b2c8ff5adbe7d',
    'lib/org.ietf.chacha20Poly1305/test/wycheproof/chacha20_poly1305_test.json':
        'fe61d25f90e1bde4461d00eafe61049e5f29bd999f36b766df9cda90906ad53d',
    'lib/org.ietf.chacha20Poly1305/test/wycheproof/xchacha20_poly1305_test.json':
        'a79de072571b90eb40c3a63ce0c7f75dcb4b62323c8870228e1f61dcc61d63a9',
})

# No Wycheproof (X)ChaCha20 case takes Poly1305's final h >= p branch, so the 'final' mutant
# passes every chunk here; RFC 8439 A.3 #5-#9 in check-pq-native.py's gate catch it. 'hround'
# (HChaCha20) reaches only XChaCha20.
AEAD_MUTANTS = {k: v for k, v in pq.MODULE_GATES['chacha20']['mutants'].items() if k != 'final'}
CHACHA_MUTANTS = {k: v for k, v in AEAD_MUTANTS.items() if k != 'hround'}
SUITES = {
    'x25519': dict(vectors='lib/org.ietf.x25519/test/wycheproof/x25519_test.json', files=pq.X25519,
                   require='[x25519.core :as x]', chunk=12, mutants=pq.MODULE_GATES['x25519']['mutants']),
    'chacha20': dict(vectors='lib/org.ietf.chacha20Poly1305/test/wycheproof/chacha20_poly1305_test.json',
                     files=pq.CHACHA, require='[chacha20.aead :as a]', chunk=24, seal='a/seal', open='a/open',
                     mutants=CHACHA_MUTANTS),
    'xchacha20': dict(vectors='lib/org.ietf.chacha20Poly1305/test/wycheproof/xchacha20_poly1305_test.json',
                      files=pq.CHACHA, require='[chacha20.aead :as a]', chunk=24, seal='a/xseal', open='a/xopen',
                      mutants=AEAD_MUTANTS),
}

HELPERS = '''(defn- cat [x :vector-i64 y :vector-i64] :vector-i64
  (let [n (vector-count x) out (vector-alloc (+ n (vector-count y)))]
    (loop [i 0] (if (= i (vector-count out)) out
      (let [z (vector-assoc! out i (if (< i n) (vector-at x i) (vector-at y (- i n))))] (recur (+ i 1)))))))
(defn- same? [x :vector-i64 y :vector-i64] :bool
  (and (= (vector-count x) (vector-count y))
       (loop [i 0] (if (= i (vector-count x)) true (if (= (vector-at x i) (vector-at y i)) (recur (+ i 1)) false)))))
(defn- refused? [v :vector-i64] :bool (and (= (vector-count v) 1) (= (vector-at v 0) -1)))
'''


def bytes_literal(hexstr):
    """A byte string as a vector literal, cut into 64-element literals joined by cat."""
    data = bytes.fromhex(hexstr)
    if not data:
        return '(vector-i64)'
    parts = ['(vector-i64 ' + ' '.join(map(str, data[i:i + 64])) + ')' for i in range(0, len(data), 64)]
    expr = parts[0]
    for part in parts[1:]:
        expr = f'(cat {expr} {part})'
    return expr


def load_cases(path):
    data = (ROOT / path).read_bytes()
    assert hashlib.sha256(data).hexdigest() == WYCHEPROOF['files'][path], ('vector file changed', path)
    return [t for g in json.loads(data)['testGroups'] for t in g['tests']]


def case_expr(name, spec, t):
    if name == 'x25519':
        assert t['result'] in ('valid', 'acceptable'), t['tcId']
        return (f'(if (same? (x/x25519-bytes {bytes_literal(t["private"])} {bytes_literal(t["public"])}) '
                f'{bytes_literal(t["shared"])}) 1 0)')
    key, iv, aad = bytes_literal(t['key']), bytes_literal(t['iv']), bytes_literal(t['aad'])
    sealed = bytes_literal(t['ct'] + t['tag'])
    if t['result'] == 'valid':
        msg = bytes_literal(t['msg'])
        return (f'(if (and (same? ({spec["seal"]} {key} {iv} {aad} {msg}) {sealed}) '
                f'(same? ({spec["open"]} {key} {iv} {aad} {sealed}) {msg})) 1 0)')
    assert t['result'] == 'invalid', t['tcId']
    return f'(if (refused? ({spec["open"]} {key} {iv} {aad} {sealed})) 1 0)'


def chunks(name, spec):
    cases = load_cases(spec['vectors'])
    out = []
    for i in range(0, len(cases), spec['chunk']):
        part = cases[i:i + spec['chunk']]
        entry = f'wp/{name}_{i // spec["chunk"]:02d}.kotoba'
        body = '\n     '.join(case_expr(name, spec, t) for t in part)
        source = (f';; Wycheproof {name} tcId {part[0]["tcId"]}..{part[-1]["tcId"]}, generated by '
                  f'scripts/check-wycheproof-native.py\n'
                  f'(ns wp.{name}-{i // spec["chunk"]:02d} (:require {spec["require"]}) (:export [main]))\n'
                  f'{HELPERS}(defn main [] :i64\n  (+ 0\n     {body}))\n')
        out.append(dict(entry=entry, source=source.encode(), cases=len(part),
                        tcIds=[part[0]['tcId'], part[-1]['tcId']]))
    return out


def run_chunk(gate, label, spec, chunk, change=None):
    files = pq.module_files(dict(files=spec['files']), change)
    files[chunk['entry']] = chunk['source']
    gate.run(label + '-run', gate.build(label, chunk['entry'], files), chunk['cases'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--compiler-sha256', required=True)
    parser.add_argument('--runner-source', type=Path, help='Linux arm64: the runner source to pack into')
    parser.add_argument('--packager', type=Path, help='macOS: the Mac packager')
    parser.add_argument('--packager-sha256')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=os.cpu_count() or 2)
    args = parser.parse_args()
    arm = platform.system() == 'Linux' and platform.machine() in ('aarch64', 'arm64')
    gate = pq.LinuxArm(args) if arm else pq.NativeGate(args)
    work = {name: chunks(name, spec) for name, spec in SUITES.items()}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        jobs = {(name, i): pool.submit(run_chunk, gate, f'{name}-{i:02d}', SUITES[name], c)
                for name, cs in work.items() for i, c in enumerate(cs)}
        for job in jobs.values():
            job.result()

        def mutant(name, label, change):
            for i, c in enumerate(work[name]):
                try:
                    run_chunk(gate, f'{name}-{label}-{i:02d}', SUITES[name], c, change)
                except AssertionError:
                    return i
            return None
        mutants = {(name, label): pool.submit(mutant, name, label, change)
                   for name, spec in SUITES.items() for label, change in spec['mutants'].items()}
        detected = {key: job.result() for key, job in mutants.items()}
    for (name, label), at in detected.items():
        assert at is not None, (name, label, 'mutant passed every chunk')
    gate.finish('PASS_WYCHEPROOF_NATIVE', wycheproof=dict(WYCHEPROOF), suites={
        name: dict(cases=sum(c['cases'] for c in cs), chunks=[dict(tcIds=c['tcIds'], cases=c['cases']) for c in cs],
                   mutants={label: dict(detectedInChunk=detected[(name, label)]) for label in SUITES[name]['mutants']})
        for name, cs in work.items()})


if __name__ == '__main__':
    main()
