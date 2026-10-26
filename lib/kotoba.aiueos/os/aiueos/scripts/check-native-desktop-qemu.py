#!/usr/bin/env python3
"""Observe native framebuffer/input on raw VM media; no rendering verdict shim."""
import argparse,hashlib,importlib.util,json,os,re,socket,struct,subprocess,time,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
def pin(p):
 b=p.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def ppm_png(source,target):
 raw=source.read_bytes();m=re.match(rb'P6\s+(\d+)\s+(\d+)\s+255\s',raw);assert m
 w,h=map(int,m.groups());pixels=raw[m.end():];assert len(pixels)==w*h*3
 def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
 scan=b''.join(b'\0'+pixels[y*w*3:(y+1)*w*3] for y in range(h))
 target.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b''))
 assert len(set(pixels[i:i+3] for i in range(0,len(pixels),3)))>4
 return pixels
def main(media,efi,kernel,font,qemu,firmware,out):
 before=pin(media);image=kernel.read_bytes();assert efi.read_bytes().count(image)==1 and efi.read_bytes().count(font.read_bytes())==1
 rw=struct.unpack_from('<IIQQQQQQ',image,120);context=rw[3];assert rw[5]==0x240000
 spec=importlib.util.spec_from_file_location('reader',HERE/'check-native-media-format.py');reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader);format_proof=reader.verify(media,efi)
 out.mkdir(parents=True,exist_ok=False)
 args=[str(qemu),'-machine','q35,accel=tcg','-cpu','max','-m','128M','-smp','1','-drive',f'if=pflash,format=raw,readonly=on,file={firmware}',
       '-drive',f'file={media},format=raw,if=ide,snapshot=on','-boot','order=c','-nic','none','-display','none','-no-reboot',
       '-serial','file:serial.log','-debugcon','file:debug.log','-qmp','unix:qmp.sock,server=on,wait=off','-d','int','-D','exceptions.log']
 (out/'command.json').write_text(json.dumps(args,indent=2)+'\n');log=open(out/'qemu.log','wb');p=subprocess.Popen(args,cwd=out,stdout=log,stderr=subprocess.STDOUT)
 old=Path.cwd();os.chdir(out);sock=None;stream=None;seq=0;events=[]
 try:
  deadline=time.monotonic()+15
  while True:
   assert p.poll() is None,('QEMU exited',p.returncode)
   try:
    sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);sock.settimeout(10);sock.connect('qmp.sock');break
   except (FileNotFoundError,ConnectionRefusedError):
    sock.close();sock=None;assert time.monotonic()<deadline;time.sleep(.1)
  stream=sock.makefile('rwb',buffering=0);assert 'QMP' in json.loads(stream.readline())
  def call(name,data=None):
   nonlocal seq
   seq+=1;row=dict(execute=name,id=seq)
   if data is not None:row['arguments']=data
   stream.write(json.dumps(row).encode()+b'\n')
   while True:
    row=json.loads(stream.readline())
    if row.get('id')==seq:
     assert 'error' not in row,row
     return row['return']
  def hmp(s):return call('human-monitor-command',{'command-line':s})
  def dump(at,n,name):
   assert hmp(f'pmemsave 0x{at:x} {n} {name}')=='';return (out/name).read_bytes()
  def state():
   surface=struct.unpack('<2048I',dump(context+0x238000,8192,'surface.bin'))
   work=struct.unpack('<2048I',dump(context+0x23a000,8192,'desktop-context.bin'))
   goal_length=surface[2038]
   goal=''.join(chr(cp) for cp in surface[224:224+goal_length]) if 12<=goal_length<=63 else None
   return dict(windows=surface[1],focus=surface[2],width=surface[3],height=surface[4],itonamiGoal=goal,x=work[50],y=work[51],buttons=work[67],magic=work[72],keys=work[73],packets=work[75],clicks=work[76],lastKey=work[77],framesStarted=work[78],framesCompleted=work[79])
  def wait(name,predicate,timeout=120):
   end=time.monotonic()+timeout
   while time.monotonic()<end:
    assert p.poll() is None,('guest exited',p.returncode)
    s=state();(out/'last-state.json').write_text(json.dumps(s,indent=2)+'\n')
    if predicate(s):events.append(dict(name=name,state=s));return s
    registers=hmp('info registers');(out/'registers-last.txt').write_text(registers)
    time.sleep(.2)
   raise AssertionError((name,'native desktop state not reached',s))
  def screenshot(name):
   assert hmp(f'screendump {name}.ppm')==''
   return ppm_png(out/(name+'.ppm'),out/(name+'.png'))
  call('qmp_capabilities')
  initial=wait('native-first-frame',lambda s:s['magic']==0x31545844 and s['framesCompleted']>=1)
  assert initial['windows']==0 and initial['focus']==0 and initial['keys']==0
  assert initial['itonamiGoal']=='Goal (RAM):\n'
  registers=hmp('info registers');(out/'registers-native-desktop.txt').write_text(registers)
  reg=lambda name:int(re.search(rf'\b{name}\s*=([0-9a-f]+)',registers,re.I)[1],16)
  assert reg('CR3')==context+0x30000 and reg('CR0')&0x10000 and reg('EFER')&0x801==0x801
  assert re.search(r'\bCPL=0\b',registers) and struct.unpack('<Q',dump(context+480,8,'current-domain.bin'))[0]==73
  gop=struct.unpack('<8Q',dump(context+30416,64,'sealed-gop.bin'));base,size,width,height,stride,fmt,ready,font_base=gop
  assert ready==0x31504f47 and width==initial['width'] and height==initial['height'] and stride>=width and fmt in (0,1)
  pci=dump(context+20480,8224,'sealed-pci.bin');count=struct.unpack_from('<Q',pci,16)[0];assert 0<count<=128
  bars=[struct.unpack_from('<8Q',pci,32+i*64) for i in range(count)]
  assert any(r[0]<=base and base+size<=r[0]+r[1] for r in bars)
  assert pin(font)==dict(bytes=524288,sha256=hashlib.sha256(dump(font_base,524288,'font.bin')).hexdigest())
  first=screenshot('desktop-initial')
  def key(qcode):call('send-key',{'keys':[{'type':'qcode','data':qcode}],'hold-time':60})
  key('1');one=wait('keyboard-opens-murakumo-card',lambda s:s['windows']==1 and s['focus']==1 and s['lastKey']==2 and s['framesCompleted']>initial['framesCompleted'])
  key('a');unfocused=wait('itonami-goal-ignores-other-focus',lambda s:s['focus']==1 and s['lastKey']==30 and s['itonamiGoal']=='Goal (RAM):\n' and s['keys']>one['keys'])
  key('2');two=wait('keyboard-opens-itonami-card',lambda s:s['windows']==2 and s['focus']==2 and s['lastKey']==3 and s['framesCompleted']>one['framesCompleted'])
  assert two['itonamiGoal']=='Goal (RAM):\n'
  key('a');typed_a=wait('itonami-native-goal-a',lambda s:s['focus']==2 and s['lastKey']==30 and s['itonamiGoal']=='Goal (RAM):\na' and s['framesCompleted']>two['framesCompleted'])
  goal_a_pixels=screenshot('itonami-goal-a')
  key('b');typed_b=wait('itonami-native-goal-ab',lambda s:s['lastKey']==48 and s['itonamiGoal']=='Goal (RAM):\nab' and s['framesCompleted']>typed_a['framesCompleted'])
  goal_ab_pixels=screenshot('itonami-goal-ab');assert goal_a_pixels!=goal_ab_pixels
  key('backspace');deleted=wait('itonami-native-goal-backspace',lambda s:s['lastKey']==14 and s['itonamiGoal']=='Goal (RAM):\na' and s['framesCompleted']>typed_b['framesCompleted'])
  call('input-send-event',{'events':[{'type':'rel','data':{'axis':'x','value':80}},{'type':'rel','data':{'axis':'y','value':40}}]})
  moved=wait('mouse-moves-native-pointer',lambda s:s['x']>two['x'] and s['y']>two['y'] and s['packets']>two['packets'] and s['framesCompleted']>two['framesCompleted'])
  call('input-send-event',{'events':[{'type':'btn','data':{'down':True,'button':'left'}}]})
  clicked=wait('mouse-click-reduced',lambda s:s['clicks']==moved['clicks']+1 and s['buttons']==1 and s['framesCompleted']>moved['framesCompleted'])
  call('input-send-event',{'events':[{'type':'btn','data':{'down':False,'button':'left'}}]})
  released=wait('mouse-release-reduced',lambda s:s['buttons']==0 and s['framesCompleted']>clicked['framesCompleted'])
  key('esc');closed=wait('keyboard-closes-focused-card',lambda s:s['windows']==1 and s['lastKey']==1 and s['framesCompleted']>released['framesCompleted'])
  final=screenshot('desktop-after-input');assert first!=final
  assert pin(media)==before
  report=dict(status='PASS_NATIVE_DESKTOP_INPUT_QEMU',kernel=pin(kernel),efi=pin(efi),media=before,font=pin(font),firmware=pin(firmware),observer=pin(Path(__file__)),independentMedia=format_proof,events=events,sealedGop=dict(base=base,bytes=size,width=width,height=height,stride=stride,format=fmt,pciBarContained=True),screenshots=['desktop-initial.png','itonami-goal-a.png','itonami-goal-ab.png','desktop-after-input.png'],guestEmulation='QEMU TCG',blockDevice='q35 SATA with temporary overlay',privatePageTables=True,currentDomain=73,nativeCDCI=False,BrowserCSSOMParity=False,dappsExecuted=False,preemptiveScheduler=False,completeKernel=False,physicalHardware=False)
  (out/'native-desktop-qemu.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
 finally:
  if p.poll() is None:
   try:
    if stream:call('quit')
   except (OSError,ValueError,AssertionError):pass
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=5)
  if stream:stream.close()
  if sock:sock.close()
  log.close();os.chdir(old)
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for n in ['media','efi','kernel','font','qemu','firmware','output']:p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();main(*(getattr(a,n).resolve() for n in ['media','efi','kernel','font','qemu','firmware','output']))
