#!/usr/bin/env python3
"""Exercise actual office draft policy bounds in experimental compact Wasm.

Usage: script AMU COMPACT_COMPILER NEW_OUTPUT CHROME
Synthetic data only; this is not an OS/QEMU or production-storage test.
"""
import hashlib,importlib.util,json,re,sys
from pathlib import Path
if len(sys.argv)!=5:raise SystemExit(__doc__)
amu,compiler,out=map(lambda x:Path(x).resolve(),sys.argv[1:4]);chrome=sys.argv[4]
out.mkdir(parents=True,exist_ok=False)
root=Path(__file__).resolve().parents[1]/'lib/kotoba.aiueos/os/aiueos/kotoba/aiueos'
source=(root/'draft_policy.kotoba').read_text();driver=(root/'draft_policy_browser.kotoba').read_text()
pn='(ns aiueos.draft-policy (:export [classify classify-chunks units]))'
dn='(ns aiueos.draft-policy-browser\n  (:export [main])\n  (:capabilities [:cli/args :io/write])\n  (:require [aiueos.draft-policy :as policy]))'
if source.count(pn)!=1 or driver.count(dn)!=1:raise ValueError('namespace changed')
staged=source.replace(pn,'(ns aiueos.draft-policy-browser (:export [main]))',1)+'\n'+driver.replace(dn,'',1).replace('policy/classify-chunks','classify-chunks').replace('policy/units','units')
(out/'policy.kotoba').write_text(staged)
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
mac=load('mac',amu/'scripts/seed/check-aiueos-user-macos-native.py');browser=load('browser',amu/'scripts/seed/check-js-browser.py')
mac.native_run(compiler,out,'compile','policy.kotoba','--target','wasm32-browser','--output','policy.wasm')
id='a'*64
frame=lambda s:str(len(s.encode()))+':'+s
def args(entries,keys,raw='80000'):
 return ['classify',raw,'35000','1',id,'string','old','state',id,'string','old','state',str(len(entries))]+[v for pair in entries for v in pair]+[str(len(keys)),''.join(map(frame,keys))]
keys=['body']+[str(i).zfill(3)+'x'*125 for i in range(511)]
bad=args([('body','x')],['body']);bad[-1]='1:雪'
cases=[('small',args([('body','x')],['body']),'2\n'),('max-ascii',args([('body','x'*65536)],['body']),'2\n'),('over-ascii',args([('body','x'*65537)],['body']),'0\n'),('max-unicode',args([('body','😀'*32768)],['body'],raw='70000'),'2\n'),('max-visible',args([('body','x')],keys,raw='100'),'2\n'),('split-unicode',bad,'0\n'),('near-million',args([(f'key-{i}','x'*30000) for i in range(33)],[f'key-{i}' for i in range(33)],raw='990900'),'2\n')]
page=out/'browser';page.mkdir();version,results=browser.run_js(chrome,page,[(name,out/'policy.wasm',{'allow':[37,38],'args':a,'fuel':100000000}) for name,a,_ in cases],timeout=600)
for name,_,expected in cases:
 r=results[name]
 if r.get('exit')!=0 or r.get('wasmTrap') is not None or r.get('output')!=expected or not re.search(r'\{:status :ok :result 0(?:\s|\})',r.get('report') or ''):raise ValueError((name,r.get('exit'),r.get('report'),r.get('stderr')))
sha=lambda b:hashlib.sha256(b).hexdigest()
report={'status':'PASS_COMPACT_DRAFT_POLICY','browser':version,'sourceSha256':sha(source.encode()),'driverSha256':sha(driver.encode()),'compilerSha256':sha(compiler.read_bytes()),'wasmSha256':sha((out/'policy.wasm').read_bytes()),'cases':[x[0] for x in cases],'scope':'synthetic browser resource test; no OS/QEMU, real storage migration or release'}
(out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
