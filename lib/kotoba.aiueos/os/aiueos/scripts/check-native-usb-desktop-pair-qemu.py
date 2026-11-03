#!/usr/bin/env python3
"""Compare two pinned native input-profile images with synthetic USB input.

No physical deployment, network, user approval, compilation or VNC login.
The caller supplies separately built baseline/candidate kernel, EFI and media.
This observer qualifies only this USB/Goal/render fixture, not whole OS parity.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import time
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))

def pin(p):
    b=p.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())

def main(a):
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=False,mode=0o700)
    state=dict(schema='aiueos.native-usb-desktop-pair.v1',state='OBSERVING',observer=pin(Path(__file__)),profiles={},physicalDeployment=False,trustedApproval=False)
    def save():(out/'receipt.json').write_text(json.dumps(state,indent=2)+'\n')
    save()
    try:
        paths={}
        for name in ['qemu','firmware','baseline_kernel','baseline_efi','baseline_media','candidate_kernel','candidate_efi','candidate_media']:
            p=getattr(a,name).resolve(strict=True)
            if pin(p)['sha256']!=getattr(a,name+'_sha256'):raise ValueError('pin mismatch: '+name)
            paths[name]=p
        state['qemu']=pin(paths['qemu']);state['firmware']=pin(paths['firmware'])
        helper=HERE/'check-native-input-state-qemu.py';state['inputHelper']=pin(helper)
        spec=importlib.util.spec_from_file_location('usb_desktop_pair',helper);g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
        state['bootHelper']=pin(HERE/'check-native-keystore-qemu.py')
        for label in ['baseline','candidate']:
            stage=out/label;stage.mkdir();media=paths[label+'_media'];before=pin(media)
            kernel=paths[label+'_kernel'];image=kernel.read_bytes()
            if struct.unpack_from('<H',image,56)[0]!=2:raise ValueError('expected two PT_LOAD entries')
            args=SimpleNamespace(kernel=kernel,efi=paths[label+'_efi'],media=media,qemu=paths['qemu'],firmware=paths['firmware'])
            b=g.StateBoot.__new__(g.StateBoot)
            try:
                extra=['-machine','q35,accel=tcg,i8042=off','-cpu','max,phys-bits=37','-device','qemu-xhci,id=xhci',
                    '-device','usb-kbd,bus=xhci.0,port=1','-device','usb-hub,id=hub,bus=xhci.0,port=2','-device','usb-mouse,bus=xhci.0,port=2.1']
                g.StateBoot.__init__(b,args,stage,label,None,extra,first_frame_seconds=180)
                if (b.W(138),b.W(139))!=(15,16383):raise AssertionError('native USB controller/topology differs')
                g.observed_key(b,'2',3)
                for key,scan in [('a',30),('b',48),('a',30)]:g.observed_key(b,key,scan)
                if (b.S(2),b.S(2038))!=(2,15):raise AssertionError('native Goal fixture differs')
                g.wait_input_ready(b);initial=[b.W(50),b.W(51)];frames=b.W(79)
                b.send('mouse_move 20 10',1);expected=[initial[0]+20,initial[1]+10];deadline=time.monotonic()+30
                while [b.W(50),b.W(51)]!=expected:
                    if b.proc.poll() is not None:raise RuntimeError('native desktop terminated')
                    if time.monotonic()>deadline:raise TimeoutError('USB pointer input not consumed')
                    time.sleep(.1)
                g.wait_input_ready(b)
                if b.W(79)<=frames:raise AssertionError('pointer motion did not present a frame')
                shot=b.screenshot('desktop');(stage/'browser-context.bin').write_bytes(b.dump(b.work,8192))
                state['profiles'][label]=dict(kernel=pin(kernel),efi=pin(args.efi),media=before,goal='aba',usbController=15,usbDevices=16383,
                    pointerBefore=initial,pointerAfter=expected,frames=b.W(79),dimensions=shot[:2],screenshot=pin(stage/'desktop.ppm'),pixelsSHA256=hashlib.sha256(shot[2]).hexdigest())
                save()
            except BaseException:
                if hasattr(b,'proc') and b.proc.poll() is None:
                    (stage/'failure-context.bin').write_bytes(b.dump(b.work,8192));b.screenshot('failure')
                raise
            finally:
                if hasattr(b,'proc'):b.quit()
            if pin(media)!=before:raise AssertionError('fixture medium changed')
        first=state['profiles']['baseline'];second=state['profiles']['candidate']
        if first['dimensions']!=second['dimensions'] or first['pixelsSHA256']!=second['pixelsSHA256']:raise AssertionError('paired desktop pixels differ')
        state['state']='PASS_NATIVE_USB_DESKTOP_PAIR';state['allPixelsEqual']=True;save();print(state['state'])
    except BaseException as error:
        state['failure']=type(error).__name__+': '+str(error);save();raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['qemu','firmware','baseline-kernel','baseline-efi','baseline-media','candidate-kernel','candidate-efi','candidate-media']:
        p.add_argument('--'+name,type=Path,required=True);p.add_argument('--'+name+'-sha256',required=True)
    p.add_argument('--output',type=Path,required=True)
    main(p.parse_args())
