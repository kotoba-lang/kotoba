#!/usr/bin/env python3
"""Compare synthetic office UI traces with and without read-only Wasm counters.

Usage: script AMU BUNSHO HYOKEISAN ZUHYO OUT CHROME
Counters are arena usage at guest exit, not historical peaks or OS measurements.
The instrumented Worker is an isolated observer, not the delivered artifact.
"""
import functools,hashlib,http.server,importlib.util,json,shutil,sys,threading,time
from pathlib import Path
if len(sys.argv)!=7:raise SystemExit(__doc__)
amu,bun,hy,zu,out,chrome=map(lambda s:Path(s).resolve(),sys.argv[1:]);out.mkdir(parents=True,exist_ok=False)
spec=importlib.util.spec_from_file_location('browser',amu/'scripts/seed/check-wasm32-browser.py');browser=importlib.util.module_from_spec(spec);spec.loader.exec_module(browser)
sha=lambda b:hashlib.sha256(b).hexdigest()
compiler=amu/'seed/bootstrap/aarch64-macos/amu-full-root.macho'
if sha(compiler.read_bytes())!='2c551579c06a0228029bb06bae177e93126ecbbc37d636d693c471dbac8d1536':raise ValueError('unrecognized compiler')
for build in (bun,hy,zu):
 receipt=json.loads((build/'build-receipt.json').read_text())
 for name,key in (('program.wasm','wasmSha256'),('program.kotoba','sourceSha256'),('worker.js','workerSha256')):
  if sha((build/name).read_bytes())!=receipt[key]:raise ValueError('candidate digest mismatch: '+name)
 if receipt['compilerSha256']!=sha(compiler.read_bytes()):raise ValueError('candidate compiler mismatch')
expected_runtime={'81-wasm32.kotoba':'0647a1ff4f59ba7cd239b3b53df671be99847622d1db91a8efc74259f1a4cc06',
 '82-wasm32-rt.kotoba':'5e7747e5186ed4107445303608d237ea85ea4933330e483b5250b89903514bc0',
 '77-aarch64-static-rt.kotoba':'a9d894c778f53b4b0de6bf86daaa18b4af40bf006bac8046171a242d2026fbcd',
 '73-keyword-intern.kotoba':'e0117cb3ae77b3464bd06b5399f83c040c00fbbd805baca4bfc2bae064d70fe6'}
for name,digest in expected_runtime.items():
 if sha((amu/'seed'/name).read_bytes())!=digest:raise ValueError('unrecognized runtime source: '+name)
source_81=(amu/'seed/81-wasm32.kotoba').read_text();source_77=(amu/'seed/77-aarch64-static-rt.kotoba').read_text()
if '(def XW-CTX 4096)' not in source_81 or '(defn- kxrt-g [] :i64 (+ (kxrt-ctx) 1024))' not in (amu/'seed/82-wasm32-rt.kotoba').read_text():raise ValueError('runtime context changed')
# seed/77 documents these as current allocation counters, not high-water marks.
for check in ('(kxrt-gl 8)', '(kxrt-gl 32)', '(kxrt-gl 48)', '(kxrt-gl 64)', '(kxrt-gl 704)'):
 if check not in source_77:raise ValueError('runtime accounting changed')
needle='    return { exit, stdout: out, stderr: concat(stderr), wasmTrap, capLog,'
replacement='''    let arenaProfile = null;
    if (memory && exit === 0 && !wasmTrap) {
      const d = new DataView(memory.buffer), g = 4096 + 1024;
      const read = o => Number(d.getBigUint64(g + o, true));
      arenaProfile = {linearBytes: memory.buffer.byteLength, pairs: read(8), poolBytes: read(32), vectors: read(48), items: read(64), regions: read(704), keywordRows: read(784)};
    }
    return { arenaProfile, exit, stdout: out, stderr: concat(stderr), wasmTrap, capLog,'''
