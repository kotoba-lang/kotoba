import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { once } from 'node:events';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { Worker } from 'node:worker_threads';
import { fileURLToPath } from 'node:url';
import { hostCaps } from '../src/actor-host.js';
import { instantiateKotobaComponent } from '../src/component-runtime.js';
import { instantiateLinkedKotobaComponents, PG_CANCELLABLE_SCRAM_LINKS, PG_QUERY_STATE_LINKS } from '../src/component-linker.js';
import { createNodeCredentialProvider } from '../src/node-credential-provider.js';
import { createNodeTransportBroker } from '../src/node-transport-broker.js';

const compilerRepo = resolve(fileURLToPath(new URL('.', import.meta.url)), '../../kotoba');
const dir = mkdtempSync(join(tmpdir(), 'kotoba-pg-cancel-component-'));
try {
  const keyPath=join(dir,'key.pem'),certPath=join(dir,'cert.pem'),dbPath=join(dir,'db.wasm'),scramPath=join(dir,'scram.wasm');
  const queryPath=join(dir,'query.wasm'),cancelPath=join(dir,'cancel.wasm');
  execFileSync('openssl',['req','-x509','-newkey','rsa:2048','-nodes','-sha256','-keyout',keyPath,
    '-out',certPath,'-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost'],{stdio:'ignore'});
  const expression=`(require '[clojure.edn :as edn] '[kotoba.runtime :as runtime])
    (doseq [[s p o] [["providers/db_transport.kotoba" "providers/transport_policy.edn" "${dbPath}"]
                     ["providers/pg_scram.kotoba" "providers/pg_scram_policy.edn" "${scramPath}"]
                     ["providers/pg_cancellable_query_consumer.kotoba" "providers/db_component_policy.edn" "${queryPath}"]
                     ["providers/pg_cancel_consumer.kotoba" "providers/db_component_policy.edn" "${cancelPath}"]]]
      (let [r (runtime/wasm-binary (runtime/read-file s :kotoba) (edn/read-string (slurp p)))]
        (assert (:kotoba.wasm/ok? r))
        (java.nio.file.Files/write (java.nio.file.Paths/get o (make-array String 0)) ^bytes (:kotoba.wasm/binary r) (make-array java.nio.file.OpenOption 0))))`;
  execFileSync('clojure',['-M:dev','-i','tools/cljk_loader.cljk','-e',expression],{cwd:compilerRepo,stdio:'ignore'});
  const key=readFileSync(keyPath,'utf8'),cert=readFileSync(certPath,'utf8');
  const server=new Worker(`
    const {parentPort,workerData}=require('node:worker_threads');const net=require('node:net'),tls=require('node:tls');
    const context=tls.createSecureContext(workerData),cancel=[];
    const sasl=Buffer.concat([Buffer.from([82,0,0,0,23,0,0,0,10]),Buffer.from('SCRAM-SHA-256\\0\\0')]);
    const sf=Buffer.from('r=AAECAwQFBgcICQoLDA0ODxARserver,s=W22ZaJ0SNY7soEsUEjb6gQ==,i=4096');
    const cont=Buffer.concat([Buffer.from([82,0,0,0,sf.length+8,0,0,0,11]),sf]);
    const fin=Buffer.from('v=QAdQmJ+lRK7pdc/DBEeFAbUmtBhFLhQXsQNpv3KJgJQ=');
    const final=Buffer.concat([Buffer.from([82,0,0,0,fin.length+8,0,0,0,12]),fin]);
    const tail=Buffer.from([82,0,0,0,8,0,0,0,0,75,0,0,0,12,0,0,0,1,0,0,0,2,90,0,0,0,5,73]);
    const server=net.createServer(socket=>{let input=Buffer.alloc(0);socket.on('data',function initial(c){input=Buffer.concat([input,c]);if(input.length<8)return;
      const code=input.readInt32BE(4);if(code===80877102){if(input.length<16)return;cancel.push(Buffer.from(input.subarray(0,16)));parentPort.postMessage({cancel:cancel[0]});return socket.destroy()}
      socket.removeListener('data',initial);socket.write(Buffer.from('S'));const secure=new tls.TLSSocket(socket,{isServer:true,secureContext:context});let auth=Buffer.alloc(0),stage=0;
      secure.on('error',()=>{});secure.on('data',c2=>{auth=Buffer.concat([auth,c2]);while(true){const needed=stage===0?(auth.length>=4?auth.readInt32BE(0):Infinity):(auth.length>=5?auth.readInt32BE(1)+1:Infinity);if(auth.length<needed)break;auth=auth.subarray(needed);if(stage===0){secure.write(sasl);stage=1}else if(stage===1){secure.write(cont);stage=2}else if(stage===2){secure.write(Buffer.concat([final,tail]));stage=3}}});secure.resume()})});
    server.listen(0,'127.0.0.1',()=>parentPort.postMessage({port:server.address().port}));parentPort.on('message',()=>server.close());
  `,{eval:true,workerData:{key,cert}});
  const [{port}]=await once(server,'message');let cancelBytes;
  server.on('message',message=>{if(message.cancel)cancelBytes=Buffer.from(message.cancel)});
  const broker=createNodeTransportBroker({endpointAllowlist:[`localhost:${port}`],resolvedAddressAllowlist:['127.0.0.1'],maxConnections:2,
    connectTimeoutMs:1500,readTimeoutMs:1500,maxReadBytes:65536,maxWriteBytes:65536,maxCancelHandles:1,maxCancelRequests:1,trustedCaPem:cert});
  const transport=['transport-connect','tls-open','tls-server-end-point','transport-write','transport-read','transport-close'];
  try{
    const db=await instantiateKotobaComponent(readFileSync(dbPath),hostCaps({grants:transport,limits:{maxTransportConnections:2,allowWriteImports:true}}),{transport:broker});
    const low=[...transport,'scram-sha256','random-bytes','pg-cancel-register','pg-cancel'];
    const scram=await instantiateKotobaComponent(readFileSync(scramPath),hostCaps({grants:low,limits:{maxTransportConnections:2,maxScramProofs:1,maxRandomBytes:18,
      maxPgCancelHandles:1,maxPgCancelRequests:1,allowSecretImports:true,allowWriteImports:true,scramCredentialAllowlist:['db/primary']}}),
      {transport:broker,credentials:createNodeCredentialProvider({credentialAllowlist:['db/primary'],maxProofs:1,credentials:{'db/primary':'pencil'}}),randomBytes:n=>Uint8Array.from({length:n},(_,i)=>i)});
    const query=await instantiateLinkedKotobaComponents(readFileSync(queryPath),hostCaps({grants:['pg-open-scram-cancellable-random','pg-query-state','pg-close-scram'],limits:{allowSecretImports:true,allowWriteImports:true}}),[
      {instance:db.instance,specs:PG_QUERY_STATE_LINKS},{instance:scram.instance,specs:PG_CANCELLABLE_SCRAM_LINKS}]);
    const tokenPtr=8192,channel=query.instance.exports.open(port,tokenPtr,4);
    assert.ok(channel>0n,'cancellable SCRAM session returns an affine i64 channel');
    const token=new DataView(query.instance.exports.memory.buffer).getInt32(tokenPtr);
    assert.ok(token>0,'cancel authority is copied as an opaque i32 token');
    const cancel=await instantiateLinkedKotobaComponents(readFileSync(cancelPath),hostCaps({grants:['pg-cancel-authority-use'],limits:{allowSecretImports:true,allowWriteImports:true}}),
      [{instance:scram.instance,specs:[PG_CANCELLABLE_SCRAM_LINKS[1]]}]);
    assert.equal(cancel.instance.exports.run(token),0,'compiled cancel consumer consumes the one-shot authority');
    for(let i=0;!cancelBytes&&i<50;i++)await new Promise(r=>setTimeout(r,10));
    assert.deepEqual([...cancelBytes],[0,0,0,16,4,210,22,46,0,0,0,1,0,0,0,2]);
    assert.equal(cancel.instance.exports.run(token),-1,'cancel authority cannot be reused');
    assert.equal(query.instance.exports.close(channel),0);
  }finally{await broker.closeAll();server.postMessage('close');await server.terminate()}
  console.log('compiled cancellable PostgreSQL consumers: opaque one-shot authority and fixed CancelRequest pass');
}finally{rmSync(dir,{recursive:true,force:true})}
