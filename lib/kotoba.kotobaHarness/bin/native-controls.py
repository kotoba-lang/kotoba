#!/usr/bin/env python3
"""Stage fixed Kotoba controls; only Amu selfhost compiles and Chrome runs them.

This is a test orchestrator, not a replacement search engine or EDN evaluator.
No model API, credential lookup, source generation or legacy compiler selection.
"""
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'test/native/manifest.json'
FUEL = 1_000_000


class Blocked(Exception):
    pass


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned(path, pin):
    if not path.is_file() or path.stat().st_size != pin['bytes'] or sha(path) != pin['sha256']:
        raise Blocked(f'native artifact pin mismatch: {path.name}')


def environment():
    obsolete = [key for key in ('NBB', 'KOTOBA_BIN', 'KOTOBA_BROWSER_HOST') if os.environ.get(key)]
    if obsolete:
        raise Blocked('retired configuration: ' + ', '.join(obsolete))
    amu = Path(os.environ.get('KOTOBA_AMU_ROOT', ROOT.parent / 'amu')).resolve()
    if not (amu / 'seed/bootstrap/aarch64-linux-static-root.json').is_file():
        raise Blocked('set KOTOBA_AMU_ROOT to an Amu checkout with native artifact pins')
    system, machine = platform.system(), platform.machine().lower()
    if machine in ('arm64', 'aarch64') and system in ('Darwin', 'Linux'):
        compiler = amu / 'seed/bootstrap/aarch64-linux-static-root.elf'
        pinfile = amu / 'seed/bootstrap/aarch64-linux-static-root.json'
        container = system == 'Darwin'
    elif system == 'Linux' and machine in ('x86_64', 'amd64'):
        compiler, pinfile, container = amu / 'bin/amu', amu / 'native-product.json', False
    else:
        raise Blocked('unsupported native host; no emulation or hosted fallback')
    pin = json.loads(pinfile.read_text())['image']
    pinned(compiler, pin)
    if container and not shutil.which('podman'):
        raise Blocked('local ARM64 Podman VM is required; no compiler fallback')
    if container:
        vm = subprocess.run(['podman', 'machine', 'ssh', 'uname', '-m'], capture_output=True, text=True, timeout=20)
        if vm.returncode or vm.stdout.strip() not in ('aarch64', 'arm64'):
            raise Blocked('Podman VM must already be running native ARM64 Linux')
    hostfile = amu / 'scripts/seed/check-wasm32-browser.py'
    if not hostfile.is_file():
        raise Blocked('current Amu static browser test host is missing')
    spec = importlib.util.spec_from_file_location('amu_browser', hostfile)
    host = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(host)
    browser = host.find_browser(os.environ.get('KOTOBA_BROWSER') or
                                ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' if system == 'Darwin' else None))
    if not browser:
        raise Blocked('Chrome/Chromium is required; no Node or legacy Wasm host fallback')
    return dict(compiler=compiler, pin=pin, container=container, target='aarch64-linux' if machine in ('arm64', 'aarch64') else 'x86_64-linux', host=host, browser=browser,
                host_sha256=sha(amu / 'runtime/wasm32-browser-static-host.js'))


def command(cfg, directory, args, guest=False):
    if cfg['container']:
        return ['podman', 'run', '--rm', '--pull=never', '--network=none', '--read-only',
                '--cap-drop=all', '--security-opt=no-new-privileges',
                '-v', f'{cfg["compiler"]}:/compiler:ro', '-v', f'{directory}:/work',
                '-e', 'KEXE_ALLOW=35,37,38,39', '-e', 'KEXE_CAP_RESOURCES_35=/work', '-e', 'KEXE_STACK_BYTES=8388608',
                '-e', 'KEXE_CPU_SECONDS=30', '-e', 'KEXE_WALL_SECONDS=40',
                '--entrypoint', '/work/verdict.elf' if guest else '/compiler',
                os.environ.get('KOTOBA_PODMAN_IMAGE', 'docker.io/library/alpine:3'), *args]
    return [str(directory / 'verdict.elf') if guest else str(cfg['compiler']), *args]


def run_control(cfg, name, method, entry, out):
    fixture = ROOT / entry['source']
    if sha(fixture) != entry['sha256']:
        raise Blocked('control fixture pin mismatch')
    directory = Path(tempfile.mkdtemp(prefix=f'{name}-{method}-', dir=out))
    source, wasm = directory / 'verify.kotoba', directory / 'verify.wasm'
    shutil.copyfile(fixture, source)
    shutil.copyfile(ROOT / 'src/kotoba_harness/control_verdict.kotoba', directory / 'verdict.kotoba')
    prefix = '/work' if cfg['container'] else str(directory)
    receipt = dict(format='kotoba-harness.native-control/v1', project=name, method=method,
                   compiler=cfg['pin'], source_sha256=entry['sha256'], fuel=FUEL, commands=[])
    try:
        for args in [['check', prefix + '/verify.kotoba'],
                     ['compile', prefix + '/verify.kotoba', '--target', 'wasm32-browser', '--output', prefix + '/verify.wasm'],
                     ['compile', prefix + '/verdict.kotoba', '--target', cfg['target'], '--output', prefix + '/verdict.elf', '--format', 'static']]:
            argv = command(cfg, directory, args)
            env = dict({k:v for k,v in os.environ.items() if not k.startswith('KEXE_')}, KEXE_ALLOW='35,37,38,39', KEXE_CAP_RESOURCES_35=str(directory), KEXE_STACK_BYTES='8388608',
                       KEXE_CPU_SECONDS='30', KEXE_WALL_SECONDS='40')
            result = subprocess.run(argv, capture_output=True, text=True, timeout=50, env=env)
            receipt['commands'].append(dict(args=args, exit=result.returncode, stdout=result.stdout, stderr=result.stderr))
            if result.returncode:
                raise Blocked('native check/compile failed; see receipt (no fallback attempted)')
        (directory / 'verdict.elf').chmod(0o755)
        selftest = subprocess.run(command(cfg, directory, ['selftest'], guest=True),
                                  capture_output=True, text=True, timeout=50, env=env)
        receipt['native_selftest'] = dict(exit=selftest.returncode, stdout=selftest.stdout, stderr=selftest.stderr)
        if selftest.returncode:
            raise Blocked('native verdict selftest failed; no browser result accepted')
        version, lines = cfg['host'].run_modules(cfg['browser'], directory / 'browser',
                                                [(name, wasm, dict(fuel=FUEL))], timeout=45)
        line = lines[name]
        observation = cfg['host'].observe(line)
        receipt.update(browser=version, observation=observation, raw=line, wasm_sha256=sha(wasm),
                       browser_host_sha256=cfg['host_sha256'])
        verdict_args = [name, method, str(observation['status']), str(observation['exit']),
                        str(observation['result']), line.get('wasmTrap') or '']
        verdict = subprocess.run(command(cfg, directory, verdict_args, guest=True),
                                 capture_output=True, text=True, timeout=50, env=env)
        receipt.update(status=verdict.stdout.strip() or 'blocked', failures=observation['result'],
                       expected_failures=entry['failures'], control_passed=verdict.returncode == 0,
                       verdict=dict(exit=verdict.returncode, stdout=verdict.stdout, stderr=verdict.stderr,
                                    source_sha256=sha(directory / 'verdict.kotoba'), image_sha256=sha(directory / 'verdict.elf')))
    except (Blocked, OSError, subprocess.TimeoutExpired, RuntimeError, TimeoutError) as error:
        receipt.update(status='blocked', error=str(error), control_passed=False)
    (directory / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(project=name, method=method, status=receipt['status'], failures=receipt.get('failures'),
                          control_passed=receipt['control_passed'], receipt=str(directory / 'receipt.json'))), flush=True)
    return receipt


