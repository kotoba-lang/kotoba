#!/usr/bin/env python3
"""Inspect or drive an already running native desktop through local QMP.

This is a host-side debugger. It does not use VNC, a password, a guest agent,
network access, or a substitute implementation of the guest's UI/store.
For isolated commit and cold-restore assertions, use
check-native-draft-restart-qemu.py instead.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import select
import shutil
import socket
import struct
import string
import subprocess
import time


HERE = Path(__file__).resolve().parent
KEYS = {'2', 'space', 'backspace', 'esc', 'f5'} | set(string.ascii_lowercase)


class QMP:
    def __init__(self, path):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(15)
        self.sock.connect(str(path))
        self.stream = self.sock.makefile('rwb', buffering=0)
        self.seq = 0
        assert 'QMP' in json.loads(self.stream.readline())
        self.call('qmp_capabilities')

    def call(self, name, arguments=None):
        self.seq += 1
        request = {'execute': name, 'id': self.seq}
        if arguments is not None:
            request['arguments'] = arguments
        self.stream.write(json.dumps(request).encode() + b'\n')
        while True:
            response = json.loads(self.stream.readline())
            if response.get('id') == self.seq:
                if 'error' in response:
                    raise RuntimeError(response['error'])
                return response['return']

    def close(self):
        self.stream.close()
        self.sock.close()


class QMPStdio:
    """Own one isolated VM; QMP stays on private pipes with no listener."""

    def __init__(self, args, output):
        command = [str(args.qemu), '-machine', 'q35,accel=tcg', '-cpu', 'max',
                   '-m', '128M', '-smp', '1', '-drive',
                   f'if=pflash,format=raw,readonly=on,file={args.firmware}',
                   '-drive', f'file={args.boot_media},format=raw,if=ide,snapshot=on',
                   '-boot', 'order=c', '-nic', 'none', '-display', 'none',
                   '-no-reboot', '-serial', 'file:serial.log',
                   '-debugcon', 'file:debug.log', '-qmp', 'stdio']
        if args.local_draft:
            # The only writable disk is a new, marked fixture inside output.
            disk = output/'draft.raw'
            raw = bytearray(128*512)
            struct.pack_into('<4I', raw, 0, 0x49415741, 0x54465244, 1, 128)
            disk.write_bytes(raw)
            disk.chmod(0o600)
            command += ['-device', 'isa-ide,id=draft-controller', '-drive',
                        f'file={disk},format=raw,if=none,id=draft,cache=directsync',
                        '-device', 'ide-hd,drive=draft,bus=draft-controller.0,unit=1,serial=AWAI90DRAFT000001']
        (output/'command.json').write_text(json.dumps(command, indent=2)+'\n')
        self.log = (output/'qemu.log').open('wb')
        self.process = subprocess.Popen(command, cwd=output,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.log, bufsize=0)
        self.seq = 0
        try:
            assert 'QMP' in json.loads(self.read_line(15))
            self.call('qmp_capabilities')
        except BaseException:
            self.close(hard=True)
            raise

    def read_line(self, timeout):
        if not select.select([self.process.stdout], [], [], timeout)[0]:
            raise TimeoutError('QMP stdio response timed out')
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(f'QEMU exited during QMP: {self.process.poll()}')
        return line

    def call(self, name, arguments=None):
        self.seq += 1
        request = {'execute': name, 'id': self.seq}
        if arguments is not None:
            request['arguments'] = arguments
        self.process.stdin.write(json.dumps(request).encode()+b'\n')
        while True:
            response = json.loads(self.read_line(10))
            if response.get('id') == self.seq:
                if 'error' in response:
                    raise RuntimeError(response['error'])
                return response['return']

    def close(self, hard=False):
        if self.process.poll() is None:
            if hard:
                self.process.kill()
            else:
                try:
                    self.call('quit')
                except (OSError, RuntimeError, TimeoutError):
                    self.process.kill()
            self.process.wait(timeout=10)
        self.process.stdin.close()
        self.process.stdout.close()
        self.log.close()


def read_state(qmp, context, output):
    for name, offset, size in (('surface.bin', 0x238000, 8192),
                               ('context.bin', 0x23a000, 8192),
                               ('fuel.bin', 8, 8)):
        path = output / name
        qmp.call('pmemsave', {'val': context+offset, 'size': size,
                             'filename': str(path)})
    surface = struct.unpack('<2048I', (output/'surface.bin').read_bytes())
    work = struct.unpack('<2048I', (output/'context.bin').read_bytes())
    count = surface[2038]
    goal = ''.join(chr(c) for c in surface[224:224+count]) if 12 <= count <= 63 else None
    signed = lambda value: value if value < 0x80000000 else value-0x100000000
    return {'magic': work[72], 'goal': goal, 'focus': surface[2],
            'keys': work[73], 'lastKey': work[77],
            'framesStarted': work[78], 'frames': work[79],
            'generation': work[80], 'restoreCode': signed(work[81]),
            'commitCode': signed(work[82]), 'draftEnabled': work[84],
            'fuelRemaining': struct.unpack('<Q', (output/'fuel.bin').read_bytes())[0]}


def wait_for_frame(qmp, context, output, prior_keys=None, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = read_state(qmp, context, output)
        if (state['magic'] == 0x31545844 and state['frames'] >= 1
                and state['frames'] == state['framesStarted']
                and (prior_keys is None or state['keys'] > prior_keys)
                and state['frames'] >= state['keys']+1):
            return state
        time.sleep(.2)
    raise TimeoutError(f'native desktop did not complete a frame: {state}')


def resolve_boot_inputs(args, parser):
    if args.build_dir:
        build = args.build_dir.resolve()
        if args.kernel or args.efi:
            parser.error('--build-dir supplies --kernel and --efi')
        args.boot_media = build/'media/awai-native.img'
        args.efi = build/'kernel/BOOTX64.EFI'
        args.kernel = build/'kernel/KERNEL.ELF'
        if args.font is None and args.expect_visible_goal:
            args.font = build/'font/aiueos-padded.fnt'
    if args.qmp_socket:
        if args.qemu or args.firmware or args.efi or args.local_draft:
            parser.error('boot options require --boot-media or --build-dir')
        if args.kernel is None or not args.kernel.is_file():
            parser.error('--qmp-socket requires an exact --kernel file')
        if not args.qmp_socket.is_socket():
            parser.error('QMP socket must exist')
        return
    if args.qemu is None:
        found = shutil.which('qemu-system-x86_64')
        if found is None:
            parser.error('QEMU not found; pass --qemu')
        args.qemu = Path(found).resolve()
    if args.firmware is None:
        args.firmware = args.qemu.resolve().parent.parent/'share/qemu/edk2-x86_64-code.fd'
    for name in ('boot_media', 'qemu', 'firmware', 'efi', 'kernel'):
        path = getattr(args, name)
        if path is None or not path.is_file():
            parser.error(f'--{name.replace("_", "-")} requires a regular file')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--qmp-socket', type=Path,
                        help='attach to an existing VM (local Unix socket)')
    target.add_argument('--boot-media', type=Path,
                        help='launch a fresh, headless VM over private QMP pipes')
    target.add_argument('--build-dir', type=Path,
                        help='use media/ and kernel/ artifacts from one native desktop build')
    parser.add_argument('--qemu', type=Path, help='QEMU binary for --boot-media')
    parser.add_argument('--firmware', type=Path, help='OVMF image for --boot-media')
    parser.add_argument('--efi', type=Path, help='matching EFI image for --boot-media')
    parser.add_argument('--local-draft', action='store_true',
                        help='create a new 64 KiB diagnostic draft disk in --output')
    parser.add_argument('--kernel', type=Path)
    parser.add_argument('--font', type=Path,
                        help='matching guest font for visible Goal pixel assertions')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--keys', nargs='*', default=[], choices=sorted(KEYS))
    parser.add_argument('--allow-draft-write', action='store_true',
                        help='required before sending F5 to a live VM')
    parser.add_argument('--expect-goal', help='exact goal text after the final key')
    parser.add_argument('--expect-visible-goal',
                        help='lowercase Goal body that must appear in the guest scanout')
    parser.add_argument('--expect-focus', type=int,
                        help='expected focused window after the final key')
    parser.add_argument('--expect-draft-enabled', type=int, choices=(0, 1),
                        help='expected native draft profile switch (0 or 1)')
    parser.add_argument('--expect-generation', type=int,
                        help='expected committed draft generation')
    parser.add_argument('--expect-restore-code', type=int,
                        help='expected native draft restore result')
    parser.add_argument('--expect-commit-code', type=int,
                        help='expected native draft commit result')
    args = parser.parse_args()
    if args.expect_visible_goal:
        if (not args.expect_goal or not args.expect_goal.endswith('\n'+args.expect_visible_goal)
                or any(c not in string.ascii_lowercase+' ' for c in args.expect_visible_goal)):
            parser.error('--expect-visible-goal requires matching --expect-goal with lowercase/space body')
    if 'f5' in args.keys and not args.allow_draft_write:
        parser.error('F5 can write the attached VM disk; pass --allow-draft-write')
    resolve_boot_inputs(args, parser)
    image = args.kernel.read_bytes()
    rw = struct.unpack_from('<IIQQQQQQ', image, 120)
    if rw[0:2] != (1, 6) or rw[5] != 0x240000:
        parser.error('unexpected native desktop kernel context contract')
    if args.boot_media:
        if args.efi.read_bytes().count(image) != 1:
            parser.error('kernel must appear exactly once in matching EFI image')
        spec = importlib.util.spec_from_file_location('media_reader', HERE/'check-native-media-format.py')
        reader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reader)
        reader.verify(args.boot_media, args.efi)
    if args.expect_visible_goal:
        if args.font is None or not args.font.is_file():
            parser.error('visible Goal check requires the exact guest --font')
        if args.efi and args.efi.read_bytes().count(args.font.read_bytes()) != 1:
            parser.error('font must appear exactly once in matching EFI image')
    output = args.output.resolve()
    # Screenshots and memory dumps may contain user state.
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    qmp = QMP(args.qmp_socket) if args.qmp_socket else QMPStdio(args, output)
    try:
        status = qmp.call('query-status')
        assert status['running'], status
        state = wait_for_frame(qmp, rw[3], output)
        events = [{'action': 'initial', 'state': state}]
        for key in args.keys:
            previous = state
            qcode = 'spc' if key == 'space' else key
            qmp.call('send-key', {'keys': [{'type': 'qcode', 'data': qcode}],
                                  'hold-time': 60})
            state = wait_for_frame(qmp, rw[3], output, prior_keys=previous['keys'])
            events.append({'action': key, 'state': state})
            time.sleep(.12)
        spec = importlib.util.spec_from_file_location('desktop_observer', HERE/'check-native-desktop-qemu.py')
        observer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(observer)
        ppm = output/'desktop.ppm'
        glyphs = []
        scanout_error = None
        if args.expect_visible_goal:
            spec = importlib.util.spec_from_file_location(
                'draft_observer', HERE/'check-native-draft-restart-qemu.py')
            draft_observer = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(draft_observer)
            font_bytes = args.font.read_bytes()
        deadline = time.monotonic()+10
        while True:
            qmp.call('screendump', {'filename': str(ppm)})
            pixels = observer.ppm_png(ppm, output/'desktop.png')
            if not args.expect_visible_goal:
                break
            try:
                glyphs = draft_observer.visible_goal_ink(
                    (output/'surface.bin').read_bytes(), font_bytes,
                    pixels, args.expect_visible_goal)
                scanout_error = None
            except AssertionError as error:
                scanout_error = str(error)
            if (scanout_error is None and glyphs
                    and all((row['inkPixels'] == 0 if row['codepoint'] == 32
                             else row['inkPixels'] > 0) for row in glyphs)):
                break
            if time.monotonic() >= deadline:
                break
            time.sleep(.1)
        expected = {'goal': args.expect_goal, 'focus': args.expect_focus,
                    'draftEnabled': args.expect_draft_enabled,
                    'generation': args.expect_generation,
                    'restoreCode': args.expect_restore_code,
                    'commitCode': args.expect_commit_code}
        expected = {name: value for name, value in expected.items() if value is not None}
        failures = {name: {'expected': value, 'actual': state[name]}
                    for name, value in expected.items() if state[name] != value}
        if args.expect_visible_goal and (scanout_error is not None or not glyphs
                                          or any((row['inkPixels'] != 0 if row['codepoint'] == 32
                                                  else row['inkPixels'] <= 0) for row in glyphs)):
            failures['visibleGoal'] = {'expected': args.expect_visible_goal,
                                       'glyphs': glyphs, 'error': scanout_error}
        report = {'schema': 'aiueos.native-desktop-qmp-debug.v1',
                  'status': 'PASS' if not failures else 'FAIL',
                  'observerSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'kernelSha256': hashlib.sha256(image).hexdigest(),
                  'bootMediaSha256': hashlib.sha256(args.boot_media.read_bytes()).hexdigest()
                                     if args.boot_media else None,
                  'screenshotSha256': hashlib.sha256(ppm.read_bytes()).hexdigest(),
                  'events': events, 'expected': expected, 'failures': failures,
                  'visibleGoalGlyphs': glyphs,
                  'fontSha256': hashlib.sha256(font_bytes).hexdigest()
                                if args.expect_visible_goal else None,
                  'qmpTransport': 'unix-socket' if args.qmp_socket else 'stdio',
                  'localDraftFixture': bool(args.local_draft),
                  'vncUsed': False, 'networkUsed': False,
                  'guestStoreEmulated': False}
        (output/'debug.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(state, ensure_ascii=False))
        if failures:
            parser.exit(1, f'guest state assertion failed; see {output / "debug.json"}\n')
    finally:
        qmp.close()


if __name__ == '__main__':
    main()
