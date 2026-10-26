// Pull-based HTTP byte streaming. The OpenAI SDK remains the SSE parser.
export function createModelTransport({endpoint,headers,signal,maxBytes=16*1024*1024}) {
  const streams=new Map();
  async function request(payload) {
    const body=JSON.stringify(payload);
    if(new TextEncoder().encode(body).length>1048576)throw Error('model request exceeds byte limit');
    return fetch(endpoint,{method:'POST',headers:{...headers,'Content-Type':'application/json'},body,signal,credentials:'omit',redirect:'error'});
  }
  async function boundedJSON(response) {
    const reader=response.body.getReader(),chunks=[];let length=0;
    try {for(;;){const {done,value}=await reader.read();if(done)break;length+=value.length;if(length>1048576){await reader.cancel();throw Error('model response exceeds byte limit');}chunks.push(value);}}
    finally{reader.releaseLock();}
    const joined=new Uint8Array(length);let offset=0;for(const c of chunks){joined.set(c,offset);offset+=c.length;}
    return {status:response.status,body:JSON.parse(new TextDecoder().decode(joined))};
  }
  return {async call(operation,payload) {
    if(operation==='model')return boundedJSON(await request(payload));
    if(operation==='stream-open') {
      const response=await request({...payload,stream:true});
      if(!response.ok)return boundedJSON(response);
      if(!response.headers.get('content-type')?.includes('text/event-stream'))throw Error('model did not return SSE');
      const id=crypto.randomUUID();streams.set(id,{reader:response.body.getReader(),bytes:0,pending:new Uint8Array()});
      return {status:response.status,streamId:id};
    }
    const stream=streams.get(payload.id);if(!stream)throw Error('unknown model stream');
    if(operation==='stream-close'){streams.delete(payload.id);await stream.reader.cancel();stream.reader.releaseLock();return null;}
    if(operation!=='stream-read')throw Error('unknown transport operation');
    if(!stream.pending.length) {
      const {done,value}=await stream.reader.read();
      if(done){streams.delete(payload.id);stream.reader.releaseLock();return {done:true};}
      stream.bytes+=value.length;
      if(stream.bytes>maxBytes){await stream.reader.cancel();streams.delete(payload.id);throw Error('model stream exceeds byte limit');}
      stream.pending=value;
    }
    // Encode at most 64 KiB per RPC, preserving arbitrary UTF-8/SSE chunk boundaries.
    const chunk=stream.pending.subarray(0,65536);stream.pending=stream.pending.subarray(chunk.length);
    let binary='';for(const byte of chunk)binary+=String.fromCharCode(byte);
    return {done:false,bytes:btoa(binary)};
  },async close(){const active=[...streams.values()];streams.clear();await Promise.allSettled(active.map(async s=>{await s.reader.cancel();s.reader.releaseLock();}));}};
}
