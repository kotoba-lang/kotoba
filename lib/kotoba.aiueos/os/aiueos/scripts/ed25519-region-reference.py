"""Independent public raw-message Ed25519/stream SHA-512 diagnostic data.

Never a compiler or application runtime. Uses the pre-existing RFC8032
integer reference plus hashlib, published vectors and fixed public test seeds.
"""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def fixtures():
    ref=load('ed_region_integer_reference',HERE/'check-native-consent-qemu.py')
    old=load('ed_region_published_rfc',HERE/'check-native-ed25519-qemu.py')
    seeds=[bytes.fromhex(v) for v in [
        '9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60',
        '4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb',
        'c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7']]
    identity=bytes([1])+bytes(31)
    def prime(pub):
        if len(pub)!=32:return False
        a=ref._dec(pub)
        return a is not None and ref._enc(a)==pub and pub!=identity and ref._enc(ref._mul(ref._L,a))==identity
    def strict(pub,msg,sig):
        if len(pub)!=32 or len(sig)!=64 or not prime(pub):return False
        r=ref._dec(sig[:32])
        return r is not None and ref._enc(r)==sig[:32] and ref.ed_verify(pub,msg,sig)
    def sign(seed,msg):
        expanded=bytearray(hashlib.sha512(seed).digest());scalar=bytearray(expanded[:32]);scalar[0]&=248;scalar[31]&=127;scalar[31]|=64
        a=int.from_bytes(scalar,'little');pub=ref._enc(ref._mul(a,ref._B))
        r=int.from_bytes(hashlib.sha512(expanded[32:]+msg).digest(),'little')%ref._L
        rr=ref._enc(ref._mul(r,ref._B));k=int.from_bytes(hashlib.sha512(rr+pub+msg).digest(),'little')%ref._L
        return pub,rr+((r+k*a)%ref._L).to_bytes(32,'little')
    rows=[];legacy=[]
    for i,seed in enumerate(seeds):
        msg=[b'',b'\x72',bytes.fromhex('af82')][i];pub,sig=sign(seed,msg)
        assert pub.hex()==old.CASES[i][1] and sig.hex()==old.SIGS[i][1] and strict(pub,msg,sig)
        legacy.append(seed+pub+sig+msg.ljust(64,b'\0'))
    corpus=json.loads((ROOT/'lib/org.ietf.ed25519/test/wycheproof/ed25519_test.json').read_text())
    cases=[(g,t) for g in corpus['testGroups'] for t in g['tests']]
    assert corpus['numberOfTests']==len(cases)==210 and len({t['tcId'] for _,t in cases})==210
    for group,test in cases:
        pub=bytes.fromhex(group['publicKey']['pk']);sig=bytes.fromhex(test['sig']);msg=bytes.fromhex(test['msg'])
        accepted=strict(pub,msg,sig)
        assert accepted==(test['result']=='valid'),(test['tcId'],test['result'],test['flags'],accepted)
        rows.append(dict(label='wycheproof-'+str(test['tcId']),public=pub,signature=sig,message=msg,mode=0,expected=int(accepted),tcId=test['tcId'],published=test['result'],flags=test['flags']))
    sizes=[0,1,2,31,32,63,64,65,111,112,113,127,128,129,255,256,257,1023,1024,4096,12224,12225,12288,16384,65535,65536]
    for n in sizes:
        msg=bytes((i*17+3)%256 for i in range(n));pub,sig=sign(seeds[1],msg)
        assert strict(pub,msg,sig)
        rows.append(dict(label='generated-'+str(n),public=pub,signature=sig,message=msg,mode=1,expected=1,tcId=0))
        if n:
            bad=msg[:-1]+bytes([msg[-1]^1]);assert not strict(pub,bad,sig)
            rows.append(dict(label='generated-tail-tamper-'+str(n),public=pub,signature=sig,message=msg,mode=2,expected=0,tcId=0))
    text=(ROOT/'lib/kotoba.kekkai/test/fixtures/netmap.signed.edn').read_text()
    fields=dict(re.findall(r':netmap/([a-z0-9-]+) "([^"]*)"',text))
    msg=base64.b64decode(fields['payload-b64'],validate=True);sig=base64.b64decode(fields['signature-b64'],validate=True)
    spki=base64.b64decode(fields['signer-spki-b64'],validate=True)
    assert spki[:12]==bytes.fromhex('302a300506032b6570032100') and len(spki)==44 and hashlib.sha256(msg).hexdigest()==fields['sha256']
    pub=spki[12:];assert strict(pub,msg,sig)
    netmap_index=len(rows);rows.append(dict(label='existing-signed-netmap-payload',public=pub,signature=sig,message=msg,mode=0,expected=1,tcId=0))
    # A canonical identity authority makes the unguarded equation forgeable
    # for every message. The opt-in authority policy must reject it.
    msg=b'public identity-key forgery';sig=ref._enc(ref._B)+(1).to_bytes(32,'little')
    assert ref.ed_verify(identity,msg,sig) and not strict(identity,msg,sig)
    rows.append(dict(label='identity-authority-forgery',public=identity,signature=sig,message=msg,mode=0,expected=0,tcId=0))
    header=bytearray(64);header[:8]=b'EDREGN01';struct.pack_into('<I',header,8,len(rows));table=bytearray(len(rows)*40);data=bytearray()
    def append(value):
        at=64+len(table)+len(data);data.extend(value);return at
    for i,row in enumerate(rows):
        pub,sig,msg=row['public'],row['signature'],row['message']
        po=append(pub);so=append(sig);mo=append(msg) if row['mode']==0 else 0
        struct.pack_into('<10I',table,i*40,po,len(pub),so,len(sig),mo,len(msg),row['mode'],row['expected'],int(len(pub)==32 and len(sig)==64),row['tcId'])
    legacy_at=append(b''.join(legacy));struct.pack_into('<III',header,12,264,legacy_at,netmap_index)
    blob=bytes(header+table+data);assert len(blob)<=131072
    sha_sizes=list(range(258))+[1023,1024,4096,12288,65536,1048576]
    digests=b''.join(hashlib.sha512(bytes((i*17+3)%256 for i in range(n))).digest() for n in sha_sizes)
    expected=struct.pack('<%dI'%len(rows),*(r['expected'] for r in rows))
    descriptions=[{k:v for k,v in r.items() if k not in ('public','signature','message')}|dict(publicBytes=len(r['public']),signatureBytes=len(r['signature']),messageBytes=len(r['message']),messageSHA256=hashlib.sha256(r['message']).hexdigest()) for r in rows]
    return blob,digests,expected,dict(cases=descriptions,shaSizes=sha_sizes,wycheproofCases=210,wycheproofValid=117,wycheproofInvalid=64,wycheproofAcceptableRejected=29,legacyRFCs=3,netmapCase=netmap_index,netmapPayloadSHA256=fields['sha256'])
