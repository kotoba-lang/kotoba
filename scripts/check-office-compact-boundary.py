#!/usr/bin/env python3
"""Compare baseline and compact runtime on bounded Bunsho snapshots.

Usage: script AMU BASELINE_BUILD COMPACT_BUILD LAB_DIR NEW_OUTPUT CHROME
The lab is not a production compiler or an OS/QEMU runtime.
"""
import hashlib,importlib.util,json,sys
from pathlib import Path
if len(sys.argv)!=7:raise SystemExit(__doc__)
amu,normal,small,lab,out=map(lambda x:Path(x).resolve(),sys.argv[1:6]);chrome=sys.argv[6];out.mkdir(parents=True,exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
r0=json.loads((normal/'build-receipt.json').read_text());r1=json.loads((small/'build-receipt.json').read_text());experiment=json.loads((lab/'build.json').read_text())
for build,receipt in ((normal,r0),(small,r1)):
 for name,key in (('program.wasm','wasmSha256'),('program.kotoba','sourceSha256')):
  if sha((build/name).read_bytes())!=receipt[key]:raise ValueError('candidate digest mismatch: '+name)
if r0['sourceSha256']!=r1['sourceSha256'] or r1['compilerSha256']!=experiment['instrumentedCompilerSha256']:raise ValueError('source/compiler mismatch')
spec=importlib.util.spec_from_file_location('harness',amu/'scripts/seed/check-js-browser.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
def frame(x):return str(len(x.encode('utf-8')))+':'+x
runs=[]
for n in (2,4,8,16,24,32):
 data='BS3|1'+''.join(map(frame,['境界😀','edit',str(n)]+sum((['p','x'*1024] for _ in range(n)),[])))
 assert len(data.encode())<35000
 for name,path in [('normal',normal),('compact',small)]:runs.append((name+'-'+str(n),path/'program.wasm',{'allow':[37,38],'args':['view',data],'fuel':100000000}))
version,results=h.run_js(chrome,out,runs,timeout=600)
report={'status':'PASS_COMPACT_BOUNDARY_CHARACTERIZATION','compilerSha256':r1['compilerSha256'],'sourceSha256':r1['sourceSha256'],'browser':version,'cases':{},'scope':'Synthetic Bunsho snapshot; bounded runtime is experimental and not OS/QEMU or production'}
for n in (2,4,8,16,24,32):
 row={}
 for name in ('normal','compact'):
  v=results[name+'-'+str(n)];o=v.get('output') or '';row[name]={'exit':v.get('exit'),'report':v.get('report'),'trap':v.get('wasmTrap'),'stderr':(v.get('stderr') or '')[-300:],'outputSha256':hashlib.sha256(o.encode()).hexdigest(),'outputBytes':len(o.encode())}
 row['sameOutput']=row['normal']['exit']==0 and row['compact']['exit']==0 and row['normal']['outputSha256']==row['compact']['outputSha256']
 report['cases'][str(n)]=row
 if not (row['normal']['exit']==0 and (row['normal']['report'] or '').startswith('{:status :ok :result 0')):raise ValueError('baseline refused '+str(n))
 if n<=4 and not row['sameOutput']:raise ValueError('small case differs '+str(n))
 if n>=8 and not (row['compact']['exit']==120 and ':arena :string-pool' in row['compact']['stderr']):raise ValueError('expected budget refusal missing '+str(n))
(out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:{'normal':v['normal']['exit'],'compact':v['compact']['exit'],'sameOutput':v['sameOutput'],'compactError':v['compact']['stderr']} for k,v in report['cases'].items()},ensure_ascii=False),flush=True)
