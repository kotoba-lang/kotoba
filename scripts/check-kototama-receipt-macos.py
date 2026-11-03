#!/usr/bin/env python3
"""Run a bounded pure-i64 fixture and mutant on native macOS ARM64."""
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
    p.add_argument('--fixture', choices=('receipt', 'reference', 'cbor-reference'), default='receipt')
    a = p.parse_args()
    if (platform.system(), platform.machine()) != ('Darwin', 'arm64'):
        raise ValueError('requires native macOS arm64')
    compiler = a.compiler.resolve(strict=True)
    if digest(compiler) != a.compiler_sha256:
        raise ValueError('compiler digest mismatch')
    subprocess.run(['/usr/bin/codesign', '--verify', '--strict', str(compiler)], check=True, capture_output=True, timeout=30)
    ledger = json.loads(LEDGER.read_text())['added']
    extra_modules = {}
    extra_keys = []
    if a.fixture == 'cbor-reference':
        source_key = 'test/kototama/experimental_cbor_reference_bridge.kotoba'
        gate_key = 'test/kototama/experimental_cbor_reference_gate.kotoba'
        module, gate_module = 'bridge', 'comparison'
        original = '(vector-assoc! base kind)'
        replacement = '(vector-assoc! base (if (= kind 1) 5 kind))'
        reference_key = 'test/kototama/experimental_i64_reference.kotoba'
        extra_keys.append(reference_key)
        extra_modules['reference'] = LIB / reference_key
        for name in ('codec', 'fragment', 'value'):
            extra_modules['cbor.' + name] = ROOT / ('lib/org.ietf.cbor/src/cbor/' + name + '.kotoba')
    elif a.fixture == 'reference':
        source_key = 'test/kototama/experimental_i64_reference.kotoba'
        gate_key = 'test/kototama/experimental_i64_reference_gate.kotoba'
        module, gate_module = 'reference', 'gate'
        original = '(if (= value 0) 3 2)'
        replacement = '(if (= value 0) 2 3)'
    else:
        source_key = 'src/kototama/pure_i64_receipt.kotoba'
        gate_key = 'test/kototama/pure_i64_receipt_gate.kotoba'
        module, gate_module = 'kototama.pure-i64-receipt', 'kototama.pure-i64-receipt-gate'
        original = '(= magic 14164133038085195)'
        replacement = '(= magic magic)'
    src, fixture = LIB / source_key, LIB / gate_key
    for path, name in ((src, source_key), (fixture, gate_key)):
        if digest(path) != ledger[name]['sha256']:
            raise ValueError('source digest mismatch: ' + name)
    for key in extra_keys:
        if digest(LIB / key) != ledger[key]['sha256']:
            raise ValueError('source digest mismatch: ' + key)
    inputs = {str(path): digest(path) for path in
              (compiler, src, fixture, LEDGER, Path(__file__).resolve(), *extra_modules.values())}
    output = a.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = {'PATH': '/nonexistent', 'LANG': 'C'}

    def observe(name, mutant, expected):
        work = output / name
        work.mkdir()
        source, gate = work / 'source.kotoba', work / 'gate.kotoba'
        text = src.read_text()
        if mutant:
            old, new = (("(valid-methods methods 0)", "true") if name == 'mutant-methods'
                        else ("(>= count 4095)", "(>= count 4096)") if name == 'mutant-limit'
                        else (original, replacement))
            if text.count(old) != 1:
                raise ValueError('negative-control anchor drift')
            text = text.replace(old, new)
        source.write_text(text)
        shutil.copyfile(fixture, gate)
        lock = work / 'project.ksl'
        modules = [(module, source), (gate_module, gate)]
        for mod, original_path in sorted(extra_modules.items()):
            dest = work / (mod + '.kotoba')
            shutil.copyfile(original_path, dest)
            if name == 'mutant-synthetic' and mod == 'reference':
                text = dest.read_text(); old = '(or (= op 8) (>= op 11))'
                if text.count(old) != 1:
                    raise ValueError('synthetic-charge control anchor drift')
                dest.write_text(text.replace(old, 'false'))
            modules.append((mod, dest))
        modules.sort()
        paths = sorted(path for _, path in modules)
        lock.write_text('KSL2\nentry ' + str(gate) + '\n' +
                        ''.join('module ' + m + ' ' + str(f) + '\n' for m, f in modules) +
                        ''.join('file ' + digest(f) + ' ' + str(f) + '\n' for f in paths))
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
    method_negative = observe('mutant-methods', True, 0) if a.fixture == 'cbor-reference' else None
    limit_negative = observe('mutant-limit', True, 0) if a.fixture == 'cbor-reference' else None
    synthetic_negative = observe('mutant-synthetic', False, 0) if a.fixture == 'cbor-reference' else None
    if any(digest(Path(path)) != sha for path, sha in inputs.items()):
        raise ValueError('input changed during observation')
    receipt = {'status': 'PASS_BOUNDED_PURE_I64_' + a.fixture.upper() + '_MACOS', 'inputs': inputs,
               'positive': positive, 'negative': negative, 'methodNegative': method_negative, 'limitNegative': limit_negative, 'syntheticNegative': synthetic_negative, 'fullVmQualified': False}
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(receipt['status'])


if __name__ == '__main__':
    main()
