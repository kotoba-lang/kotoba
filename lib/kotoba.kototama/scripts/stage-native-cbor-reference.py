#!/usr/bin/env python3
"""Stage native CBOR/model comparisons from trusted Amu test observations.

Python selects and transports bytes; native Kotoba performs decoding, the
experimental mapping and evaluation, and the comparison. This is neither VM
admission nor a complete evaluator. Selection must be supplied explicitly.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

ROOT = Path(__file__).resolve().parents[3]
LIB = ROOT / 'lib/kotoba.kototama'
CBOR = ROOT / 'lib/org.ietf.cbor/src/cbor'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def literal(data):
    chunks = ['[' + ' '.join(map(str, data[i:i + 48])) + ']' for i in range(0, len(data), 48)]
    if not chunks:
        return '[]'
    value = chunks[0]
    for chunk in chunks[1:]:
        value = '(into ' + value + ' ' + chunk + ')'
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('receipt-dir', 'selection', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    corpus = a.receipt_dir.resolve(strict=True)
    report_data, selected_data = (corpus / 'report.json').read_bytes(), a.selection.read_bytes()
    report, selection = json.loads(report_data), json.loads(selected_data)
    if report.get('status') != 'PASS' or report.get('profile') != 'kototama.pure-i64-receipt/v2':
        raise ValueError('expected a passing v2 corpus')
    if selection.get('reportSha256') != sha(report_data):
        raise ValueError('selection refers to a different report')
    indices = selection['indices']
    if not indices or len(set(indices)) != len(indices) or any(type(i) is not int or not 0 <= i <= 999999 for i in indices):
        raise ValueError('invalid selected indices')
    records = {r['index']: r for r in report['cases']}
    rows = []
    for i in indices:
        r = records[i]
        if r['compileExit'] != 0 or r['outputBytes'] != 64:
            raise ValueError('selected case has no receipt')
        raw, receipt = (corpus / f'{i:03d}.cbor').read_bytes(), (corpus / f'{i:03d}-guest.stdout').read_bytes()
        if sha(raw) != r['inputSHA256'] or len(receipt) != 64:
            raise ValueError('input digest or receipt length mismatch')
        w = struct.unpack('<8q', receipt)
        if list(w) != r['receipt'] or w[0] != 0x003252343649544b or type(r['budget']) is not int or w[3] != r['budget']:
            raise ValueError('receipt/context mismatch')
        rows.append((raw, r['budget'], w[1], w[2], w[4]))
    if rows[0][0][:1] != b'\x83':
        raise ValueError('unexpected envelope in negative control')
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    modules = {}
    for module, src in [('bridge', LIB / 'test/kototama/experimental_cbor_reference_bridge.kotoba'),
                        ('reference', LIB / 'test/kototama/experimental_i64_reference.kotoba'),
                        ('cbor.codec', CBOR / 'codec.kotoba'), ('cbor.fragment', CBOR / 'fragment.kotoba'),
                        ('cbor.value', CBOR / 'value.kotoba')]:
        dst = out / (module + '.kotoba'); shutil.copyfile(src, dst); modules[module] = dst
    parts = ['(ns comparison (:export [main]) (:require [bridge :as b] [reference :as r]))\n',
             '(defn- is [a :vector-i64 s :i64 v :i64 f :i64] :bool '
             '(and (= (vector-at a 0) s) (= (vector-at a 1) v) (= (vector-at a 2) f)))\n']
    for start in range(0, len(rows), 8):
        terms = [f'(is (r/evaluate (b/nodes {literal(raw)}) {budget}) {status} {value} {spent})'
                 for raw, budget, status, value, spent in rows[start:start + 8]]
        parts.append(f'(defn- group-{start // 8} [] :bool (and ' + ' '.join(terms) + '))\n')
    raw = rows[0][0]
    checks = ' '.join(f'(= (vector-at (b/nodes {literal(x)}) 0) -1)' for x in (b'\x98\x03' + raw[1:], raw + b'\x00'))
    groups = ' '.join(f'(group-{i})' for i in range((len(rows) + 7) // 8))
    parts.append(f'(defn main [] :i64 (if (and {checks} {groups}) 42 0))\n')
    gate = out / 'comparison.kotoba'; gate.write_text(''.join(parts)); modules['comparison'] = gate
    lock = out / 'project.ksl'
    lock.write_text('KSL2\nentry ' + str(gate) + '\n' +
                    ''.join('module ' + name + ' ' + str(path) + '\n' for name, path in sorted(modules.items())) +
                    ''.join('file ' + sha(path.read_bytes()) + ' ' + str(path) + '\n' for path in sorted(modules.values())))
    manifest = {'schema': 'kototama.experimental-native-cbor-reference.v1', 'caseCount': len(rows),
                'reportSha256': sha(report_data), 'selectionSha256': sha(selected_data),
                'modules': {name: sha(path.read_bytes()) for name, path in modules.items()},
                'lockSha256': sha(lock.read_bytes()), 'canonicalVmAdmission': False, 'wholeVmQualified': False}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('staged', len(rows), 'actual receipt observations and two CBOR refusals')


if __name__ == '__main__':
    main()
