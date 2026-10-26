import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const imports=JSON.parse(fs.readFileSync(path.join(root,'maintenance/capability-source-imports.json'))).imports;
let modules=0,unbound=0;
for(const origin of imports)for(const source of origin.files){
  if(!source.path?.endsWith('.wasm'))continue;
  const bytes=fs.readFileSync(path.join(root,source.path));assert(WebAssembly.validate(bytes));modules++;
  if(['http/fetch','llm/infer'].some(id=>origin.id==='kotoba.capability.'+id.replace('/','.'))){
    const module=new WebAssembly.Module(bytes);assert.deepEqual(WebAssembly.Module.imports(module),[]);
    const instance=new WebAssembly.Instance(module);
    const field=origin.id.endsWith('http.fetch')?'http_fetch':'llm_infer';
    assert.equal(instance.exports[field](...Array(field==='http_fetch'?4:6).fill(0)),-3);unbound++;
  }
}
assert.equal(modules,10);assert.equal(unbound,2);
console.log('capability artifacts: 10 existing Wasm cores validate; both unbound network/inference cores execute with result -3 and no host imports');
