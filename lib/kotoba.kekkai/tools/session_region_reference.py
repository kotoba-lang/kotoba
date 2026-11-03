"""Public signed bytes and independent Noise expectations; no EDN evaluator.

All secrets are published RFC7748/RFC8032 data or named public digest seeds.
This supplies test data only, never a product RNG, crypto service or verdict.
"""
import base64
import hashlib
import hmac
import importlib.util
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[3]
NOW=1750000000

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def fixtures(suite='policy',fault=None):
    scripts=ROOT/'lib/kotoba.aiueos/os/aiueos/scripts';sys.path.insert(0,str(scripts))
    ed=load('managed_public_ed',scripts/'check-native-consent-qemu.py');old=load('managed_legacy_rfc',scripts/'check-native-ed25519-qemu.py')
    x=load('managed_independent_x',ROOT/'lib/org.ietf.x25519/tools/reference.py');c=load('managed_independent_c',ROOT/'lib/org.ietf.chacha20Poly1305/tools/reference.py')
    seed=bytes.fromhex('4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb');pub=ed.ed_public(seed)
    def signed(msg):
        h=hashlib.sha512(seed).digest();a=bytearray(h[:32]);a[0]&=248;a[31]&=127;a[31]|=64
        scalar=int.from_bytes(a,'little');nonce=int.from_bytes(hashlib.sha512(h[32:]+msg).digest(),'little')%ed._L
        rr=ed._enc(ed._mul(nonce,ed._B));k=int.from_bytes(hashlib.sha512(rr+pub+msg).digest(),'little')%ed._L
        signature=rr+((nonce+k*scalar)%ed._L).to_bytes(32,'little');assert ed.ed_verify(pub,msg,signature)
        fields=[('payload-b64',base64.b64encode(msg).decode()),('signature-b64',base64.b64encode(signature).decode()),('signer-spki-b64',base64.b64encode(bytes.fromhex('302a300506032b6570032100')+pub).decode()),('sha256',hashlib.sha256(msg).hexdigest())]
        return ('{'+', '.join(':netmap/'+k+' "'+v+'"' for k,v in fields)+'}').encode()
    alice=bytes.fromhex('77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a')
    bob=bytes.fromhex('5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb')
    ea=hashlib.blake2s(b'JUN-757 managed public Alice ephemeral').digest();eb=hashlib.blake2s(b'JUN-757 managed public Bob ephemeral').digest()
    ap=x.x25519(alice,bytes([9])+bytes(31));bp=x.x25519(bob,bytes([9])+bytes(31))
    assert ap.hex()=='8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a' and bp.hex()=='de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f'
    def roster(version=42,status=b'authorized',expiry=NOW+1000,tailnet=b'"default"'):
        return signed(b'{:netmap/version '+str(version).encode()+b' :netmap/tailnet '+tailnet+b' :netmap/self {:node/id "n-laptop" :node/key "'+bp.hex().encode()+b'" :node/overlay-ip "10.0.0.1"} :netmap/peers [{:node/id "n-server" :node/key "'+ap.hex().encode()+b'" :node/overlay-ip "10.0.0.2" :node/status "'+status+b'" :node/expires-at '+str(expiry).encode()+b'}] :netmap/edges [{:edge/from "n-laptop" :edge/to "n-server" :edge/capabilities [:overlay :ssh] :edge/ports [22]}] :netmap/relays []}')
    digest=lambda value:hashlib.blake2s(value).digest()
    def hkdf(ck,data):
        temp=hmac.digest(ck,data,'blake2s');one=hmac.digest(temp,b'\1','blake2s');return one,hmac.digest(temp,one+b'\2','blake2s')
    def handshake(si,ei,sr,er,prologue,first=b'',second=b''):
        spi,epi,spr,epr=(x.x25519(key,bytes([9])+bytes(31)) for key in [si,ei,sr,er])
        ck=digest(b'Noise_IK_25519_ChaChaPoly_BLAKE2s');hh=digest(digest(ck+prologue)+spr)
        hh=digest(hh+epi);ck,key=hkdf(ck,x.x25519(ei,spr));static=c.seal(key,bytes(12),hh,spi);hh=digest(hh+static)
        ck,key=hkdf(ck,x.x25519(si,spr));token0=hh;ct=c.seal(key,bytes(12),hh,first);hh=digest(hh+ct);wire0=epi+static+ct
        hh=digest(hh+epr);ck,key=hkdf(ck,x.x25519(er,epi));ck,key=hkdf(ck,x.x25519(er,spi));ct=c.seal(key,bytes(12),hh,second);hh=digest(hh+ct)
        tx,rx=hkdf(ck,b'');return wire0,epr+ct,hh,tx,rx,token0
    prologue=b'kekkai-node/1 tailnet:default netmap:42'
    first,response,transcript,tx,rx,token0=handshake(alice,ea,bob,eb,prologue)
    body=b'\1JUN-757 roster-bound transport';hdr=bytes(8)
    incoming=hdr+c.seal(tx,bytes(12),hdr,body);reply=hdr+c.seal(rx,bytes(12),hdr,body)
    pattern=lambda n,start:bytes((i*17+start)%256 for i in range(n))
    rows=[]
    def case(label,role=0,version=42,n0=0,n1=0,body_size=31,index=0,tailnet=b'default',tailtext=b'"default"',life=0,continuation=False,expiry=NOW+1000,generation=None):
        local_e=digest(('JUN-757 managed public local ephemeral '+str(index)).encode());remote_e=digest(('JUN-757 managed public remote ephemeral '+str(index)).encode())
        si,ei,sr,er=(bob,local_e,alice,remote_e) if role else (alice,remote_e,bob,local_e)
        start=(index*13+3)%256;p0=pattern(n0,start);p1=pattern(n1,(start+7)%256);plain=pattern(body_size,(start+14)%256)
        wire0,wire1,hh,tx,rx,_=handshake(si,ei,sr,er,b'kekkai-node/1 tailnet:'+tailnet+b' netmap:'+str(version).encode(),p0,p1)
        native_tx,native_rx=(tx,rx) if role else (rx,tx)
        incoming=bytes(8)+c.seal(native_rx,bytes(12),bytes(8),plain);outgoing=bytes(8)+c.seal(native_tx,bytes(12),bytes(8),plain)
        row=dict(label=label,role=role,version=version,roster=roster(version,expiry=expiry,tailnet=tailtext),tailnet=tailnet,secret=bob+local_e,
            peerWire=wire1 if role else wire0,nativePayloadBytes=n0 if role else n1,peerPlainBytes=n1 if role else n0,
            nativeWireHash=digest(wire0 if role else wire1),transcript=hh,tx=native_tx,rx=native_rx,incoming=incoming,plainBytes=body_size,
            outgoingHash=digest(outgoing),patternStart=start,life=life,generation=generation if generation is not None else (2 if continuation else 1),continuation=int(continuation),expiry=expiry,
            nextRoster=roster(43) if life==1 else b'',revokedRoster=roster(43,status=b'revoked') if life==2 else b'',wrongStatic=b'',wrongPrologue=b'')
        if index==0 and role==0:
            row['wrongStatic']=handshake(digest(b'JUN-757 public unauthorized peer'),remote_e,bob,local_e,b'kekkai-node/1 tailnet:default netmap:42')[0]
            row['wrongPrologue']=handshake(alice,remote_e,bob,local_e,b'kekkai-node/1 tailnet:default netmap:41')[0]
        bad=bytearray(row['roster']);at=bad.index(b':netmap/signature-b64 "')+len(b':netmap/signature-b64 "');bad[at]=65 if bad[at]!=65 else 66
        row['badEnvelope']=bytes(bad);row['oldIncoming']=rows[-1]['incoming'] if continuation else b'';rows.append(row)
    if suite in ('policy','faults'):
        case('responder-new-version-clears',life=1,index=0)
        case('reconnect-version43-fresh-ephemeral',version=43,index=1,continuation=True,body_size=1)
        case('initiator-revoke-clears',role=1,index=2,life=2,body_size=0)
        case('responder-revoke-clears',index=3,life=2,n0=1,n1=1,body_size=64)
        case('initiator-block-boundary',role=1,index=4,n0=16,n1=16,body_size=257)
        case('responder-uneven-payloads',index=5,n0=65,n1=63,body_size=1024)
        case('initiator-multiblock',role=1,index=6,n0=257,n1=257,body_size=31)
        case('unicode-decoded-tailnet',index=7,tailnet='default-😀'.encode(),tailtext=b'"d\\u0065fault-\\ud83d\\ude00"')
        case('version-zero',role=1,index=8,version=0,body_size=1)
        case('version-i64-maximum',index=9,version=9223372036854775807,body_size=17)
        case('peer-expiry-clears-live-keys',role=1,index=10,life=3,expiry=NOW+60)
        case('explicit-stop-clears-live-keys',index=15,life=4)
        case('reconnect-same-version-fresh-ephemeral',role=1,index=16,continuation=True,generation=1)
    elif suite=='handshake-responder':case('maximum-handshake-responder',n0=65439,n1=65487,index=11,body_size=16)
    elif suite=='handshake-initiator':case('maximum-handshake-initiator',role=1,n0=65439,n1=65487,index=12,body_size=16)
    elif suite=='transport-responder':case('maximum-datagram-responder',index=13,body_size=65511)
    elif suite=='transport-initiator':case('maximum-datagram-initiator',role=1,index=14,body_size=65511)
    else:raise ValueError('unknown managed session suite')
    if suite=='faults':
        targets={'ms-unicode':'unicode-decoded-tailnet','ms-lifetime':'initiator-block-boundary','ms-stop':'explicit-stop-clears-live-keys'}
        target=targets.get(fault,'responder-new-version-clears');rows=[r for r in rows if r['label']==target];assert len(rows)==1
    header=bytearray(192);header[:8]=b'KSESS002';table=bytearray(160*len(rows));pool=bytearray()
    def add(value):
        if not value:return 0
        at=pool.find(value)
        if at<0:at=len(pool);pool.extend(value)
        return 192+len(table)+at
    legacy=b''
    for i,s in enumerate(['9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60','4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb','c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7']):legacy+=bytes.fromhex(s+old.CASES[i][1]+old.SIGS[i][1])+[b'',b'\x72',bytes.fromhex('af82')][i].ljust(64,b'\0')
    struct.pack_into('<I',header,12,add(legacy));struct.pack_into('<I',header,16,add(hashlib.sha256(b'abc').digest()))
    raw=roster();struct.pack_into('<II',header,20,add(raw),len(raw))
    for at,value in [(28,pub),(32,bp),(36,ap),(40,bob+eb),(44,alice+ea),(48,first),(56,response),(64,incoming),(72,reply),(96,transcript),(100,tx),(104,rx),(108,body)]:struct.pack_into('<I',header,at,add(value))
    for at,value in [(52,len(first)),(60,len(response)),(68,len(incoming)),(76,len(reply)),(112,len(body))]:struct.pack_into('<I',header,at,value)
    for at,value in [(80,roster(43)),(88,roster(43,status=b'revoked'))]:struct.pack_into('<II',header,at,add(value),len(value))
    struct.pack_into('<III',header,116,add(prologue),len(prologue),add(token0))
    struct.pack_into('<II',header,128,len(rows),192)
    descriptions=[]
    for i,row in enumerate(rows):
        record=i*160
        struct.pack_into('<I',table,record,row['role']);struct.pack_into('<Q',table,record+8,row['version'])
        values={16:add(row['roster']),20:len(row['roster']),24:add(row['tailnet']),28:len(row['tailnet']),32:add(row['secret']),
            36:add(row['peerWire']),40:len(row['peerWire']),44:row['nativePayloadBytes'],48:row['peerPlainBytes'],52:add(row['nativeWireHash']),
            56:add(row['transcript']),60:add(row['tx']),64:add(row['rx']),68:add(row['incoming']),72:len(row['incoming']),76:row['plainBytes'],80:add(row['outgoingHash']),
            88:row['patternStart'],92:row['life'],96:row['generation'],100:row['continuation'],104:add(row['nextRoster']),108:len(row['nextRoster']),
            112:add(row['revokedRoster']),116:len(row['revokedRoster']),120:add(row['wrongStatic']),124:add(row['wrongPrologue']),128:row['expiry']}
        values.update({132:add(row['badEnvelope']),136:len(row['badEnvelope']),140:add(row['oldIncoming']),144:len(row['oldIncoming'])})
        for at,value in values.items():struct.pack_into('<I',table,record+at,value)
        descriptions.append({k:v for k,v in row.items() if isinstance(v,(str,int))}|{k+'SHA256':hashlib.sha256(v).hexdigest() for k,v in row.items() if isinstance(v,bytes)})
    blob=bytes(header+table+pool);assert len(blob)<=131072,len(blob)
    return blob,dict(prototype=False,suite=suite,count=len(rows),cases=descriptions,expectedNativeHashes=[r[k].hex() for r in rows for k in ['nativeWireHash','outgoingHash']],syntheticNow=NOW,publicSeedsOnly=True,rosterSHA256=hashlib.sha256(raw).hexdigest(),firstWireSHA256=hashlib.sha256(first).hexdigest(),responseWireSHA256=hashlib.sha256(response).hexdigest(),transcriptHex=transcript.hex())
