import {loadPyodide} from 'pyodide';
function rpc(operation, payload) {
  const buffer=new SharedArrayBuffer(1048584), state=new Int32Array(buffer,0,2);
  self.postMessage({kind:'rpc',operation,payload:JSON.parse(payload),buffer});
  if(Atomics.wait(state,0,0,60000)==='timed-out') throw Error('bridge request timed out');
  const response=JSON.parse(new TextDecoder().decode(new Uint8Array(buffer,8,Atomics.load(state,1)).slice()));
  if(response.error) throw Error(response.error);
  return JSON.stringify(response.result);
}
self.onmessage=async ({data})=>{
 try {
  const py=await loadPyodide({indexURL:new URL('./pyodide/',self.location.href).href});
  const manifest=await (await fetch(new URL('./hermes-dependencies.json',self.location.href))).json();
  await py.loadPackage(manifest.seeds);
  py.globals.set('_kuro_wheels',py.toPy(manifest.packages.filter(p=>p.path.startsWith('wheels/')).map(p=>new URL(p.path,self.location.href).href)));
  await py.runPythonAsync('import micropip\nawait micropip.install(_kuro_wheels, deps=False)');
  const sourceManifest = await (await fetch(new URL('./hermes-source.json',self.location.href))).json();
  const sourceResponse = await fetch(data.sourceUrl);
  if(!sourceResponse.ok) throw Error('Hermes source snapshot unavailable');
  const archive = await sourceResponse.arrayBuffer();
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', archive)),b=>b.toString(16).padStart(2,'0')).join('');
  if(digest!==sourceManifest.sha256 || sourceManifest.revision!=='4f649c65e35beed816f9a9ec5647d33133a25abf') throw Error('unqualified Hermes source snapshot');
  py.globals.set('_kuro_archive',py.toPy(new Uint8Array(archive)));
  py.globals.set('_kuro_rpc',rpc);
  py.globals.set('_kuro_emit',(event,text)=>{if(typeof text==='string' && text)self.postMessage({kind:'event',event,text});});
  py.globals.set('_kuro_inputs',py.toPy(data));
  const adapter=await (await fetch(new URL('./hermes-adapter.py',self.location.href))).text();
  await py.runPythonAsync(adapter);
  const result=await py.runPythonAsync(data.code || 'run_browser_agent(_kuro_inputs["prompt"])');
  py.globals.set('_kuro_result',result);
  self.postMessage({kind:'done',result:JSON.parse(py.runPython('json.dumps(_kuro_result, default=str)'))});
 } catch(error) {self.postMessage({kind:'done',error:String(error.message||error)});}
};
