import {chromium} from 'playwright';
import {serve} from './serve-browser-tools.mjs';
import {mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import assert from 'node:assert/strict';
const requests=[], acknowledgements=[];let fixtureFailure;
let acknowledge;const firstDelta=new Promise(r=>{acknowledge=r;});
let cancelledRequest;const pendingRequest=new Promise(r=>{cancelledRequest=r;});
const chunk=(delta,finish_reason=null)=>({id:'stream-fixture',object:'chat.completion.chunk',created:1,model:'browser-fixture',choices:[{index:0,delta,finish_reason}]});
const {server,url}=await serve(undefined,0,{handleRequest:async(req,res)=>{
 if(req.url==='/delta-observed'){acknowledgements.push(Date.now());acknowledge();res.writeHead(200);res.end('ok');return true;}
 if(req.url!=='/stream-model')return false;
 try {
  let body='';for await(const c of req)body+=c;const request=JSON.parse(body);requests.push(request);
  assert.equal(request.stream,true);assert.deepEqual(request.tools.map(t=>t.function.name),['js','python']);
  const lastUser=request.messages.filter(m=>m.role==='user').at(-1).content;
  res.writeHead(200,{'Content-Type':'text/event-stream','Cache-Control':'no-cache'});res.flushHeaders();
  const send=async frame=>{const bytes=Buffer.from('data: '+JSON.stringify(frame)+'\r\n\r\n');for(let i=0;i<bytes.length;i+=7){res.write(bytes.subarray(i,i+7));await new Promise(r=>setTimeout(r,1));}};
  if(lastUser==='cancel-stream'){await send(chunk({role:'assistant',content:'pending '}));cancelledRequest();return true;}
  if(lastUser==='remember-42' && !request.messages.some(m=>m.role==='tool')) {
    await send(chunk({role:'assistant',tool_calls:[{index:0,id:'stream-js',type:'function',function:{name:'js',arguments:'{"code":"21 * '}}]}));
    await send(chunk({tool_calls:[{index:0,function:{arguments:'2"}'}}]}));
    await send(chunk({tool_calls:[{index:1,id:'stream-python',type:'function',function:{name:'python',arguments:'{"code":"sum([20, '}}]}));
    await send(chunk({tool_calls:[{index:1,function:{arguments:'22])"}'}}]}));
    await send(chunk({},'tool_calls'));
  } else {
    const tools=request.messages.filter(m=>m.role==='tool');assert.equal(tools.length,2);
    for(const message of tools){const value=JSON.parse(message.content);assert.equal(value.result,42);assert.equal(value.id,message.tool_call_id);assert.equal(value.receipt['kuro/exit-code'],0);}
    await send(chunk({role:'assistant',content:'42 '}));
    if(lastUser==='remember-42')await firstDelta;
    await send(chunk({content:lastUser==='resume-42'?'を覚えています。':'両ツールで確認しました。'}));
    await send(chunk({},'stop'));
  }
  await send({id:'stream-fixture',object:'chat.completion.chunk',created:1,model:'browser-fixture',choices:[],usage:{prompt_tokens:100,completion_tokens:10,total_tokens:110}});
  res.end('data: [DONE]\r\n\r\n');
 } catch(error){fixtureFailure=String(error);res.end();}
 return true;
}});
const profile=`target/hermes-browser-profile-${Date.now()}`;await mkdir(profile,{recursive:true});
let context;
async function open(){context=await chromium.launchPersistentContext(profile,{headless:true,executablePath:process.env.KURO_CHROMIUM_PATH});const page=await context.newPage();page.on('console',m=>{if(m.type()==='error')console.log('browser:',m.text());});await page.goto(url);return page;}
async function turn(page,prompt){return page.evaluate(async prompt=>{
 const {createHermesBrowser}=await import('./hermes.js');let delta='';const times=[];
 const host=createHermesBrowser({model:'browser-fixture',modelEndpoint:'/stream-model',capabilities:['tool/js','tool/python','tool/python-js-bridge','network/model','session/persist']});
 const result=await host.run({sessionId:'stream-session',prompt},{onDelta:text=>{delta+=text;times.push(performance.now());if(prompt==='remember-42')void fetch('/delta-observed');}});
 return {result,delta,times,saved:await host.load('stream-session')};
},prompt);}
try {
 let page=await open();
 const first=await turn(page,'remember-42');
 assert.equal(fixtureFailure,undefined);assert.equal(first.result.completed,true);assert.equal(first.result.saved,true);
 assert.equal(first.saved.revision,1);assert.equal(first.delta.trim(),first.result.final_response);assert.ok(first.times.length>=2);assert.ok(acknowledgements.length>0,'delta must reach UI before server can finish the stream');
 assert.equal(first.result.total_tokens,220);
 await context.close();context=null;
 page=await open();
 const second=await turn(page,'resume-42');
 assert.equal(fixtureFailure,undefined);assert.equal(second.saved.revision,2);assert.equal(second.delta.trim(),second.result.final_response);
 assert.deepEqual(second.result.messages.map(m=>m.role),['user','assistant','tool','tool','assistant','user','assistant']);
 assert.equal(first.saved.systemPrompt,second.saved.systemPrompt);assert.equal(requests[0].messages[0].content,requests[2].messages[0].content);
 await page.evaluate(async()=>{
  const {createHermesBrowser}=await import('./hermes.js');window.stopStream=new AbortController();
  const host=createHermesBrowser({model:'browser-fixture',modelEndpoint:'/stream-model',capabilities:['tool/js','tool/python','tool/python-js-bridge','network/model','session/persist']});
  window.pendingStream=host.run({sessionId:'stream-session',prompt:'cancel-stream'},{signal:window.stopStream.signal}).then(()=>false,error=>error.message==='cancelled');
  window.concurrent=host.run({sessionId:'stream-session',prompt:'overlap'}).then(()=>false,error=>error.message.includes('active turn'));
 });
 let timer;try{await Promise.race([pendingRequest,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('cancel stream not reached')),20000);})]);}finally{clearTimeout(timer);}
 const cancelled=await page.evaluate(async()=>{window.stopStream.abort();return {cancelled:await window.pendingStream,concurrentRejected:await window.concurrent};});
 assert.deepEqual(cancelled,{cancelled:true,concurrentRejected:true});
 const saved=await page.evaluate(async()=>{const {createHermesBrowser}=await import('./hermes.js');return createHermesBrowser({model:'browser-fixture',modelEndpoint:'/stream-model',capabilities:['tool/js','tool/python','tool/python-js-bridge','network/model','session/persist']}).load('stream-session');});
 assert.equal(saved.revision,2);assert.deepEqual(saved.messages,second.saved.messages,'cancel must retain the last committed turn');
 const identityDenied=await page.evaluate(async()=>{const {createHermesBrowser}=await import('./hermes.js');try{await createHermesBrowser({model:'different-model',modelEndpoint:'/stream-model',capabilities:['tool/js','tool/python','tool/python-js-bridge','network/model','session/persist']}).run({sessionId:'stream-session',prompt:'wrong model'});return false;}catch(e){return e.message.includes('identity differs');}});
 assert.equal(identityDenied,true);
 const lockResult=await page.evaluate(async()=>{const {commitSession}=await import('./sessions.js');const db=await new Promise((resolve,reject)=>{const r=indexedDB.open('kuro-hermes-sessions',1);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});const value=await new Promise(resolve=>{const r=db.transaction('sessions').objectStore('sessions').get('stream-session');r.onsuccess=()=>resolve(r.result);});db.close();try{await commitSession({...value,revision:2},1);return false;}catch(e){return e.message.includes('revision conflict');}});
 assert.equal(lockResult,true);
 // Exercise the shipped interface, including a saved conversation after reload.
 await page.goto(url+'/hermes.html');
 await page.locator('#model').fill('browser-fixture');await page.locator('#endpoint').fill('/stream-model');
 await page.locator('#session').fill('stream-session');await page.locator('#prompt').fill('resume-42');
 await page.locator('#run').click();await page.waitForFunction(()=>document.getElementById('status').textContent==='会話を保存しました。');
 assert.equal(await page.locator('#output').textContent(),'42 を覚えています。');
 await page.reload();await page.locator('#model').fill('browser-fixture');await page.locator('#endpoint').fill('/stream-model');await page.locator('#session').fill('stream-session');
 await page.locator('#restore').click();await page.waitForFunction(()=>document.getElementById('output').textContent.includes('42 を覚えています。'));
 const provenance=JSON.parse(await readFile('target/browser-tools/hermes-source.json'));
 await writeFile('docs/verification/hermes-browser-streaming.json',JSON.stringify({provenance,liveModel:false,originalHermesSSEAccumulator:true,first:{final:first.result.final_response,tokens:first.result.total_tokens,delta:first.delta,revision:first.saved.revision},resumed:{final:second.result.final_response,delta:second.delta,revision:saved.revision,roles:saved.messages.map(m=>m.role)},checks:{beforeStreamEnd:true,utf8AndToolArgumentFragments:true,stablePrompt:true,persistedAcrossBrowserRestart:true,cancelledRetainsCommit:true,concurrentTurnDenied:true,identityMismatchDenied:true,revisionConflictDenied:true,demoSendAndRestore:true}},null,2)+'\n');
 console.log('PASS: original Hermes SSE, fragments, live UI deltas, usage, browser restart/resume, cancellation and session consistency');
} finally {await context?.close();server.closeAllConnections();await new Promise(r=>server.close(r));await rm(profile,{recursive:true,force:true});}
