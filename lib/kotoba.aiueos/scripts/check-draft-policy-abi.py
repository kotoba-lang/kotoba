#!/usr/bin/env python3
"""Exercise the office recovery transport in native macOS and browser Wasm.

Usage: check-draft-policy-abi.py AMU_DIR CHROME NEW_OUTPUT_DIR
Synthetic values only. JSON conversion and application integration are separate.
"""
import hashlib
import importlib.util
import json
import re
import sys
import types
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
native = module('native', root / 'lib/kotoba.hata/scripts/native_gate.py')
source = (root / 'lib/kotoba.aiueos/os/aiueos/kotoba/aiueos/draft_policy.kotoba').read_text()
driver = (root / 'lib/kotoba.aiueos/os/aiueos/kotoba/aiueos/draft_policy_browser.kotoba').read_text()
pn = '(ns aiueos.draft-policy (:export [classify classify-chunks units]))'
dn = '(ns aiueos.draft-policy-browser\n  (:export [main])\n  (:capabilities [:cli/args :io/write])\n  (:require [aiueos.draft-policy :as policy]))'
if source.count(pn) != 1 or driver.count(dn) != 1:
    raise ValueError('unexpected namespace')
compiler = amu / 'seed/bootstrap/aarch64-macos/amu-full-root.macho'
packager = amu / 'seed/bootstrap/aarch64-macos/kotoba-packager-root.macho'
compiler_sha = '2c551579c06a0228029bb06bae177e93126ecbbc37d636d693c471dbac8d1536'
packager_sha = 'e95284408f091c8979ef74ece57116a4df2250e61e42074da5dc95ca30264142'
sha = lambda b: hashlib.sha256(b).hexdigest()
if sha(compiler.read_bytes()) != compiler_sha or sha(packager.read_bytes()) != packager_sha:
    raise ValueError('compiler or packager pin mismatch')
id = 'a' * 64
def wire(keys):
    return ''.join(f'{len(key.encode("utf-8"))}:{key}' for key in keys)
def make_args(entries, keys, *, program=id, draft_program=id, base='old', persisted='old',
         state='state😀', snapshot='state😀', allow='1', raw='100', limit='35000'):
    return ['classify', raw, limit, allow, program, 'null' if persisted is None else 'string',
            persisted or '', snapshot, draft_program, 'null' if base is None else 'string',
            base or '', state, str(len(entries))] + [part for pair in entries for part in pair] + [str(len(keys)), wire(keys)]
good = make_args([('body', '雪😀')], ['body'])
def change(row, index, value):
    result = row.copy()
    result[index] = value
    return result
many_entries = [(f'key-{i}', 'v') for i in range(33)]
many_keys = [f'visible-{i}' for i in range(512)]
cases = [
    ('good', good, '2\n', 0),
    ('preview', make_args([('body', 'x')], ['body'], allow='0'), '1\n', 0),
    ('different-base', make_args([('body', 'x')], ['body'], persisted='different'), '1\n', 0),
    ('different-state', make_args([('body', 'x')], ['body'], snapshot='different'), '1\n', 0),
    ('missing-visible', make_args([('body', 'x')], ['other']), '1\n', 0),
    ('bad-hash', make_args([('body', 'x')], ['body'], draft_program='x'), '0\n', 0),
    ('invalid-allow', change(good, 3, 'x'), '', 2), ('truncated', good[:8], '', 2),
    ('bad-count', change(good, 12, '3'), '', 2), ('bad-number', change(good, 1, 'abc'), '', 2),
    ('duplicate', make_args([('body', 'x'), ('body', 'y')], ['body']), '0\n', 0),
    ('many-visible', make_args([('body', 'x')], ['body'] + many_keys[1:]), '2\n', 0),
    ('too-many-visible', make_args([('body', 'x')], ['body'] * 513), '', 2),
    ('empty-entries', make_args([], ['body']), '0\n', 0),
    ('worst-absent', make_args(many_entries, many_keys), '1\n', 0),
    ('all-33-visible', make_args(many_entries, [key for key, _ in many_entries]), '2\n', 0),
    ('tail-duplicate', make_args(many_entries[:32] + [many_entries[0]], [key for key, _ in many_entries]), '0\n', 0),
    ('unicode-key', make_args([('雪😀', 'v')], ['雪😀']), '2\n', 0),
    ('bad-frame', change(good, -1, '04:body'), '0\n', 0),
    ('frame-trailing', change(good, -1, '4:bodyx'), '0\n', 0),
    ('frame-truncated', change(good, -1, '5:body'), '0\n', 0),
    ('null-base', make_args([('body', 'x')], ['body'], base=None, persisted=None), '2\n', 0),
    ('max-value', make_args([('body', 'x' * 65536)], ['body']), '2\n', 0),
    ('over-value', make_args([('body', 'x' * 65537)], ['body']), '0\n', 0),
    ('max-key', make_args([('雪' * 42 + 'ab', 'v')], ['雪' * 42 + 'ab']), '2\n', 0),
    ('unicode-units', make_args([('body', '😀' * 32768)], ['body']), '2\n', 0),
]

