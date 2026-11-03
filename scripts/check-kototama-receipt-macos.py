#!/usr/bin/env python3
"""Run the bounded pure-i64 receipt validator and a mutant on native macOS ARM64."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
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
    p.add_argument('--compiler', type=Path, required=True)
    p.add_argument('--compiler-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if (platform.system(), platform.machine()) != ('Darwin', 'arm64'):
        raise ValueError('requires native macOS arm64')
    compiler = a.compiler.resolve(strict=True)
    if digest(compiler) != a.compiler_sha256:
        raise ValueError('compiler digest mismatch')
    subprocess.run(['/usr/bin/codesign', '--verify', '--strict', str(compiler)], check=True, capture_output=True, timeout=30)
    ledger = json.loads(LEDGER.read_text())['added']
    for path, name in ((SOURCE, 'src/kototama/pure_i64_receipt.kotoba'),
                       (GATE, 'test/kototama/pure_i64_receipt_gate.kotoba')):
        if digest(path) != ledger[name]['sha256']:
            raise ValueError('source digest mismatch: ' + name)
    inputs = {str(path): digest(path) for path in (compiler, SOURCE, GATE, LEDGER, Path(__file__).resolve())}
    output = a.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = {'PATH': '/nonexistent', 'LANG': 'C'}

    def observe(name, mutant, expected):
        work = output / name
        work.mkdir()
        source, gate = work / SOURCE.name, work / GATE.name
        text = SOURCE.read_text()
        if mutant:
            original = '(= magic 14164133038085195)'
            if text.count(original) != 1:
                raise ValueError('negative-control anchor drift')
            text = text.replace(original, '(= magic magic)')
        source.write_text(text)
        shutil.copyfile(GATE, gate)
        lock = work / 'project.ksl'
        lock.write_text('KSL2\nentry ' + str(gate) + '\n' +
                        'module kototama.pure-i64-receipt ' + str(source) + '\n' +
                        'module kototama.pure-i64-receipt-gate ' + str(gate) + '\n' +
                        ''.join('file ' + digest(f) + ' ' + str(f) + '\n' for f in (source, gate)))
        binary = work / 'gate'
        commands = [[str(compiler), 'check', str(gate), '--source-lock', str(lock)],
                    [str(compiler), 'compile', str(gate), '--source-lock', str(lock), '-o', str(binary)],
                    [str(binary)]]
        for label, cmd in zip(('check', 'compile', 'run'), commands):
            r = subprocess.run(cmd, cwd=work, env=env, capture_output=True, timeout=300)
            (work / (label + '.stdout')).write_bytes(r.stdout)
            (work / (label + '.stderr')).write_bytes(r.stderr)
            if r.returncode or r.stderr or (label == 'run' and r.stdout.strip() != str(expected).encode()):
                raise RuntimeError(f'{name} {label} failed: exit={r.returncode} stdout={r.stdout[-300:]!r} stderr={r.stderr[-300:]!r}')
        return {'sourceSha256': digest(source), 'lockSha256': digest(lock),
                'binarySha256': digest(binary), 'result': expected}

    positive = observe('positive', False, 42)
    negative = observe('mutant', True, 0)
    if any(digest(Path(path)) != sha for path, sha in inputs.items()):
        raise ValueError('input changed during observation')
    receipt = {'status': 'PASS_BOUNDED_PURE_I64_RECEIPT_MACOS', 'inputs': inputs,
               'positive': positive, 'negative': negative, 'fullVmQualified': False}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(receipt['status'])


if __name__ == '__main__':
    main()
