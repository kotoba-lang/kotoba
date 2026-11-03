#!/usr/bin/env python3
"""Execute pinned CBOR inputs through AOT and a native reference on Linux x86.

Python stages fixed bytes and transports actual process outputs. The native
Kotoba gate validates receipt framing/context and compares status/value/fuel.
The reference covers an experimental subset; this is not VM qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'lib/kotoba.kototama'
SNAPSHOT = LIB / 'test/kototama/fixtures/jun-792-aot-receipts-20261103.json'
REPORT = LIB / 'docs/evidence/jun-792-20261103/amu-receipt-v2-x86-287-report.json'
LEDGER = LIB / 'local-changes.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def literal(data):
    chunks = ['[' + ' '.join(map(str, data[i:i + 48])) + ']' for i in range(0, len(data), 48)]
    value = chunks[0] if chunks else '[]'
    for chunk in chunks[1:]:
        value = '(into ' + value + ' ' + chunk + ')'
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('compiler', 'runner', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    for name in ('compiler-sha256', 'runner-sha256'):
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'AMD64'):
        raise ValueError('requires native Linux x86-64')
    compiler, runner = a.compiler.resolve(strict=True), a.runner.resolve(strict=True)
    if sha(compiler.read_bytes()) != a.compiler_sha256 or sha(runner.read_bytes()) != a.runner_sha256:
        raise ValueError('compiler or runner digest mismatch')
    ledger = json.loads(LEDGER.read_text())['added']
    for key in ('test/kototama/fixtures/jun-792-aot-receipts-20261103.json',
                'test/kototama/experimental_cbor_reference_bridge.kotoba',
                'test/kototama/experimental_i64_reference.kotoba',
                'src/kototama/pure_i64_receipt.kotoba'):
        if sha((LIB / key).read_bytes()) != ledger[key]['sha256']:
            raise ValueError('source digest mismatch: ' + key)
    snapshot = json.loads(SNAPSHOT.read_text()); report_data = REPORT.read_bytes(); report = json.loads(report_data)
    if (snapshot.get('schema') != 'kototama.experimental-aot-receipts-snapshot.v1'
            or snapshot.get('caseCount') != 98 or len(snapshot.get('cases', [])) != 98
            or snapshot.get('profile') != 'kototama.pure-i64-receipt/v2'
            or snapshot.get('reportSha256') != sha(report_data)
            or snapshot.get('compilerSha256') != report.get('compilerSHA256')
            or snapshot.get('gateSha256') != report.get('gateSHA256') or report.get('status') != 'PASS'):
        raise ValueError('snapshot/report binding mismatch')
    records = {row['index']: row for row in report['cases']}
    tracked = [compiler, runner, SNAPSHOT, REPORT, LEDGER, Path(__file__).resolve()]
    sources = {
        'bridge.kotoba': LIB / 'test/kototama/experimental_cbor_reference_bridge.kotoba',
        'reference.kotoba': LIB / 'test/kototama/experimental_i64_reference.kotoba',
        'kototama/pure_i64_receipt.kotoba': LIB / 'src/kototama/pure_i64_receipt.kotoba',
        **{'cbor/' + n + '.kotoba': ROOT / ('lib/org.ietf.cbor/src/cbor/' + n + '.kotoba')
           for n in ('codec', 'fragment', 'value')},
    }
    tracked.extend(sources.values()); hashes = {str(path): sha(path.read_bytes()) for path in tracked}
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    inputs = out / 'inputs'; inputs.mkdir()
    env = {'PATH': '/nonexistent', 'KEXE_CAP_RESOURCES_35': str(out), 'KEXE_STACK_BYTES': '8388608'}
    observations, seen = [], set()
    for row in snapshot['cases']:
        i = row['index']
        if type(i) is not int or i < 0 or i > 999999 or i in seen:
            raise ValueError('invalid case index')
        seen.add(i); record = records[i]; program = bytes.fromhex(row['programHex']); old = bytes.fromhex(row['receiptHex'])
        if (sha(program) != row['inputSha256'] or row['inputSha256'] != record['inputSHA256']
                or len(old) != 64 or list(struct.unpack('<8q', old)) != record['receipt']
                or row['budget'] != record['budget'] or row['exit'] != record['guestExit']
                or row['name'] != record['name']):
            raise ValueError('snapshot case does not match retained report')
        source, binary = inputs / f'{i:03d}.cbor', inputs / f'{i:03d}.elf'
        source.write_bytes(program)
        build = subprocess.run([str(compiler), 'compile-kototama', str(source), '--target', 'x86_64-linux',
                                '--output', str(binary), '--fuel', str(row['budget']), '--profile', snapshot['profile']],
                               cwd=out, env=env, capture_output=True, timeout=120)
        (inputs / f'{i:03d}-compile.stderr').write_bytes(build.stderr)
        if build.returncode or not binary.is_file():
            raise RuntimeError(f'AOT compile failed for {i}: {build.stderr[-300:]!r}')
        binary.chmod(0o700)
        guest = subprocess.run([str(binary)], cwd=out, env={'PATH': '/nonexistent'}, capture_output=True, timeout=10)
        (inputs / f'{i:03d}-guest.stdout').write_bytes(guest.stdout)
        (inputs / f'{i:03d}-guest.stderr').write_bytes(guest.stderr)
        if len(guest.stdout) != 64 or guest.stderr:
            raise RuntimeError(f'AOT transport failed for {i}: exit={guest.returncode} bytes={len(guest.stdout)}')
        # The stack bound is a fixed historical fixture, not independent admission.
        stack = struct.unpack('<8q', old)[7]
        observations.append((i, program, guest.stdout, guest.returncode, row['budget'], stack))
    parts = ['(ns comparison (:export [main]) (:require [bridge :as b] [reference :as r] [kototama.pure-i64-receipt :as receipt]))\n',
             '(defn- word [d :vector-i64 off :i64] :i64 (loop [i 0 v 0] (if (= i 8) v '
             '(recur (+ i 1) (bit-or v (i64-shift-left (vector-at d (+ off i)) (* i 8)))))))\n',
             '(defn- check [program :vector-i64 data :vector-i64 exit :i64 budget :i64 stack :i64] :bool '
             '(and (receipt/valid? data exit budget stack) '
             '(let [v (r/evaluate (b/nodes program) budget)] '
             '(and (= (vector-at v 0) (word data 8)) (= (vector-at v 1) (word data 16)) '
             '(= (vector-at v 2) (word data 32))))))\n']
    for start in range(0, len(observations), 8):
        terms = []
        for _, program, data, exit_code, budget, stack in observations[start:start + 8]:
            pv, rv = literal(program), literal(data)
            terms.append(f'(check {pv} {rv} {exit_code} {budget} {stack})')
            terms.append(f'(not (check {pv} (vector-assoc! {rv} 0 0) {exit_code} {budget} {stack}))')
        parts.append(f'(defn- group-{start // 8} [] :bool (and ' + ' '.join(terms) + '))\n')
    groups = ' '.join(f'(group-{i})' for i in range((len(observations) + 7) // 8))
    parts.append(f'(defn main [] :i64 (if (and {groups}) 42 0))\n')
    gate_text = ''.join(parts)

    def native(name, mutant, expected):
        root = out / name / 'src'; root.mkdir(parents=True)
        for relative, source in sources.items():
            dest = root / relative; dest.parent.mkdir(parents=True, exist_ok=True)
            text = source.read_text()
            if mutant and relative == 'bridge.kotoba':
                needle = '(vector-assoc! base kind)'
                if text.count(needle) != 1:
                    raise ValueError('mutant anchor drift')
                text = text.replace(needle, '(vector-assoc! base (if (= kind 1) 5 kind))')
            dest.write_text(text)
        gate = root / 'comparison.kotoba'; gate.write_text(gate_text)
        lock = out / (name + '.ksl')
        lock.write_text('KSL1\nentry ' + str(gate) + '\nroot ' + str(root) + '\n' +
                        ''.join('file ' + sha(f.read_bytes()) + ' ' + str(f) + '\n' for f in sorted(root.rglob('*.kotoba'))))
        image, payload = out / (name + '.kx64'), out / (name + '.bin')
        build = subprocess.run([str(compiler), 'compile', str(gate), '--target', 'x86_64-linux', '--output', str(image),
                                '--format', 'kx64-v1', '--source-path', str(root), '--source-lock', str(lock),
                                '--source-lock-sha256', sha(lock.read_bytes())], cwd=out, env=env, capture_output=True, timeout=900)
        (out / (name + '-compile.stderr')).write_bytes(build.stderr)
        if build.returncode or build.stderr:
            raise RuntimeError(f'{name} native compile failed: {build.stderr[-300:]!r}')
        header, body = image.read_bytes().split(b'\n\n', 1)
        m = re.fullmatch(rb'KX64V1 x86_64-linux sysv-ctx-v11 ([0-9]+) 0', header)
        if not m or int(m[1]) != len(body) or body[:1] != b'\xe9':
            raise ValueError('invalid KX64 artifact')
        payload.write_bytes(body)
        runenv = dict(env, KEXE_ALLOW='-', KEXE_FUEL='off', KEXE_STRUCTURED_REPORT='1', KEXE_STRING_POOL='268435456')
        result = subprocess.run([str(runner), str(payload), '0', '0', 'x86_64', '-', '--'],
                                cwd=out, env=runenv, capture_output=True, timeout=300)
        (out / (name + '-run.stdout')).write_bytes(result.stdout)
        (out / (name + '-run.stderr')).write_bytes(result.stderr)
        if result.returncode or result.stderr or not re.search(rb':status :ok\s+:result ' + str(expected).encode() + rb'\b', result.stdout):
            raise RuntimeError(f'{name} verdict mismatch: {result.returncode} {result.stdout[-300:]!r} {result.stderr[-300:]!r}')
        return {'result': expected, 'lockSha256': sha(lock.read_bytes()), 'imageSha256': sha(image.read_bytes())}

    positive, mutant = native('positive', False, 42), native('mutant', True, 0)
    if any(sha(Path(path).read_bytes()) != digest for path, digest in hashes.items()):
        raise ValueError('input changed during observation')
    evidence = {'status': 'PASS_BOUNDED_LIVE_AOT_REFERENCE_LINUX_X86_64', 'caseCount': len(observations),
                'compilerAndReferenceShareBackend': True, 'stackFromHistoricalFixture': True,
                'wholeVmQualified': False, 'inputs': hashes, 'positive': positive, 'mutant': mutant}
    (out / 'receipt.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(evidence['status'], len(observations))


if __name__ == '__main__':
    main()