gate = native.NativeGate(types.SimpleNamespace(compiler=compiler, compiler_sha256=compiler_sha,
    packager=packager, packager_sha256=packager_sha, output=out / 'native'))
if not gate.darwin:
    raise ValueError('macOS Arm native host required')
image = gate.build('abi', 'aiueos/draft_policy_browser.kotoba', {
    'aiueos/draft_policy.kotoba': source.encode(),
    'aiueos/draft_policy_browser.kotoba': driver.encode(),
})
for name, args, expected, status in cases:
    result = gate.run(name, image, expected=status, args=args, allow='37,38')
    if result.stdout.decode() != expected or result.stderr:
        raise ValueError((name, result.stdout, result.stderr))
# A policy mutant that ignores the persisted base must be detected by the
# mismatched-base case on both targets.
anchor = '(string=? base persisted)'
if source.count(anchor) != 1:
    raise ValueError('base-equality mutation anchor changed')
mutant = source.replace(anchor, 'true', 1)
mutant_image = gate.build('base-mutant', 'aiueos/draft_policy_browser.kotoba', {
    'aiueos/draft_policy.kotoba': mutant.encode(),
    'aiueos/draft_policy_browser.kotoba': driver.encode(),
})
mutant_result = gate.run('base-mutant-detected', mutant_image, args=cases[2][1], allow='37,38')
if mutant_result.stdout != b'2\n' or mutant_result.stderr:
    raise ValueError('base-equality mutant was not detected')
staged = source.replace(pn, '(ns aiueos.draft-policy-browser (:export [main]))', 1) + '\n' + driver.replace(dn, '', 1).replace('policy/classify-chunks', 'classify-chunks').replace('policy/units', 'units')
(out / 'abi.kotoba').write_text(staged)
mac.native_run(compiler, out, 'compile', 'abi.kotoba', '--target', 'wasm32-browser', '--output', 'abi.wasm')
mutant_staged = staged.replace(anchor, 'true', 1)
(out / 'mutant.kotoba').write_text(mutant_staged)
mac.native_run(compiler, out, 'compile', 'mutant.kotoba', '--target', 'wasm32-browser', '--output', 'mutant.wasm')
# Nearly one million units cannot be sent through the macOS exec argv limit;
# this case exercises the browser host interface independently.
browser_large = ('browser-near-million', make_args([(f'key-{i}', 'x' * 30000) for i in range(33)],
                 [f'key-{i}' for i in range(33)], raw='990900'), '2\n', 0)
version, results = browser.run_modules(str(chrome), out, [
    (name, out / 'abi.wasm', dict(fuel=0, allow=[37, 38], args=args))
    for name, args, _, _ in cases + [browser_large]
] + [('base-mutant', out / 'mutant.wasm', dict(fuel=0, allow=[37, 38], args=cases[2][1]))])
for name, _, expected, status in cases + [browser_large, ('base-mutant', [], '2\n', 0)]:
    row = results[name]
    if (row.get('exit') != 0 or row.get('wasmTrap') is not None or row.get('output') != expected
        or not re.search(rf':status :ok :result {status}(?:\s|\}})', row.get('report') or '')):
        raise ValueError((name, row))
receipt = dict(status='PASS_DRAFT_POLICY_ABI_NATIVE_BROWSER_SYNTHETIC', browser=version,
    compilerSHA256=compiler_sha, packagerSHA256=packager_sha, sourceSHA256=sha(source.encode()),
    driverSHA256=sha(driver.encode()), stagedSHA256=sha(staged.encode()),
    wasmSHA256=sha((out / 'abi.wasm').read_bytes()), nativeObservations=gate.observations, results=results,
    scope='typed transport and policy only; JSON/surrogate adapter, app integration, OS/QEMU and release remain open')
(out / 'evidence.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(receipt['status'], flush=True)
