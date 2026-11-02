#!/usr/bin/env python3
"""Run the native policy corpus and a negative control as browser Wasm.

Usage: check-draft-policy-browser.py AMU_DIR CHROME NEW_OUTPUT_DIR
Synthetic inputs only; no application storage or OS integration.
"""
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

if len(sys.argv) != 4:
    raise SystemExit(__doc__)
amu, chrome, out = (Path(x).resolve() for x in sys.argv[1:])
root = Path(__file__).resolve().parents[3]
out.mkdir(parents=True, exist_ok=False)
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value
mac = module('mac', amu / 'scripts/seed/check-aiueos-user-macos-native.py')
browser = module('browser', amu / 'scripts/seed/check-wasm32-browser.py')
source = (root / 'lib/kotoba.aiueos/os/aiueos/kotoba/aiueos/draft_policy.kotoba').read_text()
driver = (root / 'lib/kotoba.aiueos/test/aiueos/draft_policy_test.kotoba').read_text()
namespace = '(ns aiueos.draft-policy (:export [classify]))'
testns = '(ns aiueos.draft-policy-test (:export [main]) (:require [aiueos.draft-policy :as p]))'
if source.count(namespace) != 1 or driver.count(testns) != 1:
    raise ValueError('unexpected policy namespace')
staged = source.replace(namespace, '(ns aiueos.draft-policy (:export [main]))', 1) + '\n' + driver.replace(testns, '', 1).replace('p/classify', 'classify')
needle = '(document-equal? base persisted)'
if staged.count(needle) != 1:
    raise ValueError('unexpected negative control')
compiler = amu / 'seed/bootstrap/aarch64-macos/amu-full-root.macho'
sha = lambda b: hashlib.sha256(b).hexdigest()
if sha(compiler.read_bytes()) != '2c551579c06a0228029bb06bae177e93126ecbbc37d636d693c471dbac8d1536':
    raise ValueError('compiler mismatch')
rows = []
for name, text in [('good', staged), ('mutant', staged.replace(needle, 'true'))]:
    (out / (name + '.kotoba')).write_text(text)
    mac.native_run(compiler, out, 'compile', name + '.kotoba', '--target', 'wasm32-browser', '--output', name + '.wasm')
    rows.append((name, out / (name + '.wasm'), {'fuel': 0}))
version, results = browser.run_modules(str(chrome), out, rows)
for name, expected in [('good', 0), ('mutant', 1)]:
    row = results[name]
    if row.get('exit') != 0 or row.get('wasmTrap') is not None or not re.search(rf':status :ok :result {expected}(?:\s|\}})', row.get('report') or ''):
        raise ValueError((name, row))
receipt = {'status': 'PASS_DRAFT_POLICY_BROWSER_SYNTHETIC', 'browser': version,
           'compilerSha256': sha(compiler.read_bytes()), 'sourceSha256': sha(source.encode()),
           'driverSha256': sha(driver.encode()), 'stagedSha256': sha(staged.encode()),
           'wasmSha256': {name: sha((out / (name + '.wasm')).read_bytes()) for name in ('good', 'mutant')},
           'results': results,
           'scope': 'synthetic Chrome Wasm; no JSON/surrogate adapter, app integration, OS/QEMU or release'}
(out / 'evidence.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(receipt['status'], flush=True)
