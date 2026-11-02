"""Independent public byte fixtures for native envelope admission; no runtime/compiler.

Only public RFC8032 test seeds and the existing public signed envelope are used.
The native guest receives raw envelope fragments, never host-parsed admission.
"""
import base64
import hashlib
import importlib.util
import itertools
from pathlib import Path
import re
import struct
import sys

ROOT=Path(__file__).resolve().parents[3]
KEYS=['payload-b64','signature-b64','signer-spki-b64','sha256']
DER=bytes.fromhex('302a300506032b6570032100')

def fixtures():
    p=ROOT/'lib/kotoba.aiueos/os/aiueos/scripts/check-native-consent-qemu.py'
    sys.path.insert(0,str(p.parent))
    spec=importlib.util.spec_from_file_location('envelope_public_ed_reference',p)
    ed=importlib.util.module_from_spec(spec);spec.loader.exec_module(ed)
    seed=bytes.fromhex('4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb')
    pub=ed.ed_public(seed)
    def sign(msg):
        h=hashlib.sha512(seed).digest();a=bytearray(h[:32]);a[0]&=248;a[31]&=127;a[31]|=64
        scalar=int.from_bytes(a,'little');r=int.from_bytes(hashlib.sha512(h[32:]+msg).digest(),'little')%ed._L
        rr=ed._enc(ed._mul(r,ed._B));k=int.from_bytes(hashlib.sha512(rr+pub+msg).digest(),'little')%ed._L
        sig=rr+((r+k*scalar)%ed._L).to_bytes(32,'little');assert ed.ed_verify(pub,msg,sig);return sig
    assert pub.hex()=='3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c'
    pattern=lambda n:bytes((17*i+3)%256 for i in range(n))
    b64=lambda b:base64.b64encode(b).decode()
    def fields(msg):return dict(zip(KEYS,[b64(msg),b64(sign(msg)),b64(DER+pub),hashlib.sha256(msg).hexdigest()]))
    def render(f,order=KEYS,sep=', '):return ('{'+sep.join(':netmap/'+k+' "'+f[k]+'"' for k in order)+'}').encode()
    rows=[]
    def add(label,raw,expected=-1,payload=b'',authority=pub,capacity=65536,mode=1):
        assert len(raw)<=98304 and len(authority)==32 and 0<=capacity<=65536
        rows.append(dict(label=label,raw=raw,expected=expected,payload=payload,authority=authority,capacity=capacity,mode=mode))
    for n in [0,1,2,3,55,56,57,63,64,65,111,112,113,127,128,129,1023,1024,4096,12288,12289,16384,65535]:
        msg=pattern(n);add('pattern-'+str(n),render(fields(msg)),n,msg)
    small=fields(pattern(1));normal=render(small)
    add('empty-exact-output',render(fields(b'')),0,capacity=0)
    add('one-byte-exact-output',normal,1,pattern(1),capacity=1)
    for i,order in enumerate(itertools.permutations(KEYS)):
        add('key-order-'+str(i),render(small,order),1,pattern(1))
    for sep in [' ', '\n', '\r\n\t', ',\n\t']:
        add('outer-whitespace-'+repr(sep),b' \t\r\n'+render(small,sep=sep)+b'\r\n',1,pattern(1))
    fixture=ROOT/'lib/kotoba.kekkai/test/fixtures/netmap.signed.edn'
    actual=fixture.read_bytes();f=dict(re.findall(r':netmap/([a-z0-9-]+) "([^"]*)"',actual.decode()))
    msg=base64.b64decode(f['payload-b64'],validate=True);spki=base64.b64decode(f['signer-spki-b64'],validate=True)
    assert spki[:12]==DER and len(spki)==44 and hashlib.sha256(msg).hexdigest()==f['sha256']
    assert ed.ed_verify(spki[12:],msg,base64.b64decode(f['signature-b64'],validate=True))
    add('existing-signed-netmap',actual,len(msg),msg,spki[12:],mode=0)
    for key in KEYS:
        add('duplicate-'+key,('{:netmap/'+key+' "'+small[key]+'", ').encode()+normal[1:])
        add('missing-'+key,render({k:v for k,v in small.items() if k!=key},[k for k in KEYS if k!=key]))
    for label,raw in [('empty',b''),('empty-map',b'{}'),('not-map',b'[]'),('reader',b'#='+normal),
        ('namespace-map',normal.replace(b'{:netmap/',b'#:netmap{:',1)),('comment',b';ignored\n'+normal),
        ('unknown',normal[:-1]+b' :other "x"}'),('trailing-form',normal+b' {}'),('trailing-byte',normal+b'x'),
        ('nested-value',normal.replace(b'"Aw=="',b'{:a 1}',1)),('escaped-value',normal.replace(b'Aw==',b'A\\w==',1)),
        ('control-value',normal.replace(b'Aw==',b'A\x00w==',1)),('non-ascii-value',normal.replace(b'Aw==',b'\xc3\xa9',1))]:add(label,raw)
    for cut in [1,2,7,19,20,21,22,23,len(normal)//2,len(normal)-2,len(normal)-1]:add('truncated-'+str(cut),normal[:cut])
    def changed(label,key,value,authority=pub):
        f=dict(small);f[key]=value;add(label,render(f),authority=authority)
    for value in ['A','Aw','Aw=','Aw===','Aw======','Aw=A','Aw==AAAA','A===','====','AB==','Ax==','Aw-=','Aw_=', 'Aw==\n']:
        changed('bad-payload-base64-'+repr(value),'payload-b64',value)
    for value in ['AB==','AwB=','A===','AAAA====']:
        changed('bad-signature-base64-'+value,'signature-b64',value)
    sig=bytearray(base64.b64decode(small['signature-b64']));sig[-1]^=1;changed('bad-signature','signature-b64',b64(sig))
    changed('short-signature','signature-b64',b64(sig[:-1]));changed('long-signature','signature-b64',b64(sig+b'\0'))
    changed('bad-digest','sha256','0'*64);changed('uppercase-digest','sha256',small['sha256'].upper())
    changed('short-digest','sha256',small['sha256'][:-1]);changed('long-digest','sha256',small['sha256']+'0')
    bad_der=bytearray(DER);bad_der[8]^=1
    changed('wrong-spki-oid','signer-spki-b64',b64(bad_der+pub))
    changed('short-spki','signer-spki-b64',b64((DER+pub)[:-1]))
    changed('long-spki','signer-spki-b64',b64(DER+pub+b'\0'))
    changed('spki-null-parameters','signer-spki-b64',b64(bytes.fromhex('302c300706032b65700500032100')+pub))
    alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
    spki_text=small['signer-spki-b64'];changed('spki-nonzero-pad-bits','signer-spki-b64',spki_text[:-2]+alphabet[alphabet.index(spki_text[-2])+1]+'=')
    other=ed.ed_public(bytes.fromhex('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60'))
    add('wrong-configured-authority',normal,authority=other)
    changed('wrong-envelope-signer','signer-spki-b64',b64(DER+other))
    identity=bytes([1])+bytes(31);forged=dict(small);forged['signer-spki-b64']=b64(DER+identity)
    forged['signature-b64']=b64(ed._enc(ed._B)+(1).to_bytes(32,'little'))
    assert ed.ed_verify(identity,pattern(1),base64.b64decode(forged['signature-b64']))
    add('identity-authority-forgery',render(forged),authority=identity)
    add('short-output',normal,capacity=0)
    big=pattern(65536);bigfields=fields(big)
    add('maximum-wrong-digest',render(bigfields|{'sha256':'0'*64}))
    add('maximum-wrong-signature',render(bigfields|{'signature-b64':b64(bytes(64))}))
    oversize=pattern(65537);add('oversized-decoded-payload',render(bigfields|{'payload-b64':b64(oversize)}))
    add('maximum-short-output',render(bigfields),capacity=65535)
    # Last case leaves the complete independently expected max payload for a
    # separate QMP readback, after every refusal and shape guard has run.
    add('maximum-payload-final',render(bigfields),65536,big)
    assert len(rows)<512
    header=bytearray(64);header[:8]=b'KENVREG1';struct.pack_into('<I',header,8,len(rows))
    table=bytearray(len(rows)*96);pool=bytearray(base64.b64encode(oversize))
    def intern(value):
        if not value:return 0
        found=pool.find(value)
        if found<0:found=len(pool);pool.extend(value)
        return 64+len(table)+found
    descriptions=[]
    for i,row in enumerate(rows):
        raw=row['raw'];match=re.search(rb':netmap/payload-b64 "([^"]*)"',raw)
        if match and len(match[1])>1024:
            # Reuse the long pattern's exact raw Base64 prefixes. All fragment
            # concatenations are checked against the complete envelope bytes.
            at,end=match.span(1);parts=[raw[:at],raw[at:end-4],raw[end-4:end],raw[end:]]
        else:parts=re.split(rb'(?=:netmap/)',raw)
        assert b''.join(parts)==raw and len(parts)<=8
        po=intern(row['authority']);mo=intern(row['payload']) if row['mode']==0 else 0
        struct.pack_into('<8I',table,i*96,len(parts),po,row['expected']&0xffffffff,row['mode'],mo,len(row['payload']),row['capacity'],len(raw))
        for j,part in enumerate(parts):struct.pack_into('<II',table,i*96+32+j*8,intern(part),len(part))
        descriptions.append(dict(label=row['label'],envelopeBytes=len(raw),envelopeSHA256=hashlib.sha256(raw).hexdigest(),authorityHex=row['authority'].hex(),expected=row['expected'],capacity=row['capacity'],payloadBytes=len(row['payload']),payloadSHA256=hashlib.sha256(row['payload']).hexdigest() if row['expected']>=0 else None))
    # Published RFC8032 examples qualify the retained legacy API/profile as
    # actual calls, rather than synthetic stubs for unused imported exports.
    old_path=ROOT/'lib/kotoba.aiueos/os/aiueos/scripts/check-native-ed25519-qemu.py'
    spec=importlib.util.spec_from_file_location('envelope_legacy_rfc',old_path)
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    legacy=b''
    for i,seed_hex in enumerate(['9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60','4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb','c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7']):
        legacy+=bytes.fromhex(seed_hex+old.CASES[i][1]+old.SIGS[i][1])+[b'',b'\x72',bytes.fromhex('af82')][i].ljust(64,b'\0')
    struct.pack_into('<I',header,12,intern(legacy))
    struct.pack_into('<I',header,16,intern(hashlib.sha256(b'abc').digest()))
    blob=bytes(header+table+pool);assert len(blob)<=131072,len(blob)
    expected=struct.pack('<%dI'%len(rows),*(r['expected']&0xffffffff for r in rows))
    return blob,expected,big,dict(cases=descriptions,count=len(rows),accept=sum(r['expected']>=0 for r in rows),refuse=sum(r['expected']<0 for r in rows),legacyRFCs=3,actualNetmapPayloadSHA256=f.get('sha256'))
