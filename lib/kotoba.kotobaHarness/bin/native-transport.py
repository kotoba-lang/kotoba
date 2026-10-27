#!/usr/bin/env python3
"""Explicit I/O mechanisms for the selfhost-built Kotoba controller.

Python stages/hashes bytes, launches pinned binaries and the official Chrome
test host, and transports framed observations / opaque HTTP bodies. It never
reads project EDN, chooses candidates, assembles source, admits model answers,
or creates a semantic receipt. Those belong to canonical Kotoba.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import select
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
_boundary_spec = importlib.util.spec_from_file_location('harness_process_boundary', ROOT / 'bin/process-boundary.py')
_boundary = importlib.util.module_from_spec(_boundary_spec)
_boundary_spec.loader.exec_module(_boundary)
clean_env = _boundary.clean_env
MODULES = ('data', 'catalog', 'ast', 'decision', 'search', 'io', 'verification', 'main', 'gate')
CLOSURES = {'main': (*MODULES[:-1], 'ledger'), 'gate': ('data', 'io', 'gate'), 'data': ('data',),
            'catalog': ('data', 'catalog'), 'search': ('data', 'catalog', 'ast', 'decision', 'search'),
            'boundary': ('data', 'catalog', 'ast', 'decision', 'search', 'verification', 'ledger')}
CLOSURES['bench'] = ('data', 'io', 'decision', 'ledger', 'bench')
IMAGE = 'docker.io/library/alpine:3'
ENDPOINT = 'https://openrouter.ai/api/alpha/decisions'


class Blocked(Exception):
    pass


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Native:
    def __init__(self, amu, output):
        obsolete = [key for key in ('NBB', 'KOTOBA_BIN', 'KOTOBA_BROWSER_HOST') if os.environ.get(key)]
        if obsolete:
            raise Blocked('retired configuration: ' + ', '.join(obsolete))
        self.amu, self.output = Path(amu).resolve(), Path(output).resolve()
        self.pin = json.loads((ROOT / 'test/native/toolchain.json').read_text())
        for name in ('compiler', 'runner', 'browser-driver', 'browser-host', 'browser-page'):
            item = self.pin[name]
            if not (self.amu / item['path']).is_file() or sha(self.amu / item['path']) != item['sha256']:
                raise Blocked('pinned native dependency mismatch: ' + name)
        if platform.machine().lower() not in ('aarch64', 'arm64') or platform.system() not in ('Darwin', 'Linux'):
            raise Blocked('this whole-harness route requires native ARM64 Linux (macOS: ARM64 Podman VM); no emulation/fallback')
        self.container = platform.system() == 'Darwin'
        if self.container:
            vm = subprocess.run(['podman', 'machine', 'ssh', 'uname', '-m'], capture_output=True, text=True, timeout=20, env=clean_env())
            if vm.returncode or vm.stdout.strip() not in ('aarch64', 'arm64'):
                raise Blocked('an already-running native ARM64 Podman VM is required')
        self.compiler = self.amu / self.pin['compiler']['path']
        self.output.mkdir(parents=True, exist_ok=True)
        self.commands = []

    def command(self, directory, args, executable=None, stdin=False):
        if self.container:
            return ['podman', 'run', *(['-i'] if stdin else []), '--rm', '--pull=never', '--network=none',
                    '--read-only', '--cap-drop=all', '--security-opt=no-new-privileges',
                    '-v', f'{self.compiler}:/compiler:ro', '-v', f'{self.amu}:/amu:ro', '-v', f'{directory}:/work',
                    '-e', 'KEXE_ALLOW=' + ('3,7,37,39,41' if executable else '35,37,38,39'),
                    '-e', 'KEXE_CAP_RESOURCES_35=/work:/amu', '-e', 'KEXE_STACK_BYTES=8388608',
                    '-e', 'KEXE_CPU_SECONDS=300', '-e', 'KEXE_WALL_SECONDS=1800',
                    '-e', 'KEXE_FUEL=2000000000', '-e', 'KEXE_STRUCTURED_REPORT=' + ('1' if executable else '0'),
                    '-e', 'PATH=/native-no-host-tools',
                    '--entrypoint', '/work/' + executable if executable else '/compiler', IMAGE, *args]
        return [str(directory / executable) if executable else str(self.compiler), *args]

    def environment(self, **grants):
        # Podman itself needs the host PATH; its guest receives the empty
        # tool path above. Direct Linux guests use absolute executable paths.
        return clean_env(PATH=os.environ.get('PATH', '') if self.container else '/native-no-host-tools', **grants)

    def path(self, directory, name):
        return '/work/' + name if self.container else str(directory / name)

    def run(self, directory, args, label):
        env = self.environment(KEXE_ALLOW='35,37,38,39', KEXE_CAP_RESOURCES_35=f'{directory}:{self.amu}',
                        KEXE_STACK_BYTES='8388608', KEXE_CPU_SECONDS='300', KEXE_WALL_SECONDS='1800')
        r = subprocess.run(self.command(directory, args), capture_output=True, text=True, timeout=180, env=env)
        (directory / (label + '.stdout')).write_text(r.stdout)
        (directory / (label + '.stderr')).write_text(r.stderr)
        # Packed compiler reports are observations, not OS exit codes. Never
        # treat an OS-zero / native-nonzero result as successful compilation.
        reports = re.findall(r'\{:status :ok :result (-?[0-9]+) :fuel \{[^\n]+\}\}', r.stdout)
        code = r.returncode if r.returncode else (int(reports[-1]) if reports else 0)
        self.commands.append(dict(label=label, args=args, exit=code, process_exit=r.returncode))
        return dict(exit=code, stdout=r.stdout, stderr=r.stderr)

    def build(self, entry='main', test=False):
        directory = self.output / ('build-' + entry)
        directory.mkdir(exist_ok=True)
        source = directory / 'src/kotoba_harness'
        source.mkdir(parents=True, exist_ok=True)
        staged = []
        for name in CLOSURES[entry]:
            dst = source / (name + '.kotoba')
            dst.write_bytes((ROOT / 'src/kotoba_harness' / dst.name).read_bytes())
            staged.append(dst)
        if test:
            dst = source / (entry + '_test.kotoba')
            dst.write_bytes((ROOT / 'test/native' / dst.name).read_bytes())
            staged.append(dst)
        relative = 'src/kotoba_harness/' + entry + ('_test' if test else '') + '.kotoba'
        target = self.path(directory, relative)
        lock = ('KSL1\nentry ' + target + '\nroot ' + self.path(directory, 'src') + '\n' +
                ''.join('file ' + sha(p) + ' ' + self.path(directory, str(p.relative_to(directory))) + '\n' for p in sorted(staged)))
        (directory / 'source.ksl').write_text(lock)
        options = ['--source-path', self.path(directory, 'src'), '--source-lock', self.path(directory, 'source.ksl'),
                   '--source-lock-sha256', hashlib.sha256(lock.encode()).hexdigest()]
        for name in ('controller.kseed', 'controller.elf'):
            (directory / name).unlink(missing_ok=True)
        commands = [('check', ['check', target, *options]),
                    ('payload', ['compile', target, '--target', 'aarch64-macos', '--output', self.path(directory, 'controller.kseed'), *options]),
                    ('pack', ['compile', '/amu/' + self.pin['runner']['path'] if self.container else str(self.amu / self.pin['runner']['path']),
                              '--target', 'aarch64-linux', '--output', self.path(directory, 'controller.elf'),
                              '--format', 'packed', '--payload', self.path(directory, 'controller.kseed')])]
        for label, args in commands:
            result = self.run(directory, args, label)
            if result['exit']:
                raise Blocked(f'native {label} failed; inspect {directory / (label + ".stderr")}')
        (directory / 'controller.elf').chmod(0o755)
        (directory / 'build.json').write_text(json.dumps(dict(toolchain=self.pin, commands=self.commands,
            source_lock_sha256=sha(directory / 'source.ksl'), payload_sha256=sha(directory / 'controller.kseed'),
            image_sha256=sha(directory / 'controller.elf')), indent=2) + '\n')
        return directory

    def browser(self):
        spec = importlib.util.spec_from_file_location('amu_browser', self.amu / self.pin['browser-driver']['path'])
        host = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(host)
        host.subprocess = _boundary.BrowserProcesses()
        browser = host.find_browser(os.environ.get('KOTOBA_BROWSER') or
                   ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' if platform.system() == 'Darwin' else None))
        if not browser:
            raise Blocked('Chrome/Chromium missing; no hosted Wasm fallback')
        return host, browser

    def verify(self, effect, index):
        directory = self.output / ('verify-' + str(index))
        directory.mkdir()
        # Source bytes and check selection are emitted by Kotoba; transport
        # writes them verbatim to fixed paths, never evaluates or edits them.
        module = directory / effect['module-file']
        if not module.resolve().is_relative_to(directory.resolve()) or module == directory:
            raise Blocked('native output path leaves the staging directory')
        module.parent.mkdir(parents=True, exist_ok=True)
        module.write_text(effect['source'])
        (directory / 'verify.kotoba').write_text(effect['verify-source'])
        begin = time.monotonic()
        check = self.run(directory, ['check', self.path(directory, effect['module-file'])], 'check')
        result = dict(check=check)
        if check['exit'] == 0:
            result['compile'] = self.run(directory, ['compile', self.path(directory, 'verify.kotoba'), '--target', 'wasm32-browser',
                                                    '--output', self.path(directory, 'verify.wasm')], 'compile')
            if result['compile']['exit'] == 0:
                host, browser = self.browser()
                version, lines = host.run_modules(browser, directory / 'browser', [('verify', directory / 'verify.wasm', dict(fuel=10_000_000))], timeout=45)
                result.update(browser=lines['verify'], version=version)
                result['wasm-sha256'] = sha(directory / 'verify.wasm')
        result['wall-ms'] = int((time.monotonic() - begin) * 1000)
        (directory / 'observation.json').write_text(json.dumps(result, indent=2) + '\n')
        return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def decide(body, key):
    request = urllib.request.Request(ENDPOINT, data=body.encode(), method='POST',
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json', 'X-OpenRouter-Title': 'kotoba-harness'})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
            raw = response.read(1048577)
            if len(raw) > 1048576:
                raise Blocked('HTTP response exceeds transport bound')
            return dict(status=response.status, body=raw.decode())
    except urllib.error.HTTPError as error:
        return dict(status=error.code, body=error.read(1048576).decode(errors='replace'))


def send(stream, value):
    data = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
    pending = memoryview(str(len(data)).encode() + b'\n' + data)
    while pending:
        count = stream.write(pending)
        if not count:
            raise Blocked('native input pipe closed during a frame')
        pending = pending[count:]
    stream.flush()


def receive(stream):
    deadline = time.monotonic() + 180
    def read(count):
        chunks = []
        while count:
            if not select.select([stream], [], [], max(0, deadline - time.monotonic()))[0]:
                raise Blocked('native frame deadline exceeded')
            chunk = os.read(stream.fileno(), count)
            if not chunk:
                raise Blocked('native frame truncated')
            chunks.append(chunk)
            count -= len(chunk)
        return b''.join(chunks)
    length = b''
    while len(length) < 9 and not length.endswith(b'\n'):
        length += read(1)
    if not re.fullmatch(rb'[0-9]{1,7}\n', length) or int(length) > 1048576:
        raise Blocked('invalid native frame length')
    return json.loads(read(int(length)))


def execute(native, build, config, key=None):
    stderr = open(native.output / 'controller.stderr', 'wb')
    env = native.environment(KEXE_ALLOW='3,7,37,39,41', KEXE_FUEL='2000000000', KEXE_STRUCTURED_REPORT='1',
                    KEXE_STACK_BYTES='8388608', KEXE_CPU_SECONDS='300', KEXE_WALL_SECONDS='1800')
    process = subprocess.Popen(native.command(build, [], executable='controller.elf', stdin=True), stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=stderr, env=env, bufsize=0)
    try:
        send(process.stdin, config)
        index = 0
        while True:
            effect = receive(process.stdout)
            if effect.get('op') == 'finish':
                raw = effect['receipt']
                expected = effect['exit']
                if type(expected) is not int or expected not in (0, 1, 78) or not isinstance(raw, str):
                    raise Blocked('invalid native completion frame')
                process.stdin.close()
                code = process.wait(timeout=20)
                tail = process.stdout.read()
                # Process failure after a success frame is never accepted.
                report = rb'\{:status :ok :result ' + str(expected).encode() + rb' :fuel \{:initial [0-9]+ :remaining [0-9]+\}\}\s*'
                if code != 0 or not re.fullmatch(report, tail):
                    raise Blocked('native completion interrupted or exit/report mismatch')
                (native.output / 'receipt.json').write_text(raw + '\n')
                return expected, json.loads(raw)
            if effect.get('op') == 'verify':
                try:
                    observation = native.verify(effect, index)
                except (OSError, RuntimeError, TimeoutError, subprocess.SubprocessError) as error:
                    observation = dict(error=type(error).__name__)
                index += 1
            elif effect.get('op') == 'decide' and key:
                try:
                    observation = decide(effect['body'], key)
                except (OSError, ValueError, Blocked) as error:
                    observation = dict(status=0, body='', error=type(error).__name__)
                (native.output / ('http-' + str(index) + '.json')).write_text(json.dumps(dict(
                    status=observation['status'], response_bytes=len(observation['body'].encode()),
                    response_sha256=hashlib.sha256(observation['body'].encode()).hexdigest())) + '\n')
                index += 1
            elif effect.get('op') == 'native-test' and effect.get('entry') in ('data', 'catalog', 'search', 'boundary'):
                test = native.builds[effect['entry']]
                result = subprocess.run(native.command(test, [], executable='controller.elf', stdin=True),
                    capture_output=True, input=(ROOT / 'projects/itonami.edn').read_bytes(), timeout=90, env=env)
                observation = dict(exit=result.returncode, stdout=result.stdout.decode(), stderr=result.stderr.decode())
                (test / 'run.json').write_text(json.dumps(observation, indent=2) + '\n')
            elif effect.get('op') in ('session', 'benchmark') and hasattr(native, 'builds'):
                child = copy.copy(native)
                child.output = native.output / ('session-' + str(index))
                child.output.mkdir()
                child_config = {k: v for k, v in effect.items() if k != 'op'}
                child_config.update(date=config.get('date'), **{'native-route': config.get('native-route')})
                code, _ = execute(child, native.builds['bench' if effect['op'] == 'benchmark' else 'main'], child_config, key)
                observation = dict(exit=code, receipt=(child.output / 'receipt.json').read_text())
                index += 1
            else:
                raise Blocked('undeclared native effect or missing explicit credential')
            send(process.stdin, observation)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=20)
        stderr.close()


def main(argv):
    obsolete = [key for key in ('NBB', 'KOTOBA_BIN', 'KOTOBA_BROWSER_HOST') if os.environ.get(key)]
    if obsolete:
        raise Blocked('retired configuration: ' + ', '.join(obsolete))
    parser = argparse.ArgumentParser()
    parser.add_argument('project', type=Path)
    parser.add_argument('method', choices=('validate', 'known', 'wrong', 'scripted', 'jev'))
    parser.add_argument('output', nargs='?', type=Path, default=ROOT / 'runs/native-harness')
    parser.add_argument('--amu', default=os.environ.get('KOTOBA_AMU_ROOT'))
    parser.add_argument('--script', type=Path)
    parser.add_argument('--no-escalate', action='store_true')
    parser.add_argument('--budget-usd', type=float)
    args = parser.parse_args(argv)
    supplied_key = os.environ.pop('OPENROUTER_API_KEY', None)
    key = supplied_key if args.method == 'jev' else None
    if args.method == 'jev' and (not key or args.budget_usd is None or not 0 < args.budget_usd <= 0.05):
        raise Blocked('Jev needs explicit OPENROUTER_API_KEY and --budget-usd (0 < budget <= 0.05)')
    if not args.amu:
        raise Blocked('pass --amu or KOTOBA_AMU_ROOT for the exact pinned Amu checkout')
    args.output.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='session-', dir=args.output.resolve()))
    native = Native(args.amu, output)
    build = native.build()
    config = dict(project=args.project.read_text(), method=args.method, escalate=not args.no_escalate,
                  date=datetime.now(timezone.utc).isoformat(), script=json.loads(args.script.read_text()) if args.script else None,
                  **{'budget-usd': args.budget_usd or 0, 'native-route': json.loads((build / 'build.json').read_text())})
    # Only immutable identities are sent; verbose compiler command logs stay in build.json.
    config['native-route'] = dict(toolchain=native.pin, **{k: config['native-route'][k]
                                 for k in ('source_lock_sha256', 'payload_sha256', 'image_sha256')})
    code, receipt = execute(native, build, config, key)
    print(json.dumps({k: receipt.get(k) for k in ('project', 'method', 'status', 'error', 'api-usd')}, ensure_ascii=False))
    print(json.dumps(dict(receipt=str(output / 'receipt.json'))))
    return code


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except (Blocked, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(json.dumps(dict(status='blocked', error=str(error))), file=sys.stderr)
        sys.exit(78)
