#!/usr/bin/env python3
"""Run the native post-quantum known-answer gates (JUN-352 P1b) and their mutants.

Each gate is one unity source: the library bodies with their `ns` forms removed, the
`sha3/` alias dropped, then the gate body. The gate's main returns a bitmask; a pass is
every bit set. Each mutant changes one line of a library body and must not pass.
Runs on Linux arm64 (the aarch64 payload packed into an aarch64-linux runner image, as
the arm64 owner lane does), on Apple Silicon (Mac root and packager, through
lib/kotoba.hata/scripts/native_gate.py) and on Linux x86_64 (KX64 under the native
runner). The pinned x86_64 KX64 profile refuses string literals (E7101 detail 16), which
the gates use for their vectors, so x86_64 is not run in CI yet.
"""
import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib/kotoba.hata/scripts'))
from native_gate import NativeGate  # noqa: E402

SHA3 = 'lib/gov.nist.sha3/kotoba/sha3/core.kotoba'
GATES = {
    'sha3': dict(bodies=[SHA3], gate='lib/gov.nist.sha3/kotoba/sha3/native_gate.kotoba', passing=63, mutants={
        'constant': (SHA3, '0x0000000000008082', '0x0000000000008083'),
        'suffix': ('lib/gov.nist.sha3/kotoba/sha3/core.kotoba', '(sponge bytes 136 6 32))', '(sponge bytes 136 1 32))'),
    }),
    'mlkem': dict(bodies=[SHA3, 'lib/gov.nist.mlKem/kotoba/mlkem/core.kotoba'],
                  gate='lib/gov.nist.mlKem/kotoba/mlkem/native_gate.kotoba', passing=63, mutants={
        'zeta': ('lib/gov.nist.mlKem/kotoba/mlkem/core.kotoba', '(vector-i64 1 1729 ', '(vector-i64 1 1730 '),
        'mask': ('lib/gov.nist.mlKem/kotoba/mlkem/core.kotoba', '(if (= differ 0) 0 255)', '(if (= differ 0) 255 0)'),
        'cbd': ('lib/gov.nist.mlKem/kotoba/mlkem/core.kotoba', '(md (- x y))', '(md (- y x))'),
    }),
    'mldsa': dict(bodies=[SHA3, 'lib/gov.nist.mlDsa/kotoba/mldsa/core.kotoba'],
                  gate='lib/gov.nist.mlDsa/kotoba/mldsa/native_gate.kotoba', passing=31, mutants={
        'ctx': ('lib/gov.nist.mlDsa/kotoba/mldsa/core.kotoba', '(vector-i64 0 (vector-count ctx))', '(vector-i64 1 (vector-count ctx))'),
        'hint': ('lib/gov.nist.mlDsa/kotoba/mldsa/core.kotoba',
                 '(and (> p idx) (>= (vector-at hb (- p 1)) (vector-at hb p))) -1', 'false -1'),
        'znorm': ('lib/gov.nist.mlDsa/kotoba/mldsa/core.kotoba',
                  '(if (or (= (vector-count h) 0) (>= (vnorm z) 524092)) false', '(if (= (vector-count h) 0) false'),
    }),
}

def strip_ns(text):
    return re.sub(r'^\(ns [^\n]*\n(?:[^\n]*\n)*?[^\n]*\)\)\n', '', text, count=1, flags=re.M)

def unity(name, spec, change=None):
    parts = [f'(ns pq.{name}-gate (:export [main]))\n']
    for path in spec['bodies'] + [spec['gate']]:
        text = (ROOT / path).read_text()
        if change and change[0] == path:
            assert text.count(change[1]) == 1, (name, change)
            text = text.replace(change[1], change[2])
        parts.append(strip_ns(text).replace('sha3/', '') if path != spec['gate'] else strip_ns(text))
    return ''.join(parts).encode()

