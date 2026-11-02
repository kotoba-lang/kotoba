#!/usr/bin/env python3
"""Contrast a baseline and compact Wasm runtime on a synthetic near-limit pull.

Usage: script AMU BASELINE_BUILD COMPACT_BUILD LAB_DIR PULL_JSON NEW_OUTPUT CHROME
This is a lab qualification, not a real migration or an OS/QEMU test.
"""
import hashlib,importlib.util,json,sys
from pathlib import Path
if len(sys.argv)!=8:raise SystemExit(__doc__)
amu,normal,compact,lab,fixture,out,chrome=map(lambda x:Path(x).resolve(),sys.argv[1:]);out.mkdir(parents=True,exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
r0=json.loads((normal/'build-receipt.json').read_text());r1=json.loads((compact/'build-receipt.json').read_text());labinfo=json.loads((lab/'build.json').read_text())
for build,receipt in ((normal,r0),(compact,r1)):
 for name,key in (('program.wasm','wasmSha256'),('program.kotoba','sourceSha256')):
  if sha((build/name).read_bytes())!=receipt[key]:raise ValueError('candidate digest mismatch: '+name)
if r0['sourceSha256']!=r1['sourceSha256'] or r1['compilerSha256']!=labinfo['instrumentedCompilerSha256']:raise ValueError('source/compiler mismatch')
spec=importlib.util.spec_from_file_location('check',amu/'scripts/seed/check-js-browser.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
raw=fixture.read_text();runs=[]
for name,path in [('normal',normal),('compact',compact)]:
 for fuel in (25000000,100000000):runs.append((name+'-'+str(fuel),path/'program.wasm',{'allow':[37,38],'args':['legacy-pull',raw],'fuel':fuel}))
_,results=h.run_js(str(chrome),out,runs,timeout=600);report={}
for name,item in results.items():
 text=item.get('output') or '';report[name]={'exit':item['exit'],'report':item['report'],'stderr':item['stderr'][-400:],'outputSha256':hashlib.sha256(text.encode()).hexdigest(),'outputBytes':len(text.encode())}
for fuel in (25000000,100000000):
 n=report['normal-'+str(fuel)];c=report['compact-'+str(fuel)]
 if n['exit']!=0 or not (n['report'] or '').startswith('{:status :ok :result 0'):raise ValueError('baseline failed')
 if c['exit']!=120 or 'vector-table-exhausted' not in c['stderr']:raise ValueError('expected compact vector refusal missing')
if report['normal-25000000']['outputSha256']!=report['normal-100000000']['outputSha256']:raise ValueError('baseline outputs differ')
result={'status':'PASS_COMPACT_PULL_REFUSAL_CHARACTERIZATION','fixtureSha256':sha(fixture.read_bytes()),'sourceSha256':r0['sourceSha256'],'compilerSha256':r1['compilerSha256'],'cases':report,'scope':'synthetic near-limit pull; no real data or QEMU'}
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'],flush=True)
