import {spawn} from 'node:child_process';
import {resolve} from 'node:path';
export function createHuggingFaceRelay({source,endpoint,model,evidence}) {
 const route=new URL(endpoint);
 if(route.protocol!=='https:'||!route.hostname.endsWith('.endpoints.huggingface.cloud')||route.username||route.password||route.search||route.hash||route.port)throw Error('expected HF dedicated Endpoint URL');
 if(!model||!source)throw Error('Python checkout and served model are required');
const active=new Set();
const handleRequest=async(req,res)=>{
 if(req.url==='/live-model-config' && req.method==='GET'){res.writeHead(200,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify({model,modelEndpoint:'/live-model'}));return true;}
 if(req.url!=='/live-model')return false;
 if(req.method!=='POST' || req.headers.origin!=='http://'+req.headers.host){res.writeHead(403);res.end();return true;}
 const incoming=[];let inputBytes=0;for await(const c of req){inputBytes+=c.length;if(inputBytes>1048576){res.writeHead(413);res.end();return true;}incoming.push(c);}
 const body=Buffer.concat(incoming).toString('utf8');let payload;try{payload=JSON.parse(body);}catch{res.writeHead(400);res.end();return true;}if(!payload || !Array.isArray(payload.messages)){res.writeHead(400);res.end();return true;}if(payload.model!==model){res.writeHead(403);res.end();return true;}
 if(active.size>=4){res.writeHead(429);res.end();return true;}
 const attempt={stream:payload.stream,roles:payload.messages.map(m=>m.role),toolResults:payload.messages.filter(m=>m.role==='tool'),requestedAt:new Date().toISOString()};evidence?.attempts.push(attempt);
 const child=spawn(resolve(source,'venv/bin/python'),[resolve('scripts/hermes-model-relay.py'),source,model,endpoint],{stdio:['pipe','pipe','ignore']});active.add(child);
 const timer=setTimeout(()=>{child.kill();res.destroy();},130000);
 child.stdin.on('error',()=>{});child.stdin.end(body);let metadata=Buffer.alloc(0),started=false,errorBody='';
 child.stdout.on('data',chunk=>{
  if(!started){metadata=Buffer.concat([metadata,chunk]);const newline=metadata.indexOf(10);if(newline<0){if(metadata.length>8192){child.kill();res.writeHead(502);res.end();}return;}
   let head;try{head=JSON.parse(metadata.subarray(0,newline));}catch{child.kill();res.writeHead(502);res.end();started=true;return;}
   attempt.status=head.status;started=true;res.writeHead(head.status,{'Content-Type':head.contentType,'Cache-Control':'no-store'});res.flushHeaders();chunk=metadata.subarray(newline+1);
  }
  if(chunk.length){if(attempt.status>=400 && errorBody.length<4096)errorBody+=chunk.toString('utf8');attempt.responseBytes=(attempt.responseBytes||0)+chunk.length;if(!res.write(chunk))child.stdout.pause();}
 });
 res.on('drain',()=>child.stdout.resume());
 child.on('error',()=>{if(!started)res.writeHead(502);res.end();clearTimeout(timer);active.delete(child);});
 child.on('close',code=>{try{const e=JSON.parse(errorBody);attempt.error={code:e.code||e.error?.code,type:e.error?.type,message:typeof e.error==='string'?e.error:e.error?.message};}catch{}if(!started){res.writeHead(502,{'Content-Type':'application/json'});res.end(JSON.stringify({error:{type:'relay_error',code:'native_runtime_unavailable'}}));}else res.end();attempt.relayExit=code;clearTimeout(timer);active.delete(child);});
 res.on('close',()=>{if(!res.writableEnded)child.kill();});return true;
};
return {handleRequest,close(){for(const child of active)child.kill();}};
}
