#!/usr/bin/env python3
"""Run a pinned historical AOT receipt snapshot through the native CBOR model.

The snapshot is not a fresh AOT run. Python checks and transports fixed bytes;
source-locked Kotoba performs the CBOR mapping, evaluation and comparison.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'lib/kotoba.kototama'
SNAPSHOT = LIB / 'test/kototama/fixtures/jun-792-aot-receipts-20261103.json'
REPORT = LIB / 'docs/evidence/jun-792-20261103/amu-receipt-v2-x86-287-report.json'
LEDGER = LIB / 'local-changes.json'
STAGER = LIB / 'scripts/stage-native-cbor-reference.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler', type=Path, required=True)
    p.add_argument('--compiler-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if (platform.system(), platform.machine()) != ('Darwin', 'arm64'):
        raise ValueError('requires native macOS ARM64')
    compiler = a.compiler.resolve(strict=True)
    if sha(compiler) != a.compiler_sha256:
        raise ValueError('compiler digest mismatch')
    subprocess.run(['/usr/bin/codesign', '--verify', '--strict', str(compiler)], check=True, capture_output=True, timeout=30)
    ledger = json.loads(LEDGER.read_text())['added']
    for key in ('test/kototama/fixtures/jun-792-aot-receipts-20261103.json',
                'test/kototama/experimental_cbor_reference_bridge.kotoba',
                'test/kototama/experimental_i64_reference.kotoba',
                'scripts/stage-native-cbor-reference.py'):
        if sha(LIB / key) != ledger[key]['sha256']:
            raise ValueError('source digest mismatch: ' + key)
    data = json.loads(SNAPSHOT.read_text()); report_bytes = REPORT.read_bytes(); report = json.loads(report_bytes)
    if (data.get('schema') != 'kototama.experimental-aot-receipts-snapshot.v1'
            or data.get('caseCount') != 149 or len(data.get('cases', [])) != 149
            or data.get('profile') != 'kototama.pure-i64-receipt/v2'
            or data.get('reportSha256') != hashlib.sha256(report_bytes).hexdigest()
            or data.get('compilerSha256') != report.get('compilerSHA256')
            or data.get('gateSha256') != report.get('gateSHA256') or report.get('status') != 'PASS'):
        raise ValueError('snapshot/report binding mismatch')
    records = {row['index']: row for row in report['cases']}
    output = a.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    corpus = output / 'corpus'; corpus.mkdir(); (corpus / 'report.json').write_bytes(report_bytes)
    indices = []
    for row in data['cases']:
        i = row['index']
        if type(i) is not int or not 0 <= i <= 999999 or i in indices:
            raise ValueError('invalid snapshot index')
        record = records[i]; raw, receipt = bytes.fromhex(row['programHex']), bytes.fromhex(row['receiptHex'])
        if (hashlib.sha256(raw).hexdigest() != row['inputSha256'] or row['inputSha256'] != record['inputSHA256']
                or len(receipt) != 64 or list(struct.unpack('<8q', receipt)) != record['receipt']
                or row['budget'] != record['budget'] or row['exit'] != record['guestExit']
                or row['name'] != record['name']):
            raise ValueError('snapshot case does not match retained report')
        (corpus / f'{i:03d}.cbor').write_bytes(raw)
        (corpus / f'{i:03d}-guest.stdout').write_bytes(receipt)
        indices.append(i)
    selection = output / 'selection.json'
    selection.write_text(json.dumps({'indices': indices, 'reportSha256': data['reportSha256']}) + '\n')
    tracked = (compiler, SNAPSHOT, REPORT, LEDGER, STAGER, Path(__file__).resolve(),
               LIB / 'test/kototama/experimental_cbor_reference_bridge.kotoba',
               LIB / 'test/kototama/experimental_i64_reference.kotoba',
               *(ROOT / ('lib/org.ietf.cbor/src/cbor/' + name + '.kotoba')
                 for name in ('codec', 'fragment', 'value')))
    inputs = {str(path): sha(path) for path in tracked}
    env = {'PATH': '/nonexistent', 'LANG': 'C'}

    def observe(name, mutant, expected):
        work = output / name
        stage = subprocess.run([sys.executable, str(STAGER), '--receipt-dir', str(corpus),
                                '--selection', str(selection), '--output', str(work)],
                               cwd=output, env=env, capture_output=True, timeout=60)
        if stage.returncode or stage.stderr:
            raise RuntimeError(f'{name} staging failed: {stage.stderr[-500:]!r}')
        source, gate, lock = work / 'bridge.kotoba', work / 'comparison.kotoba', work / 'project.ksl'
        if mutant:
            text = source.read_text(); before = '(vector-assoc! base kind)'
            if text.count(before) != 1:
                raise ValueError('negative-control anchor drift')
            source.write_text(text.replace(before, '(vector-assoc! base (if (= kind 1) 5 kind))'))
            lines = lock.read_text().splitlines()
            lock.write_text('\n'.join(('file ' + sha(source) + ' ' + str(source))
                                      if line.startswith('file ') and line.endswith(' ' + str(source)) else line
                                      for line in lines) + '\n')
        binary = work / 'comparison'
        for label, command in [('compile', [str(compiler), 'compile', str(gate), '--source-lock', str(lock), '-o', str(binary)]),
                               ('run', [str(binary)])]:
            result = subprocess.run(command, cwd=work, env=env, capture_output=True, timeout=300)
            (work / (label + '.stdout')).write_bytes(result.stdout)
            (work / (label + '.stderr')).write_bytes(result.stderr)
            if result.returncode or result.stderr or (label == 'run' and result.stdout.strip() != str(expected).encode()):
                raise RuntimeError(f'{name} {label} failed: {result.returncode} {result.stdout[-200:]!r} {result.stderr[-200:]!r}')
        return {'result': expected, 'lockSha256': sha(lock), 'artifactSha256': sha(binary)}

    positive, negative = observe('positive', False, 42), observe('mutant', True, 0)
    if any(sha(Path(path)) != digest for path, digest in inputs.items()):
        raise ValueError('input changed during observation')
    evidence = {'status': 'PASS_BOUNDED_SNAPSHOT_NATIVE_CBOR_REFERENCE_MACOS', 'caseCount': len(indices),
                'freshAotRun': False, 'fullVmQualified': False, 'inputs': inputs,
                'positive': positive, 'negative': negative}
    (output / 'receipt.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(evidence['status'], len(indices))


if __name__ == '__main__':
    main()