class LinuxArm:
    """Linux aarch64: compile to an aarch64 payload, pack it into the runner (from
    --runner-source) as an aarch64-linux image, and read main's result from the
    structured report."""
    def __init__(self, args):
        assert (platform.system(), platform.machine()) in {('Linux', 'aarch64'), ('Linux', 'arm64')}
        self.compiler = args.compiler.resolve()
        assert hashlib.sha256(self.compiler.read_bytes()).hexdigest() == args.compiler_sha256
        self.runner_source = args.runner_source.resolve()
        self.out = args.output.resolve()
        self.out.mkdir(parents=True, exist_ok=False, mode=0o700)
        self.observations, self.artifacts = [], {}

    def env(self, **extra):
        # The compiler reads sources and the lock through the scoped resource capability.
        return dict(PATH='/nonexistent', KEXE_STACK_BYTES='8388608', KEXE_CAP_RESOURCES_35=str(self.out), **extra)

    def call(self, label, argv, env=None):
        start = time.monotonic()
        result = subprocess.run(list(map(str, argv)), cwd=self.out, capture_output=True, timeout=900,
                                env=env or self.env())
        (self.out / (label + '.stdout')).write_bytes(result.stdout)
        (self.out / (label + '.stderr')).write_bytes(result.stderr)
        self.observations.append(dict(name=label, exit=result.returncode, seconds=round(time.monotonic() - start, 3)))
        print(label, result.returncode, result.stderr.decode(errors='replace')[:300], flush=True)
        return result

    def build(self, label, entry, files):
        root = self.out / label / 'src'
        for name, data in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_bytes(data)
        source = root / entry
        lock = self.out / (label + '.ksl')
        lock.write_text(f'KSL1\nentry {source}\nroot {root}\n' + ''.join(
            f'file {hashlib.sha256(data).hexdigest()} {root / name}\n' for name, data in sorted(files.items())))
        flags = ['--source-path', root, '--source-lock', lock,
                 '--source-lock-sha256', hashlib.sha256(lock.read_bytes()).hexdigest()]
        for step, argv in [('check', [self.compiler, 'check', source, *flags]),
                           ('compile', [self.compiler, 'compile', source, '--target', 'aarch64-macos',
                                        '--output', self.out / (label + '.kseed'), *flags]),
                           ('pack', [self.compiler, 'compile', self.runner_source, '--target', 'aarch64-linux',
                                     '--output', self.out / (label + '.elf'), '--format', 'packed',
                                     '--payload', self.out / (label + '.kseed')])]:
            r = self.call(f'{label}-{step}', argv)
            assert r.returncode == 0 and not r.stderr, (label, step, r.returncode, r.stderr[-500:])
        image = self.out / (label + '.elf')
        image.chmod(0o755)
        self.artifacts[label] = dict(imageSHA256=hashlib.sha256(image.read_bytes()).hexdigest(),
                                     sources={n: hashlib.sha256(b).hexdigest() for n, b in files.items()})
        return image

    def run(self, label, image, expected):
        r = self.call(label, [image], self.env(KEXE_STRUCTURED_REPORT='1', KEXE_ALLOW='-'))
        match = re.search(rb':result (-?[0-9]+)', r.stdout)
        assert r.returncode == 0 and match and int(match[1]) == expected, (label, r.returncode, r.stdout[-300:])
        return r

    def finish(self, status, **details):
        (self.out / 'evidence.json').write_text(json.dumps(dict(
            status=status, compilerSHA256=hashlib.sha256(self.compiler.read_bytes()).hexdigest(),
            runnerSourceSHA256=hashlib.sha256(self.runner_source.read_bytes()).hexdigest(),
            host=[platform.system(), platform.machine()], artifacts=self.artifacts,
            observations=self.observations, **details), indent=2) + '\n')
        print(status, flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--compiler-sha256', required=True)
    parser.add_argument('--runner', type=Path, help='Linux x86_64: the native runner')
    parser.add_argument('--runner-source', type=Path, help='Linux arm64: the runner source to pack into')
    parser.add_argument('--packager', type=Path, help='macOS: the Mac packager')
    parser.add_argument('--packager-sha256')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    gate = LinuxArm(args) if platform.system() == 'Linux' and platform.machine() in ('aarch64', 'arm64') else NativeGate(args)
    results = {}
    for name, spec in GATES.items():
        entry = f'pq/{name}_gate.kotoba'
        image = gate.build(name, entry, {entry: unity(name, spec)})
        gate.run(name + '-pass', image, spec['passing'])
        results[name] = dict(passing=spec['passing'], mutants={})
        for label, change in spec['mutants'].items():
            mutant = gate.build(f'{name}-{label}', entry, {entry: unity(name, spec, change)})
            try:
                gate.run(f'{name}-{label}-detected', mutant, spec['passing'])
                detected = False
            except AssertionError:
                detected = True
            results[name]['mutants'][label] = detected
            assert detected, (name, label, 'mutant passed the gate')
    gate.finish('PASS_PQ_NATIVE_GATES', gates=results)

if __name__ == '__main__':
    main()