inject='''(()=>{const Base=window.Worker;window.__arena=[];window.Worker=class extends Base {constructor(...a){super(...a);this.addEventListener('message',e=>{if(e.data?.arenaProfile)window.__arena.push({operation:this.operation,...e.data.arenaProfile})})}postMessage(data,...rest){this.operation=data.args?.[0]||'unknown';return super.postMessage(data,...rest)}}})()'''
class Quiet(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass

def run(app,build,instrument):
 case=out/(app+('-observed' if instrument else '-baseline'));case.mkdir();site=case/'site';shutil.copytree(build,site);(case/'profile').mkdir()
 w=site/'worker.js';original=w.read_text();assert original.count(needle)==1
 if instrument:w.write_text(original.replace(needle,replacement))
 assert (site/'program.wasm').read_bytes()==(build/'program.wasm').read_bytes()
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(site)));threading.Thread(target=server.serve_forever,daemon=True).start();pipe=browser.Pipe(str(chrome),case/'profile')
 try:
  t=pipe.call('Target.createTarget',{'url':'about:blank'})['targetId'];s=pipe.call('Target.attachToTarget',{'targetId':t,'flatten':True})['sessionId'];pipe.call('Page.enable',{},s)
  pipe.call('Page.addScriptToEvaluateOnNewDocument',{'source':inject},s);pipe.call('Page.navigate',{'url':f'http://127.0.0.1:{server.server_port}/index.html'},s)
  def ev(x,awaited=False):
   r=pipe.call('Runtime.evaluate',{'expression':x,'returnByValue':True,'awaitPromise':awaited},s)
   if 'exceptionDetails' in r:raise ValueError(r['exceptionDetails'])
   return r.get('result',{}).get('value')
  def wait(x,label):
   end=time.time()+90
   while time.time()<end:
    if ev(x):return
    time.sleep(.1)
   raise TimeoutError(app+' '+label+': '+str(ev('document.getElementById("status")?.textContent')))
  initial={'bunsho':'b0','hyokeisan':'c0','zuhyo':'body'}[app];wait('document.querySelector("[data-k='+initial+']")!==null','initial')
  def edit(key,value):
   ev('document.getElementById("status").textContent="待機";(()=>{let e=document.querySelector("[data-k='+key+']");e.value='+json.dumps(value,ensure_ascii=False)+';e.dispatchEvent(new Event("input",{bubbles:true}))})()')
   wait('document.getElementById("status").textContent==="保存しました"','save '+key)
  def click(key,condition):
   ev('document.getElementById("status").textContent="待機";document.querySelector("[data-k='+key+']").click()')
   wait(condition+' && document.getElementById("status").textContent==="保存しました"','click '+key)
  if app=='bunsho':
   edit('b0','本文😀'+'あ'*150);click('add-h3','document.querySelector("[data-k=b2]")!==null');edit('b2','見出し')
  elif app=='hyokeisan':
   edit('c0','6');edit('c1','4');edit('c4','=A1+B1');wait('document.querySelector("[data-k=c4]")?.parentElement.querySelector(".value")?.textContent==="10"','formula')
  else:
   edit('body','本文😀\n二行目');click('add','document.querySelector(".stats")?.textContent==="2 / 2"');edit('heading','二枚目')
  stored=ev('''new Promise((resolve,reject)=>{let o=indexedDB.open('itonami.office.APP.v2',1);o.onsuccess=()=>{let d=o.result,t=d.transaction('records'),g=t.objectStore('records').get('current');g.onsuccess=()=>resolve(g.result.value);t.oncomplete=()=>d.close()};o.onerror=()=>reject(Error('open'))})'''.replace('APP',app),True)
  metrics=ev('window.__arena');
  if instrument and (not metrics or any(not x['linearBytes'] for x in metrics)):raise ValueError('observer missing')
  if not instrument and metrics:raise ValueError('unmodified worker emitted diagnostics')
  result={'snapshotSha256':sha(stored.encode()),'metrics':metrics,'workerSha256':sha(w.read_bytes()),'originalWorkerSha256':sha(original.encode()),'wasmSha256':sha((site/'program.wasm').read_bytes())}
  return result
 finally:pipe.close();server.shutdown();server.server_close()
results={}
for app,build in [('bunsho',bun),('hyokeisan',hy),('zuhyo',zu)]:
 normal=run(app,build,False);observed=run(app,build,True)
 if normal['snapshotSha256']!=observed['snapshotSha256']:raise ValueError(app+' instrument changed state')
 metrics=observed['metrics'];groups={}
 for m in metrics:
  group=groups.setdefault(m['operation'],{'samples':0,'max':{}});group['samples']+=1
  for k,v in m.items():
   if k!='operation':group['max'][k]=max(group['max'].get(k,0),v)
 if not {'init','view','step'}.issubset(groups):raise ValueError(app+' missing operation profile')
 results[app]={'wasmSha256':normal['wasmSha256'],'originalWorkerSha256':normal['workerSha256'],'observedWorkerSha256':observed['workerSha256'],'finalSnapshotSha256':normal['snapshotSha256'],'operations':groups}
 print(app,'PASS',flush=True)
report={'status':'PASS_OFFICE_WASM_EXIT_COUNTERS_SYNTHETIC','observerSha256':sha(Path(__file__).read_bytes()),'compilerSha256':sha(compiler.read_bytes()),'runtimeSourceSha256':{n:sha((amu/'seed'/n).read_bytes()) for n in ('81-wasm32.kotoba','82-wasm32-rt.kotoba','77-aarch64-static-rt.kotoba','73-keyword-intern.kotoba')},'apps':results,'scope':'Synthetic UI traces in Chrome; instrumented worker reads current counters only at successful guest exit, not transient peaks, crash behavior, OS/QEMU or real user data.'}
(out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(report['status'],flush=True)
