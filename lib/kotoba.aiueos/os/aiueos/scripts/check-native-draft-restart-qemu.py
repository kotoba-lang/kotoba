#!/usr/bin/env python3
"""Observe a real native draft commit/cold boot; never emulate the guest store.

The tiny scratch disk is test input, not a D2 workspace image. No physical disk
is accepted here. Run the native build queue around this controller as usual.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import select
import struct
import subprocess
import time

HERE = Path(__file__).resolve().parent
PREFIX = 'Goal local:\n'


def pin(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def visible_goal_ink(surface_bytes, font_bytes, pixels, goal):
    """Bind restored text draw ops to dark pixels in the QEMU scanout."""
    surface = struct.unpack('<2048I', surface_bytes)
    assert surface[427] == 0 and 0 < surface[416] <= 259
    windows = [surface[5+5*i:10+5*i] for i in range(surface[1])]
    itonami = [window for window in windows if window[0] == 2]
    assert len(itonami) == 1
    _, wx, wy, ww, _ = itonami[0]
    count = struct.unpack_from('<I', font_bytes, 8)[0]
    ops = [surface[480+6*i:486+6*i] for i in range(surface[416])]
    body = sorted((op for op in ops if op[0] == 2
                   and wx+14 <= op[1] < wx+ww-14
                   and wy+60 <= op[2] < wy+100), key=lambda op: (op[2], op[1]))
    assert len(body) == len(goal), ('Goal draw length differs', len(body), len(goal))
    result = []
    for character, target in zip(goal, body):
        cp = ord(character)
        glyphs = [i for i in range(count)
                  if struct.unpack_from('<I', font_bytes, 16+4*i)[0] & 0xffffff == cp]
        assert len(glyphs) == 1, (character, 'font glyph absent or duplicated')
        assert target[3] == glyphs[0], (character, 'Goal glyph order differs')
        _, x, y, _, width, _ = target
        assert width in (8, 16) and x+width <= surface[3] and y+16 <= surface[4]
        ink = sum(1 for row in range(y, y+16) for column in range(x, x+width)
                  if all(channel < 64 for channel in
                         pixels[(row*surface[3]+column)*3:(row*surface[3]+column)*3+3]))
        result.append(dict(codepoint=cp, glyph=glyphs[0], x=x, y=y,
                           width=width, inkPixels=ink))
    return result


class Guest:
    def __init__(self, args, directory, disk):
        self.args = args
        self.directory = directory
        # QMP controls the VM and its memory. Keep its pipe private to this
        # process; a Unix listener also makes sandboxed local runs require
        # approval merely to bind a socket.
        directory.mkdir(mode=0o700)
        rw = struct.unpack_from('<IIQQQQQQ', args.kernel.read_bytes(), 120)
        assert rw[0:2]==(1, 6) and rw[5]==0x240000, 'unexpected kernel context contract'
        self.context = rw[3]
        command = [str(args.qemu), '-machine', 'q35,accel=tcg', '-cpu', 'max',
                   '-m', '128M', '-smp', '1', '-drive',
                   f'if=pflash,format=raw,readonly=on,file={args.firmware}',
                   '-drive', f'file={args.media},format=raw,if=ide,snapshot=on',
                   '-boot', 'order=c', '-nic', 'none', '-display', 'none',
                   '-no-reboot', '-serial', 'file:serial.log',
                   '-debugcon', 'file:debug.log',
                   '-qmp', 'stdio']
        if disk:
            command += ['-device', 'isa-ide,id=draft-controller', '-drive',
                        f'file={disk},format=raw,if=none,id=draft,cache=directsync',
                        '-device', 'ide-hd,drive=draft,bus=draft-controller.0,unit=1,serial=AWAI90DRAFT000001']
        (directory/'command.json').write_text(json.dumps(command, indent=2)+'\n')
        self.log = (directory/'qemu.log').open('wb')
        self.process = subprocess.Popen(command, cwd=directory,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.log, bufsize=0)
        self.seq = 0
        try:
            greeting = self.read_qmp_line(15)
            assert greeting and 'QMP' in json.loads(greeting), (directory, 'QMP unavailable')
            self.call('qmp_capabilities')
        except BaseException:
            self.close(hard=True)
            raise

    def read_qmp_line(self, timeout):
        if not select.select([self.process.stdout], [], [], timeout)[0]:
            raise TimeoutError((self.directory, 'QMP response timed out'))
        response = self.process.stdout.readline()
        assert response, (self.directory, 'QMP closed', self.process.poll())
        return response

    def call(self, name, data=None):
        self.seq += 1
        row = dict(execute=name, id=self.seq)
        if data is not None:
            row['arguments'] = data
        self.process.stdin.write(json.dumps(row).encode()+b'\n')
        while True:
            row = json.loads(self.read_qmp_line(10))
            if row.get('id') == self.seq:
                assert 'error' not in row, row
                return row['return']

    def hmp(self, command):
        return self.call('human-monitor-command', {'command-line': command})

    def dump(self, address, name):
        assert self.hmp(f'pmemsave 0x{address:x} 8192 {name}') == ''
        return struct.unpack('<2048I', (self.directory/name).read_bytes())

    def state(self):
        surface = self.dump(self.context+0x238000, 'surface.bin')
        context = self.dump(self.context+0x23a000, 'context.bin')
        length = surface[2038]
        signed = lambda v: v if v<0x80000000 else v-0x100000000
        return dict(goal=''.join(chr(c) for c in surface[224:224+length]) if 12<=length<=63 else None,
                    focus=surface[2], magic=context[72], keys=context[73], lastKey=context[77],
                    framesStarted=context[78], frames=context[79], generation=context[80], restore=signed(context[81]),
                    commit=signed(context[82]), enabled=context[84])

    def wait(self, name, predicate, timeout=90):
        end = time.monotonic()+timeout
        while time.monotonic()<end:
            assert self.process.poll() is None, ('guest exited', self.process.returncode)
            state = self.state()
            (self.directory/'last-state.json').write_text(json.dumps(state, indent=2)+'\n')
            # Each make event in this gate requests exactly one complete frame.
            # State mutation precedes rendering, so observing focus/goal alone
            # can capture the previous framebuffer during a cold restore.
            if (predicate(state) and state['frames']==state['framesStarted']
                    and state['frames']>=state['keys']+1):
                (self.directory/(name+'.json')).write_text(json.dumps(state, indent=2)+'\n')
                return state
            time.sleep(.2)
        (self.directory/'registers.txt').write_text(self.hmp('info registers'))
        raise AssertionError((name, state))

    def boot(self, restore, goal):
        state = self.wait('boot', lambda s:s['magic']==0x31545844 and s['frames']>=1)
        assert self.hmp(f'pmemsave 0x{self.context+8:x} 8 fuel.bin') == ''
        fuel = struct.unpack('<Q', (self.directory/'fuel.bin').read_bytes())[0]
        assert 2**52 <= fuel <= 2**53-1, ('interactive fuel exhausted or too short', fuel)
        state['fuelRemaining'] = fuel
        assert state['enabled']==1 and state['restore']==restore and state['goal']==PREFIX+goal, state
        assert state['keys']==0 and state['focus']==0, state
        return state

    def key(self, code):
        self.call('send-key', {'keys':[{'type':'qcode', 'data':code}], 'hold-time':60})
        # Avoid overlapping PS/2 presses; the guest owns state transitions.
        time.sleep(.12)

    def open(self):
        before = self.state()
        self.key('2')
        return self.wait('open', lambda s:s['focus']==2 and s['lastKey']==3 and s['frames']>before['frames'])

    def edit(self, code, goal):
        before = self.state()
        self.key(code)
        return self.wait('edit-'+code, lambda s:s['goal']==PREFIX+goal and s['keys']>before['keys'] and s['frames']>before['frames'])

    def commit(self, generation):
        before = self.state()
        self.key('f5')
        return self.wait('commit', lambda s:s['lastKey']==63 and s['commit']==generation and s['keys']>before['keys'] and s['frames']>before['frames'])

    def screenshot(self, name, visible_goal=None):
        spec = importlib.util.spec_from_file_location('desktop_observer', HERE/'check-native-desktop-qemu.py')
        observer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(observer)
        deadline = time.monotonic()+10
        attempts = 0
        while time.monotonic() < deadline:
            attempts += 1
            assert self.hmp(f'screendump {name}.ppm') == ''
            png = self.directory/(name+'.png')
            pixels = observer.ppm_png(self.directory/(name+'.ppm'), png)
            if visible_goal is None or self.args.font is None:
                return None
            glyphs = visible_goal_ink(
                (self.directory/'surface.bin').read_bytes(),
                self.args.font.read_bytes(), pixels, visible_goal)
            if all((row['inkPixels'] == 0 if row['codepoint'] == 32
                    else row['inkPixels'] > 0) for row in glyphs):
                return dict(name=name, goal=visible_goal, glyphs=glyphs,
                            attempts=attempts, screenshot=pin(png))
            time.sleep(.1)
        raise AssertionError((name, 'restored Goal glyphs did not reach QEMU scanout', glyphs))

    def close(self, hard=False):
        if self.process.poll() is None:
            if hard:
                self.process.kill()
            else:
                self.call('quit')
            self.process.wait(timeout=10)
        self.process.stdin.close()
        self.process.stdout.close()
        self.log.close()


def main(args):
    for name in ('media', 'efi', 'kernel', 'qemu', 'firmware'):
        assert getattr(args, name).is_file(), (name, 'regular file required')
    if args.font:
        assert args.font.is_file() and args.efi.read_bytes().count(args.font.read_bytes()) == 1
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    before = pin(args.media)
    assert args.efi.read_bytes().count(args.kernel.read_bytes())==1
    spec = importlib.util.spec_from_file_location('media_reader', HERE/'check-native-media-format.py')
    reader = importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    media_proof = reader.verify(args.media, args.efi)
    events = []
    visible = []
    active = None
    # Provision only an output-owned test fixture. The native guest refuses an
    # unmarked medium and never formats/provisions one itself.
    disk = args.output/'draft.raw'
    raw = bytearray(128*512)
    struct.pack_into('<4I', raw, 0, 0x49415741, 0x54465244, 1, 128)
    disk.write_bytes(raw)
    blank = bytes(raw)
    try:
        active = Guest(args, args.output/'commit', disk)
        active.boot(0, '')
        active.open()
        active.edit('a', 'a')
        active.edit('b', 'ab')
        committed = active.commit(1)
        assert committed['generation']==1
        proof = active.screenshot('committed-ab', 'ab')
        if proof: visible.append(proof)
        active.close();active=None
        first = disk.read_bytes()
        assert first[:512]==blank[:512] and first[2048:]==blank[2048:] and first!=blank
        assert hashlib.sha256(first[1536:2016]).digest()==first[2016:2048]
        events.append(dict(name='native-commit-generation-1', state=committed, disk=pin(disk)))

        active = Guest(args, args.output/'cold-restore', disk)
        restored = active.boot(1, 'ab')
        active.open()
        proof = active.screenshot('restored-ab', 'ab')
        if proof: visible.append(proof)
        active.edit('c', 'abc')
        active.close(hard=True);active=None
        assert disk.read_bytes()==first, 'uncommitted edit changed durable bytes'
        events.append(dict(name='cold-restore-and-uncommitted-power-loss', state=restored))

        active = Guest(args, args.output/'last-commit', disk)
        active.boot(1, 'ab');active.open();active.edit('d', 'abd')
        second_state = active.commit(2)
        active.close();active=None
        second = disk.read_bytes()
        assert second[:512]==blank[:512] and second[2048:]==blank[2048:]
        assert second[1536:2048]==first[1536:2048], 'previous committed slot overwritten'
        assert hashlib.sha256(second[1024:1504]).digest()==second[1504:1536]
        events.append(dict(name='native-commit-generation-2', state=second_state, disk=pin(disk)))

        # Even a fully hashed higher-generation orphan is not a published commit.
        orphan = bytearray(second)
        orphan[1536:2048] = second[1024:1536]
        struct.pack_into('<I', orphan, 1544, 3)
        orphan[2016:2048] = hashlib.sha256(orphan[1536:2016]).digest()
        disk.write_bytes(orphan)
        active = Guest(args, args.output/'orphan-refused', disk)
        restored = active.boot(2, 'abd')
        active.open()
        proof = active.screenshot('restored-abd', 'abd')
        if proof: visible.append(proof)
        active.close();active=None
        assert disk.read_bytes()==orphan
        events.append(dict(name='unpublished-higher-generation-ignored', state=restored))

        cases = []
        corrupt = bytearray(second);corrupt[1056] ^= 1
        cases.append(('tampered-slot', corrupt, -18))
        wrong = bytearray(second);struct.pack_into('<I', wrong, 516, 9)
        cases.append(('unsupported-head-version', wrong, -20))
        dirty = bytearray(blank);dirty[512+64] = 1
        cases.append(('dirty-empty-head', dirty, -16))
        reserved = bytearray(second);reserved[512+64] = 1
        cases.append(('head-reserved-bytes', reserved, -20))
        invalid_goal = bytearray(second);struct.pack_into('<I', invalid_goal, 1056, 0xD800)
        invalid_goal[1504:1536] = hashlib.sha256(invalid_goal[1024:1504]).digest()
        invalid_goal[992:1024] = invalid_goal[1504:1536]
        cases.append(('valid-digest-invalid-goal', invalid_goal, -17))
        unmarked = bytearray(blank);unmarked[0] ^= 1
        cases.append(('unprovisioned-medium', unmarked, -22))
        for name, data, result in cases:
            disk.write_bytes(data)
            active = Guest(args, args.output/name, disk)
            state = active.boot(result, '')
            active.open();active.commit(-24)
            active.close();active=None
            assert disk.read_bytes()==data, (name, 'refusal wrote disk')
            events.append(dict(name=name+'-refused-without-write', state=state))
        active = Guest(args, args.output/'missing-medium', None)
        state = active.boot(-22, '')
        active.open();active.commit(-24)
        active.close();active=None
        events.append(dict(name='missing-medium-refused', state=state))
        assert pin(args.media)==before
        report = dict(schema='aiueos.native-draft-restart.v1', status='PASS_NATIVE_LOCAL_DRAFT_COLD_RESTORE',
                      kernel=pin(args.kernel), efi=pin(args.efi), media=before, firmware=pin(args.firmware),
                      observer=pin(Path(__file__)), font=pin(args.font) if args.font else None,
                      independentMedia=media_proof, events=events,
                      visibleGoalScreenshots=visible,
                      nativeATACommit=True, coldProcessBoot=True, previousCommitAfterUncommittedCrash=True,
                      PythonGuestImplementation=False, JVMNodeOrGraalFallback=False, cCompilerOrLoader=False,
                      BrowserCSSOMParity=False, registeredDappExecution=False, D2WorkspaceCodec=False,
                      signedHeadAuthority=False, releaseAdmission=False, distributedDurability=False,
                      physicalHardware=False)
        (args.output/'native-draft-restart.json').write_text(json.dumps(report, indent=2)+'\n')
        print(report['status'])
    finally:
        if active:
            active.close(hard=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('media', 'efi', 'kernel', 'qemu', 'firmware', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--font', type=Path)
    parsed = parser.parse_args()
    for name in vars(parsed):
        value = getattr(parsed, name)
        if value is not None:
            setattr(parsed, name, value.resolve())
    main(parsed)
