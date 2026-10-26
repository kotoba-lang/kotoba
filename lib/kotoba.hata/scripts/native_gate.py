"""Native test byte staging/hash/process observer; no guest semantics."""
import hashlib
import json
import os
import platform
import re
import subprocess
import time
from pathlib import Path

LIB = Path(__file__).resolve().parents[1]

def sha(data):
    return hashlib.sha256(data).hexdigest()

class NativeGate:
    def __init__(self, args):
        assert (platform.system(), platform.machine()) == ('Linux', 'x86_64')
        self.compiler, self.runner = args.compiler.resolve(), args.runner.resolve()
        assert sha(self.compiler.read_bytes()) == args.compiler_sha256
        self.out = args.output.resolve()
        self.out.mkdir(parents=True, exist_ok=False, mode=0o700)
        self.artifacts, self.observations = {}, []

    def env(self, allow='35,37,38,39', scope=None):
        return dict(PATH='/nonexistent', KEXE_ALLOW=allow, KEXE_STACK_BYTES='8388608',
                    KEXE_CAP_RESOURCES_35=str(scope or self.out))

    def call(self, label, argv, env=None, expected=0, timeout=600):
        start = time.monotonic()
        result = subprocess.run(list(map(str, argv)), env=env or self.env(), cwd=self.out,
                                capture_output=True, timeout=timeout)
        (self.out / (label + '.stdout')).write_bytes(result.stdout)
        (self.out / (label + '.stderr')).write_bytes(result.stderr)
        self.observations.append(dict(name=label, exit=result.returncode,
            seconds=round(time.monotonic()-start, 3), stdoutSHA256=sha(result.stdout), stderrSHA256=sha(result.stderr)))
        print(label, result.returncode, flush=True)
        assert result.returncode == expected, (label, result.returncode, result.stdout[-500:], result.stderr[-1000:])
        return result

    def build(self, label, entry, files):
        root = self.out / label / 'src'
        for name, data in files.items():
            dest = root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        lock = self.out / (label + '.ksl')
        source = root / entry
        lock.write_text(f'KSL1\nentry {source}\nroot {root}\n' + ''.join(
            f'file {sha(data)} {root / name}\n' for name, data in sorted(files.items())))
        flags = ['--source-path', root, '--source-lock', lock, '--source-lock-sha256', sha(lock.read_bytes())]
        self.call(label + '-check', [self.compiler, 'check', source, *flags])
        artifact = self.out / (label + '.kx64')
        self.call(label + '-compile', [self.compiler, 'compile', source, '--target', 'x86_64-linux',
                                       '--output', artifact, '--format', 'kx64-v1', *flags])
        header, payload = artifact.read_bytes().split(b'\n\n', 1)
        match = re.fullmatch(rb'KX64V1 x86_64-linux sysv-ctx-v11 ([0-9]+) 0', header)
        assert match and int(match[1]) == len(payload) and payload[0] == 0xe9
        image = self.out / (label + '.bin')
        image.write_bytes(payload)
        self.artifacts[label] = dict(artifactSHA256=sha(artifact.read_bytes()), payloadSHA256=sha(payload),
                                    lockSHA256=sha(lock.read_bytes()), sources={n: sha(b) for n,b in files.items()})
        return image

    def run(self, label, image, expected=0, args=(), allow='-', scope=None):
        command = [self.runner, image, 0, 0, 'x86_64', allow]
        if args:
            command += ['--', *args]
        env = dict(self.env(allow, scope), KEXE_FUEL='100000000000', KEXE_STRUCTURED_REPORT='1')
        result = self.call(label, command, env)
        match = re.search(rb':result (-?[0-9]+)\b', result.stdout)
        assert match and int(match[1]) == expected and not result.stderr, (label, result.stdout, result.stderr)
        return result

    def finish(self, status, **details):
        report = dict(status=status, compilerSHA256=sha(self.compiler.read_bytes()),
                      runnerSHA256=sha(self.runner.read_bytes()), artifacts=self.artifacts,
                      observations=self.observations, publicTestKeysOnly=True, **details)
        (self.out / 'evidence.json').write_text(json.dumps(report, indent=2) + '\n')
        print(status, flush=True)
