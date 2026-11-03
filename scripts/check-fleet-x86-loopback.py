#!/usr/bin/env python3
"""Check synthetic signed Noise successors with an x86 KX64 runner on loopback.

Usage: RUNNER PAYLOAD NEW_OUTPUT. Test keys only; no live fleet or user data.
"""
import hashlib, json, os, platform, socket, subprocess, sys, time
from pathlib import Path
if len(sys.argv) != 4 or platform.system() != 'Linux' or platform.machine() != 'x86_64':
    raise SystemExit(__doc__)
runner, payload = (Path(p).resolve(strict=True) for p in sys.argv[1:3])
out = Path(sys.argv[3]).resolve()
out.mkdir(mode=0o700, parents=True, exist_ok=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
old = '27f405f0a3100de2e7558e9a291a7ed34212e76dd06b7dadd5e7877ad5e08398'
new = 'fabe0b11d39020d3f9b2dd9ab7f3e253cb7ce4c5ddfc9026494730bb64785073'
results = {}
for name in ('good', 'wrong', 'wrong-server', 'tampered', 'bad-ack', 'bad-record'):
    case = out / name
    case.mkdir(mode=0o700)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        addr = '127.0.0.1:' + str(probe.getsockname()[1])
    common = dict(PATH='/usr/bin:/bin', KEXE_STACK_BYTES='8388608', KEXE_FUEL='100000000000',
                  KEXE_STRUCTURED_REPORT='1', KEXE_SECCOMP='if-available', KEXE_CAP_RESOURCES_35=str(case))
    def start(mode, allow):
        env = dict(common, KEXE_ALLOW=allow, KEXE_CAP_RESOURCES_43=addr, KEXE_CAP_RESOURCES_45=addr)
        return subprocess.Popen([str(runner), str(payload), '0', '0', 'x86_64', allow, '--',
                                 mode, str(case), addr], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    def finish(proc):
        stdout, stderr = proc.communicate(timeout=180)
        if proc.returncode or stderr or b':status :ok :result 0 ' not in stdout:
            raise ValueError((name, proc.returncode, stdout[-200:], stderr[-500:]))
        return stdout.decode().strip()
    finish(start('init', '35,38'))
    if sha(case / 'fleet.state') != old:
        raise ValueError('unexpected initial checkpoint')
    receiver = start('recv-' + name, '35,38,43,44,46,47')
    try:
        deadline = time.monotonic() + 30
        while not (case / 'ready').exists():
            if receiver.poll() is not None:
                raise ValueError(('receiver exited', receiver.communicate()))
            if time.monotonic() >= deadline:
                raise TimeoutError(name)
            time.sleep(.1)
        sender = finish(start('send-' + name, '38,45,46,47'))
        received = finish(receiver)
        digest = sha(case / 'fleet.state')
        if digest != (new if name in ('good', 'bad-ack') else old):
            raise ValueError((name, 'checkpoint mismatch', digest))
        results[name] = {'sender': sender, 'receiver': received, 'checkpointSha256': digest}
        print(name, 'PASS', flush=True)
    finally:
        if receiver.poll() is None:
            receiver.kill()
            receiver.wait()
report = {'status': 'PASS_SYNTHETIC_FLEET_X86_LOOPBACK', 'observerSha256': sha(Path(__file__)),
          'runnerSha256': sha(runner), 'payloadSha256': sha(payload), 'cases': results,
          'scope': 'Native x86 Linux, synthetic fixture and loopback only; not live trust, production route, or release.'}
(out / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')
print(report['status'], flush=True)
