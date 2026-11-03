#!/usr/bin/env python3
"""Run every committed NIST ACVP ML-KEM-768 test through the native ML-KEM module, with
mutants (AWAI-117).

The native ML-KEM gate in check-pq-native.py embeds eight ACVP tests. This runs all 80
that lib/gov.nist.mlKem/test/mlkem/acvp/ holds (imported by tools/import_acvp.py from the
ACVP-Server vector sets named in test/acvp/PROVENANCE.md). Each file's sha256 is
checked before use. The files are read as data only, with a regular expression; no
.cljk is compiled or run.

* keyGen AFT (25): keygen(d, z) equals ek || dk.
* encapsulation AFT (25): encaps(ek, m) equals k || c.
* decapsulation VAL (10): decaps(dk, c) equals k; for the four `modified ciphertext`
  cases k is the implicit-rejection key.
* decapsulationKeyCheck VAL (10) and encapsulationKeyCheck VAL (10): valid-dk? and
  valid-ek? give the ACVP verdict; the failing cases (`modified H`, a coefficient
  >= q) must be refused.

One image holds only a few ML-KEM operations before its heap runs out, so each suite is
cut into chunks; each chunk is its own entry module whose main returns the number of
passing cases, and a pass is every case of the chunk. Each mutant (the one-line
library changes check-pq-native.py uses for its ML-KEM gate) must fail at least one
chunk; chunks run in order, stop at the first failure, and the evidence records which
chunk caught it. Bytes are vector literals. Runs on Linux arm64 (the payload packed
into the runner from --runner-source) and Apple Silicon (Mac root and packager).
"""
import argparse
import concurrent.futures
import hashlib
import importlib.util
import os
import platform
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('pq_native', ROOT / 'scripts/check-pq-native.py')
pq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pq)
_spec = importlib.util.spec_from_file_location('wp_native', ROOT / 'scripts/check-wycheproof-native.py')
wp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wp)

ACVP_DIR = 'lib/gov.nist.mlKem/test/mlkem/acvp'
ACVP = dict(repository='https://github.com/usnistgov/ACVP-Server', provenance='lib/gov.nist.mlKem/test/acvp/PROVENANCE.md',
            files={
    f'{ACVP_DIR}/keygen.cljk': 'a5a08515ba44503ef5e800f17cfa643c9df9ae0f3f7544089d7f7e9b62c9628b',
    f'{ACVP_DIR}/encaps.cljk': 'a60d7f643992de035e0adfdffbda4d312a94d7593a95dec2c20b0a768d109130',
    f'{ACVP_DIR}/decaps.cljk': 'f262bd4835a6fd32590bcae4d0e517dbf3371ede05e47e05781884c8158f8eb7',
    f'{ACVP_DIR}/dk_check.cljk': 'da2f2cb10a03a22659f25e606bea78c9f2aaa264aec5a50b653561fa901f8a81',
    f'{ACVP_DIR}/ek_check.cljk': '98e135256bae916b5384f268f8643c84e2647826f5894d9428662f5d89e4c1ec',
})

MLKEM = 'lib/gov.nist.mlKem/kotoba/mlkem/core.kotoba'
FILES = {'sha3/core.kotoba': pq.SHA3, 'mlkem/core.kotoba': MLKEM}
# check-pq-native.py names the library by its repository path; a module build names it by module path.
MUTANTS = {label: ('mlkem/core.kotoba', old, new) for label, (path, old, new) in pq.GATES['mlkem']['mutants'].items()
           if path == MLKEM}
assert len(MUTANTS) == len(pq.GATES['mlkem']['mutants'])

# Each suite: its vector file, the fields of one vector after the tc id, and the chunk size.
SUITES = {
    'keygen': dict(file='keygen.cljk', fields=['d', 'z', 'ek', 'dk'], chunk=5),
    'encaps': dict(file='encaps.cljk', fields=['ek', 'm', 'c', 'k'], chunk=5),
    'decaps': dict(file='decaps.cljk', fields=['dk', 'c', 'k', 'reason'], chunk=5),
    'dk-check': dict(file='dk_check.cljk', fields=['dk', 'passed', 'reason'], chunk=10),
    'ek-check': dict(file='ek_check.cljk', fields=['ek', 'passed', 'reason'], chunk=10),
}

