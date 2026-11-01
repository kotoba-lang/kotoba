#!/usr/bin/env python3
"""AWAI-119: loopback OpenSSH forced-command adapter to signed native debug.

This is a Mac management bridge, not an SSH server inside Itonami OS.
OpenSSH authenticates the local operator; the board independently verifies
its boot nonce, command counter and pinned Ed25519 signature.
"""
import argparse
import contextlib
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shlex
import socket
import sys
import time

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('management_remote', HERE/'aiueos-remote.py')
remote = importlib.util.module_from_spec(spec); spec.loader.exec_module(remote)


def listen(port, timeout):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 << 20)
    s.bind(('', port)); s.settimeout(timeout)
    return s


def private_json(path):
    assert not path.is_symlink() and path.stat().st_uid == os.getuid()
    assert path.stat().st_mode & 0o077 == 0
    return json.loads(path.read_text())


def save_nonce(state, nonce):
    p = state/'boot.json'; tmp = state/('boot.'+str(os.getpid())+'.tmp')
    with os.fdopen(os.open(tmp, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600), 'w') as f:
        json.dump(dict(nonce=f'{nonce:016x}', observedAt=time.time()), f)
    os.replace(tmp, p)


def get_nonce(state, sock):
    p = state/'boot.json'
    if p.exists(): return int(private_json(p)['nonce'], 16)
    nonce = remote.wait_nonce(sock, 15); save_nonce(state, nonce); return nonce


def watch(state):
    s = listen(7799, .5)
    # Retain only public boot identity, never pairing codes or arbitrary logs.
    while True:
        for tag, value in remote.records(s, time.monotonic()+60):
            if tag == 0xc000 and value: save_nonce(state, value)


def main(a):
    cfg = private_json(a.config.resolve(strict=True)); state = Path(cfg['state'])
    assert state.is_dir() and state.stat().st_mode & 0o077 == 0
    if a.mode == 'watch': return watch(state)
    words = shlex.split(os.environ.get('SSH_ORIGINAL_COMMAND', 'help')) if a.mode == 'ssh' else a.command
    if not words: words = ['help']
    op, args = words[0], words[1:]
    if op == 'help' and not args:
        print('Mac SSH management bridge -> signed Itonami debug link')
        print('status | ping | key SCANCODE | type TEXT | screenshot | usb-select BDF | reboot')
        print('This endpoint is not the OS-native SSH server.'); return
    modes = {'status': 'ping', 'ping': 'ping', 'reboot': 'reboot', 'key': 'key',
             'type': 'type', 'usb-select': 'usb-select', 'screenshot': 'shot'}
    if op not in modes: raise ValueError('unsupported management operation')
    cmd = modes[op]
    if cmd in ('ping','reboot','shot') and args: raise ValueError('unexpected arguments')
    if cmd in ('key','type','usb-select') and len(args) != 1: raise ValueError('one argument required')
    if cmd == 'key' and not 0 < int(args[0], 0) < 128: raise ValueError('scan code outside1..127')
    if cmd == 'usb-select' and not 0 <= int(args[0], 0) <= 65535: raise ValueError('invalid BDF')
    if cmd == 'type' and (not 0 < len(args[0]) <= 64 or any(c not in remote.SCAN for c in args[0])):
        raise ValueError('unsupported text; use64 or fewer supported ASCII characters')
    key = Path(cfg['remoteKey']); assert key.stat().st_mode & 0o077 == 0
    seed = key.read_bytes(); assert len(seed) == 32
    # Serialize operations across SSH sessions and keep reply attribution exact.
    with (state/'command.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        log = listen(7799, .5); nonce = get_nonce(state, log)
        if cmd == 'shot':
            target = state/('screen-'+str(time.time_ns())+'.png')
            remote.listen = listen; remote.wait_nonce = lambda sock, seconds: nonce
            sys.argv = [str(HERE/'aiueos-remote.py'), '--key', str(key), '--wait','10',
                        '--nonce',hex(nonce),'shot',str(target)]
            with contextlib.redirect_stdout(io.StringIO()) as result: remote.main()
            if '600 rows, 800x600' not in result.getvalue():
                raise RuntimeError('incomplete physical screenshot: '+result.getvalue())
            sys.stdout.buffer.write(target.read_bytes()); return
        ids = {'ping':1,'reboot':2,'key':3,'usb-select':7,'type':3}
        expected = {'ping':0xc001,'reboot':0xc002,'key':0xc003,'usb-select':0xc007,'type':0xc003}
        counter = time.time_ns()
        values = [remote.SCAN[c] for c in args[0]] if cmd == 'type' else [int(args[0],0) if args else 0]
        replies = []
        for index, value in enumerate(values):
            remote.send(argparse.Namespace(broadcast=cfg.get('broadcast','10.77.0.255')), seed,
                        nonce,counter+index,ids[cmd],value)
            reply = remote.reply(log,{expected[cmd]},15)
            if reply is None or reply[0] == 0xc0ff: raise RuntimeError(f'board did not accept operation: {reply}')
            if cmd in ('ping','reboot') and reply[1] != counter+index: raise RuntimeError('reply counter differs')
            if cmd in ('key','type') and reply[1] != value: raise RuntimeError('reply key differs')
            replies.append(dict(tag=f'{reply[0]:04x}',value=reply[1]))
        print(json.dumps(dict(transport='Mac loopback SSH -> signed UDP',nativeSSH=False,
                              operation=op,bootNonce=f'{nonce:016x}',replies=replies)))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True)
    p.add_argument('mode',choices=('watch','ssh','run'));p.add_argument('command',nargs=argparse.REMAINDER)
    try: main(p.parse_args())
    except (ValueError,RuntimeError,AssertionError,OSError) as e:
        print('itonami management: '+str(e),file=sys.stderr);sys.exit(1)
