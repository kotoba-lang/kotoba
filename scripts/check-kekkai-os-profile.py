#!/usr/bin/env python3
"""Try the shared Kekkai closure under the pinned native OS target.

Stage immutable bytes from a previously built kernel lock, retain its actual
ValueRuntime root, and let Amu discover/check/lower the graph. No source parser,
compiler substitution, guest execution, physical deployment, or identity use.
A compiler refusal is recorded and returns 2; it is not a passing OS gate.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--compiler-sha256', required=True)
    parser.add_argument('--source-stage', type=Path, required=True)
    parser.add_argument('--source-lock-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert platform.system() == 'Darwin' and platform.machine() == 'arm64'
    compiler = args.compiler.resolve(strict=True)
    assert sha(compiler.read_bytes()) == args.compiler_sha256
    baseline = args.source_stage.resolve(strict=True)
    lock = (baseline / 'kernel.ksl').read_bytes()
    assert sha(lock) == args.source_lock_sha256
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    stage = out / 'source'
    stage.mkdir()
    roots = []
    entry = None
    assert lock.startswith(b'KSL1\n')
    for line in lock.decode().splitlines()[1:]:
        kind, value = line.split(' ', 1)
        if kind == 'entry':
            entry = value
        elif kind == 'root':
            roots.append(value)
        elif kind == 'file':
            expected, virtual = value.split(' ', 1)
            path = Path(virtual)
            assert path.is_absolute() and '..' not in path.parts
            data = (baseline / virtual.lstrip('/')).read_bytes()
            assert sha(data) == expected, virtual
            target = stage / virtual.lstrip('/')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        else:
            raise ValueError('unknown lock record')
    assert entry == '/os/aiueos/native/usb-update-test-entry.kotoba'
    data = (stage / entry.lstrip('/')).read_text()
    for before, after in [
        ('aiueos.native.usb-update-test-entry', 'aiueos.native.kekkai-integration-probe'),
        ('[aiueos.native.usb-update-probe :as fixture]', '[noise.datagram :as datagram]'),
        ('(fixture/run)', '(datagram/advice (vector-alloc 2118) 100)')
    ]:
        assert data.count(before) == 1, before
        data = data.replace(before, after)
    entry = '/os/aiueos/native/kekkai-integration-probe.kotoba'
    (stage / entry.lstrip('/')).write_text(data)
    spec = importlib.util.spec_from_file_location('pq', ROOT / 'scripts/check-pq-native.py')
    pq = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pq)
    for virtual, source in pq.MODULE_GATES['datagram']['files'].items():
        if virtual == 'noise/datagram_gate.kotoba':
            continue
        target = stage / 'kekkai' / virtual
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / source).read_bytes())
    roots.append('/kekkai')
    flags = [part for root in roots for part in ('--source-path', root)]
    calls = []
    # This dedicated observer process owns FD3; existing services are untouched.
    scope = os.open(stage, os.O_RDONLY | os.O_DIRECTORY)
    if scope != 3:
        os.dup2(scope, 3)
        os.close(scope)

    def run(label, argv):
        p = subprocess.run([str(compiler), *argv], cwd=stage,
                           env={'PATH': '/nonexistent'}, pass_fds=(3,),
                           capture_output=True, timeout=120)
        for suffix, raw in [('stdout', p.stdout), ('stderr', p.stderr)]:
            (out / (label + '.' + suffix)).write_bytes(raw)
        calls.append(dict(label=label, argv=argv, exit=p.returncode,
                          stdout=p.stdout.decode(errors='replace'),
                          stderr=p.stderr.decode(errors='replace')))
        return p

    p = run('modules', ['modules', entry, *flags])
    sources = {}
    if p.returncode == 0:
        for line in p.stdout.decode().splitlines():
            namespace, virtual = line.split(' ', 1)
            path = Path(virtual)
            assert namespace and path.is_absolute() and '..' not in path.parts
            assert virtual not in sources
            sources[virtual] = sha((stage / virtual.lstrip('/')).read_bytes())
        new_lock = ('KSL1\nentry ' + entry + '\n'
                    + ''.join('root ' + r + '\n' for r in roots)
                    + ''.join('file ' + digest + ' ' + path + '\n'
                              for path, digest in sorted(sources.items())))
        (stage / 'probe.ksl').write_text(new_lock)
        p = run('compile', ['compile', entry, '--target', 'x86_64-aiueos-kernel-v3',
                           '--artifact', 'image', '--output', 'PROBE.ELF',
                           '--fuel', '9007199254740991', *flags, '--source-lock', 'probe.ksl',
                           '--source-lock-sha256', sha(new_lock.encode())])
    state = 'COMPILED_NOT_BOOTED' if p.returncode == 0 else 'NATIVE_COMPILER_REFUSAL'
    (out / 'receipt.json').write_text(json.dumps(dict(
        schema='kekkai.os-profile-probe.v1', state=state,
        compilerSHA256=args.compiler_sha256, baselineLockSHA256=sha(lock),
        sourceGraph=sources, calls=calls, physicalDeployment=False,
        bootQualified=False), indent=2) + '\n')
    print(state)
    print(p.stderr.decode(), end='')
    return 0 if p.returncode == 0 else 2


if __name__ == '__main__':
    raise SystemExit(main())
