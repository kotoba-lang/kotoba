#!/usr/bin/env python3
"""Compare two draft policy Wasm builds using synthetic Unicode frame cases.

Usage: script AMU OLD_WASM NEW_WASM NEW_OUTPUT CHROME
This is policy parity, not storage, QEMU or release qualification.
"""
import hashlib,importlib.util,json,random,re,sys
from pathlib import Path
if len(sys.argv)!=6:raise SystemExit(__doc__)
amu,old,new,out=map(lambda x:Path(x).resolve(),sys.argv[1:5]);chrome=sys.argv[5];out.mkdir(parents=True,exist_ok=False)
spec=importlib.util.spec_from_file_location('browser',amu/'scripts/seed/check-js-browser.py');browser=importlib.util.module_from_spec(spec);spec.loader.exec_module(browser)
f=lambda s:str(len(s.encode()))+':'+s
id='a'*64
def make(key,wire,count='1',value='入力😀'):
 return ['classify','100','35000','1',id,'string','old','state',id,'string','old','state','1',key,value,count,wire]
rng=random.Random(780); alphabet=['a','Z','0','雪','😀','é','|',':','\n'];cases=[]
for i in range(30):
 key=''.join(rng.choice(alphabet) for _ in range(1+rng.randrange(15)))
 cases.append((f'visible-{i}',make(key,f(key))))
 cases.append((f'absent-{i}',make(key,f(key+'x'))))
for i,w in enumerate(['1:雪','2:雪','01:a','3:ab','4:ab😀','雪:a','0:x','1:aX','0:', '128:'+('雪'*42+'ab')]):
 cases.append((f'frame-{i}',make('body',w)))
cases += [('over-value',make('body',f('body'),value='x'*65537)),('max-value',make('body',f('body'),value='x'*65536)),('max-unicode',make('body',f('body'),value='😀'*32768))]
paths=[('old',old),('new',new)]
version,results=browser.run_js(chrome,out,[(name+'-'+label,path,{'allow':[37,38],'args':a,'fuel':100000000}) for name,a in cases for label,path in paths],timeout=600)
for name,_ in cases:
 a,b=[results[name+'-'+label] for label,_ in paths]
 for x in (a,b):
  if x.get('exit')!=0 or x.get('wasmTrap') is not None or not re.search(r'\{:status :ok :result 0(?:\s|\})',x.get('report') or ''):raise ValueError((name,x.get('report'),x.get('stderr')))
 if a.get('output')!=b.get('output'):raise ValueError((name,a.get('output'),b.get('output')))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report={'status':'PASS_DRAFT_POLICY_PARITY','cases':len(cases),'browser':version,'oldWasmSha256':sha(old),'newWasmSha256':sha(new),'scope':'deterministic synthetic browser policy parity; no QEMU or production data'}
(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'],len(cases))
