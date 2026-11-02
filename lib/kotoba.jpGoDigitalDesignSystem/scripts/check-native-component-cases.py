#!/usr/bin/env python3
"""Observe native heading and table decisions, not complete DDS parity."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / 'kotoba/components.kotoba'
TABLE = ROOT / 'kotoba/table.kotoba'
BUTTON = ROOT / 'kotoba/button.kotoba'
TEST = ROOT / 'test/native/dds_components_test.kotoba'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--amu', type=Path, required=True)
    ap.add_argument('--amu-sha256', required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    if (platform.system(), platform.machine()) != ('Darwin', 'arm64'):
        raise ValueError('requires native macOS ARM64')
    amu = a.amu.resolve(strict=True)
    if sha(amu) != a.amu_sha256:
        raise ValueError('Amu digest mismatch')
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    tracked = [amu, COMPONENTS, TABLE, BUTTON, TEST, Path(__file__).resolve()]
    pins = {str(p): sha(p) for p in tracked}
    env = {'PATH': '/nonexistent', 'LANG': 'C'}

    def run(name, table, expected, components=COMPONENTS, button=BUTTON):
        modules = {'components': components, 'table': table, 'button': button, 'dds-components-test': TEST}
        lock = out / (name + '.ksl')
        lock.write_text('KSL2\nentry ' + str(TEST.resolve()) + '\n' +
                        ''.join('module ' + n + ' ' + str(p.resolve()) + '\n' for n, p in sorted(modules.items())) +
                        ''.join('file ' + sha(p) + ' ' + str(p.resolve()) + '\n' for p in sorted(modules.values())))
        binary = out / name
        build = subprocess.run([str(amu), 'compile', str(TEST), '--source-lock', str(lock), '-o', str(binary)],
                               cwd=ROOT, env=env, capture_output=True, timeout=180)
        if build.returncode or build.stderr or not binary.is_file():
            raise RuntimeError(('native compile failed', name, build.returncode, build.stderr[-500:]))
        result = subprocess.run([str(binary)], cwd=ROOT, env=env, capture_output=True, timeout=180)
        if result.returncode or result.stderr or result.stdout != expected:
            raise RuntimeError(('native verdict mismatch', name, result.returncode, result.stdout, result.stderr[-500:]))
        return {'binarySha256': sha(binary), 'lockSha256': sha(lock)}

    positive = run('dds', TABLE, b'42\n')
    text = TABLE.read_text()
    needle = '(= (get cell :index) 0)'
    if text.count(needle) != 1:
        raise ValueError('mutation anchor changed')
    mutant = out / 'mutant-table.kotoba'
    mutant.write_text(text.replace(needle, '(= (get cell :index) 1)'))
    negative = run('dds-negative', mutant, b'7\n')
    component_text = COMPONENTS.read_text()
    component_needle = '"dds-ext-container"'
    if component_text.count(component_needle) != 1:
        raise ValueError('container mutation anchor changed')
    component_mutant = out / 'mutant-components.kotoba'
    component_mutant.write_text(component_text.replace(component_needle, '"wrong-container"'))
    negative_container = run('dds-container-negative', TABLE, b'7\n', component_mutant)
    button_text = BUTTON.read_text()
    button_needle = '(document-string "dads-button")'
    if button_text.count(button_needle) != 1:
        raise ValueError('button mutation anchor changed')
    button_mutant = out / 'mutant-button.kotoba'
    button_mutant.write_text(button_text.replace(button_needle, '(document-string "wrong-button")'))
    negative_button = run('dds-button-negative', TABLE, b'7\n', button=button_mutant)
    if any(sha(p) != pins[str(p)] for p in tracked):
        raise ValueError('source or compiler changed during gate')
    result = {'status': 'PASS_NATIVE_DDS_COMPONENT_CASES', 'inputs': pins,
              'positive': positive, 'rowHeaderMutationRejected': negative,
              'containerMutationRejected': negative_container, 'buttonMutationRejected': negative_button,
              'fullComponentParity': False, 'siteGenerated': False}
    (out / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'])


if __name__ == '__main__':
    main()
