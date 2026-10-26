// Browser-origin conversation snapshots. Commit only completed turns, never credentials.
const MAX_BYTES=4*1024*1024;
function open() {
  return new Promise((resolve,reject)=>{
    const request=indexedDB.open('kuro-hermes-sessions',1);
    request.onupgradeneeded=()=>request.result.createObjectStore('sessions',{keyPath:'id'});
    request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
  });
}
export function validateSession(value) {
  if(!value || value.version!==1 || typeof value.id!=='string' || !value.id || !Number.isSafeInteger(value.revision) || value.revision<1 ||
    !Array.isArray(value.messages) || typeof value.systemPrompt!=='string' || !value.systemPrompt || typeof value.identity!=='string') throw Error('invalid saved Hermes session');
  if(new TextEncoder().encode(JSON.stringify(value)).length>MAX_BYTES) throw Error('session exceeds byte limit');
  const outstanding=new Set();
  for(const message of value.messages) {
    if(!['user','assistant','tool'].includes(message.role))throw Error('invalid saved message role');
    if(message.role==='assistant')for(const tool of message.tool_calls||[]) {if(!tool.id || outstanding.has(tool.id))throw Error('invalid saved tool call');outstanding.add(tool.id);}
    if(message.role==='tool') {if(!outstanding.delete(message.tool_call_id))throw Error('orphan saved tool result');}
    if(message.role==='user' && outstanding.size)throw Error('unfinished saved tool round');
  }
  if(outstanding.size || value.messages.at(-1)?.role!=='assistant') throw Error('incomplete saved turn');
  return value;
}
export async function loadSession(id) {
  const db=await open();
  try {return await new Promise((resolve,reject)=>{
    const tx=db.transaction('sessions','readonly');const request=tx.objectStore('sessions').get(id);
    tx.oncomplete=()=>{try{resolve(request.result ? validateSession(request.result) : null);}catch(error){reject(error);}};
    tx.onerror=tx.onabort=()=>reject(tx.error||Error('session read aborted'));
  });}finally{db.close();}
}
export async function commitSession(value, previousRevision=0) {
  validateSession(value);if(value.revision!==previousRevision+1)throw Error('session revision conflict');const db=await open();
  try {await new Promise((resolve,reject)=>{
    const tx=db.transaction('sessions','readwrite',{durability:'strict'}),store=tx.objectStore('sessions');
    let failure;
    const request=store.get(value.id);
    request.onsuccess=()=>{if((request.result?.revision||0)!==previousRevision){failure=Error('session revision conflict');tx.abort();}else store.put(value);};
    tx.oncomplete=resolve;tx.onerror=tx.onabort=()=>reject(failure||tx.error||Error('session commit aborted'));
  });}finally{db.close();}
}
