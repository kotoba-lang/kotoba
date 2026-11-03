#!/usr/bin/env python3
"""Exercise the OS office view parser with actual bounded Bunsho views.

Usage: script AMU BUNSHO_BUILD COMPACT_COMPILER NEW_OUTPUT CHROME
Experimental Wasm is a resource probe, not an Itonami OS or QEMU run.
"""
import hashlib, importlib.util, json, re, sys
from pathlib import Path
if len(sys.argv)!=6:raise SystemExit(__doc__)
amu,build,compiler,out=map(lambda x:Path(x).resolve(),sys.argv[1:5]);chrome=sys.argv[5]
out.mkdir(parents=True,exist_ok=False)
root=Path(__file__).resolve().parents[1]
source=(root/'lib/kotoba.aiueos/os/aiueos/kotoba/aiueos/office_view.kotoba').read_text()
test=(root/'lib/kotoba.aiueos/test/aiueos/office_view_native_test.kotoba').read_text()
source=source.split('\n',1)[1]
test,n=re.subn(r'^\(ns aiueos\.office-view-native-test\s+\(:export \[main\]\)\s+\(:capabilities \[:cli/args :io/write\]\)\s+\(:require \[aiueos\.office-view :as view\]\)\)','',test,count=1)
if n!=1:raise ValueError('test namespace changed')
staged='(ns office-test (:export [main]))\n'+source+'\n'+test.replace('view/','')
(out/'program.kotoba').write_text(staged)
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
mac=load('mac',amu/'scripts/seed/check-aiueos-user-macos-native.py')
h=load('browser',amu/'scripts/seed/check-js-browser.py')
mac.native_run(compiler,out,'compile','program.kotoba','--target','wasm32-browser','--output','program.wasm')
sha=lambda x:hashlib.sha256(x).hexdigest()
r=json.loads((build/'build-receipt.json').read_text())
if sha((build/'program.kotoba').read_bytes())!=r['sourceSha256'] or sha((build/'program.wasm').read_bytes())!=r['wasmSha256']:raise ValueError('candidate receipt mismatch')
f=lambda s:str(len(s.encode('utf-8')))+':'+s
small='BS1|'+''.join(map(f,['無題の文書','edit','2','h1','itonami Bunsho','p','Write here.']))
maximum='BS3|1'+''.join(map(f,['題'*341+'x','edit','32']+sum((['p','x'*1024] for _ in range(32)),[])))
gen=out/'generate';gen.mkdir()
version,views=h.run_js(chrome,gen,[(name,build/'program.wasm',{'allow':[37,38],'args':['view',value],'fuel':100000000}) for name,value in [('small',small),('max',maximum)]],timeout=300)
for name,item in views.items():
 if item.get('exit')!=0 or not (item.get('report') or '').startswith('{:status :ok :result 0'):raise ValueError(name+' generation failed')
wire=views['max']['output'];data=wire.encode();p=4;idx=0;last=-1
while p<len(data)-1:
 fields=[]
 for _ in range(8):
  end=data.index(b':',p);size=int(data[p:end]);p=end+1;fields.append(data[p:p+size].decode());p+=size
 if fields[3]=='b31':last=idx
 idx+=1
if idx!=466 or last<0:raise ValueError('unexpected maximum view')
cases=[('small',[views['small']['output'],''],0,'46:div\n'),('maximum',[wire,''],0,'466:div\n'),
       ('last-action',[wire,'current',str(last),'input','最後😀'],0,'app|input|b31|最後😀\n'),
       ('stale-action',[wire,'stale-generation',str(last),'input','x'],3,''),
       ('invalid-boundary',['BV2|1:é3:bad\n',''],3,'')]
target=out/'parse';target.mkdir()
_,results=h.run_js(chrome,target,[(name,out/'program.wasm',{'allow':[37,38],'args':args,'fuel':100000000}) for name,args,_,_ in cases],timeout=300)
for name,_,expected,output in cases:
 item=results[name]
 if item.get('exit')!=0 or item.get('wasmTrap') is not None or item.get('output')!=output or not re.search(rf'\{{:status :ok :result {expected}(?:\s|\}})',item.get('report') or ''):raise ValueError((name,item.get('exit'),item.get('report'),item.get('stderr')))
report={'status':'PASS_COMPACT_OFFICE_VIEW','browser':version,'sourceSha256':sha(staged.encode()),'compilerSha256':sha(compiler.read_bytes()),'wasmSha256':sha((out/'program.wasm').read_bytes()),'bunshoSourceSha256':r['sourceSha256'],'bunshoWasmSha256':r['wasmSha256'],'viewBytes':len(wire.encode()),'nodes':idx,'cases':[x[0] for x in cases],'scope':'synthetic browser resource test; not OS/QEMU execution or release'}
(out/'receipt.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(report['status'])
