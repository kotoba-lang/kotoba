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
import { instantiateLinkedKotobaComponents, PG_BATCH_LINKS, PG_COPY_LINKS, PG_PORTAL_LINKS, PG_PREPARED_LINKS, PG_QUERY_STATE_LINKS,
  PG_SESSION_RESET_LINKS,
  PG_SCRAM_SESSION_LINKS, PG_TYPED_PREPARED_LINKS } from '../src/component-linker.js';
import { createNodeCredentialProvider } from '../src/node-credential-provider.js';
import { createNodeTransportBroker } from '../src/node-transport-broker.js';

const compilerRepo = resolve(fileURLToPath(new URL('.', import.meta.url)), '../../kotoba');
const dir = mkdtempSync(join(tmpdir(), 'kotoba-pg-prepared-'));
try {
  const keyPath=join(dir,'key.pem'), certPath=join(dir,'cert.pem');
  const dbPath=join(dir,'db.wasm'), scramPath=join(dir,'scram.wasm'), consumerPath=join(dir,'consumer.wasm');
  const typedConsumerPath=join(dir,'typed-consumer.wasm');
  const portalConsumerPath=join(dir,'portal-consumer.wasm');
  const batchConsumerPath=join(dir,'batch-consumer.wasm');
  const resetConsumerPath=join(dir,'reset-consumer.wasm');
  const copyConsumerPath=join(dir,'copy-consumer.wasm');
  execFileSync('openssl',['req','-x509','-newkey','rsa:2048','-nodes','-sha256','-keyout',keyPath,
    '-out',certPath,'-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost'],{stdio:'ignore'});
  const expression=`(require '[clojure.edn :as edn] '[kotoba.runtime :as runtime])
    (doseq [[s p o] [["providers/db_transport.kotoba" "providers/transport_policy.edn" "${dbPath}"]
                     ["providers/pg_scram.kotoba" "providers/pg_scram_policy.edn" "${scramPath}"]
                     ["providers/pg_prepared_consumer.kotoba" "providers/db_component_policy.edn" "${consumerPath}"]
                     ["providers/pg_typed_prepared_consumer.kotoba" "providers/db_component_policy.edn" "${typedConsumerPath}"]
                     ["providers/pg_portal_consumer.kotoba" "providers/db_component_policy.edn" "${portalConsumerPath}"]
                     ["providers/pg_batch_consumer.kotoba" "providers/db_component_policy.edn" "${batchConsumerPath}"]
                     ["providers/pg_pool_reset_consumer.kotoba" "providers/db_component_policy.edn" "${resetConsumerPath}"]
                     ["providers/pg_copy_consumer.kotoba" "providers/db_component_policy.edn" "${copyConsumerPath}"]]]
      (let [r (runtime/wasm-binary (runtime/read-file s :kotoba) (edn/read-string (slurp p)))]
        (assert (:kotoba.wasm/ok? r))
        (java.nio.file.Files/write (java.nio.file.Paths/get o (make-array String 0)) ^bytes (:kotoba.wasm/binary r) (make-array java.nio.file.OpenOption 0))))`;
  execFileSync('clojure',['-M:dev','-i','tools/cljk_loader.cljk','-e',expression],{cwd:compilerRepo,stdio:'ignore'});
  const key=readFileSync(keyPath,'utf8'), cert=readFileSync(certPath,'utf8');
  const server=new Worker(`
    const {parentPort,workerData}=require('node:worker_threads');
    const net=require('node:net'),tls=require('node:tls'),context=tls.createSecureContext(workerData);
    const sasl=Buffer.concat([Buffer.from([82,0,0,0,23,0,0,0,10]),Buffer.from('SCRAM-SHA-256\\0\\0')]);
    const sf=Buffer.from('r=AAECAwQFBgcICQoLDA0ODxARserver,s=W22ZaJ0SNY7soEsUEjb6gQ==,i=4096');
    const cont=Buffer.concat([Buffer.from([82,0,0,0,sf.length+8,0,0,0,11]),sf]);
    const fin=Buffer.from('v=QAdQmJ+lRK7pdc/DBEeFAbUmtBhFLhQXsQNpv3KJgJQ=');
    const final=Buffer.concat([Buffer.from([82,0,0,0,fin.length+8,0,0,0,12]),fin]);
    const tail=Buffer.from([82,0,0,0,8,0,0,0,0,75,0,0,0,12,0,0,0,1,0,0,0,2,90,0,0,0,5,73]);
    const ready=Buffer.from([90,0,0,0,5,73]), parsed=Buffer.from([49,0,0,0,4,110,0,0,0,4]), bound=Buffer.from([50,0,0,0,4]);
    const row=Buffer.from([68,0,0,0,12,0,1,0,0,0,2,52,50]);
    const complete=Buffer.from([67,0,0,0,13,83,69,76,69,67,84,32,49,0]);
    const bad=Buffer.from([69,0,0,0,12,67,50,50,80,48,50,0,0]);
    const division=Buffer.from([69,0,0,0,12,67,50,50,48,49,50,0,0]);
    const missing=Buffer.from([69,0,0,0,12,67,50,54,48,48,48,0,0]);
    const closed=Buffer.from([51,0,0,0,4]);
    const replies=[Buffer.concat([parsed,ready]),Buffer.concat([bound,row,complete,ready]),Buffer.concat([bad,ready]),Buffer.concat([bound,row,complete,ready]),Buffer.concat([closed,ready])];
    const readyT=Buffer.from([90,0,0,0,5,84]), suspended=Buffer.from([115,0,0,0,4]);
    const data=n=>Buffer.from([68,0,0,0,11,0,1,0,0,0,1,48+n]);
    const command=tag=>Buffer.concat([Buffer.from([67,0,0,0,tag.length+5]),Buffer.from(tag+'\0')]);
    const portalReplies=[Buffer.concat([parsed,ready]),Buffer.concat([command('BEGIN'),readyT]),Buffer.concat([bound,readyT]),
      Buffer.concat([data(1),data(2),suspended,readyT]),Buffer.concat([data(3),command('SELECT 3'),readyT]),
      Buffer.concat([closed,readyT]),Buffer.concat([command('COMMIT'),ready]),Buffer.concat([closed,ready])];
    const batchReplies=[Buffer.concat([parsed,ready]),Buffer.concat([parsed,ready]),Buffer.concat([parsed,ready]),
      Buffer.concat([bound,row,complete,bound,row,complete,ready]),
      Buffer.concat([bound,row,complete,division,ready]),Buffer.concat([bound,row,complete,ready]),
      Buffer.concat([closed,ready]),Buffer.concat([closed,ready]),Buffer.concat([closed,ready])];
    const emptyRow=Buffer.from([68,0,0,0,10,0,1,0,0,0,0]);
    const trueRow=Buffer.from([68,0,0,0,11,0,1,0,0,0,1,116]);
    const resetReplies=[Buffer.concat([command('SET'),ready]),Buffer.concat([command('CREATE TABLE'),ready]),Buffer.concat([parsed,ready]),
      Buffer.concat([command('BEGIN'),readyT]),Buffer.concat([command('INSERT 0 1'),readyT]),Buffer.concat([command('ROLLBACK'),ready]),
      Buffer.concat([command('DISCARD ALL'),ready]),Buffer.concat([emptyRow,command('SHOW'),ready]),
      Buffer.concat([trueRow,command('SELECT 1'),ready]),Buffer.concat([missing,ready]),Buffer.concat([row,complete,ready])];
    const copyIn=Buffer.from([71,0,0,0,7,0,0,0]), copyOut=Buffer.from([72,0,0,0,7,0,0,0]);
    const copyData=n=>Buffer.from([100,0,0,0,6,48+n,10]), copyDone=Buffer.from([99,0,0,0,4]);
    const sixRow=Buffer.from([68,0,0,0,11,0,1,0,0,0,1,54]);
    const copyReplies=[Buffer.concat([command('CREATE TABLE'),ready]),copyIn,Buffer.concat([command('COPY 3'),ready]),
      Buffer.concat([copyOut,copyData(1),copyData(2),copyData(3),copyDone,command('COPY 3'),ready]),
      Buffer.concat([sixRow,command('SELECT 1'),ready])];
    const server=net.createServer(socket=>{let plain=Buffer.alloc(0);socket.on('data',function ssl(c){plain=Buffer.concat([plain,c]);if(plain.length<8)return;socket.removeListener('data',ssl);socket.write(Buffer.from('S'));
      const secure=new tls.TLSSocket(socket,{isServer:true,secureContext:context});let input=Buffer.alloc(0),stage=0,operation=0,mode='prepared',group=[];
      secure.on('error',()=>{});secure.on('data',c2=>{input=Buffer.concat([input,c2]);while(true){const needed=stage===0?(input.length>=4?input.readInt32BE(0):Infinity):(input.length>=5?input.readInt32BE(1)+1:Infinity);if(input.length<needed)break;const frame=input.subarray(0,needed);input=input.subarray(needed);
        if(stage===0){secure.write(sasl);stage=1}else if(stage===1){secure.write(cont);stage=2}else if(stage===2){secure.write(Buffer.concat([final,tail]));stage=3}else{group.push(frame);if(frame[0]===83||frame[0]===81||(mode==='copy'&&frame[0]===99)){if(operation===0){const bytes=Buffer.concat(group);if(bytes.includes(Buffer.from('generate_series')))mode='portal';else if(bytes.includes(Buffer.from('forty2a')))mode='batch';else if(bytes.includes(Buffer.from('dirty-lease')))mode='reset';else if(bytes.includes(Buffer.from('copy_values')))mode='copy'}parentPort.postMessage({group:group.map(x=>Buffer.from(x))});const selected=mode==='portal'?portalReplies:mode==='batch'?batchReplies:mode==='reset'?resetReplies:mode==='copy'?copyReplies:replies;secure.write(selected[operation]);group=[];operation++}}}});secure.resume()})});
    server.listen(0,'127.0.0.1',()=>parentPort.postMessage({port:server.address().port}));parentPort.on('message',()=>server.close());
  `,{eval:true,workerData:{key,cert}});
  const [{port}]=await once(server,'message'); const groups=[];
  server.on('message',m=>{if(m.group)groups.push(m.group.map(x=>Buffer.from(x)))});
  const broker=createNodeTransportBroker({endpointAllowlist:[`localhost:${port}`],resolvedAddressAllowlist:['127.0.0.1'],maxConnections:1,
    connectTimeoutMs:1500,readTimeoutMs:1500,maxReadBytes:65536,maxWriteBytes:65536,trustedCaPem:cert});
  const low=['transport-connect','tls-open','tls-server-end-point','transport-write','transport-read','transport-close','scram-sha256','pg-cancel-register','pg-cancel','random-bytes'];
  const lowCaps=hostCaps({grants:low,limits:{maxTransportConnections:1,maxScramProofs:1,maxPgCancelHandles:1,maxPgCancelRequests:1,maxRandomBytes:18,allowSecretImports:true,allowWriteImports:true,scramCredentialAllowlist:['db/primary']}});
  try{
    const db=await instantiateKotobaComponent(readFileSync(dbPath),hostCaps({grants:low.slice(0,6),limits:{maxTransportConnections:1,allowWriteImports:true}}),{transport:broker});
    const scram=await instantiateKotobaComponent(readFileSync(scramPath),lowCaps,{transport:broker,credentials:createNodeCredentialProvider({credentialAllowlist:['db/primary'],maxProofs:1,credentials:{'db/primary':'pencil'}}),randomBytes:n=>Uint8Array.from({length:n},(_,i)=>i)});
    const high=['pg-prepare','pg-execute-params2','pg-close-statement','pg-open-scram-random','pg-close-scram'];
    const consumer=await instantiateLinkedKotobaComponents(readFileSync(consumerPath),hostCaps({grants:high,limits:{allowSecretImports:true,allowWriteImports:true}}),[
      {instance:db.instance,specs:PG_PREPARED_LINKS},{instance:scram.instance,specs:PG_SCRAM_SESSION_LINKS}]);
    assert.equal(consumer.instance.exports.run(port),1,'prepared statements preserve parameter separation and recover after 22P02');
    for(let i=0;groups.length<5&&i<50;i++)await new Promise(r=>setTimeout(r,10));
    assert.deepEqual(groups.map(g=>g.map(f=>String.fromCharCode(f[0])).join('')),['PDS','BES','BES','BES','CS']);
    const parseBytes=Buffer.concat(groups[0]).toString('utf8');
    const injectedBind=Buffer.concat(groups[2]).toString('utf8');
    assert.ok(parseBytes.includes('select $1::int4 + $2::int4'));
    assert.ok(!parseBytes.includes('1;select 99')&&injectedBind.includes('1;select 99'),'injected text remains a Bind value, never query text');
    const typedBroker=createNodeTransportBroker({endpointAllowlist:[`localhost:${port}`],resolvedAddressAllowlist:['127.0.0.1'],maxConnections:1,
      connectTimeoutMs:1500,readTimeoutMs:1500,maxReadBytes:65536,maxWriteBytes:65536,trustedCaPem:cert});
    try{
      const typedDb=await instantiateKotobaComponent(readFileSync(dbPath),hostCaps({grants:low.slice(0,6),limits:{maxTransportConnections:1,allowWriteImports:true}}),{transport:typedBroker});
      const typedScram=await instantiateKotobaComponent(readFileSync(scramPath),lowCaps,{transport:typedBroker,credentials:createNodeCredentialProvider({credentialAllowlist:['db/primary'],maxProofs:1,credentials:{'db/primary':'pencil'}}),randomBytes:n=>Uint8Array.from({length:n},(_,i)=>i)});
      const typedHigh=['pg-prepare-typed','pg-execute-params','pg-close-statement','pg-open-scram-random','pg-close-scram'];
      const typed=await instantiateLinkedKotobaComponents(readFileSync(typedConsumerPath),hostCaps({grants:typedHigh,limits:{allowSecretImports:true,allowWriteImports:true}}),[
        {instance:typedDb.instance,specs:[...PG_TYPED_PREPARED_LINKS,PG_PREPARED_LINKS[2]]},
        {instance:typedScram.instance,specs:PG_SCRAM_SESSION_LINKS}]);
      assert.equal(typed.instance.exports.run(port),1,'typed text/binary/null parameters remain bounded and recover after 22P02');
      for(let i=0;groups.length<10&&i<50;i++)await new Promise(r=>setTimeout(r,10));
      assert.deepEqual(groups.slice(5).map(g=>g.map(f=>String.fromCharCode(f[0])).join('')),['PDS','BES','BES','BES','CS']);
      const typedParse=Buffer.concat(groups[5]);
      const typedBind=Buffer.concat(groups[6]);
      const typedInjection=Buffer.concat(groups[7]).toString('utf8');
      assert.ok(typedParse.includes(Buffer.from([0,3,0,0,0,23,0,0,0,23,0,0,0,23])),'Parse declares three int4 OIDs');
      assert.ok(typedBind.includes(Buffer.from([0,3,0,0,0,0,0,1])),'Bind declares text,text,binary formats');
      assert.ok(typedBind.includes(Buffer.from([255,255,255,255])),'Bind preserves SQL NULL sentinel');
      assert.ok(typedBind.includes(Buffer.from([0,0,0,4,0,0,0,22])),'binary int4 parameter remains four big-endian bytes');
      assert.ok(!typedParse.toString('utf8').includes('1;select 99')&&typedInjection.includes('1;select 99'));
    }finally{await typedBroker.closeAll()}
    const portalBroker=createNodeTransportBroker({endpointAllowlist:[`localhost:${port}`],resolvedAddressAllowlist:['127.0.0.1'],maxConnections:1,
      connectTimeoutMs:1500,readTimeoutMs:1500,maxReadBytes:65536,maxWriteBytes:65536,trustedCaPem:cert});
    try{
      const portalDb=await instantiateKotobaComponent(readFileSync(dbPath),hostCaps({grants:low.slice(0,6),limits:{maxTransportConnections:1,allowWriteImports:true}}),{transport:portalBroker});
      const portalScram=await instantiateKotobaComponent(readFileSync(scramPath),lowCaps,{transport:portalBroker,credentials:createNodeCredentialProvider({credentialAllowlist:['db/primary'],maxProofs:1,credentials:{'db/primary':'pencil'}}),randomBytes:n=>Uint8Array.from({length:n},(_,i)=>i)});
      const portalHigh=['pg-prepare','pg-query-state','pg-bind-portal','pg-fetch-portal','pg-close-portal','pg-close-statement','pg-open-scram-random','pg-close-scram'];
      const portal=await instantiateLinkedKotobaComponents(readFileSync(portalConsumerPath),hostCaps({grants:portalHigh,limits:{allowSecretImports:true,allowWriteImports:true}}),[
        {instance:portalDb.instance,specs:[PG_PREPARED_LINKS[0],...PG_QUERY_STATE_LINKS,...PG_PORTAL_LINKS,PG_PREPARED_LINKS[2]]},
        {instance:portalScram.instance,specs:PG_SCRAM_SESSION_LINKS}]);
      assert.equal(portal.instance.exports.run(port),1,'named portal suspends and resumes inside an explicit transaction');
      for(let i=0;groups.length<18&&i<50;i++)await new Promise(r=>setTimeout(r,10));
      assert.deepEqual(groups.slice(10).map(g=>g.map(f=>String.fromCharCode(f[0])).join('')),['PDS','Q','BS','ES','ES','CS','Q','CS']);
      const portalParse=Buffer.concat(groups[10]).toString('utf8');
      const portalBind=Buffer.concat(groups[12]).toString('utf8');
      const firstExecute=groups[13][0], secondExecute=groups[14][0];
      assert.ok(portalParse.includes('series3')&&portalParse.includes('generate_series'));
      assert.ok(portalBind.includes('page')&&portalBind.includes('series3'),'Bind names both portal and prepared statement');
      assert.ok(firstExecute.toString('utf8').includes('page')&&secondExecute.toString('utf8').includes('page'));
      assert.equal(firstExecute.readInt32BE(firstExecute.length-4),2,'first Execute is bounded to two rows');
      assert.equal(secondExecute.readInt32BE(secondExecute.length-4),2,'resumed Execute preserves the row bound');
    }finally{await portalBroker.closeAll()}
    const batchBroker=createNodeTransportBroker({endpointAllowlist:[`localhost:${port}`],resolvedAddressAllowlist:['127.0.0.1'],maxConnections:1,
      connectTimeoutMs:1500,readTimeoutMs:1500,maxReadBytes:65536,maxWriteBytes:65536,trustedCaPem:cert});
    try{
      const batchDb=await instantiateKotobaComponent(readFileSync(dbPath),hostCaps({grants:low.slice(0,6),limits:{maxTransportConnections:1,allowWriteImports:true}}),{transport:batchBroker});
      const batchScram=await instantiateKotobaComponent(readFileSync(scramPath),lowCaps,{transport:batchBroker,credentials:createNodeCredentialProvider({credentialAllowlist:['db/primary'],maxProofs:1,credentials:{'db/primary':'pencil'}}),randomBytes:n=>Uint8Array.from({length:n},(_,i)=>i)});
      const batchHigh=['pg-prepare','pg-execute-batch','pg-close-statement','pg-open-scram-random','pg-close-scram'];
      const batch=await instantiateLinkedKotobaComponents(readFileSync(batchConsumerPath),hostCaps({grants:batchHigh,limits:{allowSecretImports:true,allowWriteImports:true}}),[
        {instance:batchDb.instance,specs:[PG_PREPARED_LINKS[0],...PG_BATCH_LINKS,PG_PREPARED_LINKS[2]]},
        {instance:batchScram.instance,specs:PG_SCRAM_SESSION_LINKS}]);
      assert.equal(batch.instance.exports.run(port),1,'batch recovers after a middle statement error');
      for(let i=0;groups.length<27&&i<50;i++)await new Promise(r=>setTimeout(r,10));
      assert.deepEqual(groups.slice(18).map(g=>g.map(f=>String.fromCharCode(f[0])).join('')),
        ['PDS','PDS','PDS','BEBES','BEBEBES','BES','CS','CS','CS']);
      const successBatch=Buffer.concat(groups[21]).toString('utf8');
      const failedBatch=Buffer.concat(groups[22]).toString('utf8');
      assert.ok(successBatch.includes('forty2a')&&successBatch.includes('forty2b'));
      assert.ok(failedBatch.includes('forty2a')&&failedBatch.includes('divide0')&&failedBatch.includes('forty2b'));
    }finally{await batchBroker.closeAll()}
    const resetBroker=createNodeTransportBroker({endpointAllowlist:[`localhost:${port}`],resolvedAddressAllowlist:['127.0.0.1'],maxConnections:1,
      connectTimeoutMs:1500,readTimeoutMs:1500,maxReadBytes:65536,maxWriteBytes:65536,trustedCaPem:cert});
    try{
      const resetDb=await instantiateKotobaComponent(readFileSync(dbPath),hostCaps({grants:low.slice(0,6),limits:{maxTransportConnections:1,allowWriteImports:true}}),{transport:resetBroker});
      const resetScram=await instantiateKotobaComponent(readFileSync(scramPath),lowCaps,{transport:resetBroker,credentials:createNodeCredentialProvider({credentialAllowlist:['db/primary'],maxProofs:1,credentials:{'db/primary':'pencil'}}),randomBytes:n=>Uint8Array.from({length:n},(_,i)=>i)});
      const resetHigh=['pg-query-state','pg-prepare','pg-execute-params','pg-session-reset','pg-open-scram-random','pg-close-scram'];
      const reset=await instantiateLinkedKotobaComponents(readFileSync(resetConsumerPath),hostCaps({grants:resetHigh,limits:{allowSecretImports:true,allowWriteImports:true}}),[
        {instance:resetDb.instance,specs:[...PG_QUERY_STATE_LINKS,PG_PREPARED_LINKS[0],PG_TYPED_PREPARED_LINKS[1],...PG_SESSION_RESET_LINKS]},
        {instance:resetScram.instance,specs:PG_SCRAM_SESSION_LINKS}]);
      assert.equal(reset.instance.exports.run(port),1,'session reset rolls back and discards state before reuse');
      for(let i=0;groups.length<38&&i<50;i++)await new Promise(r=>setTimeout(r,10));
      assert.deepEqual(groups.slice(27).map(g=>g.map(f=>String.fromCharCode(f[0])).join('')),
        ['Q','Q','PDS','Q','Q','Q','Q','Q','Q','BES','Q']);
      assert.ok(Buffer.concat(groups[32]).toString('utf8').includes('ROLLBACK'));
      assert.ok(Buffer.concat(groups[33]).toString('utf8').includes('DISCARD ALL'));
      assert.ok(Buffer.concat(groups[37]).toString('utf8').includes('select 42'),'reset connection is reusable');
    }finally{await resetBroker.closeAll()}
    const copyBroker=createNodeTransportBroker({endpointAllowlist:[`localhost:${port}`],resolvedAddressAllowlist:['127.0.0.1'],maxConnections:1,
      connectTimeoutMs:1500,readTimeoutMs:1500,maxReadBytes:65536,maxWriteBytes:65536,trustedCaPem:cert});
    try{
      const copyDb=await instantiateKotobaComponent(readFileSync(dbPath),hostCaps({grants:low.slice(0,6),limits:{maxTransportConnections:1,allowWriteImports:true}}),{transport:copyBroker});
      const copyScram=await instantiateKotobaComponent(readFileSync(scramPath),lowCaps,{transport:copyBroker,credentials:createNodeCredentialProvider({credentialAllowlist:['db/primary'],maxProofs:1,credentials:{'db/primary':'pencil'}}),randomBytes:n=>Uint8Array.from({length:n},(_,i)=>i)});
      const copyHigh=['pg-query-state','pg-copy-in','pg-copy-out','pg-open-scram-random','pg-close-scram'];
      const copy=await instantiateLinkedKotobaComponents(readFileSync(copyConsumerPath),hostCaps({grants:copyHigh,limits:{allowSecretImports:true,allowWriteImports:true}}),[
        {instance:copyDb.instance,specs:[...PG_QUERY_STATE_LINKS,...PG_COPY_LINKS]},
        {instance:copyScram.instance,specs:PG_SCRAM_SESSION_LINKS}]);
      assert.equal(copy.instance.exports.run(port),1,'COPY IN/OUT preserves bounded data framing and result metadata');
      for(let i=0;groups.length<43&&i<50;i++)await new Promise(r=>setTimeout(r,10));
      assert.deepEqual(groups.slice(38).map(g=>g.map(f=>String.fromCharCode(f[0])).join('')),['Q','Q','dc','Q','Q']);
      const inbound=Buffer.concat(groups[40]);
      assert.ok(inbound.includes(Buffer.from('1\n2\n3\n')),'COPY IN payload remains in CopyData');
      assert.ok(Buffer.concat(groups[41]).toString('utf8').includes('to stdout'));
      assert.ok(Buffer.concat(groups[42]).toString('utf8').includes('sum(value)'));
    }finally{await copyBroker.closeAll()}
  }finally{await broker.closeAll();server.postMessage('close');await server.terminate()}
  console.log('compiled PostgreSQL prepared + typed + portal + batch + reset + COPY consumers: bounded wire state and recovery pass');
}finally{rmSync(dir,{recursive:true,force:true})}
