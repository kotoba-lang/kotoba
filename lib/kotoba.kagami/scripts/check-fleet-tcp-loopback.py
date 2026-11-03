#!/usr/bin/env python3
"""Observe synthetic signed fleet frames across two native Linux processes.

Runs inside a network-isolated Linux container with a prebuilt test.elf at
/work. The only network address granted is the selected IPv4 loopback port.
This is not authenticated Noise, an interoperable fleet protocol, or release.
"""
import json
import os
import socket
import subprocess
import time
from pathlib import Path

root = Path('/work')
image = root / 'test.elf'
results = {}
for case, mode in [('good', 'send-good'), ('bad-utf8', 'send-bad'), ('bad-signature', 'send-tampered'),
                   ('missing-link', 'send-gap'), ('oversized', 'send-big'), ('surrogate', 'send-surrogate'),
                   ('out-of-range', 'send-out-of-range')]:
    directory = root / ('case-' + case)
    directory.mkdir()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        addr = '127.0.0.1:' + str(probe.getsockname()[1])
    common = dict(PATH='/usr/bin:/bin', KEXE_STACK_BYTES='8388608', KEXE_FUEL='100000000000',
                  KEXE_STRUCTURED_REPORT='1', KEXE_SECCOMP='if-available', KEXE_CAP_RESOURCES_35='/work')
    receiver_env = dict(common, KEXE_ALLOW='35,38,43,44,46,47', KEXE_CAP_RESOURCES_43=addr)
    sender_env = dict(common, KEXE_ALLOW='38,45,47', KEXE_CAP_RESOURCES_45=addr)
    def call(mode, env):
        return subprocess.run([str(image), mode, str(directory), addr], env=env, capture_output=True, timeout=90)
    def good(result, name):
        if result.returncode != 0 or b':status :ok :result 0 ' not in result.stdout or result.stderr:
            raise ValueError((case, name, result.returncode, result.stdout[-300:], result.stderr[-500:]))
    init = call('init', receiver_env)
    good(init, 'init')
    receiver = subprocess.Popen([str(image), 'receive-good' if case == 'good' else 'receive-bad',
                                 str(directory), addr], env=receiver_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 20
        while not (directory / 'ready').exists():
            if receiver.poll() is not None: raise ValueError((case, 'receiver stopped', receiver.communicate()))
            if time.monotonic() >= deadline: raise TimeoutError(case + ' listener readiness')
            time.sleep(.05)
        sent = call(mode, sender_env)
        good(sent, 'sender')
        stdout, stderr = receiver.communicate(timeout=90)
        good(subprocess.CompletedProcess([], receiver.returncode, stdout, stderr), 'receiver')
    finally:
        if receiver.poll() is None:
            receiver.kill()
            receiver.wait(timeout=5)
    results[case] = 'PASS'
    print(case, 'PASS', flush=True)
(root / 'tcp-loopback-result.json').write_text(json.dumps({'status':'PASS_FLEET_TCP_LOOPBACK', 'cases':results,
    'scope':'isolated Linux loopback, synthetic signed record, separate processes; no Noise handshake, real fleet trust or production transport'}, indent=2) + '\n')
