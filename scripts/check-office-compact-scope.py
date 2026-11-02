#!/usr/bin/env python3
"""Contrast instrumented and original Wasm on an arena-scope allocation.

Usage: script AMU_DIR LAB_COMPILER NEW_OUTPUT_DIR CHROME
"""
import functools,http.server,importlib.util,json,sys,threading,time
from pathlib import Path
if len(sys.argv)!=5:raise SystemExit(__doc__)
amu=Path(sys.argv[1]).resolve();instrumented=Path(sys.argv[2]).resolve();out=Path(sys.argv[3]).resolve();chrome=Path(sys.argv[4]).resolve();out.mkdir(parents=True,exist_ok=False)
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
mac=module('mac',amu/'scripts/seed/check-aiueos-user-macos-native.py');b=module('browser',amu/'scripts/seed/check-wasm32-browser.py')
source='''(ns probe (:export [main]))
(defn main [] :i64
  (let [value (arena-scope (let [v (vector-alloc 1024) changed (vector-assoc! v 0 23)] (vector-at v 0)))]
    (if (= value 23) 0 1)))
'''
(out/'probe.kotoba').write_text(source)
for name,compiler in [('baseline',amu/'seed/bootstrap/aarch64-macos/amu-full-root.macho'),('instrumented',instrumented)]:mac.native_run(compiler,out,'compile','probe.kotoba','--target','wasm32-browser','--output',name+'.wasm')
w=(amu/'runtime/wasm32-browser-static-host.js').read_text();needle='    return { exit, stdout: out, stderr: concat(stderr), wasmTrap, capLog,'
rep='''    let probe = null;
    if (memory && exit === 0 && !wasmTrap) { const d = new DataView(memory.buffer), g = 5120;
      probe = {items: Number(d.getBigUint64(g+64,true)), peakItems: Number(d.getBigUint64(g+3024,true))}; }
    return { probe, exit, stdout: out, stderr: concat(stderr), wasmTrap, capLog,'''
assert w.count(needle)==1;(out/'worker.js').write_text(w.replace(needle,rep))
(out/'index.html').write_text('''<!doctype html><script>window.go=async name=>{let w=new Worker('worker.js');let bytes=await(await fetch(name+'.wasm')).arrayBuffer();return await new Promise((resolve,reject)=>{w.onmessage=e=>{w.terminate();resolve(e.data)};w.onerror=reject;w.postMessage({bytes,fuel:25000000,allow:[],args:[]})})}</script>''')
(out/'profile').mkdir()
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(out)));threading.Thread(target=server.serve_forever,daemon=True).start();pipe=b.Pipe(str(chrome),out/'profile')
try:
 t=pipe.call('Target.createTarget',{'url':'about:blank'})['targetId'];s=pipe.call('Target.attachToTarget',{'targetId':t,'flatten':True})['sessionId'];pipe.call('Page.enable',{},s);pipe.call('Page.navigate',{'url':f'http://127.0.0.1:{server.server_port}/index.html'},s)
 def ev(x,awaited=False):
  r=pipe.call('Runtime.evaluate',{'expression':x,'returnByValue':True,'awaitPromise':awaited},s)
  if 'exceptionDetails' in r:raise ValueError(r['exceptionDetails'])
  return r.get('result',{}).get('value')
 for i in range(100):
  if ev('typeof window.go==="function"'):break
  time.sleep(.1)
 else:raise TimeoutError('page')
 res={n:ev('window.go('+json.dumps(n)+')',True) for n in ('baseline','instrumented')}
 for r in res.values():
  if r['exit']!=0 or r['wasmTrap'] is not None or not r['report'].startswith('{:status :ok :result 0'):raise ValueError('fixture failed: '+repr(r))
 if res['baseline']['probe']['peakItems']!=0:raise ValueError('baseline control unexpectedly instrumented')
 p=res['instrumented']['probe']
 if p['peakItems']<1024 or p['peakItems']<=p['items']:raise ValueError('scope peak not observed: '+repr(p))
 report={'status':'PASS_WASM_SCOPE_PEAK_CONTROL','baseline':res['baseline']['probe'],'instrumented':p,'scope':'synthetic wasm arena-scope control, not OS/QEMU'};(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
finally:pipe.close();server.shutdown();server.server_close()
