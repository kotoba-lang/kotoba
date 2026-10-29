#!/usr/bin/env python3
"""Observe a real PS/2 titlebar drag and bounded native release inertia."""
import argparse
import importlib.util
import json
from pathlib import Path
import time
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('inertia_transport', HERE/'check-native-draft-restart-qemu.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)

def main(args):
    for name in ('media','efi','kernel','font','qemu','firmware'):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    args.output.mkdir(parents=True,exist_ok=False,mode=0o700)
    guest=t.Guest(args,args.output/'guest',None)
    events=[]
    def state():
        s=guest.dump(guest.context+0x238000,'surface.bin')
        c=guest.dump(guest.context+0x23a000,'context.bin')
        e=guest.dump(guest.context+0x23c000,'effects.bin')
        return dict(keys=c[73],frames=c[79],started=c[78],packets=c[75],x=c[50],y=c[51],
                    pressed=c[67],drag=c[71],pending=c[87],active=c[103],ms=c[111],
                    frameMS=c[116],inertia=list(e[32:39]),
                    rects=[list(s[5+5*k:10+5*k]) for k in range(s[1])])
    def wait(name,predicate):
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            s=state()
            if predicate(s) and s['frames']==s['started']:
                events.append(dict(name=name,state=s));return s
            assert guest.process.poll() is None
            time.sleep(.01)
        raise AssertionError((name,s))
    def move(dx,dy):
        old=state()
        guest.call('input-send-event',{'events':[
            {'type':'rel','data':{'axis':'x','value':dx}},
            {'type':'rel','data':{'axis':'y','value':dy}}]})
        return wait('pointer',lambda s:s['packets']>old['packets'] and s['frames']>old['frames'])
    try:
        wait('ready',lambda s:s['frames']>0)
        guest.key('2');opened=wait('launch',lambda s:len(s['rects'])==1 and s['keys']>0)
        target_x,target_y=opened['rects'][0][1]+400,opened['rects'][0][2]+14
        for _ in range(20):
            s=state();dx,dy=target_x-s['x'],target_y-s['y']
            if not dx and not dy:break
            move(max(-100,min(100,dx)),max(-100,min(100,dy)))
        guest.call('input-send-event',{'events':[{'type':'btn','data':{'button':'left','down':True}}]})
        pressed=wait('titlebar-press',lambda s:s['pressed']==1 and s['drag']==2)
        moved=move(40,10)
        assert moved['rects'][0][1]==pressed['rects'][0][1]+40
        guest.call('input-send-event',{'events':[{'type':'btn','data':{'button':'left','down':False}}]})
        final=wait('release-settled',lambda s:s['pressed']==0 and s['inertia'][0]==0 and s['active']==0)
        delta=[final['rects'][0][i]-moved['rects'][0][i] for i in (1,2)]
        assert moved['inertia'][2]>512 and 0<delta[0]<=18 and 0<=delta[1]<=18,(moved,final,delta)
        assert final['pending']==0
    finally:
        guest.close()
    r=dict(status='PASS_NATIVE_WINDOW_INERTIA_QEMU',events=events,releaseDelta=delta,
           kernel=t.pin(args.kernel),efi=t.pin(args.efi),media=t.pin(args.media),font=t.pin(args.font),
           observer=t.pin(Path(__file__)),physicalHardware=False,trustedHumanConsent=False)
    (args.output/'native-window-inertia.json').write_text(json.dumps(r,indent=2)+'\n')
    print(r['status'],delta)
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('media','efi','kernel','font','qemu','firmware','output'):
        p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
