#!/usr/bin/env python3
"""Build the complete runtime fixture with an explicit native compiler/loader.

All compiler source roots are explicit. No dependency substitution, hosted
compiler fallback or prebuilt module reuse. The report pins the actual tools
and every source. This qualifies the fixture, not a compiler self-rebuild.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-image', type=Path, required=True)
    parser.add_argument('--loader', type=Path, required=True)
    parser.add_argument('--source-path', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    fixture = root / 'test/fixtures/native-runtime-values.kotoba'
    roots = [root / 'src', root / 'test/fixtures', root / 'vendor/grammar/src',
             *[p.resolve() for p in args.source_path]]
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    objects = out / 'objects'
    objects.mkdir()
    tools = {str(p.resolve()): digest(p) for p in [args.compiler_image, args.loader]}
    env = {k: v for k, v in os.environ.items() if not k.startswith('KEXE_')}
    env.update(KEXE_COMMAND='1', KEXE_FUEL='500000000', KEXE_PAIRS='16777216',
               KEXE_VECTORS='4194304', KEXE_VECTOR_ITEMS='134217728',
               KEXE_STRING_POOL='268435456', KEXE_CPU_SECONDS='300',
               KEXE_WALL_SECONDS='300', TMPDIR=str(out),
               KEXE_CAP_RESOURCES_35=':'.join(map(str, [out, *roots])))
    prefix = [args.loader, args.compiler_image, '0', '0', 'aarch64',
              '3,35,37,38,39', '--']

    def run(name, command, environment=env):
        result = subprocess.run(list(map(str, command)), cwd=out, env=environment,
                                capture_output=True, text=True, timeout=300)
        (out / (name + '.stdout')).write_text(result.stdout)
        (out / (name + '.stderr')).write_text(result.stderr)
        if result.returncode:
            raise RuntimeError(f'{name}: exit {result.returncode}: {result.stderr[:1200]}')
        if any(digest(Path(p)) != sha for p, sha in tools.items()):
            raise RuntimeError('compiler/loader changed during verification')
        return result.stdout

    command = [*prefix, 'modules', fixture]
    for source in roots:
        command += ['--source-path', source]
    modules = []
    for line in run('modules', command + ['--unpinned']).splitlines():
        namespace, source = line.split(' ', 1)
        modules.append((namespace, Path(source)))
    if not modules or modules[-1][1] != fixture:
        raise RuntimeError('module closure does not end at the fixture')
    sources = {str(p): digest(p) for _, p in modules}
    for index, (namespace, source) in enumerate(modules):
        command = [*prefix, 'compile', source, '--emit-module']
        if source == fixture:
            command += ['--entry']
        command += ['--object-dir', objects, '--output', objects / (namespace + '.kso')]
        run(f'compile-{index:02}', command)
        print(f'compiled {namespace}', flush=True)
    container, image = out / 'runtime-values.kseed', out / 'runtime-values.bin'
    run('link', [*prefix, 'link', objects / (modules[-1][0] + '.kso'),
                 '--object-dir', objects, '--output', container])
    text = run('extract', [*prefix, 'extract-native', container, '--symbol', 'main',
                           '--output', image])
    match = re.search(r':offset\s+(\d+)', text)
    if not match:
        raise RuntimeError('extract omitted entry offset')
    execution = {k: v for k, v in env.items() if not k.startswith('KEXE_')}
    execution.update(KEXE_STRUCTURED_REPORT='1', KEXE_ARENA_USE='1',
                     KEXE_FUEL='5000000', KEXE_PAIRS='1048576',
                     KEXE_VECTORS='262144', KEXE_VECTOR_ITEMS='4194304',
                     KEXE_STRING_POOL='16777216', KEXE_CPU_SECONDS='30',
                     KEXE_WALL_SECONDS='30')
    text = run('execute', [args.loader, image, match.group(1), '0', 'aarch64', '-'], execution)
    if not re.search(r':status :ok :result 127\b', text):
        raise RuntimeError(f'runtime fixture did not pass all seven checks: {text[:1200]}')
    if any(digest(Path(p)) != sha for p, sha in sources.items()):
        raise RuntimeError('source changed during verification')
    report = dict(status='pass', checks=7, result=127, tools=tools, sources=sources,
                  image_sha256=digest(image), container_sha256=digest(container),
                  evidence=text, compiler_self_rebuild=False)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: typed values, scalar compatibility, fuel, reader and policy refusal')


if __name__ == '__main__':
    main()
