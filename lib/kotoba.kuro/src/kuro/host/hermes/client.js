// A synchronous Hermes Worker may wait; the UI and tool Workers remain asynchronous.
import {createToolHost, toolDefinitions} from '../tools/client.js';
import {createModelTransport} from './transport.js';
import {loadSession,commitSession} from './sessions.js';
export function createHermesBrowser({capabilities = [], modelEndpoint, model, contextLength = 128000, modelHeaders = {}, streaming = true, timeoutMs = 120000,
  workerUrl = new URL('./hermes-worker.js', import.meta.url)} = {}) {
  if(typeof model !== 'string' || !model) throw Error('model is required');
  if(!Number.isSafeInteger(contextLength) || contextLength < 64000) throw Error('contextLength must be at least 64000');
  if(!Number.isSafeInteger(timeoutMs) || timeoutMs <= 0 || timeoutMs > 2147483647) throw Error('invalid deadline');
  const grants = new Set(capabilities);
  if (!grants.has('tool/python') || !grants.has('tool/python-js-bridge')) throw Error('Hermes requires trusted Python bridge grants');
  if (!crossOriginIsolated || typeof SharedArrayBuffer === 'undefined') throw Error('Hermes bridge requires COOP/COEP cross-origin isolation');
  const endpoint = new URL(modelEndpoint, location.href);
  if (!['http:', 'https:'].includes(endpoint.protocol) || endpoint.username || endpoint.password) throw Error('invalid model endpoint');
  const host = createToolHost({capabilities, timeoutMs: Math.min(timeoutMs, 30000)});
  const tools=toolDefinitions.filter(t=>grants.has(`tool/${t.function.name}`));
  const identity=JSON.stringify({model,endpoint:endpoint.origin+endpoint.pathname+endpoint.search,contextLength,tools:tools.map(t=>t.function.name),profile:'4f649c65-v2'});
  async function execute({sourceUrl,prompt,code,sessionId,snapshot}, {signal,onDelta,onReasoning}={}) {
    sourceUrl = new URL(sourceUrl || './hermes-probe-source.tar.gz', import.meta.url).href;
    if(new URL(sourceUrl).origin !== location.origin) throw Error('source must be served on the application origin');
    return new Promise((resolve, reject) => {
      const worker = new Worker(workerUrl, {type:'module'});
      const controller = new AbortController();
      const transport=createModelTransport({endpoint,headers:modelHeaders,signal:controller.signal});
      let done = false;
      const finish = (error, value) => {if(done)return; done=true; clearTimeout(timer); controller.abort(); void transport.close(); worker.terminate(); signal?.removeEventListener('abort',abort); error ? reject(error) : resolve(value);};
      const abort = () => finish(Error('cancelled'));
      const timer = setTimeout(()=>finish(Error('Hermes deadline exceeded')),timeoutMs);
      signal?.addEventListener('abort',abort,{once:true});
      if(signal?.aborted) return abort();
      worker.onerror = event => finish(Error(event.message));
      worker.onmessage = async ({data}) => {
        if(data.kind==='done') return finish(data.error ? Error(data.error) : null,data.result);
        if(data.kind==='event'){if(!done){try{(data.event==='reasoning' ? onReasoning : onDelta)?.(data.text);}catch{}}return;}
        if(data.kind!=='rpc' || done) return;
        const state=new Int32Array(data.buffer,0,2), body=new Uint8Array(data.buffer,8);
        try {
          let result;
          if(data.operation==='tool') result=await host.call(data.payload,{signal:controller.signal});
          else if(['model','stream-open','stream-read','stream-close'].includes(data.operation)) {
            if(!grants.has('network/model')) throw Error('missing-capabilities: network/model');
            result=await transport.call(data.operation,data.payload);
          } else throw Error('unknown bridge operation');
          const encoded=new TextEncoder().encode(JSON.stringify({result}));
          if(encoded.length>body.length) throw Error('bridge response exceeds byte limit');
          body.set(encoded); Atomics.store(state,1,encoded.length); Atomics.store(state,0,1);
        } catch(error) {
          const encoded=new TextEncoder().encode(JSON.stringify({error:String(error.message).slice(0,4096)}));
          body.set(encoded); Atomics.store(state,1,encoded.length); Atomics.store(state,0,1);
        } finally {Atomics.notify(state,0);}
      };
      worker.postMessage({sourceUrl,prompt,code,model,contextLength,streaming,sessionId,snapshot,tools});
    });
  }
  return {async load(id){if(!grants.has('session/persist'))throw Error('missing-capabilities: session/persist');return loadSession(id);},async run(args,options={}) {
    if(!args.sessionId)return execute(args,options);
    if(args.code)throw Error('diagnostic code cannot persist a conversation');
    if(typeof args.sessionId!=='string' || !/^[a-zA-Z0-9_-]{1,128}$/.test(args.sessionId))throw Error('invalid session id');
    if(!grants.has('session/persist'))throw Error('missing-capabilities: session/persist');
    return navigator.locks.request('kuro/hermes/session/'+args.sessionId,{ifAvailable:true},async lock=>{
      if(!lock)throw Error('session already has an active turn');
      const snapshot=await loadSession(args.sessionId);
      if(snapshot && snapshot.identity!==identity)throw Error('saved session runtime identity differs');
      const result=await execute({...args,snapshot},options);
      if(result.completed && !result.failed && !result.partial && !result.interrupted) {
        if(options.signal?.aborted)throw Error('cancelled before session commit');
        await commitSession({version:1,id:args.sessionId,revision:(snapshot?.revision||0)+1,identity,
          messages:result.messages,systemPrompt:result.browserSystemPrompt,updatedAt:Date.now()},snapshot?.revision||0);
        result.saved=true;
      } else result.saved=false;
      return result;
    });
  }};
}
