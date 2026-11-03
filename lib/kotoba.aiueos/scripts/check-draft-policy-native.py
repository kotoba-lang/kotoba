#!/usr/bin/env python3
"""Exercise the shared recovery policy with synthetic native inputs.

Usage: check-draft-policy-native.py AMU_DIR NEW_OUTPUT_DIR
This checks macOS Arm only; it does not claim browser or OS integration.
"""
import hashlib
import importlib.util
import sys
import types
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit(__doc__)
amu, out = (Path(x).resolve() for x in sys.argv[1:])
root = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('native_gate', root / 'lib/kotoba.hata/scripts/native_gate.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
gate = native.NativeGate(types.SimpleNamespace(
    compiler=amu / 'seed/bootstrap/aarch64-macos/amu-full-root.macho',
    compiler_sha256='2c551579c06a0228029bb06bae177e93126ecbbc37d636d693c471dbac8d1536',
    packager=amu / 'seed/bootstrap/aarch64-macos/kotoba-packager-root.macho',
    packager_sha256='e95284408f091c8979ef74ece57116a4df2250e61e42074da5dc95ca30264142', output=out))
if not gate.darwin:
    raise ValueError('macOS Arm native host required')
sources = {
    'aiueos/draft_policy.kotoba': (root / 'lib/kotoba.aiueos/os/aiueos/kotoba/aiueos/draft_policy.kotoba').read_bytes(),
    'aiueos/draft_policy_test.kotoba': (root / 'lib/kotoba.aiueos/test/aiueos/draft_policy_test.kotoba').read_bytes(),
}
image = gate.build('policy', 'aiueos/draft_policy_test.kotoba', sources)
gate.run('policy-cases', image)
needle = b'(document-equal? base persisted)'
if sources['aiueos/draft_policy.kotoba'].count(needle) != 1:
    raise ValueError('mutation anchor changed')
mutant = dict(sources)
mutant['aiueos/draft_policy.kotoba'] = mutant['aiueos/draft_policy.kotoba'].replace(needle, b'true', 1)
broken = gate.build('mutant', 'aiueos/draft_policy_test.kotoba', mutant)
gate.run('base-mismatch-detected', broken, expected=1)
gate.finish('PASS_DRAFT_POLICY_NATIVE_SYNTHETIC',
            observerSHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            scope='synthetic macOS Arm; no browser integration, JS surrogate adapter, OS/QEMU or release')
