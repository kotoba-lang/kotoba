"""Public signed bytes and explicit expected cases, never an EDN evaluator.

Only published RFC8032 seeds are used. Python constructs literal test input,
independently signs/hashes it and describes expectations; Kotoba owns parsing,
policy, state transitions and assertions in the guest.
"""
import base64
import hashlib
import importlib.util
from pathlib import Path
import re
import struct
import sys

ROOT=Path(__file__).resolve().parents[3]
NOW=1750000000
DER=bytes.fromhex('302a300506032b6570032100')

def fixtures(suite='policy',fault=None):
    scripts=ROOT/'lib/kotoba.aiueos/os/aiueos/scripts';sys.path.insert(0,str(scripts))
    def load(name,path):
        spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    old=load('roster_legacy_rfc',scripts/'check-native-ed25519-qemu.py')
    ed=load('roster_public_ed',scripts/'check-native-consent-qemu.py')
    seed=bytes.fromhex('4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb');pub=ed.ed_public(seed)
    def envelope(msg):
        h=hashlib.sha512(seed).digest();a=bytearray(h[:32]);a[0]&=248;a[31]&=127;a[31]|=64
        scalar=int.from_bytes(a,'little');nonce=int.from_bytes(hashlib.sha512(h[32:]+msg).digest(),'little')%ed._L
        rr=ed._enc(ed._mul(nonce,ed._B));k=int.from_bytes(hashlib.sha512(rr+pub+msg).digest(),'little')%ed._L
        sig=rr+((nonce+k*scalar)%ed._L).to_bytes(32,'little');assert ed.ed_verify(pub,msg,sig)
        fields=[('payload-b64',base64.b64encode(msg).decode()),('signature-b64',base64.b64encode(sig).decode()),('signer-spki-b64',base64.b64encode(DER+pub).decode()),('sha256',hashlib.sha256(msg).hexdigest())]
        return ('{'+', '.join(':netmap/'+k+' "'+v+'"' for k,v in fields)+'}').encode()
    self_node=b'{:node/id "n-laptop" :node/key "'+b'11'*32+b'" :node/overlay-ip "10.0.0.1"}'
    peer=b'{:node/id "server" :node/key "'+b'22'*32+b'" :node/overlay-ip "10.0.0.2" :node/status "authorized" :node/expires-at 1750000100}'
    edge=b'{:edge/from "n-laptop" :edge/to "server" :edge/capabilities [:overlay :ssh] :edge/ports [22]}'
    def payload(version=43,self_value=self_node,peers=peer,edges=edge,relays=b'[]',tail=b'"default"',extra=b''):
        return b'{:netmap/version '+str(version).encode()+b' :netmap/tailnet '+tail+b' :netmap/self '+self_value+b' :netmap/peers ['+peers+b'] :netmap/edges ['+edges+b'] :netmap/relays '+relays+extra+b'}'
    baseline_payload=payload(42);baseline=envelope(baseline_payload);normal=payload()
    rows=[]
    def add(label,msg=normal,result=1,config=0,now=NOW,session=1,out22=1,in22=0,out80=0,nodes=2,raw=None):
        # Refusals retain the baseline; expectations are written explicitly.
        if result==0:session,out22,in22,out80,nodes=1,1,0,0,2
        rows.append(dict(label=label,raw=envelope(msg) if raw is None else raw,expected=result,config=config,now=now,session=session,out22=out22,in22=in22,out80=out80,nodes=nodes,version=43 if result==1 else 42,generation=2 if result==1 else 1,wiped=int(result==1 or (result==2 and now>=NOW+100))))
    add('new-version')
    add('exact-same-version',baseline_payload,result=2)
    add('same-version-conflict',payload(42,extra=b' :netmap/funnels []'),result=0)
    add('older-version',payload(41),result=0)
    for mode,label in [(1,'wrong-self-id-config'),(2,'wrong-self-key-config'),(3,'wrong-tailnet-config'),(4,'configured-version-floor'),(5,'configured-clock-floor'),(6,'bad-config-magic'),(7,'malformed-config-utf8'),(8,'wrong-configured-authority'),(9,'negative-version-floor')]:add(label,result=0,config=mode)
    add('clock-backwards',result=0,now=NOW-1)
    add('exact-expiry',peer.replace(b'1750000100',b'1750000000').join(normal.split(peer)),session=0,out22=0)
    add('expired',normal.replace(b'1750000100',b'1749999999'),session=0,out22=0)
    add('expiry-nil',normal.replace(b'1750000100',b'nil'))
    add('expiry-absent',normal.replace(b' :node/expires-at 1750000100',b''))
    add('pending',normal.replace(b'"authorized"',b'"pending"'),session=0,out22=0)
    add('revoked',normal.replace(b'"authorized"',b'"revoked"'),session=0,out22=0)
    add('self-revoked',payload(self_value=self_node[:-1]+b' :node/status "revoked"}'),session=0,out22=0)
    add('self-expired',payload(self_value=self_node[:-1]+b' :node/expires-at 1750000000}'),session=0,out22=0)
    add('no-edges',payload(edges=b''),session=0,out22=0)
    add('ssh-without-overlay',payload(edges=edge.replace(b':overlay ',b'')),session=0,out22=0)
    add('reverse-edge',payload(edges=edge.replace(b'"n-laptop" :edge/to "server"',b'"server" :edge/to "n-laptop"')),out22=0,in22=1)
    add('any-port',payload(edges=edge.replace(b'[22]',b'[:any]')),out80=1)
    add('cross-edge-no-union',payload(edges=edge.replace(b'[:overlay :ssh]',b'[:overlay]')+b' '+edge.replace(b'[:overlay :ssh]',b'[:ssh]').replace(b'[22]',b'[80]')),out22=0,out80=1)
    add('unicode-escaped-identities',normal.replace(b'"server"',b'"s\\u0065rver"').replace(b'"default"',b'"d\\u0065fault"').replace(b'"authorized"',b'"authoriz\\u0065d"'))
    add('unicode-paired-self-id',normal.replace(b'"n-laptop"',b'"n-\\ud83d\\ude00"'),config=10)
    add('list-sequences',payload(edges=edge.replace(b'[:overlay :ssh]',b'(:overlay :ssh)').replace(b'[22]',b'(22)')))
    add('metadata',payload(peers=peer[:-1]+b' :node/endpoints [{:kind :reflexive :host "127.0.0.1" :port 7798}]}',relays=b'[{:relay/name "r" :relay/region "jp" :relay/host "relay.example" :relay/port 443 :relay/key "abcd"}]',extra=b' :netmap/funnels [{:funnel/host "demo.example" :funnel/edge "edge" :funnel/node "server" :funnel/service "ssh" :funnel/port 22}]'))
    add('funnel-does-not-grant',payload(edges=b'',extra=b' :netmap/funnels [{:funnel/host "demo.example" :funnel/edge "edge" :funnel/node "server" :funnel/service "ssh" :funnel/port 22}]'),session=0,out22=0)
    for label,msg in [
        ('missing-version',normal.replace(b':netmap/version 43 ',b'')),('negative-version',normal.replace(b'version 43',b'version -1')),
        ('wrong-version-type',normal.replace(b'version 43',b'version "43"')),('wrong-tailnet',normal.replace(b'"default"',b'"other"')),
        ('wrong-self-id',normal.replace(b'"n-laptop"',b'"other"')),('wrong-self-key',normal.replace(b'11'*32,b'33'*32)),
        ('duplicate-peer-id',payload(peers=peer+b' '+peer.replace(b'22'*32,b'33'*32))),
        ('duplicate-escaped-peer-id',payload(peers=peer+b' '+peer.replace(b'"server"',b'"s\\u0065rver"').replace(b'22'*32,b'33'*32))),
        ('duplicate-peer-key',payload(peers=peer+b' '+peer.replace(b'"server"',b'"other"'))),
        ('self-as-peer-id',normal.replace(b'"server"',b'"n-laptop"')),('self-as-peer-key',normal.replace(b'22'*32,b'11'*32)),
        ('zero-peer-key',normal.replace(b'22'*32,b'00'*32)),('bad-peer-key',normal.replace(b'22'*32,b'gg'*32)),
        ('short-peer-key',normal.replace(b'22'*32,b'22'*31)),('missing-status',normal.replace(b' :node/status "authorized"',b'')),
        ('negative-expiry',normal.replace(b'1750000100',b'-1')),('string-expiry',normal.replace(b'1750000100',b'"1750000100"')),
        ('unknown-field',normal[:-1]+b' :netmap/unknown true}'),('duplicate-field',normal[:-1]+b' :netmap/version 43}'),
        ('unknown-node-field',normal.replace(peer,peer[:-1]+b' :node/extra 1}')),('bad-endpoint-type',normal.replace(peer,peer[:-1]+b' :node/endpoints "x"}')),
        ('edge-unknown-peer',normal.replace(b':edge/to "server"',b':edge/to "missing"')),('nonkeyword-capability',normal.replace(b':ssh',b'"ssh"')),
        ('port-zero',normal.replace(b'[22]',b'[0]')),('port-too-high',normal.replace(b'[22]',b'[65536]')),('port-string',normal.replace(b'[22]',b'["22"]')),
        ('port-keyword-other',normal.replace(b'[22]',b'[:all]')),('empty-node-id',normal.replace(b'"server"',b'""')),
        ('escaped-control-id',normal.replace(b'"server"',b'"s\\n"')),('nonfinite-edn',normal.replace(b'version 43',b'version ##NaN')),
        ('tagged-edn',b'#unsafe '+normal),('trailing-edn',normal+b' {}'),('invalid-utf8',normal.replace(b'"default"',b'"\xc0\xaf"')),
        ('unpaired-surrogate',normal.replace(b'"default"',b'"\\ud800"')),('bad-relay-port',payload(relays=b'[{:relay/name "r" :relay/region "jp" :relay/host "x" :relay/port 0 :relay/key "abcd"}]')),
    ]:add(label,msg,result=0)
    add('bad-signature',raw=envelope(normal).replace(b':netmap/signature-b64 "',b':netmap/signature-b64 "A',1),result=0)
    add('same-version-expiry-reaps',baseline_payload,result=2,now=NOW+100,session=0,out22=0)
    # Explicit capacity probes; construction emits data and never parses it.
    many=lambda n:b' '.join(b'{:node/id "p'+str(i).encode().rjust(3,b'0')+b'" :node/key "'+(i+48).to_bytes(32,'big').hex().encode()+b'" :node/overlay-ip "x" :node/status "authorized"}' for i in range(n))
    boundary_start=len(rows)
    add('maximum-64-peers',payload(peers=many(63)+b' '+peer),nodes=65)
    add('over-64-peers',payload(peers=many(64)+b' '+peer),result=0)
    add('maximum-128-edges',payload(edges=b' '.join([edge]*128)))
    add('over-128-edges',payload(edges=b' '.join([edge]*129)),result=0)
    add('arena-overflow',payload(tail=b'"default"',peers=peer.replace(b'10.0.0.2',b'x'*16384)),result=0)
    edn=[]
    literal_values={b'0':0,b'-0':0,b'+1':1,b'-9223372036854775808':-9223372036854775808,b'9223372036854775807':9223372036854775807}
    def doc(label,raw=b'',expected=1,nodes=1,mode=0,n=0):edn.append(dict(label=label,raw=raw,expected=expected,nodes=nodes if expected else 0,mode=mode,n=n,integer=literal_values.get(raw,0)))
    for raw in [b'0',b'-0',b'+1',b'-9223372036854775808',b'9223372036854775807',b'nil',b'true',b'false',b':cap/ssh',b'""',b'"\\u0061"',b'"\\ud83d\\ude00"','"日本語"'.encode(),b'"\\n\\r\\t\\b\\f\\\\\\\""',b'[]',b'{}',b'()']:
        doc('valid-'+raw.hex(),raw)
    doc('nested',b'{:a [1 true nil] :b ("x" :z)}',nodes=10)
    doc('separators-comments',b';before\n{, :a, 1, ;inside\n :b []}, ;after',nodes=5)
    doc('invalid-utf8-comment',b';\xff\n0',expected=0)
    for label,raw in [('empty',b''),('unfinished',b'{:a'),('odd-map',b'{:a}'),('duplicate-map-key',b'{:a 1 :a 2}'),('nonkeyword-map-key',b'{"a" 1}'),('mismatched-close',b'[1)'),('two-forms',b'0 1'),('leading-zero',b'01'),('positive-overflow',b'9223372036854775808'),('negative-overflow',b'-9223372036854775809'),('sign-only',b'+'),('float',b'1.0'),('ratio',b'1/2'),('symbol',b'word'),('tag',b'#tag "x"'),('discard',b'#_ 1 2'),('set',b'#{1}'),('namespace-map',b'#:n{:a 1}'),('unclosed-string',b'"x'),('raw-control',b'"\x00"'),('bad-escape',b'"\\x"'),('lone-high',b'"\\ud800"'),('lone-low',b'"\\udfff"'),('high-non-low',b'"\\ud800\\u0041"'),('overlong-utf8',b'"\xc0\xaf"'),('surrogate-utf8',b'"\xed\xa0\x80"'),('too-high-utf8',b'"\xf4\x90\x80\x80"'),('truncated-utf8',b'"\xe3\x81"'),('bare-continuation',b'"\x80"')]:doc(label,raw,expected=0)
    doc('maximum-input-string',mode=1,n=65536)
    doc('maximum-input-whitespace',mode=4,n=65536)
    doc('depth-64',mode=2,n=63,nodes=64)
    doc('over-depth-64',mode=2,n=64,expected=0)
    doc('maximum-4096-nodes',mode=3,n=4095,nodes=4096)
    doc('over-4096-nodes',mode=3,n=4096,expected=0)
    if suite=='policy':rows=rows[:boundary_start]
    elif suite=='bounds':rows=rows[boundary_start:];edn=[]
    elif suite=='faults':
        targets={'rs-self-key':'wrong-self-key-config','rs-version':'older-version','rs-same-version':'same-version-conflict',
                 'rs-expiry':'exact-expiry','rs-status':'pending','rs-self-status':'self-revoked','rs-direction':'new-version',
                 'rs-port':'new-version','rs-wipe':'new-version','rs-epoch':'new-version'}
        documents={'rd-utf8':'invalid-utf8-comment','rd-duplicate':'duplicate-map-key','rd-overflow':'positive-overflow','rd-wipe':'odd-map'}
        if fault in targets:rows=[r for r in rows if r['label']==targets[fault]];edn=[];assert len(rows)==1
        elif fault in documents:rows=[];edn=[r for r in edn if r['label']==documents[fault]];assert len(edn)==1
        else:raise ValueError('unknown fault case')
    else:raise ValueError('unknown roster suite')
    assert len(rows)<=128 and len(edn)<=128
    header=bytearray(64);header[:8]=b'KROSTER2';table=bytearray(len(rows)*64+len(edn)*32);pool=bytearray()
    def intern(raw):
        if not raw:return 0
        at=pool.find(raw)
        if at<0:at=len(pool);pool.extend(raw)
        return 64+len(table)+at
    legacy=b''
    for i,s in enumerate(['9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60','4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb','c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7']):legacy+=bytes.fromhex(s+old.CASES[i][1]+old.SIGS[i][1])+[b'',b'\x72',bytes.fromhex('af82')][i].ljust(64,b'\0')
    struct.pack_into('<I',header,8,len(rows));struct.pack_into('<I',header,12,intern(legacy));struct.pack_into('<I',header,16,intern(hashlib.sha256(b'abc').digest()))
    raw=(ROOT/'lib/kotoba.kekkai/test/fixtures/netmap.signed.edn').read_bytes();fields=dict(re.findall(rb':netmap/([a-z0-9-]+) "([^"]*)"',raw));spki=base64.b64decode(fields[b'signer-spki-b64'],validate=True)
    assert spki[:12]==DER and len(spki)==44
    struct.pack_into('<II',header,20,intern(raw),len(raw));struct.pack_into('<I',header,28,intern(spki[12:]));struct.pack_into('<I',header,32,intern(pub))
    struct.pack_into('<III',header,36,64,len(edn),64+len(rows)*64);struct.pack_into('<II',header,48,intern(baseline),len(baseline))
    for i,row in enumerate(rows):
        struct.pack_into('<16I',table,i*64,intern(row['raw']),len(row['raw']),intern(pub),row['expected'],row['config'],row['now'],row['session'],row['out22'],row['in22'],row['out80'],row['generation'],row['version'],0,1,row['wiped'],row['nodes'])
    for i,row in enumerate(edn):struct.pack_into('<6Iq',table,len(rows)*64+i*32,intern(row['raw']),len(row['raw']),row['mode'],row['n'],row['expected'],row['nodes'],row['integer'])
    blob=bytes(header+table+pool);assert len(blob)<=131072,len(blob)
    summaries=[{k:v for k,v in row.items() if k!='raw'}|dict(bytes=len(row['raw']),sha256=hashlib.sha256(row['raw']).hexdigest()) for row in rows]
    docs=[{k:v for k,v in row.items() if k!='raw'}|dict(bytes=len(row['raw']),sha256=hashlib.sha256(row['raw']).hexdigest()) for row in edn]
    return blob,dict(existingFixtureSHA256=hashlib.sha256(raw).hexdigest(),existingPayloadSHA512=hashlib.sha512(base64.b64decode(fields[b'payload-b64'],validate=True)).hexdigest(),existingAuthorityHex=spki[12:].hex(),syntheticNow=NOW,legacyRFCs=3,prototype=False,suite=suite,fault=fault,count=len(rows),roster=summaries,ednCount=len(edn),edn=docs,baselineEnvelopeSHA256=hashlib.sha256(baseline).hexdigest())