VECTOR = re.compile(r'^\s*\[([0-9]+)((?: (?:"[^"]*"|true|false))+)\]\s*$', re.M)
FIELD = re.compile(r'"([^"]*)"|(true|false)')


def load(name, spec):
    path = f'{ACVP_DIR}/{spec["file"]}'
    data = (ROOT / path).read_bytes()
    assert hashlib.sha256(data).hexdigest() == ACVP['files'][path], ('vector file changed', path)
    out = []
    for match in VECTOR.finditer(data.decode()):
        values = [s if b == '' else b == 'true' for s, b in FIELD.findall(match[2])]
        assert len(values) == len(spec['fields']), (name, match[1])
        out.append(dict(tcId=int(match[1]), **dict(zip(spec['fields'], values))))
    assert out and len({t['tcId'] for t in out}) == len(out), (name, 'no vectors or a repeated tc id')
    return out


def case_expr(name, t):
    b = wp.bytes_literal
    if name == 'keygen':
        assert len(t['ek']) == 2 * 1184 and len(t['dk']) == 2 * 2400
        return f'(if (same? (m/keygen {b(t["d"])} {b(t["z"])}) {b(t["ek"] + t["dk"])}) 1 0)'
    if name == 'encaps':
        return f'(if (same? (m/encaps {b(t["ek"])} {b(t["m"])}) {b(t["k"] + t["c"])}) 1 0)'
    if name == 'decaps':
        return f'(if (same? (m/decaps {b(t["dk"])} {b(t["c"])}) {b(t["k"])}) 1 0)'
    check = 'm/valid-dk?' if name == 'dk-check' else 'm/valid-ek?'
    key = t['dk'] if name == 'dk-check' else t['ek']
    return f'(if ({check} {b(key)}) {1 if t["passed"] else 0} {0 if t["passed"] else 1})'


def chunks(name, spec):
    cases = load(name, spec)
    out = []
    for i in range(0, len(cases), spec['chunk']):
        part = cases[i:i + spec['chunk']]
        tag = f'{name.replace("-", "_")}_{i // spec["chunk"]:02d}'
        body = '\n     '.join(case_expr(name, t) for t in part)
        source = (f';; ACVP ML-KEM-768 {name} tc {part[0]["tcId"]}..{part[-1]["tcId"]}, generated by '
                  f'scripts/check-acvp-mlkem-native.py\n'
                  f'(ns acvp.{tag.replace("_", "-")} (:require [mlkem.core :as m]) (:export [main]))\n'
                  f'{wp.HELPERS}(defn main [] :i64\n  (+ 0\n     {body}))\n')
        out.append(dict(entry=f'acvp/{tag}.kotoba', source=source.encode(), cases=len(part),
                        tcIds=[t['tcId'] for t in part],
                        rejecting=sum(1 for t in part if t.get('passed') is False or t.get('reason') == 'modified ciphertext')))
    return out


def run_chunk(gate, label, chunk, change=None):
    files = pq.module_files(dict(files=FILES), change)
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
    assert sum(c['cases'] for cs in work.values() for c in cs) == 80, 'expected the 80 committed ACVP ML-KEM-768 tests'

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        jobs = [pool.submit(run_chunk, gate, f'{name}-{i:02d}', c) for name, cs in work.items() for i, c in enumerate(cs)]
        for job in jobs:
            job.result()

        def mutant(label, change):
            for name, cs in work.items():
                for i, c in enumerate(cs):
                    try:
                        run_chunk(gate, f'{label}-{name}-{i:02d}', c, change)
                    except AssertionError:
                        return f'{name}-{i:02d}'
            return None
        detected = {label: pool.submit(mutant, label, change) for label, change in MUTANTS.items()}
        detected = {label: job.result() for label, job in detected.items()}
    for label, at in detected.items():
        assert at is not None, (label, 'mutant passed every chunk')
    gate.finish('PASS_ACVP_MLKEM_NATIVE', acvp=ACVP, suites={
        name: dict(cases=sum(c['cases'] for c in cs), rejecting=sum(c['rejecting'] for c in cs),
                   chunks=[dict(tcIds=c['tcIds'], cases=c['cases']) for c in cs])
        for name, cs in work.items()}, mutants={label: dict(detectedInChunk=at) for label, at in detected.items()})


if __name__ == '__main__':
    main()
