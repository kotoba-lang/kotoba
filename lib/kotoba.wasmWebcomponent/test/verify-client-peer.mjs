// Canonical peer host tests; fake trusted DOM events are test-only. No sockets.
import assert from 'node:assert/strict';
import { clientRuntimeProblems, clientRuntimeConnectSrc, clientPeerEndpointProblems, createClientConsentHost, createClientOperationBroker } from '../src/kotoba-client-runtime.js';
const peer = '12D3KooWJxXy9juQKbQW8wSCuW7oGiNTJWmfg3ZkCqfaRoiLBM4P';
const endpoint = {transport:'libp2p','peer-id':peer,addresses:[`/ip4/127.0.0.1/udp/12345/quic-v1/p2p/${peer}`],protocol:'/ipfs/bitswap/1.2.0',action:'get-block','max-request-bytes':1024,'max-response-bytes':2048,'timeout-ms':1000};
const operation = {capability:'peer/public-read',service:'ipfs-peer',operation:'get-block',consent:'each-operation','data-categories':['public-content','content-identifiers'],endpoint};
const runtime = ops => ({schema:'kotoba.app.client-runtime.v1',target:'browser',profile:'trusted-page-v1',entry:'index.html','local-state':{adapter:'memory',schema:'peer-test',version:1},operations:ops});
assert.deepEqual(clientRuntimeProblems(runtime([operation]),['peer/public-read']),[]);
assert.deepEqual(clientPeerEndpointProblems({...endpoint,addresses:[`/ip4/127.0.0.1/udp/12345/webrtc-direct/certhash/u${'A'.repeat(46)}/p2p/${peer}`]}),[]);
assert.equal(clientRuntimeConnectSrc(runtime([operation]),['peer/public-read']),"connect-src 'none'");
for (const patch of [
  {addresses:[`/dns4/peer.example/udp/12345/quic-v1/p2p/${peer}`]},
  {addresses:[`/ip4/127.0.0.1/udp/12345/quic-v1/p2p/${peer}x`]},
  {addresses:[`/ip4/999.0.0.1/udp/12345/quic-v1/p2p/${peer}`]},
  {addresses:[`/ip4/127.0.0.1/udp/0/quic-v1/p2p/${peer}`]},
  {addresses:[`/ip4/127.0.0.1/udp/65536/quic-v1/p2p/${peer}`]},
  {'timeout-ms':60001},{'max-request-bytes':0},{'max-response-bytes':1048577},
  {origin:'https://fake-peer.example'}, {protocol:'https://gateway.example'},
]) assert(clientPeerEndpointProblems({...endpoint,...patch}).length, JSON.stringify(patch));
assert(clientRuntimeProblems(runtime([{...operation,'redirect-origins':[]}]),['peer/public-read']).length);
let now=0;
class Mouse { constructor(trusted){this.isTrusted=trusted;} }
const created=[];
class Element {
  constructor(tag){this.tagName=tag;this.listeners=new Map();this.open=false;this.isConnected=true;this.textContent='';}
  append(){} setAttribute(){} focus(){} remove(){this.isConnected=false;}
  addEventListener(type,f){this.listeners.set(type,[...(this.listeners.get(type)??[]),f]);}
  fire(type,e={}){e.currentTarget=this;for(const f of this.listeners.get(type)??[])f(e);}
  showModal(){this.open=true;} close(){this.open=false;queueMicrotask(()=>this.fire('close'));}
}
globalThis.document={body:new Element('body'),defaultView:{MouseEvent:Mouse,performance:{now:()=>now}},createElement(tag){const e=new Element(tag);created.push(e);return e;}};
let calls=0, captured;
const tick=()=>new Promise(r=>setTimeout(r,0));
const consentHost=createClientConsentHost();
const [deny,allow]=created.filter(e=>e.tagName==='button');
const approve=()=>{now+=600;allow.fire('pointerdown',new Mouse(true));allow.fire('click',new Mouse(true));};
const options={runtime:runtime([operation]),requestedCapabilities:['peer/public-read'],approvedOperations:[operation],hostSupportedOperations:[['peer/public-read','ipfs-peer','get-block']],consentHost};
const adapters={'ipfs-peer':{'get-block': async ({operation,payload,signal})=>{calls++;captured={operation,payload,signal};return {ok:true};}}};
const broker=createClientOperationBroker({...options,peerAdapters:adapters});
const payload={cid:'bafyfixture'};
const denied=broker.invoke(operation,payload);await tick();deny.fire('click');await assert.rejects(denied,/not approved/);assert.equal(calls,0);
const pending=broker.invoke(operation,payload);await tick();
assert(created.find(e=>e.tagName==='pre').textContent.includes(peer));
assert(created.find(e=>e.tagName==='pre').textContent.includes('/ipfs/bitswap/1.2.0'));
allow.fire('click',new Mouse(false));await tick();assert.equal(calls,0);
payload.cid='mutated';adapters['ipfs-peer']['get-block']=()=>{throw Error('replacement must not run');};
approve();assert.deepEqual(await pending,{ok:true});assert.equal(captured.payload.cid,'bafyfixture');assert(Object.isFrozen(captured.operation.endpoint));
assert.equal(captured.operation.endpoint['peer-id'],peer);
const second=broker.invoke(operation,{cid:'x'});await tick();assert.equal(calls,1);deny.fire('click');await assert.rejects(second,/not approved/);
await assert.rejects(createClientOperationBroker(options).invoke(operation,{}),/not host-supported/);
await assert.rejects(broker.invoke(operation,{text:'あ'.repeat(1024)}),/exceeds budget/);
let activeSignal;
const slowOp={...operation,endpoint:{...endpoint,'timeout-ms':10}};
const slow=createClientOperationBroker({...options,runtime:runtime([slowOp]),approvedOperations:[slowOp],peerAdapters:{'ipfs-peer':{'get-block':({signal})=>{activeSignal=signal;return new Promise(()=>{});}}}});
const timed=slow.invoke(operation,{});await tick();approve();await assert.rejects(timed,/timed out/);assert(activeSignal.aborted);
const large=createClientOperationBroker({...options,peerAdapters:{'ipfs-peer':{'get-block':()=>({data:'x'.repeat(4096)})}}});
const overflow=large.invoke(operation,{});await tick();approve();await assert.rejects(overflow,/response exceeds/);
const controller=new AbortController();const aborted=broker.invoke(operation,{}, {signal:controller.signal});await tick();controller.abort();await assert.rejects(aborted,/cancelled/);assert.equal(calls,1);
consentHost.destroy();
console.log('PASS peer scope, no HTTP CSP, denial, trusted consent, immutable handler/payload, budgets and cancellation');
