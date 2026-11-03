#!/usr/bin/env python3
"""JUN-502: observe native cursor/tile composition against forced full raster.

Private USB/QEMU events are synthetic. Pixel/counter observations do not
qualify physical flicker, refresh/vsync, gestures, or trusted approval.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import time

if not __debug__:
    raise RuntimeError('native observation assertions must remain enabled')
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('pointer_keys', HERE/'check-native-keystore-qemu.py')
keys = importlib.util.module_from_spec(spec)
spec.loader.exec_module(keys)

def pin(p):
    b = p.read_bytes()
    return dict(bytes=len(b), sha256=hashlib.sha256(b).hexdigest())

def main(a):
    for n in ('media', 'efi', 'kernel', 'font', 'qemu', 'firmware'):
        setattr(a, n, getattr(a, n).resolve(strict=True))
    assert pin(a.qemu)['sha256'] == a.qemu_sha256
    assert pin(a.firmware)['sha256'] == a.firmware_sha256
    assert a.efi.read_bytes().count(a.kernel.read_bytes()) == 1
    media_before = pin(a.media)
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False, mode=0o700)
    events = []; b = None; status = 'FAILED'
    def state():
        c = struct.unpack('<136I', b.dump(b.work, 544))
        e = struct.unpack('<83I', b.dump(b.work+8192, 332))
        return dict(x=c[50], y=c[51], started=c[78], frames=c[79], active=c[103],
                    pending=c[87], valid=e[58], baseOps=e[61], fast=e[62], stores=e[63], raster=e[64],
                    cached=e[49], forced=e[50], tileMode=e[65], tiles=e[78], tileStores=e[79],
                    tiledFrames=e[80], referenceFrames=e[81], maxTileBlurs=e[82], lastFrameMs=c[116], maxFrameMs=c[122])
    def settled():
        end = time.monotonic()+120
        while time.monotonic()<end:
            r=state()
            if r['started']==r['frames'] and r['active']==0:
                return r
            time.sleep(.05)
        raise AssertionError(('not settled', r))
    def key(code):
        b.send('sendkey '+code, .5)
        return settled()
    def move(x,y):
        for _ in range(60):
            r=settled(); dx=x-r['x']; dy=y-r['y']
            if dx==dy==0: return r
            step=lambda v:max(-100,min(100,v))
            b.send(f'mouse_move {step(dx)} {step(dy)}', .3)
        raise AssertionError(('pointer target not reached',x,y,state()))
    def screen(name):
        return b.screenshot(name)
    def compare_full(label):
        cached=screen(label+'-cached'); old=settled()
        full=key('f3'); assert full['forced']==1 and full['raster']>old['raster'], (old,full)
        assert screen(label+'-full')==cached, label+' differs from full raster'
        back=key('f3'); assert back['forced']==0
        return back
    def exercise(label,x,y,dx,dy,full_control=True):
        old=move(x,y); assert old['valid']==1
        first=screen(label+'-before')
        b.send(f'mouse_move {dx} {dy}', .4); new=settled()
        assert (new['x'],new['y'])==(x+dx,y+dy),(label,old,new)
        assert new['fast']>old['fast'] and new['raster']==old['raster'],(label,old,new)
        assert 0<new['stores']-old['stores']<=156*(new['fast']-old['fast']), (old,new)
        after=screen(label+'-after'); w,h,pixels=first
        assert (w,h)==after[:2]
        for py in range(h):
            for px in range(w):
                dirty=any(cx<=px<cx+12 and cy<=py<cy+12 for cx,cy in ((x,y),(x+dx,y+dy)))
                i=3*(py*w+px)
                if not dirty: assert pixels[i:i+3]==after[2][i:i+3],(label,'outside cursor',px,py)
        move(x,y); assert screen(label+'-roundtrip')==first, label+' ghost or changed background'
        if full_control: compare_full(label)
        events.append(dict(name=label, before=old, after=new, outsideCursorUnchanged=True,
                           exactRoundtrip=True, forcedFullRasterEqual=True if full_control else None))
    try:
        b=keys.Boot.__new__(keys.Boot)
        keys.Boot.__init__(b,a,out,'cursor',None,['-machine','q35,accel=tcg,i8042=off','-cpu','max,phys-bits=37',
                    '-device','qemu-xhci,id=usb','-device','usb-kbd,bus=usb.0,port=1',
                    '-device','usb-mouse,bus=usb.0,port=2'],first_frame_seconds=600)
        assert b.W(138)==15
        assert settled()['tiledFrames']>0 and state()['tileMode']==0
        compare_full('home-shelf-glass')
        events.append(dict(name='home-shelf-glass-tiled',state=settled(),forcedFullRasterEqual=True))
        key('2'); assert b.S(2)==2
        exercise('opaque-window',300,260,7,5)
        key('3'); assert b.S(1)==2 and b.S(2)==3
        exercise('overlapping-titlebars',300,42,8,16)
        r=settled(); w=b.W(40); h=b.W(41)
        exercise('viewport-edge-clipping',w-2,h-2,1,1)
        # Crossing the dock exercises changed base ops and alpha/blur instead
        # of incorrectly taking the cursor-only path; compare its final pixels.
        move(w//2,h-28); r=settled(); assert r['valid']==1
        compare_full('dock-material')
        events.append(dict(name='dock-material-normal-raster', state=settled(), forcedFullRasterEqual=True))
        # Hover each icon with two overlapping windows. Normal frames must
        # use offscreen tiles; F3 remains a separate direct-painter oracle.
        for k in range(4):
            before=settled()
            move((w-184)//2+20+44*k,h-28)
            normal=settled()
            assert normal['tiledFrames']>before['tiledFrames'], (k,before,normal)
            assert normal['referenceFrames']==before['referenceFrames'], (k,before,normal)
            assert normal['tiles']>before['tiles'] and normal['tileStores']>before['tileStores']
            assert normal['tileMode']==0 and normal['maxTileBlurs']<=4
            compare_full('dock-icon-'+str(k+1))
            events.append(dict(name='dock-icon-'+str(k+1)+'-tiled',before=before,after=normal,forcedFullRasterEqual=True))
        # Drag the focused top window through an overlap, then compare the
        # actual geometry and final glyph/material pixels to a direct redraw.
        def window(app):
            for i in range(b.S(1)):
                if b.S(5+5*i)==app: return [b.S(6+5*i+j) for j in range(4)]
            raise AssertionError(('missing window',app))
        geometry=window(3)
        move(geometry[0]+geometry[2]//2,geometry[1]+12)
        b.send('mouse_button 1',.3); settled()
        old=settled(); b.send('mouse_move 30 40',.3); dragged=settled()
        b.send('mouse_button 0',.3); released=settled()
        assert released['tiledFrames']>old['tiledFrames'], (old,released)
        assert released['referenceFrames']==old['referenceFrames']
        assert window(3)[:2]!=geometry[:2], ('no window movement',geometry,window(3))
        compare_full('window-drag-overlap')
        events.append(dict(name='window-drag-overlap-tiled',before=old,after=released,forcedFullRasterEqual=True))
        key('2'); modal=key('f8'); assert modal['pending']==2
        exercise('modal-cursor-no-approval',w//2,h//2,5,4,full_control=False)
        assert settled()['pending']==2 and b.W(94)==0
        denied=key('n'); assert denied['pending']==0 and b.W(94)==3
        assert b.W(96)==0 and b.words(928,8)==bytes(32), 'denial released key material'
        events.append(dict(name='modal-state-preserved-and-fresh-deny', state=denied))
        assert pin(a.media)==media_before
        status='PASS_NATIVE_POINTER_COMPOSITE_QEMU'
    finally:
        if b is not None:
            if status=='FAILED':
                try:
                    (out/'failure-state.json').write_text(json.dumps(state(),indent=2)+'\n')
                    screen('failure')
                except Exception: pass
            if hasattr(b, 'proc'): b.quit()
        (out/'receipt.json').write_text(json.dumps(dict(status=status, events=events,
            artifacts={n:pin(getattr(a,n)) for n in ('media','efi','kernel','font','qemu','firmware')},
            observer=pin(Path(__file__)), helper=pin(HERE/'check-native-keystore-qemu.py'),
            physicalFlickerQualified=False, smooth60HzQualified=False, syntheticInputProvesApproval=False),indent=2)+'\n')
    print(status,len(events))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('media','efi','kernel','font','qemu','firmware','output'):p.add_argument('--'+n,type=Path,required=True)
    for n in ('qemu-sha256','firmware-sha256'):p.add_argument('--'+n,required=True)
    main(p.parse_args())
