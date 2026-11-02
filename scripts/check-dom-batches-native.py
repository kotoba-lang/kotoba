#!/usr/bin/env python3
"""Stage exact DOM source locks and observe Amu-built native test verdicts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(args):
    root = args.root.resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    compiler = args.compiler.resolve()
    source = root / 'src'
    tests = root / 'test/native'
    roots = [source, tests]
    env = dict(PATH='/nonexistent', KEXE_STACK_BYTES='8388608',
               KEXE_CAP_RESOURCES_35=':'.join(map(str, [out, *roots])))
    results = []

    def run(name, command, extra=None):
        proc = subprocess.run(list(map(str, command)), cwd=out,
                              env=dict(env, **(extra or {})), capture_output=True, timeout=1800)
        (out / (name + '.stdout')).write_bytes(proc.stdout)
        (out / (name + '.stderr')).write_bytes(proc.stderr)
        assert proc.returncode == 0 and not proc.stderr, (name, proc.returncode, proc.stderr[-1000:])
        return proc.stdout

    for case in ('dom', 'dom_batches', 'dom_overflow', 'dom_replay'):
        entry = tests / (case + '.kotoba')
        flags = [part for path in roots for part in ('--source-path', str(path))]
        lines = run(case + '-modules', [compiler, 'modules', entry, *flags]).decode().splitlines()
        files = [Path(line.split(' ', 1)[1]) for line in lines]
        assert entry in files and len(files) == len(set(files))
        assert all(any(p.is_relative_to(root) for root in roots) for p in files)
        lock = out / (case + '.ksl')
        lock.write_text('KSL1\nentry ' + str(entry) + '\n' +
                        ''.join('root ' + str(p) + '\n' for p in roots) +
                        ''.join('file ' + digest(p) + ' ' + str(p) + '\n' for p in sorted(files)))
        flags += ['--source-lock', str(lock), '--source-lock-sha256', digest(lock)]
        run(case + '-check', [compiler, 'check', entry, *flags])
        artifact = out / (case + ('.kseed' if args.target == 'arm64' else '.kx64'))
        cmd = [compiler, 'compile', entry, '--target',
               'aarch64-macos' if args.target == 'arm64' else 'x86_64-linux', '--output', artifact]
        if args.target == 'x86_64':
            cmd += ['--format', 'kx64-v1']
        run(case + '-compile', cmd + flags)
        if args.target == 'arm64':
            image = out / (case + '.elf')
            run(case + '-pack', [compiler, 'compile', args.runner_source, '--target', 'aarch64-linux',
                                 '--output', image, '--format', 'packed', '--payload', artifact])
            image.chmod(0o755)
            command = [image]
        else:
            header, body = artifact.read_bytes().split(b'\n\n', 1)
            m = re.fullmatch(rb'KX64V1 x86_64-linux sysv-ctx-v11 ([0-9]+) 0', header)
            assert m and int(m[1]) == len(body) and body[0] == 0xe9
            image = out / (case + '.bin')
            image.write_bytes(body)
            command = [args.runner, image, 0, 0, 'x86_64', '-']
        stdout = run(case + '-execute', command, {'KEXE_STRUCTURED_REPORT': '1', 'KEXE_ALLOW': '-'})
        m = re.search(rb':result (-?[0-9]+)', stdout)
        assert m and int(m[1]) == 0, (case, stdout)
        results.append(dict(case=case, artifact=digest(artifact), lock=digest(lock),
                            sources={str(p): digest(p) for p in files}))
    (out / 'dom-batches.json').write_text(json.dumps(dict(target=args.target, compiler=digest(compiler),
                                                           cases=results), indent=2) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--compiler', type=Path, required=True)
    p.add_argument('--target', choices=('arm64', 'x86_64'), required=True)
    p.add_argument('--runner', type=Path)
    p.add_argument('--runner-source', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    assert a.runner_source if a.target == 'arm64' else a.runner
    main(a)
