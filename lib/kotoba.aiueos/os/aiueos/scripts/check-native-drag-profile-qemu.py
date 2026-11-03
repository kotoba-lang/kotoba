#!/usr/bin/env python3
"""JUN-502: repeat actual USB drags and observe native renderer phase counters.

QEMU guest cycles/clock values are diagnostic, not physical display latency.
All inputs are synthetic and cannot supply trusted application approval.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import time

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('drag_boot', HERE/'check-native-keystore-qemu.py')
keys = importlib.util.module_from_spec(spec); spec.loader.exec_module(keys)


def pin(p):
    raw = p.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def main(a):
    for name in ('efi','kernel','media','qemu','firmware'):
        setattr(a, name, getattr(a, name).resolve(strict=True))
    assert pin(a.qemu)['sha256'] == a.qemu_sha256
    assert pin(a.firmware)['sha256'] == a.firmware_sha256
    assert a.efi.read_bytes().count(a.kernel.read_bytes()) == 1
    before_media = pin(a.media)
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False, mode=0o700)
    b = None; samples = []; controls = []; status = 'FAILED'

    def state():
        c = struct.unpack('<136I', b.dump(b.work, 544))
        e = struct.unpack('<128I', b.dump(b.work+8192, 512))
        wide = lambda at: e[at] + (e[at+1] << 32)
        return dict(width=c[40], height=c[41], stride=c[42], x=c[50], y=c[51], pressed=c[67], dragID=c[71], packets=c[75],
                    started=c[78], frames=c[79], active=c[103], pending=c[87],
                    scale=c[110], reduced=c[99], sceneFrames=e[108], pointerFrames=e[109],
                    profiledFrames=e[110], mode=e[111], tileMode=e[65],
                    tiles=e[78], tileStores=e[79], tiledFrames=e[80], referenceFrames=e[81],
                    sceneListCycles=wide(112), sceneDamageCycles=wide(114),
                    sceneComposeCycles=wide(102), sceneCacheCycles=wide(116),
                    sceneTotalCycles=wide(118), maxSceneComposeCycles=wide(104),
                    sceneTileRasterCycles=wide(124), sceneTileCopyCycles=wide(126))

    def settled(after=-1):
        deadline = time.monotonic()+180
        last = None
        while time.monotonic() < deadline:
            last = state()
            if last['frames'] > after and last['started'] == last['frames'] and last['active'] == 0:
                assert last['tileMode'] == 0 and last['pending'] == 0
                assert last['profiledFrames'] == last['frames']
                return last
            time.sleep(.05)
        raise AssertionError(('not settled', last))

    def key(name):
        old = settled()
        b.send('sendkey '+name, .05)
        return settled(old['frames'])

    def move(x, y):
        for _ in range(30):
            old = settled(); dx=x-old['x']; dy=y-old['y']
            if dx == 0 and dy == 0:
                return old
            step = lambda value: max(-100, min(100, value))
            b.send(f'mouse_move {step(dx)} {step(dy)}', .05)
            settled(old['frames'])
        raise AssertionError(('pointer target not reached', x, y))

    def window(app):
        surface = struct.unpack('<32I', b.dump(b.surface, 128))
        for index in range(surface[1]):
            start = 5+5*index
            if surface[start] == app:
                return list(surface[start+1:start+5])
        raise AssertionError(('missing window', app, surface))

    def pixel_control(label):
        original = b.screenshot(label+'-normal')
        key('f3')
        assert b.screenshot(label+'-reference') == original, label+' differs from direct painter'
        key('f3')
        controls.append(dict(name=label, forcedFullRasterEqual=True))

    def drags(app, count, reduced):
        geometry = window(app)
        move(geometry[0]+geometry[2]//2, geometry[1]+12)
        old = settled(); b.send('mouse_button 1', .05); pressed = settled(old['frames'])
        assert pressed['pressed'] == 1 and pressed['dragID'] == app
        for index in range(6):
            old = settled(); geometry = window(app)
            dx, dy = ((8, 4) if index % 2 == 0 else (-8, -4))
            expected = [max(0,min(b.W(40)-geometry[2],geometry[0]+dx)),
                        max(28,min(b.W(41)-geometry[3],geometry[1]+dy))]
            b.send(f'mouse_move {dx} {dy}', .05); new = settled(old['frames'])
            actual = window(app)
            assert actual[:2] == expected, ('drag geometry', geometry, expected, actual)
            assert new['pressed'] == 1 and new['dragID'] == app
            assert new['packets'] > old['packets'] and new['sceneFrames'] > old['sceneFrames']
            assert new['tiledFrames'] > old['tiledFrames']
            assert new['referenceFrames'] == old['referenceFrames']
            total = new['sceneTotalCycles']
            assert total >= sum(new[k] for k in ('sceneListCycles','sceneDamageCycles',
                                                'sceneComposeCycles','sceneCacheCycles')) > 0
            samples.append(dict(windows=count, reducedEffects=reduced, index=index,
                                geometryBefore=geometry, geometryAfter=actual,
                                before=old, after=new,
                                guestSceneMS=(total/new['scale'] if new['scale'] > 0 else None)))
            pixel_control(f'{count}-windows-{reduced}-drag-{index}')
        old = settled(); b.send('mouse_button 0', .05); released = settled(old['frames'])
        assert released['pressed'] == 0 and released['dragID'] == 0
        pixel_control(f'{count}-windows-effects-'+('reduced' if reduced else 'normal'))

    try:
        b = keys.Boot.__new__(keys.Boot)
        keys.Boot.__init__(b,a,out,'drag',None,[
            '-machine','q35,accel=tcg,i8042=off','-cpu','max,phys-bits=37',
            '-device','qemu-xhci,id=usb','-device','usb-kbd,bus=usb.0,port=1',
            '-device','usb-mouse,bus=usb.0,port=2'], first_frame_seconds=180)
        assert b.W(138) == 15
        settled(); key('2'); assert b.S(1) == 1
        drags(2,1,False)
        key('f1'); assert settled()['reduced'] == 1
        drags(2,1,True)
        key('f1'); assert settled()['reduced'] == 0
        for app in ('1','3','4'):
            key(app)
        assert b.S(1) == 4
        drags(4,4,False)
        key('f1'); assert settled()['reduced'] == 1
        drags(4,4,True)
        assert len(samples) == 24 and len(controls) == 28
        assert pin(a.media) == before_media
        status = 'PASS_NATIVE_DRAG_PROFILE_QEMU'
    finally:
        if b is not None and hasattr(b,'proc'):
            b.quit()
        (out/'receipt.json').write_text(json.dumps(dict(
            status=status, samples=samples, controls=controls,
            timingScope='QEMU guest TSC and PIT-calibrated clock; not physical input-to-display',
            artifacts={n:pin(getattr(a,n)) for n in ('efi','kernel','media','qemu','firmware')},
            observer=pin(Path(__file__)), helper=pin(HERE/'check-native-keystore-qemu.py'),
            physicalSmoothnessQualified=False, syntheticInputProvesApproval=False),indent=2)+'\n')
    print(status, len(samples), 'drag samples')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('efi','kernel','media','qemu','firmware','output'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('qemu-sha256','firmware-sha256'):
        p.add_argument('--'+name,required=True)
    main(p.parse_args())