def main(args):
    manifest = json.loads(MANIFEST.read_text())['cases']
    if args and args[0] == '--all' and len(args) <= 2:
        selected = [(name, method, case['controls'][method]) for name, case in manifest.items() for method in ('known', 'wrong')]
        out = Path(args[1] if len(args) > 1 else ROOT / 'runs/native-controls').resolve()
        gate = True
    else:
        if len(args) not in (2, 3) or args[1] not in ('known', 'wrong'):
            raise Blocked('only pinned known/wrong controls are available; validate/search/Jev/bench require the full native port')
        project, method = Path(args[0]).resolve(), args[1]
        if not project.is_file():
            raise Blocked('project file is missing')
        digest = sha(project)
        selected = [(name, method, case['controls'][method]) for name, case in manifest.items() if digest in case['projects'].values()]
        if len(selected) != 1:
            raise Blocked('project is not a pinned control; arbitrary EDN/search is not implemented natively')
        out = Path(args[2] if len(args) > 2 else ROOT / 'runs').resolve()
        gate = False
    cfg = environment()
    out.mkdir(parents=True, exist_ok=True)
    receipts = [run_control(cfg, name, method, entry, out) for name, method, entry in selected]
    if any(r['status'] == 'blocked' for r in receipts):
        return 78
    return 0 if all(r['control_passed'] if gate else r['status'] == 'verified' for r in receipts) else 1


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except (Blocked, OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps(dict(status='blocked', error=str(error))), file=sys.stderr)
        sys.exit(78)
