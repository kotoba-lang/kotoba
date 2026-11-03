#!/usr/bin/env python3
"""Observe the pure-i64 receipt validator and a mutant on native Linux x86-64."""
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
    a = p.parse_args()
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'AMD64'):
        raise ValueError('requires native Linux x86-64')
    compiler, runner = a.compiler.resolve(strict=True), a.runner.resolve(strict=True)
    if digest(compiler) != a.compiler_sha256 or digest(runner) != a.runner_sha256:
        raise ValueError('compiler or runner digest mismatch')
    ledger = json.loads(LEDGER.read_text())['added']
    for path, name in ((SOURCE, 'src/kototama/pure_i64_receipt.kotoba'),
                       (GATE, 'test/kototama/pure_i64_receipt_gate.kotoba')):
        if digest(path) != ledger[name]['sha256']:
            raise ValueError('source digest mismatch: ' + name)
    inputs = {str(path): digest(path) for path in (compiler, runner, SOURCE, GATE, LEDGER, Path(__file__).resolve())}
    output = a.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = {'PATH': '/nonexistent', 'KEXE_CAP_RESOURCES_35': str(output), 'KEXE_STACK_BYTES': '8388608'}

    def observe(name, mutant, expected):
        root = output / name / 'src'
        (root / 'kototama').mkdir(parents=True)
        source, gate = root / 'kototama' / SOURCE.name, root / 'kototama' / GATE.name
        text = SOURCE.read_text()
        if mutant:
            original = '(= magic 14164133038085195)'
            if text.count(original) != 1:
                raise ValueError('negative-control anchor drift')
            text = text.replace(original, '(= magic magic)')
        source.write_text(text)
        shutil.copyfile(GATE, gate)
        lock = output / (name + '.ksl')
        lock.write_text('KSL1\nentry ' + str(gate) + '\nroot ' + str(root) + '\n' +
                        ''.join('file ' + digest(f) + ' ' + str(f) + '\n' for f in sorted((source, gate))))
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
    if any(digest(Path(path)) != sha for path, sha in inputs.items()):
        raise ValueError('input changed during observation')
    report = {'status': 'PASS_BOUNDED_PURE_I64_RECEIPT_LINUX_X86_64', 'inputs': inputs,
              'positive': positive, 'negative': negative, 'fullVmQualified': False}
    (output / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report['status'])


if __name__ == '__main__':
    main()
