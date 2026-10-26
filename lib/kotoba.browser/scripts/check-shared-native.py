#!/usr/bin/env python3
"""Compile and execute actual shared modules on a native Linux kernel.

Python stages source locks and observes processes. Amu emits every artifact;
the checked-in Kotoba fixtures own the verdict. No hosted compiler or loader.
The CSSOM/surface graph and a kernel desktop are separate, unqualified gates.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import time
from pathlib import Path


def pin(path):
    data = Path(path).read_bytes()
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main(a):
    machine = platform.machine()
    assert platform.system() == 'Linux'
    assert machine in ({'aarch64', 'arm64'} if a.target == 'arm64' else {'x86_64', 'AMD64'})
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    roots = [a.browser.resolve(), a.dom.resolve(), a.text.resolve()]
    calls, cases = [], []
    compiler = a.compiler.resolve()
    scope = ':'.join(map(str, [out, *roots]))
    env = dict(PATH='/nonexistent', KEXE_STACK_BYTES='8388608', KEXE_CAP_RESOURCES_35=scope)
    runner_source = out / 'runner.kotoba'
    if a.target == 'arm64':
        runner_source.write_bytes(a.runner_source.read_bytes())

    def run(name, args, custom=None, ok=True):
        start = time.monotonic()
        result = subprocess.run(list(map(str, args)), env=env if custom is None else custom,
                                cwd=out, capture_output=True, timeout=900)
        (out / (name + '.stdout')).write_bytes(result.stdout)
        (out / (name + '.stderr')).write_bytes(result.stderr)
        calls.append(dict(name=name, argv=list(map(str, args)), exit=result.returncode,
                          seconds=round(time.monotonic() - start, 3)))
        (out / 'calls.json').write_text(json.dumps(calls, indent=2) + '\n')
        print(name, result.returncode, result.stderr.decode(errors='replace')[:500], flush=True)
        if ok:
            assert result.returncode == 0 and not result.stderr, (name, result.returncode, result.stderr[-1000:])
        return result

    for name, owner, filename in [('text', a.text, 'text.kotoba'),
                                   ('dom', a.dom, 'dom.kotoba'),
                                   ('text-edit', a.browser, 'text-edit.kotoba')]:
        if a.case and name != a.case:
            continue
        entry = (owner / 'test/native' / filename).resolve()
        source_roots = [root / 'src' for root in roots] + [entry.parent]
        flags = [part for root in source_roots for part in ['--source-path', str(root)]]
        discovered = run(name + '-modules', [compiler, 'modules', entry, *flags])
        files = [Path(line.split(' ', 1)[1]) for line in discovered.stdout.decode().splitlines()]
        assert entry in files and len(files) == len(set(files))
        assert all(any(path.is_relative_to(root) for root in source_roots) for path in files)
        lock = out / (name + '.ksl')
        lock.write_text('KSL1\nentry ' + str(entry) + '\n' +
                        ''.join('root ' + str(root) + '\n' for root in source_roots) +
                        ''.join('file ' + pin(path)['sha256'] + ' ' + str(path) + '\n' for path in sorted(files)))
        flags += ['--source-lock', str(lock), '--source-lock-sha256', pin(lock)['sha256']]
        run(name + '-check', [compiler, 'check', entry, *flags])
        artifact = out / (name + ('.kseed' if a.target == 'arm64' else '.kx64'))
        args = [compiler, 'compile', entry, '--target',
                'aarch64-macos' if a.target == 'arm64' else 'x86_64-linux', '--output', artifact]
        if a.target == 'x86_64':
            args += ['--format', 'kx64-v1']
        run(name + '-compile', args + flags)
        if a.target == 'arm64':
            image = out / (name + '.elf')
            run(name + '-pack', [compiler, 'compile', runner_source, '--target', 'aarch64-linux',
                                 '--output', image, '--format', 'packed', '--payload', artifact])
            image.chmod(0o755)
            invoke = [image]
        else:
            header, body = artifact.read_bytes().split(b'\n\n', 1)
            match = re.fullmatch(rb'KX64V1 x86_64-linux sysv-ctx-v11 ([0-9]+) 0', header)
            assert match and int(match[1]) == len(body) and body[0] == 0xe9
            image = out / (name + '.bin')
            image.write_bytes(body)  # Unchanged compiler-emitted bytes, never an image writer.
            invoke = [a.runner.resolve(), image, 0, 0, 'x86_64', '-']
        result = run(name + '-execute', invoke, dict(env, KEXE_STRUCTURED_REPORT='1', KEXE_ALLOW='-'))
        match = re.search(rb':result (-?[0-9]+)', result.stdout)
        assert match and int(match[1]) == 0, (name, result.stdout)
        cases.append(dict(name=name, verdict=0, artifact=pin(artifact), executable=pin(image),
                          lock=pin(lock), sources={str(path): pin(path) for path in files}))
        (out / 'shared-native.json').write_text(json.dumps(dict(status='PASS_SHARED_COMPONENTS_NATIVE',
            target=a.target, host=[platform.system(), machine, platform.release()], compiler=pin(compiler),
            cases=cases, complete=len(cases) == 3, emulation=False, kernelDesktopQualified=False,
            cssomQualified=False, itonamiDappsQualified=False, restorationQualified=False), indent=2) + '\n')
    print('PASS_SHARED_COMPONENTS_NATIVE', a.target, len(cases), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler', type=Path, required=True)
    p.add_argument('--target', choices=['arm64', 'x86_64'], required=True)
    p.add_argument('--runner', type=Path)
    p.add_argument('--runner-source', type=Path)
    p.add_argument('--browser', type=Path, required=True)
    p.add_argument('--dom', type=Path, required=True)
    p.add_argument('--text', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--case', choices=['text', 'dom', 'text-edit'])
    a = p.parse_args()
    assert a.runner_source if a.target == 'arm64' else a.runner
    main(a)
