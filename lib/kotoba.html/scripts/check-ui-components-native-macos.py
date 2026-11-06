#!/usr/bin/env python3
"""Observe the bounded shared UI components (JUN-856) rendered with a native Amu CLI.

The fixture supplies expected output; the observer stages no legacy runtime.
It is not a whole Hiccup parity suite, page builder, or release gate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

OWNER = Path(__file__).resolve().parent.parent
CORE = OWNER / 'kotoba/html_core.kotoba'
HICCUP = OWNER / 'kotoba/html_hiccup.kotoba'
TEST = OWNER / 'test/native/ui_components_test.kotoba'
UI = OWNER / 'kotoba/ui_components.kotoba'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--amu', type=Path, required=True)
    ap.add_argument('--amu-sha256', required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if (platform.system(), platform.machine()) != ('Darwin', 'arm64'):
        raise ValueError('requires native macOS ARM64')
    amu = args.amu.resolve(strict=True)
    if sha(amu) != args.amu_sha256:
        raise ValueError('Amu digest mismatch')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    tracked = [amu, CORE, HICCUP, UI, TEST, Path(__file__).resolve()]
    pins = {str(p): sha(p) for p in tracked}
    env = {'PATH': '/nonexistent', 'LANG': 'C'}

    def run(name, source, expected):
        modules = {'ui-components-test': TEST, 'html-core': CORE, 'html-hiccup': HICCUP, 'ui-components': source}
        lock = out / (name + '.ksl')
        lock.write_text('KSL2\nentry ' + str(TEST.resolve()) + '\n' +
                        ''.join('module ' + n + ' ' + str(p.resolve()) + '\n' for n, p in sorted(modules.items())) +
                        ''.join('file ' + sha(p) + ' ' + str(p.resolve()) + '\n' for p in sorted(modules.values())))
        binary = out / name
        build = subprocess.run([str(amu), 'compile', str(TEST), '--source-lock', str(lock), '-o', str(binary)],
                               cwd=OWNER, env=env, capture_output=True, timeout=180)
        if build.returncode or build.stderr or not binary.is_file():
            raise RuntimeError(('native compile failed', name, build.returncode, build.stderr[-500:]))
        result = subprocess.run([str(binary)], cwd=OWNER, env=env, capture_output=True, timeout=180)
        if result.returncode or result.stderr or result.stdout != expected:
            raise RuntimeError(('native verdict mismatch', name, result.returncode, result.stdout, result.stderr[-500:]))
        return {'binarySha256': sha(binary), 'lockSha256': sha(lock)}

    positive = run('components', UI, b'42\n')
    text = UI.read_text()
    needle = ':data-action (str action)'
    if text.count(needle) != 1:
        raise ValueError('mutation anchor changed')
    mutant = out / 'wrong-action.kotoba'
    mutant.write_text(text.replace(needle, ':data-action (str "x")'))
    negative = run('wrong-action', mutant, b'7\n')
    if any(sha(p) != pins[str(p)] for p in tracked):
        raise ValueError('source or compiler changed during gate')
    receipt = {'status': 'PASS_NATIVE_UI_COMPONENTS', 'inputs': pins,
               'positive': positive, 'wrongActionMutationRejected': negative,
               'fullHiccupParity': False, 'siteGenerated': False, 'publicationQualified': False}
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(receipt['status'])


if __name__ == '__main__':
    main()
