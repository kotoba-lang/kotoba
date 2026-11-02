#!/usr/bin/env python3
"""Build source-bound native fleet successor fixtures with negative controls.

Public synthetic signatures and a public, untrusted historical record are used.
This does not test a receiver,
checkpoint authority, persistent trust, rotation, transport, or deployment.
"""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LIB = ROOT / 'lib/kotoba.kagami'
spec = importlib.util.spec_from_file_location('native_gate', ROOT / 'lib/kotoba.hata/scripts/native_gate.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def remove_ns(text):
    start = text.index('(ns ')
    depth = 0
    for pos in range(start, len(text)):
        if text[pos] == '(':
            depth += 1
        elif text[pos] == ')':
            depth -= 1
            if depth == 0:
                return text[:start] + text[pos + 1:]
    raise ValueError('unclosed namespace')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--compiler-sha256', required=True)
    parser.add_argument('--packager', type=Path)
    parser.add_argument('--packager-sha256')
    parser.add_argument('--runner', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    gate = module.NativeGate(args)
    ed = (ROOT / 'lib/org.ietf.ed25519/kotoba/ed25519/selfhost.kotoba').read_text()
    sha = (ROOT / 'lib/gov.nist.sha2/kotoba/sha2/core.kotoba').read_text()
    native = (LIB / 'src/kagami/fleet_native.kotoba').read_text()
    test = (LIB / 'test/kagami/fleet_native_main.kotoba').read_text()
    header = '''(ns fleet.test
  (:schemas {:fleet/native-head [:record :fleet/native-head
    [[:name :string] [:value :string] [:sequence :i64] [:parent :string]
     [:signature :string] [:signer :string] [:valid-until-nil :bool]]]})
  (:export [main]))\n'''
    mutations = {
        'atomic-output': '(let [r (verify-edn-chain heads anchor-seq anchor-hash allowed-did)]',
        'batch-size': '(> n 16)',
        'batch-failure': '(not (option-some?-of [:option :string] next))',
        'decimal-leading-zero': '(and (> (- end start) 1) (= (string-code-point-at s start) 48))',
        'layout-prefix': '(not (fn-at? raw 0 prefix))',
        'layout-sequence': '(not (fn-at? raw (+ value-at 64) mid))',
        'layout-parent': '(not (fn-at? raw seq-end parent-label))',
        'layout-expiry': '(not (fn-at? raw (+ parent-at 64) sig-label))',
        'layout-signer': '(not (fn-at? raw (+ sig-at 128) did-label))',
        'layout-length': '(not (= n (+ end 2)))',
        'subject': '(not (string=? (get h :name) "fleet-db"))',
        'sequence': '(not (= seq (+ anchor-seq 1)))',
        'parent': '(not (string=? (get h :parent) anchor-hash))',
        'expiry': '(not (get h :valid-until-nil))',
        'trust': '(not (string=? did allowed-did))',
        'signature': '(ed/verify? pk (vector-i64-from-bytes (string-to-utf8 payload)) (ed/hex-bytes sig))',
    }
    for label, needle in [('baseline', None), *mutations.items()]:
        candidate = native
        if needle:
            assert candidate.count(needle) == 1, label
            candidate = candidate.replace(needle, '(let [ignored (vector-assoc! out 0 0) r (verify-edn-chain heads anchor-seq anchor-hash allowed-did)]' if label == 'atomic-output' else 'true' if label == 'signature' else 'false')
        source = header + '\n'.join(map(remove_ns, [ed, sha, candidate]))
        source = source.replace('ed/', '').replace('sha/', '') + '\n' + test
        image = gate.build(label, 'fixture.kotoba', {'fixture.kotoba': source.encode()})
        gate.run(label + '-run', image, expected=0 if needle is None else 1)
    gate.finish('PASS_FLEET_NATIVE_SUCCESSOR', scope='bounded batch, strict EDN and synthetic/public historical fixtures only; no receiver, trust store, durable sync or deployment',
                sourceSHA256=module.sha(native.encode()), testSHA256=module.sha(test.encode()), mutations=list(mutations))
    evidence_path = gate.out / 'evidence.json'
    evidence = json.loads(evidence_path.read_text())
    evidence['publicTestKeysOnly'] = False  # includes an untrusted historical signer
    evidence['historicalSignerTrusted'] = False
    evidence_path.write_text(json.dumps(evidence, indent=2) + '\n')


if __name__ == '__main__':
    main()
