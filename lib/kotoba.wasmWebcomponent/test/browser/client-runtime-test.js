import { clientRuntimeProblems, clientEndpointAllowsRequest, effectiveClientOperations, createClientConsentHost, createClientOperationBroker, verifyClientArtifact, verifySignedClientDescriptor, clientRuntimeConnectSrc, mountRestrictedClientApp, prepareClientOperationRequest } from './console.js';

const results = [], interactive = [];
const http = { capability: 'test/public-metadata', service: 'GitHub-public-fixture', operation: 'read', consent: 'each-operation', 'data-categories': ['public-repository-metadata'], endpoint: { origin: 'https://api.github.com', method: 'GET', path: '/repos/holochain/holochain' } };
const browser = { capability: 'test/browser-counter', service: 'local-fixture', operation: 'increment', consent: 'each-operation', 'data-categories': ['fixture-number'], endpoint: { origin: 'https://fixture.invalid', 'browser-action': 'test/counter' } };
const runtime = operations => ({ schema: 'kotoba.app.client-runtime.v1', target: 'browser', profile: 'trusted-page-v1', entry: 'app.html', 'local-state': { adapter: 'localstorage', schema: 'test.state.v1', version: 1 }, workers: [], operations });
const selector = op => ({ capability: op.capability, service: op.service, operation: op.operation });
const full = runtime([http, browser]), requested = [http.capability, browser.capability], supported = [http,browser].map(op => [op.capability,op.service,op.operation]);
const consentHost = createClientConsentHost();
let calls = 0, observedValue = null;
const browserAdapters = { 'local-fixture': { increment: ({ payload }) => { calls++; observedValue=payload.value; return { value: payload.value }; } } };
const options = { runtime: full, requestedCapabilities: requested, approvedOperations: full.operations, hostSupportedOperations: supported, consentHost, browserAdapters };
const broker = createClientOperationBroker(options);
function check(condition, message) { if (!condition) throw Error(message || 'assertion failed'); }
async function refuses(fn) { let rejected=false; try { await fn(); } catch { rejected=true; } check(rejected,'expected refusal'); }
function digest(bytes) { return crypto.subtle.digest('SHA-256',bytes).then(b=>Array.from(new Uint8Array(b),v=>v.toString(16).padStart(2,'0')).join('')); }
const toHex = bytes => Array.from(new Uint8Array(bytes),v=>v.toString(16).padStart(2,'0')).join('');
function report() { document.getElementById('receipt').textContent=JSON.stringify({schema:'kotoba.client-runtime.browser-qualification.v1',results,interactive,browserHandlerCalls:calls,observedValue,httpResourceEntries:performance.getEntriesByType('resource').filter(e=>e.name.startsWith('https://api.github.com/')).map(e=>({name:e.name,initiatorType:e.initiatorType})),productionConsent:false},null,2); }
async function test(name, fn) { try { await fn(); results.push({name,pass:true}); } catch(error) { results.push({name,pass:false,error:error.message}); } const li=document.createElement('li');li.textContent=(results.at(-1).pass?'PASS ':'FAIL ')+name+(results.at(-1).error?' - '+results.at(-1).error:'');document.getElementById('results').append(li);report(); }
try {
await test('descriptor / HTTP and browser declarations',()=>check(clientRuntimeProblems(full,requested).length===0));
await test('unknown descriptor keys refused',()=>check(clientRuntimeProblems({...full,authority:true},requested).length>0));
await test('undeclared capability refused',()=>check(clientRuntimeProblems(full,[]).length>0));
await test('app-origin service refused',()=>check(clientRuntimeProblems(full,requested,['https://api.github.com']).length>0));
await test('HTTP origin refused',()=>check(clientRuntimeProblems(runtime([{...http,endpoint:{...http.endpoint,origin:'http://localhost:18714'}}]),requested).length>0));
await test('exact GET path accepted',()=>check(clientEndpointAllowsRequest(http.endpoint,'https://api.github.com/repos/holochain/holochain')));
for (const [name,url,method] of [['method','https://api.github.com/repos/holochain/holochain','POST'],['query','https://api.github.com/repos/holochain/holochain?token=x','GET'],['credentials','https://user:pass@api.github.com/repos/holochain/holochain','GET'],['origin','https://example.invalid/repos/holochain/holochain','GET'],['path','https://api.github.com/repos/holochain/other','GET']]) await test('request '+name+' widening refused',()=>check(!clientEndpointAllowsRequest(http.endpoint,url,method)));
const routed={origin:'https://service.invalid',routes:[{method:'GET',path:'/objects/:id','query-params':['v'],'query-values':{v:'1'}}]};
await test('bounded template and fixed query',()=>check(clientEndpointAllowsRequest(routed,'https://service.invalid/objects/abc?v=1')));
await test('duplicate query refused',()=>check(!clientEndpointAllowsRequest(routed,'https://service.invalid/objects/abc?v=1&v=1')));
await test('encoded slash in variable resource refused',()=>check(!clientEndpointAllowsRequest(routed,'https://service.invalid/objects/a%2fb?v=1')));
const prefixed={origin:'https://service.invalid',routes:[{method:'GET','path-prefix':'/objects/','query-params':[]}]};
await test('encoded path in prefix refused',()=>check(!clientEndpointAllowsRequest(prefixed,'https://service.invalid/objects/%2f..%2fx')));
await test('empty eligibility / no approvals',()=>check(effectiveClientOperations(full,{requestedCapabilities:requested,hostSupportedOperations:supported}).length===0));
await test('exact eligibility/support intersection',()=>check(effectiveClientOperations(full,{requestedCapabilities:requested,hostSupportedOperations:[supported[0]],approvedOperations:full.operations}).length===1));
await test('true-returning confirmation callback refused',()=>refuses(()=>createClientOperationBroker({...options,confirmOperation:()=>true})));
await test('forged consent host refused',()=>refuses(()=>createClientOperationBroker({...options,consentHost:{request:()=>true}})));
await test('arbitrary HTTP adapter refused',()=>refuses(()=>createClientOperationBroker({...options,serviceAdapters:{}})));
await test('unsupported operation cannot reach consent',()=>refuses(()=>broker.invoke({...selector(http),operation:'write'},{input:'https://api.github.com/repos/holochain/holochain'})));
await test('widened endpoint refused before consent',()=>refuses(()=>broker.invoke(selector(http),{input:'https://api.github.com/user'})));
await test('browser operation cannot use HTTP request matcher',()=>check(!clientEndpointAllowsRequest(browser.endpoint,'https://fixture.invalid/')));
await test('browser API without host handler refused',()=>refuses(()=>createClientOperationBroker({...options,browserAdapters:{}}).invoke(selector(browser),{value:1})));
await test('non-plain browser API parameters refused',()=>refuses(()=>broker.invoke(selector(browser),{value:()=>1})));
await test('offline CSP denies every service origin',()=>check(clientRuntimeConnectSrc(runtime([]),[])==="connect-src 'none'"));
await test('service CSP derived without app-origin API access',()=>check(clientRuntimeConnectSrc(full,requested)==='connect-src https://api.github.com https://fixture.invalid'));
const post={...http,endpoint:{origin:'https://service.invalid',method:'POST',path:'/commit'}};
await test('HTTP preflight snapshots body, headers and fetch policy without sending',async()=>{
 const body=new Uint8Array([97,98,99]),headers=new Headers({'Content-Type':'text/plain','X-Fixture':'original'});
 const pending=prepareClientOperationRequest(post,{input:'https://service.invalid/commit',init:{method:'POST',credentials:'include',redirect:'follow',body,headers}});
 body[0]=120;headers.set('X-Fixture','changed');const snapshot=await pending;
 const observed={body:await snapshot.input.text(),header:snapshot.input.headers.get('X-Fixture'),credentials:snapshot.input.credentials,redirect:snapshot.input.redirect,referrerPolicy:snapshot.input.referrerPolicy};
 check(observed.body==='abc'&&observed.header==='original'&&observed.credentials==='omit'&&observed.redirect==='error'&&observed.referrerPolicy==='no-referrer',JSON.stringify(observed));
});
await test('stream body byte budget enforced before consent',()=>refuses(()=>prepareClientOperationRequest(post,{input:new Request('https://service.invalid/commit',{method:'POST',body:new ReadableStream({start(c){c.enqueue(new Uint8Array(16777217));c.close();}}),duplex:'half'})})));
await test('declared read-only redirect policy survives preflight',async()=>{const snapshot=await prepareClientOperationRequest({...http,'redirect-origins':['https://delivery.invalid']},{input:'https://api.github.com/repos/holochain/holochain'});check(snapshot.input.redirect==='follow');});
const bytes=new TextEncoder().encode('abc'), declaration={revision:'1'.repeat(40),sha256:'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad','max-bytes':3};
await test('independent artifact SHA-256 vector',async()=>check((await verifyClientArtifact(bytes,declaration)).verified));
await test('digest mismatch refuses artifact',()=>refuses(()=>verifyClientArtifact(bytes,{...declaration,sha256:'0'.repeat(64)})));
await test('moving source revision refuses artifact',()=>refuses(()=>verifyClientArtifact(bytes,{...declaration,revision:'main'})));
await test('artifact byte budget enforced',()=>refuses(()=>verifyClientArtifact(bytes,{...declaration,'max-bytes':2})));
await test('verified Blob owns a byte snapshot',async()=>{const data=new Uint8Array(bytes);const artifact=await verifyClientArtifact(data,declaration);data[0]=0;check(await artifact.blob.text()==='abc');});
await test('artifact declaration pinned before asynchronous digest',async()=>{const mutable={...declaration};const pending=verifyClientArtifact(bytes,mutable);mutable.revision='0'.repeat(40);check((await pending).revision===declaration.revision);});
const keys=await crypto.subtle.generateKey('Ed25519',false,['sign','verify']), publicKey=toHex(await crypto.subtle.exportKey('raw',keys.publicKey));
const descriptorBytes=new TextEncoder().encode(JSON.stringify(full)), signature=toHex(await crypto.subtle.sign('Ed25519',keys.privateKey,descriptorBytes));
const signed={bytes:descriptorBytes,signature,publicKey,pinnedPublicKey:publicKey,revision:'2'.repeat(40),digest:await digest(descriptorBytes),requestedCapabilities:requested};
await test('host-pinned Ed25519 descriptor admission',async()=>check((await verifySignedClientDescriptor(signed)).publicKey===publicKey));
await test('changed publisher pin refused',()=>refuses(()=>verifySignedClientDescriptor({...signed,pinnedPublicKey:'0'.repeat(64)})));
await test('changed signature refused',()=>refuses(()=>verifySignedClientDescriptor({...signed,signature:'0'.repeat(128)})));
await test('changed descriptor bytes refused',()=>refuses(()=>verifySignedClientDescriptor({...signed,bytes:new TextEncoder().encode('{}')})));
await test('forged verified flag cannot mount a guest',()=>refuses(()=>mountRestrictedClientApp({artifact:{verified:true,blob:new Blob(['x'])},container:document.getElementById('restricted'),broker})));
const guestBytes=new TextEncoder().encode("<h2>Restricted guest fixture</h2><script>addEventListener('message',async function(event){if(event.data?.protocol!=='kotoba.client.host.v1')return;let isolated=false;try{parent.document.body}catch{isolated=true}let blocked=false;try{await fetch('https://api.github.com/repos/holochain/holochain')}catch{blocked=true}parent.postMessage({fixture:'restricted',isolated,blocked},'*')},{once:true});</script>\n");
await test('isolated guest / parent DOM and direct network refused',async()=>{
 const artifact=await verifyClientArtifact(guestBytes,{revision:'3'.repeat(40),sha256:await digest(guestBytes),'max-bytes':8192});
 const completion=new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('restricted guest did not report')),6000);function receive(event){if(event.source!==document.querySelector('#restricted iframe')?.contentWindow||event.origin!=='null'||event.data?.fixture!=='restricted')return;clearTimeout(timer);removeEventListener('message',receive);try{check(event.data.isolated&&event.data.blocked);resolve();}catch(e){reject(e)}}addEventListener('message',receive)});
 await mountRestrictedClientApp({artifact,container:document.getElementById('restricted'),broker});await completion;
});
document.getElementById('summary').textContent=results.filter(r=>r.pass).length+'/'+results.length+' automatic browser checks passed';
} catch(error) { document.getElementById('summary').textContent='SETUP FAILED: '+error.message; report(); }
const status=document.getElementById('interactive');
document.getElementById('deny-http').addEventListener('click',async()=>{const before=performance.getEntriesByType('resource').filter(e=>e.name.startsWith('https://api.github.com/')).length;try{await broker.invoke(selector(http),{input:'https://api.github.com/repos/holochain/holochain'});throw Error('deny test unexpectedly succeeded');}catch(error){const after=performance.getEntriesByType('resource').filter(e=>e.name.startsWith('https://api.github.com/')).length;const pass=error.message==='client operation was not approved'&&before===after;interactive.push({name:'denial sends no HTTPS request',pass,before,after});status.textContent=(pass?'PASS':'FAIL')+' denied HTTPS read; no new resource request';report();}});
document.getElementById('allow-http').addEventListener('click',async()=>{try{const result=await broker.invoke(selector(http),{input:'https://api.github.com/repos/holochain/holochain'});const json=await result.json();check(result.ok&&json.full_name==='holochain/holochain');interactive.push({name:'permitted exact HTTPS read',pass:true,status:result.status,url:result.url});status.textContent='PASS exact anonymous HTTPS GET, response origin verified';}catch(error){interactive.push({name:'permitted exact HTTPS read',pass:false,error:error.message});status.textContent='FAIL '+error.message;}report();});
document.getElementById('native-action').addEventListener('click',async()=>{const before=calls,payload={value:1};const pending=broker.invoke(selector(browser),payload);payload.value=999;document.querySelector('.kotoba-client-consent button:last-child').click();check(calls===before);try{const result=await pending;check(calls===before+1&&result.value===1&&observedValue===1);interactive.push({name:'trusted browser action; synthetic click refused; immutable payload; exactly once',pass:true});status.textContent='PASS trusted action once / original payload 1 / synthetic click refused';}catch(error){interactive.push({name:'browser action',pass:false,error:error.message});status.textContent='FAIL '+error.message;}report();});
report();
