"""Native test byte staging/hash/process observer; no guest semantics."""
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path

LIB = Path(__file__).resolve().parents[1]

def sha(data):
    return hashlib.sha256(data).hexdigest()

class NativeGate:
    """Linux x86_64: KX64 payloads under the native runner. Apple Silicon
    (JUN-593): the Mac root compiles to aarch64-macos and the Mac packager
    wraps fs2-cli-stdio-general images; FD 3 is the output directory, scope
    paths reach the guest as /<relative path>, and main's result is the exit
    status (compared modulo 256; Linux reads the full i64 from :result)."""
    def __init__(self, args):
        self.darwin = (platform.system(), platform.machine()) == ('Darwin', 'arm64')
        assert self.darwin or (platform.system(), platform.machine()) == ('Linux', 'x86_64')
        self.compiler = args.compiler.resolve()
        assert sha(self.compiler.read_bytes()) == args.compiler_sha256
        if self.darwin:
            assert getattr(args, 'packager', None) and args.packager_sha256, '--packager is required on macOS'
            self.runner = args.packager.resolve()
            assert sha(self.runner.read_bytes()) == args.packager_sha256
        else:
            self.runner = args.runner.resolve()
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

    def fd3(self, argv, scope=None, popen=False, timeout=600):
        """Run (or start) a Mac image with FD 3 = scope (default: the output directory)."""
        fd = os.open(scope or self.out, os.O_RDONLY | os.O_DIRECTORY)
        try:
            kw = dict(cwd=self.out, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'}, pass_fds=(3,),
                      preexec_fn=lambda: os.dup2(fd, 3))
            if popen:
                return subprocess.Popen(list(map(str, argv)), stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kw)
            return subprocess.run(list(map(str, argv)), capture_output=True, timeout=timeout, **kw)
        finally:
            os.close(fd)

    def guest_args(self, args):
        """Absolute paths under the output directory become /<relative> beneath FD 3."""
        out = []
        for a in args:
            p = Path(str(a))
            out.append('/' + str(p.relative_to(self.out)) if p.is_absolute() and p.is_relative_to(self.out) else str(a))
        return out

    def mac_call(self, label, argv, expected=0, scope=None, timeout=600):
        start = time.monotonic()
        result = self.fd3(argv, scope, timeout=timeout)
        (self.out / (label + '.stdout')).write_bytes(result.stdout)
        (self.out / (label + '.stderr')).write_bytes(result.stderr)
        self.observations.append(dict(name=label, exit=result.returncode,
            seconds=round(time.monotonic()-start, 3), stdoutSHA256=sha(result.stdout), stderrSHA256=sha(result.stderr)))
        print(label, result.returncode, flush=True)
        assert result.returncode == expected, (label, result.returncode, result.stdout[-500:], result.stderr[-1000:])
        return result

    def mac_build(self, label, entry, files):
        root = self.out / label / 'src'
        for name, data in files.items():
            dest = root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        rel = '/' + label + '/src'
        lock = self.out / (label + '.ksl')
        lock.write_text(f'KSL1\nentry {rel}/{entry}\nroot {rel}\n' + ''.join(
            f'file {sha(data)} {rel}/{name}\n' for name, data in sorted(files.items())))
        flags = ['--source-path', rel, '--source-lock', lock.name, '--source-lock-sha256', sha(lock.read_bytes())]
        self.mac_call(label + '-check', [self.compiler, 'check', f'{rel}/{entry}', *flags])
        self.mac_call(label + '-compile', [self.compiler, 'compile', f'{rel}/{entry}', '--target', 'aarch64-macos',
                                           '--output', label + '.kseed', *flags])
        r = self.mac_call(label + '-extract', [self.compiler, 'extract-native', label + '.kseed', '--symbol', 'main',
                                               '--output', label + '.raw'])
        match = re.search(rb':offset (\d+), :length (\d+), :arity 0}', r.stdout)
        assert match and int(match[2]) == (self.out / (label + '.raw')).stat().st_size, r.stdout[-300:]
        self.mac_call(label + '-package', [self.runner, label + '-unsigned.macho', label + '.raw',
                                           'fs2-cli-stdio-general', match[1].decode()])
        image = self.out / (label + '.macho')
        shutil.copyfile(self.out / (label + '-unsigned.macho'), image)
        image.chmod(0o755)
        subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-', str(image)], check=True, capture_output=True)
        unsigned = (self.out / (label + '-unsigned.macho')).read_bytes()
        self.artifacts[label] = dict(unsignedSHA256=sha(unsigned), lockSHA256=sha(lock.read_bytes()),
                                     sources={n: sha(b) for n,b in files.items()})
        return image

    def build(self, label, entry, files):
        if self.darwin:
            return self.mac_build(label, entry, files)
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

    def run(self, label, image, expected=0, args=(), allow='-', scope=None, timeout=600):
        if self.darwin:
            # scope is the Linux grant root; on the Mac FD 3 is always the output directory.
            return self.mac_call(label, [image, *self.guest_args(args)], expected & 0xff, timeout=timeout)
        command = [self.runner, image, 0, 0, 'x86_64', allow]
        if args:
            command += ['--', *args]
        env = dict(self.env(allow, scope), KEXE_FUEL='100000000000', KEXE_STRUCTURED_REPORT='1')
        result = self.call(label, command, env, timeout=timeout)
        match = re.search(rb':result (-?[0-9]+)\b', result.stdout)
        assert match and int(match[1]) == expected and not result.stderr, (label, result.stdout, result.stderr)
        return result

    def finish(self, status, **details):
        report = dict(status=status, compilerSHA256=sha(self.compiler.read_bytes()),
                      host=[platform.system(), platform.machine()],
                      **({'packagerSHA256': sha(self.runner.read_bytes()), 'resultBits': 8} if self.darwin
                         else {'runnerSHA256': sha(self.runner.read_bytes())}),
                      artifacts=self.artifacts,
                      observations=self.observations, publicTestKeysOnly=True, **details)
        (self.out / 'evidence.json').write_text(json.dumps(report, indent=2) + '\n')
        print(status, flush=True)
