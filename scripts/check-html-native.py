#!/usr/bin/env python3
"""Source-locked ARM64 native HTML fixtures. Python only stages and observes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
CASES = ('numeric_ref_html', 'html_named_ref', 'html_named_corpus', 'html_data_token',
         'html_attribute_token', 'html_tag', 'html_tokens', 'html_fragment', 'html_fragment_wire', 'html_chunk_limit')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(args):
    assert platform.system() == 'Linux' and platform.machine() in ('aarch64', 'arm64')
    compiler = args.compiler.resolve(strict=True)
    assert sha(compiler) == args.compiler_sha256
    owner = (ROOT / 'lib/kotoba.htmldom').resolve(strict=True)
    dom = args.dom.resolve(strict=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    runner = output / 'runner.kotoba'
    runner.write_bytes(args.runner_source.read_bytes())
    # Fixture basenames overlap dependency namespaces (html_named_ref).
    # Stage entry files under unique names so discovery cannot resolve the
    # same namespace from both its canonical source and a fixture root.
    roots = [owner / 'kotoba', dom / 'src', output]
    env = dict(PATH='/nonexistent', KEXE_STACK_BYTES='8388608',
               KEXE_CAP_RESOURCES_35=':'.join(map(str, [output, owner, dom])))
    calls = []

    def run(name, argv, environment=None, success=True):
        start = time.monotonic()
        r = subprocess.run(list(map(str, argv)), cwd=output, env=environment or env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
        (output / (name + '.stdout')).write_bytes(r.stdout)
        (output / (name + '.stderr')).write_bytes(r.stderr)
        calls.append({'name': name, 'argv': list(map(str, argv)), 'exit': r.returncode,
                      'seconds': round(time.monotonic() - start, 3)})
        (output / 'calls.json').write_text(json.dumps(calls, indent=2) + '\n')
        print(name, r.returncode, flush=True)
        if success:
            assert r.returncode == 0 and not r.stderr, (name, r.returncode, r.stderr[-1000:])
        return r

    flags = [item for root in roots for item in ('--source-path', str(root))]
    receipts = []
    def case(name, entry, expected, allow='-'):
        discovered = run(name + '-modules', [compiler, 'modules', entry, *flags])
        files = [Path(line.split(' ', 1)[1]) for line in discovered.stdout.decode().splitlines()]
        assert entry in files and len(files) == len(set(files))
        assert all(p.is_absolute() and not p.is_symlink() and any(p.is_relative_to(root) for root in roots) for p in files)
        lock = output / (name + '.ksl')
        lock.write_text('KSL1\nentry ' + str(entry) + '\n' +
                        ''.join('root ' + str(root) + '\n' for root in roots) +
                        ''.join('file ' + sha(p) + ' ' + str(p) + '\n' for p in sorted(files)))
        lock_flags = [*flags, '--source-lock', str(lock), '--source-lock-sha256', sha(lock)]
        run(name + '-check', [compiler, 'check', entry, *lock_flags])
        payload, image = output / (name + '.kseed'), output / (name + '.elf')
        run(name + '-compile', [compiler, 'compile', entry, '--target', 'aarch64-macos', '--output', payload, *lock_flags])
        run(name + '-pack', [compiler, 'compile', runner, '--target', 'aarch64-linux', '--output', image,
                             '--format', 'packed', '--payload', payload])
        image.chmod(0o755)
        run_env = dict(env, KEXE_STRUCTURED_REPORT='1', KEXE_ALLOW=allow)
        r = run(name + '-execute', [image], run_env)
        matches = re.findall(rb':status :ok :result (-?[0-9]+)', r.stdout)
        assert matches == [str(expected).encode()], (name, r.stdout[-1000:])
        receipts.append({'name': name, 'result': expected, 'sourceLock': sha(lock), 'payload': sha(payload),
                         'image': sha(image), 'sources': {str(p): sha(p) for p in files}})
        return image, r

    for name in CASES:
        source = (owner / 'test/native' / (name + '.kotoba')).resolve(strict=True)
        entry = output / ('entry-' + name + '.kotoba')
        entry.write_bytes(source.read_bytes())
        image, r = case(name, entry, 42, '37' if name == 'html_fragment_wire' else '-')
        if name == 'html_fragment_wire':
            lines = [line[5:] for line in r.stdout.splitlines() if line.startswith(b'WIRE ')]
            escaped = [line[9:] for line in r.stdout.splitlines() if line.startswith(b'WIRE_ESC ')]
            assert len(lines) == len(escaped) == 1
            json.loads(lines[0]); json.loads(escaped[0])
            denied = run(name + '-denied', [image], dict(env, KEXE_STRUCTURED_REPORT='1', KEXE_ALLOW='-'), success=False)
            assert b':wire 37 :refused :not-granted' in denied.stdout + denied.stderr
            assert not any(line.startswith(b'WIRE ') for line in denied.stdout.splitlines())

    mutant = output / 'mutant.kotoba'
    original = (owner / 'test/native/numeric_ref_html.kotoba').read_text()
    before = '(= (nr/decode-html "65" 10) 65)'
    assert original.count(before) == 1
    mutant.write_text(original.replace(before, '(= (nr/decode-html "65" 10) 66)'))
    case('mutant', mutant, 0)
    (output / 'receipt.json').write_text(json.dumps({'status': 'PASS_HTML_NATIVE_FIXTURES',
        'compilerSha256': sha(compiler), 'target': 'aarch64-linux', 'cases': receipts,
        'fullHtmlQualified': False, 'wasmQualified': False, 'browserQualified': False}, indent=2) + '\n')
    print('PASS_HTML_NATIVE_FIXTURES', len(receipts), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--compiler', type=Path, required=True)
    p.add_argument('--compiler-sha256', required=True)
    p.add_argument('--runner-source', type=Path, required=True)
    p.add_argument('--dom', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    main(p.parse_args())
