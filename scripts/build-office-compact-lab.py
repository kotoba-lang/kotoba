#!/usr/bin/env python3
"""Build an isolated experimental compact Wasm runtime compiler; not for release.

Usage: script AMU_DIR NEW_OUTPUT_DIR
"""
import hashlib,importlib.util,json,sys
from pathlib import Path
from types import SimpleNamespace
if len(sys.argv)!=3:raise SystemExit(__doc__)
amu=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=False)
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
scope=load('scope',amu/'scripts/seed/check-macos-arena-scope.py');gate=scope.module()
compiler,_,packager,_,_,_=gate.bootstrap_inputs(SimpleNamespace(compiler_image=None,compiler_sha256=None,packager_image=None,packager_sha256=None))
names=[x for x in (amu/'seed/FULL-MANIFEST').read_text().splitlines() if x and not x.startswith('#')]
old='(defn- kxrt-gs [k :i64 v :i64] :i64 (kxrt-store64 (+ (kxrt-g) k) v))'
new='''(defn- kxrt-gs [k :i64 v :i64] :i64
  (let [written (kxrt-store64 (+ (kxrt-g) k) v)
        slot (cond (= k 8) 3000 (= k 32) 3008 (= k 48) 3016 (= k 64) 3024
                   (= k 704) 3032 (= k 784) 3040 :else 0)
        recorded (if (and (> slot 0) (> v (kxrt-load64 (+ (kxrt-g) slot))))
                   (kxrt-store64 (+ (kxrt-g) slot) v) 0)] written))'''
parts=[]
for name in names:
 text=(amu/name).read_text()
 if name=='seed/82-wasm32-rt.kotoba':
  if text.count(old)!=1:raise ValueError('instrumentation anchor changed')
  text=text.replace(old,new)
  limits={'KXRT-PAIRS':65536,'KXRT-POOL':1048576,'KXRT-VECTORS':8192,'KXRT-REGIONS':8192,'KXRT-ITEMS':131072,'KXRT-VECTOR-MAX':131072,'KXRT-VALUE-MAX':262144}
  import re
  for key,value in limits.items():
   text,n=re.subn(r'\(def '+key+r' \d+\)',f'(def {key} {value})',text,count=1)
   if n!=1:raise ValueError('missing limit '+key)
 if name=='seed/73-keyword-intern.kotoba':
  if text.count('(kxrt-map 6291456)')!=1 or text.count('(>= n 262144)')!=1:raise ValueError('keyword limits changed')
  text=text.replace('(kxrt-map 6291456)','(kxrt-map 98304)').replace('(>= n 262144)','(>= n 4096)')
 parts.append(text+'\n')
unity=''.join(parts);result=scope.build(gate,compiler,packager,out,'peak-compiler',unity)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report={'compilerSha256':sha(compiler),'packagerSha256':sha(packager),'unitySha256':sha(out/'peak-compiler.kotoba'),'instrumentedCompilerSha256':sha(result),'insertion':new,'slots':[3000,3008,3016,3024,3032,3040], 'limits':limits, 'keywordRows':4096,'scope':'temporary compact and instrumented Wasm runtime experiment, not a release compiler'}
(out/'build.json').write_text(json.dumps(report,indent=2)+'\n');print('BUILT_INSTRUMENTED_COMPILER',result,flush=True)
