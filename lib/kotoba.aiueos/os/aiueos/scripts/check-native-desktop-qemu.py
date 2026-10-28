#!/usr/bin/env python3
"""Observe native framebuffer/input on GPT or EFI El Torito VM media."""
import argparse,hashlib,importlib.util,json,os,re,select,struct,subprocess,time,zlib
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
def expected_background(y,height=800):
 # Independent expected scanout of the native RGB565 wallpaper (#c6ff -> #cddd).
 def unpack(v):return ((v>>11)*255//31,((v>>5)&63)*255//63,(v&31)*255//31)
 t=y*255//max(1,height-1)
 return tuple((a*(255-t)+b*t)//255 for a,b in zip(unpack(0xc6ff),unpack(0xcddd)))
def main(media,efi,kernel,font,qemu,firmware,out,iso=None):
 before=pin(media);image=kernel.read_bytes();font_data=font.read_bytes();assert efi.read_bytes().count(image)==1 and efi.read_bytes().count(font_data)==1
 glyph_count=struct.unpack_from('<I',font_data,8)[0]
 def glyph_index(cp):
  matches=[i for i in range(glyph_count) if struct.unpack_from('<I',font_data,16+4*i)[0]&0xffffff==cp]
  assert len(matches)==1,('missing or duplicate font glyph',cp)
  return matches[0]
 goal_glyphs={cp:glyph_index(ord(cp)) for cp in ('a','b')}
 rw=struct.unpack_from('<IIQQQQQQ',image,120);context=rw[3];assert rw[5]==0x240000
 # The page-table root is fixed by the kernel target's layout: kernel-v1 has RW at 0x200000, kernel-v3 at 0x400000. An unknown layout fails closed.
 cr3_offset=int(json.loads((HERE.parent/'native'/'layout-table.json').read_text())['rungs'][hex(context)]['pageTableRootOffset'],16)
 spec=importlib.util.spec_from_file_location('reader',HERE/'check-native-media-format.py');reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader);format_proof=reader.verify(media,efi)
 iso_proof=reader.verify_iso(iso,media,efi) if iso else None
 iso_before=pin(iso) if iso else None
 out.mkdir(parents=True,exist_ok=False)
 args=[str(qemu),'-machine','q35,accel=tcg','-cpu','max','-m','128M','-smp','1','-drive',f'if=pflash,format=raw,readonly=on,file={firmware}',
       '-drive',(f'file={iso},format=raw,if=ide,media=cdrom,readonly=on' if iso else f'file={media},format=raw,if=ide,snapshot=on'),
       '-boot',('order=d' if iso else 'order=c'),'-nic','none','-display','none','-no-reboot',
       '-serial','file:serial.log','-debugcon','file:debug.log','-qmp','stdio','-d','int','-D','exceptions.log']
 (out/'command.json').write_text(json.dumps(args,indent=2)+'\n');log=open(out/'qemu.log','wb')
 p=subprocess.Popen(args,cwd=out,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,bufsize=0)
 old=Path.cwd();os.chdir(out);stream=p.stdout;input_pipe=p.stdin;seq=0;events=[];visual_glyphs=[]
 try:
  assert select.select([stream],[],[],15)[0],('QMP greeting timeout',p.poll())
  greeting=stream.readline()
  if not greeting:
   raise RuntimeError('QEMU closed before QMP greeting: '+(out/'qemu.log').read_text(errors='replace')[-800:])
  assert 'QMP' in json.loads(greeting)
  def call(name,data=None):
   nonlocal seq
   seq+=1;row=dict(execute=name,id=seq)
   if data is not None:row['arguments']=data
   input_pipe.write(json.dumps(row).encode()+b'\n')
   while True:
    assert select.select([stream],[],[],10)[0],('QMP response timeout',name,p.poll())
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
   return dict(windows=surface[1],focus=surface[2],width=surface[3],height=surface[4],itonamiGoal=goal,windowRects=[list(surface[5+5*i:10+5*i]) for i in range(surface[1])],x=work[50],y=work[51],buttons=work[67],magic=work[72],keys=work[73],packets=work[75],clicks=work[76],lastKey=work[77],framesStarted=work[78],framesCompleted=work[79],draftGeneration=work[80],draftCommit=work[82],draftEnabled=work[84])
  def wait(name,predicate,timeout=120,record=True):
   end=time.monotonic()+timeout
   while time.monotonic()<end:
    assert p.poll() is None,('guest exited',p.returncode)
    s=state();(out/'last-state.json').write_text(json.dumps(s,indent=2)+'\n')
    if predicate(s) and s['framesStarted']==s['framesCompleted']:

     if record:events.append(dict(name=name,state=s))
     return s
    registers=hmp('info registers');(out/'registers-last.txt').write_text(registers)
    time.sleep(.2)
   raise AssertionError((name,'native desktop state not reached',s))
  def screenshot(name):
   assert hmp(f'screendump {name}.ppm')==''
   return ppm_png(out/(name+'.ppm'),out/(name+'.png'))
  def rendered_goal_glyph(name,cp):
   surface=struct.unpack('<2048I',(out/'surface.bin').read_bytes())
   assert surface[427]==0 and 0<surface[416]<=259,('invalid guest draw list',surface[416],surface[427])
   windows=[surface[5+5*i:10+5*i] for i in range(surface[1])]
   itonami=[window for window in windows if window[0]==2]
   assert len(itonami)==1,('Itonami window absent',windows)
   _,wx,wy,ww,wh=itonami[0]
   ops=[surface[480+6*i:486+6*i] for i in range(surface[416])]
   target=[op for op in ops if op[0]==2 and op[3]==goal_glyphs[cp]
           and wx+14<=op[1]<wx+ww-14 and wy+60<=op[2]<wy+100]
   assert len(target)==1,('goal glyph draw op absent or ambiguous',cp,target)
   _,x,y,_,width,_=target[0]
   assert width in (8,16)
   end=time.monotonic()+10
   attempts=0
   while time.monotonic()<end:
    attempts+=1
    pixels=screenshot(name)
    ink=sum(1 for row in range(y,y+16) for col in range(x,x+width)
            if all(channel<64 for channel in pixels[(row*1280+col)*3:(row*1280+col)*3+3]))
    if ink:
     visual_glyphs.append(dict(name=name,codepoint=ord(cp),glyph=goal_glyphs[cp],
                               x=x,y=y,width=width,inkPixels=ink,attempts=attempts))
     return pixels
    time.sleep(.1)
   raise AssertionError(('guest goal glyph did not reach QEMU scanout',cp,target[0]))
  call('qmp_capabilities')
  initial=wait('native-first-frame',lambda s:s['magic']==0x31545844 and s['framesCompleted']>=1)
  assert initial['windows']==0 and initial['focus']==0 and initial['keys']==0
  assert initial['itonamiGoal']=='Goal (RAM):\n'
  assert initial['draftEnabled']==0 and initial['draftGeneration']==0 and initial['draftCommit']==0
  initial_fuel=struct.unpack('<Q',dump(context+8,8,'desktop-fuel-initial.bin'))[0]
  assert 2**52<=initial_fuel<=2**53-1,('desktop fuel too short for interaction',initial_fuel)
  registers=hmp('info registers');(out/'registers-native-desktop.txt').write_text(registers)
  reg=lambda name:int(re.search(rf'\b{name}\s*=([0-9a-f]+)',registers,re.I)[1],16)
  assert reg('CR3')==context+cr3_offset and reg('CR0')&0x10000 and reg('EFER')&0x801==0x801
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
  goal_a_pixels=rendered_goal_glyph('itonami-goal-a','a')
  key('b');typed_b=wait('itonami-native-goal-ab',lambda s:s['lastKey']==48 and s['itonamiGoal']=='Goal (RAM):\nab' and s['framesCompleted']>typed_a['framesCompleted'])
  goal_ab_pixels=rendered_goal_glyph('itonami-goal-ab','b');assert goal_a_pixels!=goal_ab_pixels
  key('f5');disabled=wait('normal-profile-has-no-draft-commit',lambda s:s['lastKey']==63 and s['framesCompleted']>typed_b['framesCompleted'])
  assert disabled['draftEnabled']==0 and disabled['draftCommit']==0 and disabled['draftGeneration']==0 and disabled['itonamiGoal']=='Goal (RAM):\nab'
  key('backspace');deleted=wait('itonami-native-goal-backspace',lambda s:s['lastKey']==14 and s['itonamiGoal']=='Goal (RAM):\na' and s['framesCompleted']>typed_b['framesCompleted'])
  # Native minimize/restore: retain geometry and Goal, skip hidden windows
  # during Tab, never accept typing into a hidden window, restore via dock/key.
  itonami_rect=next(r for r in deleted['windowRects'] if r[0]==2)
  key('f2');hidden=wait('keyboard-minimizes-itonami',lambda s:s['focus']==1 and s['lastKey']==60 and s['framesCompleted']>deleted['framesCompleted'])
  assert next(r for r in hidden['windowRects'] if r[0]==2)==itonami_rect[:4]+[itonami_rect[4]+65536]
  key('b');ignored=wait('hidden-goal-ignores-typing',lambda s:s['lastKey']==48 and s['keys']>hidden['keys'])
  assert ignored['itonamiGoal']=='Goal (RAM):\na'
  key('tab');cycled=wait('tab-skips-minimized-window',lambda s:s['lastKey']==15 and s['keys']>ignored['keys'])
  assert cycled['focus']==1
  key('f2');all_hidden=wait('all-windows-minimized',lambda s:s['focus']==0 and s['lastKey']==60 and s['framesCompleted']>cycled['framesCompleted'])
  hidden_pixels=screenshot('all-minimized')
  ix,iy,iw,ih=itonami_rect[1:]
  assert hidden_pixels[3*((iy+80)*1280+ix+100):3*((iy+80)*1280+ix+100)+3]==bytes(expected_background(iy+80))
  dock_left=(1280-184)//2+8+44
  marker=3*((800-8)*1280+dock_left+16)
  assert hidden_pixels[marker:marker+3]==bytes((0x1a,0x3a,0x6b)), 'minimized app lost its running marker'
  def move_to(x,y):
   for _ in range(40):
    now=state();dx=x-now['x'];dy=y-now['y']
    if abs(dx)<=1 and abs(dy)<=1:return
    call('input-send-event',{'events':[{'type':'rel','data':{'axis':'x','value':max(-100,min(100,dx))}},{'type':'rel','data':{'axis':'y','value':max(-100,min(100,dy))}}]})
    wait('pointer-step',lambda s:s['packets']>now['packets'] and s['framesCompleted']>now['framesCompleted'],record=False)
   raise AssertionError(('pointer did not reach target',x,y,state()))
  def click():
   before_press=state()
   call('input-send-event',{'events':[{'type':'btn','data':{'down':True,'button':'left'}}]})
   pressed=wait('pointer-press',lambda s:s['buttons']==1 and s['framesCompleted']>before_press['framesCompleted'],record=False)
   call('input-send-event',{'events':[{'type':'btn','data':{'down':False,'button':'left'}}]})
   wait('pointer-release',lambda s:s['buttons']==0 and s['framesCompleted']>pressed['framesCompleted'],record=False)
  move_to(dock_left+18,800-28);click()
  restored=wait('dock-restores-itonami',lambda s:s['focus']==2 and s['buttons']==0 and s['framesCompleted']>all_hidden['framesCompleted'])
  assert restored['windows']==2 and restored['itonamiGoal']=='Goal (RAM):\na'
  assert next(r for r in restored['windowRects'] if r[0]==2)==itonami_rect
  rendered_goal_glyph('restored-goal','a')
  move_to(ix+iw-56,iy+14);click()
  pointer_hidden=wait('pointer-minimizes-itonami',lambda s:s['focus']==0 and s['buttons']==0 and s['framesCompleted']>restored['framesCompleted'])
  key('2');restored_key=wait('launcher-key-restores-itonami',lambda s:s['focus']==2 and s['lastKey']==3 and s['framesCompleted']>pointer_hidden['framesCompleted'])
  assert next(r for r in restored_key['windowRects'] if r[0]==2)==itonami_rect
  assert restored_key['itonamiGoal']=='Goal (RAM):\na'
  # Restore the other app, then return to Itonami for the original close check.
  key('1');wait('launcher-restores-other-window',lambda s:s['focus']==1 and s['lastKey']==2)
  key('2');wait('launcher-focuses-itonami',lambda s:s['focus']==2 and s['lastKey']==3)
  call('input-send-event',{'events':[{'type':'rel','data':{'axis':'x','value':80}},{'type':'rel','data':{'axis':'y','value':40}}]})
  moved=wait('mouse-moves-native-pointer',lambda s:s['x']>two['x'] and s['y']>two['y'] and s['packets']>two['packets'] and s['framesCompleted']>two['framesCompleted'])
  call('input-send-event',{'events':[{'type':'btn','data':{'down':True,'button':'left'}}]})
  clicked=wait('mouse-click-reduced',lambda s:s['clicks']==moved['clicks']+1 and s['buttons']==1 and s['framesCompleted']>moved['framesCompleted'])
  call('input-send-event',{'events':[{'type':'btn','data':{'down':False,'button':'left'}}]})
  released=wait('mouse-release-reduced',lambda s:s['buttons']==0 and s['framesCompleted']>clicked['framesCompleted'])
  key('esc');closed=wait('keyboard-closes-focused-card',lambda s:s['windows']==1 and s['lastKey']==1 and s['framesCompleted']>released['framesCompleted'])
  final=screenshot('desktop-after-input');assert first!=final
  assert pin(media)==before
  if iso:assert pin(iso)==iso_before
  report=dict(status='PASS_NATIVE_DESKTOP_INPUT_QEMU',layoutTable=pin(HERE.parent/'native'/'layout-table.json'),kernel=pin(kernel),efi=pin(efi),media=before,font=pin(font),firmware=pin(firmware),observer=pin(Path(__file__)),independentMedia=format_proof,events=events,renderedGoalGlyphs=visual_glyphs,initialFuelRemaining=initial_fuel,sealedGop=dict(base=base,bytes=size,width=width,height=height,stride=stride,format=fmt,pciBarContained=True),screenshots=['desktop-initial.png','itonami-goal-a.png','itonami-goal-ab.png','all-minimized.png','restored-goal.png','desktop-after-input.png'],guestEmulation='QEMU TCG',blockDevice=('q35 virtual optical EFI El Torito' if iso else 'q35 SATA with temporary overlay'),privatePageTables=True,currentDomain=73,nativeCDCI=False,BrowserCSSOMParity=False,dappsExecuted=False,preemptiveScheduler=False,completeKernel=False,physicalHardware=False)
  if iso:report.update(iso=iso_before,independentISO=iso_proof)
  (out/'native-desktop-qemu.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
 finally:
  if p.poll() is None:
   try:
    if stream:call('quit')
   except (OSError,ValueError,AssertionError):pass
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=5)
  input_pipe.close();stream.close()
  log.close();os.chdir(old)
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for n in ['media','efi','kernel','font','qemu','firmware','output']:p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--iso',type=Path)
 a=p.parse_args();main(*(getattr(a,n).resolve() for n in ['media','efi','kernel','font','qemu','firmware','output']),a.iso.resolve() if a.iso else None)
