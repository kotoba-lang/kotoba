// Real inference through an explicitly selected Hugging Face dedicated Endpoint.
import {chromium} from 'playwright';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {serve} from './serve-browser-tools.mjs';
import {createHuggingFaceRelay} from './huggingface-relay.mjs';
const source=process.argv[2];if(!source)throw Error('Usage: node scripts/verify-hermes-live.mjs /path/to/native/hermes <endpoint-url> <model>');
const endpoint=process.argv[3]||process.env.HF_ENDPOINT_URL;
const model=process.argv[4]||process.env.HF_MODEL;
if(!endpoint||!model)throw Error('HF endpoint URL and served model are required');
const route=new URL(endpoint);
if(route.protocol!=='https:'||!route.hostname.endsWith('.endpoints.huggingface.cloud')||route.username||route.password||route.search||route.hash||route.port)throw Error('expected HF dedicated Endpoint URL');
const evidence={provider:'huggingface-endpoints',endpoint,model,modelFixture:false,attempts:[],status:'started'};
const relay=createHuggingFaceRelay({source,endpoint,model,evidence});
const {server,url}=await serve(undefined,0,{handleRequest:relay.handleRequest});
let browser;
try {
 browser=await chromium.launch({headless:true,executablePath:process.env.KURO_CHROMIUM_PATH});
 const page=await browser.newPage();await page.goto(url);
 const result=await page.evaluate(async model=>{
  const {createHermesBrowser}=await import('./hermes.js');let text='',deltas=0;
  const host=createHermesBrowser({model,modelEndpoint:'/live-model',capabilities:['tool/js','tool/python','tool/python-js-bridge','network/model','session/persist'],timeoutMs:90000});
  try {const result=await host.run({sessionId:'live-'+crypto.randomUUID(),prompt:'Use the js tool to compute 21 * 2 and the python tool to compute sum([20,22]). Execute both tools, then report their actual results briefly.'},{onDelta:delta=>{text+=delta;deltas++;}});return {result,text,deltas};}
  catch(error){return {error:String(error.message)};}
 },model);
 evidence.browser={error:result.error,completed:result.result?.completed,failed:result.result?.failed,final:result.result?.final_response,streamedText:result.text,deltas:result.deltas,saved:result.result?.saved};
 const tools=result.result?.messages?.filter(m=>m.role==='tool')||[];
 evidence.toolResults=tools;
 evidence.liveToolRoundTrip=tools.some(m=>m.name==='js'||result.result.messages.some(a=>a.tool_calls?.some(t=>t.id===m.tool_call_id&&t.function.name==='js'))) && tools.some(m=>result.result.messages.some(a=>a.tool_calls?.some(t=>t.id===m.tool_call_id&&t.function.name==='python'))) && tools.every(m=>{try{const v=JSON.parse(m.content);return v.result===42&&v.receipt['kuro/exit-code']===0;}catch{return false;}});
 evidence.status=evidence.liveToolRoundTrip&&result.result?.completed&&result.deltas>0 ? 'qualified' : 'blocked';
 evidence.provenance=JSON.parse(await readFile('target/browser-tools/hermes-source.json'));
 evidence.sourceSha256=createHash('sha256').update(await readFile('src/kuro/host/hermes/adapter.py')).digest('hex');
 await writeFile('docs/verification/hermes-browser-live.json',JSON.stringify(evidence,null,2)+'\n');
 console.log(JSON.stringify({status:evidence.status,model,attempts:evidence.attempts.map(a=>({status:a.status,stream:a.stream})),browser:evidence.browser,liveToolRoundTrip:evidence.liveToolRoundTrip}));
 assert.equal(evidence.status,'qualified','real model qualification failed; inspect recorded evidence');
}finally{relay.close();await browser?.close();server.closeAllConnections();await new Promise(r=>server.close(r));}
