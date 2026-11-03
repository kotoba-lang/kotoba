#!/usr/bin/env python3
"""Synthetic receiver on a task-owned ARM VM, exposed only on a chosen host IP.

The VM must already contain the pinned Alpine ARM image and mount /task with
runner-arm.elf. The host's Podman VM networking forwards the published port;
no application-level byte relay or production fleet credentials are used.
"""
import json
import re
import socket
import subprocess
import sys
import time

if len(sys.argv) != 6:
    raise SystemExit('usage: observer PODMAN MACHINE BIND_IP RUN_ID CASE')
pod, machine, host, run_id, case = sys.argv[1:]
if not re.fullmatch(r'[A-Za-z0-9]{1,20}', run_id):
    raise ValueError('invalid run ID')
if case not in ('good', 'wrong', 'wrong-server', 'tampered', 'bad-ack', 'bad-record'):
    raise ValueError('invalid case')
with socket.socket() as probe:
    probe.bind((host, 0))
    port = probe.getsockname()[1]
address = '0.0.0.0:' + str(port)
published = host + ':' + str(port)
base = '/var/home/core/jun351-direct-' + run_id + '-' + case
name = 'jun351-' + run_id + '-' + case
common = [pod, 'run', '--rm', '--pull', 'never',
          '-v', '/task/runner-arm.elf:/runner:ro', '-v', base + ':/state:rw,Z',
          '-e', 'KEXE_STACK_BYTES=8388608', '-e', 'KEXE_FUEL=100000000000',
          '-e', 'KEXE_STRUCTURED_REPORT=1', '-e', 'KEXE_SECCOMP=if-available',
          '-e', 'KEXE_ALLOW=35,38,43,44,46,47', '-e', 'KEXE_CAP_RESOURCES_35=/state',
          '-e', 'KEXE_CAP_RESOURCES_43=' + address]
image = 'docker.io/library/alpine:latest'
def checked(result, label):
    if result.returncode or result.stderr or ':status :ok :result 0 ' not in result.stdout:
        raise RuntimeError((label, result.returncode, result.stdout[-800:], result.stderr[-800:]))

# All components of base are fixed or validated above.
subprocess.run([pod, 'machine', 'ssh', machine, 'mkdir ' + base], check=True, timeout=20)
initial = subprocess.run(common + [image, '/runner', 'init', '/state', address],
                         capture_output=True, text=True, timeout=60)
checked(initial, 'init')
receiver = subprocess.Popen(common + ['--name', name, '-p', published + ':' + str(port),
                                      image, '/runner', 'recv-' + case, '/state', address],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
try:
    deadline = time.monotonic() + 20
    while True:
        if receiver.poll() is not None:
            raise RuntimeError(('receiver exited before ready', receiver.communicate()))
        status = subprocess.run([pod, 'machine', 'ssh', machine,
                                 'if test -f ' + base + '/ready; then echo READY; fi'],
                                capture_output=True, text=True, timeout=10)
        if status.returncode == 0 and status.stdout.strip() == 'READY':
            break
        if time.monotonic() > deadline:
            raise TimeoutError('receiver not ready')
        time.sleep(.1)
    mapping = subprocess.run([pod, 'port', name], capture_output=True, text=True, timeout=10, check=True)
    if published not in mapping.stdout:
        raise RuntimeError(('unexpected published port', mapping.stdout))
    print(json.dumps({'ready': True, 'port': port, 'case': case}), flush=True)
    stdout, stderr = receiver.communicate(timeout=180)
    result = subprocess.CompletedProcess([], receiver.returncode, stdout, stderr)
    checked(result, 'receiver')
    saved = subprocess.run([pod, 'machine', 'ssh', machine,
                            'sha256sum ' + base + '/fleet.state'],
                           capture_output=True, text=True, timeout=10, check=True)
    expected = ('fabe0b11d39020d3f9b2dd9ab7f3e253cb7ce4c5ddfc9026494730bb64785073'
                if case in ('good', 'bad-ack') else
                '27f405f0a3100de2e7558e9a291a7ed34212e76dd06b7dadd5e7877ad5e08398')
    if not saved.stdout.startswith(expected + ' '):
        raise RuntimeError(('checkpoint mismatch', saved.stdout, saved.stderr))
    print(json.dumps({'receiver': 'PASS', 'case': case, 'stdout': stdout.strip(),
                      'checkpointSha256': expected}), flush=True)
finally:
    if receiver.poll() is None:
        subprocess.run([pod, 'stop', '--time', '1', name], capture_output=True, timeout=10)
        receiver.terminate()
        receiver.wait(timeout=5)
