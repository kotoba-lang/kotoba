#!/usr/bin/env python3
"""Observe bounded pure-i64 fixtures and mutants on native Linux x86-64."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'lib/kotoba.kototama'
SOURCE = LIB / 'src/kototama/pure_i64_receipt.kotoba'
GATE = LIB / 'test/kototama/pure_i64_receipt_gate.kotoba'
LEDGER = LIB / 'local-changes.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('compiler', 'runner', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    for name in ('compiler-sha256', 'runner-sha256'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--fixture', choices=('receipt', 'cbor-reference'), default='receipt')
    a = p.parse_args()
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'AMD64'):
        raise ValueError('requires native Linux x86-64')
    compiler, runner = a.compiler.resolve(strict=True), a.runner.resolve(strict=True)
    if digest(compiler) != a.compiler_sha256 or digest(runner) != a.runner_sha256:
        raise ValueError('compiler or runner digest mismatch')
    ledger = json.loads(LEDGER.read_text())['added']
    extras = {}
    extra_keys = []
    if a.fixture == 'cbor-reference':
        source_key = 'test/kototama/experimental_cbor_reference_bridge.kotoba'
        gate_key = 'test/kototama/experimental_cbor_reference_gate.kotoba'
        source_name, gate_name = 'bridge.kotoba', 'comparison.kotoba'
        original, replacement = '(vector-assoc! base kind)', '(vector-assoc! base (if (= kind 1) 5 kind))'
        extra_keys.append('test/kototama/experimental_i64_reference.kotoba')
        extras['reference.kotoba'] = LIB / extra_keys[0]
        for name in ('codec', 'fragment', 'value'):
            extras['cbor/' + name + '.kotoba'] = ROOT / ('lib/org.ietf.cbor/src/cbor/' + name + '.kotoba')
    else:
        source_key = 'src/kototama/pure_i64_receipt.kotoba'
        gate_key = 'test/kototama/pure_i64_receipt_gate.kotoba'
        source_name, gate_name = 'kototama/pure_i64_receipt.kotoba', 'kototama/pure_i64_receipt_gate.kotoba'
        original, replacement = '(= magic 14164133038085195)', '(= magic magic)'
    src, fixture = LIB / source_key, LIB / gate_key
    for key in (source_key, gate_key, *extra_keys):
        if digest(LIB / key) != ledger[key]['sha256']:
            raise ValueError('source digest mismatch: ' + key)
    inputs = {str(path): digest(path) for path in
              (compiler, runner, src, fixture, LEDGER, Path(__file__).resolve(), *extras.values())}
    output = a.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = {'PATH': '/nonexistent', 'KEXE_CAP_RESOURCES_35': str(output), 'KEXE_STACK_BYTES': '8388608'}

    def observe(name, mutant, expected):
        root = output / name / 'src'
        root.mkdir(parents=True)
        source, gate = root / source_name, root / gate_name
        source.parent.mkdir(parents=True, exist_ok=True)
        gate.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text()
        if mutant:
            old, new = (("(valid-methods methods 0)", "true") if name == 'mutant-methods'
                        else ("(>= count 4095)", "(>= count 4096)") if name == 'mutant-limit'
                        else ("(if (string=? (typed-list-nth [:list :string] env i) name) i",
                              "(if (string=? (typed-list-nth [:list :string] env i) name) "
                              "(if (> i 0) (let [prior (lookup env name (- i 1))] (if (< prior 0) i prior)) i)")
                        if name == 'mutant-shadow' else (original, replacement))
            if text.count(old) != 1:
                raise ValueError('negative-control anchor drift')
            text = text.replace(old, new)
        source.write_text(text)
        shutil.copyfile(fixture, gate)
        for relative, path in extras.items():
            dest = root / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
            if name == 'mutant-synthetic' and relative == 'reference.kotoba':
                text = dest.read_text(); old = '(or (= op 8) (= op 11) (= op 12) (= op 13))'
                if text.count(old) != 1:
                    raise ValueError('synthetic-charge control anchor drift')
                dest.write_text(text.replace(old, 'false'))
            if name == 'mutant-compare-eager' and relative == 'reference.kotoba':
                text = dest.read_text(); old = '(if (= next-link -1)'
                if text.count(old) != 1:
                    raise ValueError('comparison eagerness control anchor drift')
                dest.write_text(text.replace(old, '(if (or (= next-link -1) (not good))'))
        lock = output / (name + '.ksl')
        lock.write_text('KSL1\nentry ' + str(gate) + '\nroot ' + str(root) + '\n' +
                        ''.join('file ' + digest(f) + ' ' + str(f) + '\n' for f in sorted(root.rglob('*.kotoba'))))
        artifact, payload = output / (name + '.kx64'), output / (name + '.bin')
        command = [str(compiler), 'compile', str(gate), '--target', 'x86_64-linux', '--output', str(artifact),
                   '--format', 'kx64-v1', '--source-path', str(root), '--source-lock', str(lock),
                   '--source-lock-sha256', digest(lock)]
        r = subprocess.run(command, cwd=output, env=env, capture_output=True, timeout=900)
        (output / (name + '-compile.stdout')).write_bytes(r.stdout)
        (output / (name + '-compile.stderr')).write_bytes(r.stderr)
        if r.returncode or r.stderr:
            raise RuntimeError(f'{name} compile failed: {r.returncode} {r.stderr[-500:]!r}')
        header, body = artifact.read_bytes().split(b'\n\n', 1)
        match = re.fullmatch(rb'KX64V1 x86_64-linux sysv-ctx-v11 ([0-9]+) 0', header)
        if not match or int(match[1]) != len(body) or body[:1] != b'\xe9':
            raise ValueError('invalid native payload')
        payload.write_bytes(body)
        runenv = dict(env, KEXE_ALLOW='-', KEXE_FUEL='off', KEXE_STRUCTURED_REPORT='1', KEXE_STRING_POOL='268435456')
        r = subprocess.run([str(runner), str(payload), '0', '0', 'x86_64', '-', '--'],
                           cwd=output, env=runenv, capture_output=True, timeout=300)
        (output / (name + '-run.stdout')).write_bytes(r.stdout)
        (output / (name + '-run.stderr')).write_bytes(r.stderr)
        if r.returncode or r.stderr or not re.search(rb':status :ok\s+:result ' + str(expected).encode() + rb'\b', r.stdout):
            raise RuntimeError(f'{name} result mismatch: {r.returncode} {r.stdout[-500:]!r} {r.stderr[-500:]!r}')
        return {'sourceSha256': digest(source), 'lockSha256': digest(lock),
                'artifactSha256': digest(artifact), 'result': expected}

    positive, negative = observe('positive', False, 42), observe('mutant', True, 0)
    method_negative = observe('mutant-methods', True, 0) if a.fixture == 'cbor-reference' else None
    limit_negative = observe('mutant-limit', True, 0) if a.fixture == 'cbor-reference' else None
    synthetic_negative = observe('mutant-synthetic', False, 0) if a.fixture == 'cbor-reference' else None
    eager_negative = observe('mutant-compare-eager', False, 0) if a.fixture == 'cbor-reference' else None
    shadow_negative = observe('mutant-shadow', True, 0) if a.fixture == 'cbor-reference' else None
    if any(digest(Path(path)) != sha for path, sha in inputs.items()):
        raise ValueError('input changed during observation')
    report = {'status': 'PASS_BOUNDED_PURE_I64_' + a.fixture.upper() + '_LINUX_X86_64', 'inputs': inputs,
              'positive': positive, 'negative': negative, 'methodNegative': method_negative, 'limitNegative': limit_negative, 'syntheticNegative': synthetic_negative, 'eagerNegative': eager_negative, 'shadowNegative': shadow_negative, 'fullVmQualified': False}
    (output / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report['status'])


if __name__ == '__main__':
    main()
