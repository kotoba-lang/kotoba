import {chromium} from 'playwright';
import {serve} from './serve-browser-tools.mjs';
import {writeFile,readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const modelRequests=[];
let cancelObserved; const cancellationRequest = new Promise(resolve => {cancelObserved=resolve;});
const {server,url}=await serve(undefined,0,{handleRequest: async(req,res)=>{
 if(req.url!=='/hermes-probe-model.json')return false;
 let body='';for await(const chunk of req)body+=chunk;
 const request=JSON.parse(body);modelRequests.push(request);console.log('model request roles:',request.messages.map(m=>m.role));
 if(request.messages[0]?.content==='cancel-test'){cancelObserved();return true;}
 const results=request.messages.filter(m=>m.role==='tool');
 if(results.length) {console.log('tool results:',JSON.stringify(results));assert.equal(results.length,2);for(const m of results){const value=JSON.parse(m.content);assert.equal(value.id,m.tool_call_id);assert.equal(value.result,42);assert.equal(value.receipt['kuro/exit-code'],0);}}
 const message=request.messages[0]?.content==='fixture' ? {role:'assistant',content:'transport fixture only'} :
  results.length ? {role:'assistant',content:'Both browser tools returned 42.'} :
  {role:'assistant',content:null,tool_calls:['js','python'].map((name,i)=>({id:`call-${i}`,type:'function',function:{name,arguments:JSON.stringify({code:name==='js'?'21 * 2':'sum([20, 22])'})}}))};
 res.writeHead(200,{'Content-Type':'application/json'});
 res.end(JSON.stringify({id:'browser-fixture',object:'chat.completion',created:1,model:'browser-fixture',streaming:false,choices:[{index:0,message,finish_reason:message.tool_calls?'tool_calls':'stop'}],usage:{prompt_tokens:100,completion_tokens:10,total_tokens:110}}));return true;
}});
let browser;
try {
 browser=await chromium.launch({headless:true,executablePath:process.env.KURO_CHROMIUM_PATH});
 const page=await browser.newPage();
 page.on('console',m=>console.log('browser:',m.text())); const requests=[];
 page.on('request',r=>{if(!r.url().startsWith(url) && !r.url().startsWith('blob:'+url))requests.push(r.url());});
 await page.goto(url);
 const result=await page.evaluate(async()=>{
  const {createHermesBrowser}=await import('./hermes.js');
  const host=createHermesBrowser({capabilities:['tool/js','tool/python','tool/python-js-bridge','network/model'],modelEndpoint:'/hermes-probe-model.json',model:'browser-fixture',streaming:false});
  return host.run({sourceUrl:location.origin+'/hermes-probe-source.tar.gz',code:`
report = {'checks': {}}
def check(name, fn):
    try: report['checks'][name] = {'ok': True, 'value': fn()}
    except BaseException as exc: report['checks'][name] = {'ok': False, 'error': str(exc), 'traceback': traceback.format_exc(limit=15)}
def import_agent():
    from run_agent import AIAgent
    return AIAgent.__name__
check('agent_import', import_agent)
check('conversation', lambda: run_browser_agent('Calculate 42 using both browser tools.'))
check('serial_pool', lambda: tools.daemon_pool.DaemonThreadPoolExecutor().submit(lambda: 42).result())
check('model_transport', lambda: bridge('model', {'messages': [{'role':'user','content':'fixture'}]}))
check('js_tool', lambda: bridge('tool', {'id':'js-1','type':'function','function':{'name':'js','arguments':json.dumps({'code':'21 * 2'})}}))
check('python_tool', lambda: bridge('tool', {'id':'py-1','type':'function','function':{'name':'python','arguments':json.dumps({'code':'sum([20, 22])'})}}))
report
`});
 });
 assert.equal(result.checks.agent_import.ok,true);
 assert.equal(result.checks.conversation.ok,true,JSON.stringify(result.checks.conversation));
 assert.equal(result.checks.serial_pool.value,42);
 assert.equal(result.checks.model_transport.ok,true);
 for(const key of ['js_tool','python_tool']) {assert.equal(result.checks[key].value.result,42); assert.equal(result.checks[key].value.receipt['kuro/exit-code'],0);}
 assert.deepEqual(requests,[]);
 const conversation = result.checks.conversation.value;
 assert.equal(conversation.completed,true);
 assert.equal(conversation.final_response,'Both browser tools returned 42.');
 assert.deepEqual(conversation.messages.map(m=>m.role),['user','assistant','tool','tool','assistant']);
 assert.equal(modelRequests[0].messages[0].content,modelRequests[1].messages[0].content,'system prompt must stay stable across tool round trip');
 // Exercise cancellation while the Python Worker is synchronously waiting for browser fetch.
 await page.evaluate(async()=>{
   const {createHermesBrowser}=await import('./hermes.js');
   window.cancelController=new AbortController();window.uiTicks=0;
   window.uiTimer=setInterval(()=>window.uiTicks++,10);
   const host=createHermesBrowser({model:'browser-fixture',streaming:false,capabilities:['tool/python','tool/python-js-bridge','network/model'],modelEndpoint:'/hermes-probe-model.json'});
   window.cancelResult=host.run({code:"bridge('model', {'messages': [{'role':'user','content':'cancel-test'}]})"},{signal:window.cancelController.signal}).then(()=>({cancelled:false}),error=>({cancelled:error.message==='cancelled'}));
 });
 await Promise.race([cancellationRequest,new Promise((_,reject)=>setTimeout(()=>reject(Error('cancellation fixture was not reached')),20000))]);
 const cancelled=await page.evaluate(async()=>{window.cancelController.abort();const value=await window.cancelResult;clearInterval(window.uiTimer);return {...value,uiTicks:window.uiTicks};});
 assert.equal(cancelled.cancelled,true);assert.ok(cancelled.uiTicks>0,'UI must remain responsive');
 result.checks.cancellation={ok:true,value:cancelled};
 const denied=await page.evaluate(async()=>{
   const {createHermesBrowser}=await import('./hermes.js');
   const host=createHermesBrowser({model:'browser-fixture',streaming:false,capabilities:['tool/python','tool/python-js-bridge'],modelEndpoint:'/hermes-probe-model.json'});
   try {await host.run({code:"bridge('model', {'messages': []})"});return false;}catch(error){return error.message.includes('missing-capabilities: network/model');}
 });
 assert.equal(denied,true);result.checks.network_denial={ok:true};
 assert.deepEqual(requests,[]);
 const provenance=JSON.parse(await readFile('target/browser-tools/hermes-source.json'));
 await writeFile('docs/verification/hermes-browser-adapter.json',JSON.stringify({provenance,verdict:{originalHermesConversationLoop:true,browserProfile:true,modelToolRoundTrip:true,liveModel:false},result,modelRequests:modelRequests.map(r=>({model:r.model,roles:r.messages.map(m=>m.role),tools:r.tools?.map(t=>t.function.name),toolResults:r.messages.filter(m=>m.role==='tool')})),externalRequests:requests},null,2)+'\n');
 console.log('Hermes browser qualification passed: original loop, SDK, JS/Python round trip, cancellation, UI responsiveness, network denial.');
}finally {await browser?.close(); server.closeAllConnections();await new Promise(r=>server.close(r));}
