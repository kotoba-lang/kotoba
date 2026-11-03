#!/usr/bin/env python3
"""Observe the native stopped-USB update borrow/restore component fixture.

The public signature/digest fixture is exercised without an NIC or disk
write, followed by actual QEMU USB input after controller reinitialization.
This is not a physical updater, auto-update or user-consent qualification.
"""
import argparse,hashlib,importlib.util,json,time
from pathlib import Path
if not __debug__: raise RuntimeError('assertions must remain enabled')
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('maintenance_boot',HERE/'check-native-keystore-qemu.py')
keys=importlib.util.module_from_spec(spec);spec.loader.exec_module(keys)
def pin(p):
 b=p.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def main(a):
 for n in ('efi','kernel','media','qemu','firmware'):setattr(a,n,getattr(a,n).resolve(strict=True))
 assert pin(a.qemu)['sha256']==a.qemu_sha256 and pin(a.firmware)['sha256']==a.firmware_sha256
 assert a.efi.read_bytes().count(a.kernel.read_bytes())==1
 before=pin(a.media);out=a.output.resolve();out.mkdir(mode=0o700,exist_ok=False)
 b=None;status='FAILED';mask=0
 try:
  b=keys.Boot.__new__(keys.Boot)
  keys.Boot.__init__(b,a,out,'maintenance',None,['-machine','q35,accel=tcg,i8042=off','-cpu','max,phys-bits=37','-device','qemu-xhci,id=usb','-device','usb-kbd,bus=usb.0,port=1','-device','usb-mouse,bus=usb.0,port=2'],first_frame_seconds=180)
  mask=b.W(74);assert mask==63,('native pre-input mask',hex(mask))
  b.send('sendkey a',.5);b.send('mouse_move 20 10',.5)
  end=time.monotonic()+30
  while time.monotonic()<end:
   mask=b.W(74)
   if mask==255:break
   time.sleep(.1)
  assert mask==255,('native final mask',hex(mask))
  (out/'retained-key-app-pattern.bin').write_bytes(b.words(768,256))
  assert pin(a.media)==before
  status='PASS_NATIVE_INPUT_MAINTENANCE_QEMU'
 finally:
  if b and hasattr(b,'proc'):b.quit()
  (out/'receipt.json').write_text(json.dumps(dict(status=status,nativeMask=hex(mask),checks=['uninitialized USB refuses borrow','initial two HID devices','signature/changed-header/changed-image self-test uses borrowed scratchpad','all3072..4095 key/app pattern bytes retained','USB resume and two HID devices','pending modal refuses borrow with memory/HID retained','post-maintenance keyboard a','post-maintenance mouse20,10'],artifacts={n:pin(getattr(a,n)) for n in ('efi','kernel','media','qemu','firmware')},observer=pin(Path(__file__)),helper=pin(HERE/'check-native-keystore-qemu.py'),physicalUpdate=False,autoUpdate=False,syntheticInputProvesApproval=False),indent=2)+'\n')
 print(status,hex(mask))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('efi','kernel','media','qemu','firmware','output'):p.add_argument('--'+n,type=Path,required=True)
 for n in ('qemu-sha256','firmware-sha256'):p.add_argument('--'+n,required=True)
 main(p.parse_args())
