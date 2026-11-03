"""Independent public Kekkai packet expectations for an isolated native VM.

Python constructs/checks test data only: never an app, tunnel or native socket
backend. All keys are Cacophony/public derivations. Both sockets are loopback.
"""
import hashlib
import hmac
import json
import importlib.util
from pathlib import Path
import socket
import struct
import time

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def fixtures():
    ref = load('link_ik_reference', ROOT/'lib/kotoba.noise/tools/ik_region_reference.py')
    blob, _, _ = ref.fixtures()  # Independently checks all published IK vectors.
    row = blob[64:576]
    x = load('link_x_reference', ROOT/'lib/org.ietf.x25519/tools/reference.py')
    c = load('link_c_reference', ROOT/'lib/org.ietf.chacha20Poly1305/tools/reference.py')
    corpus = ref.read_fixture((ROOT/'lib/kotoba.noise/test/noise/cacophony_vectors.edn').read_text())
    known, = [v for v in corpus if v['protocol-name']=='Noise_IK_25519_ChaChaPoly_BLAKE2s']
    init = bytes.fromhex(known['messages'][0]['ciphertext'])
    response = bytes.fromhex(known['messages'][1]['ciphertext'])
    tx, rx = row[224:256], row[256:288]
    digest = lambda v: hashlib.blake2s(v).digest()
    def hkdf(ck, data):
        temp=hmac.digest(ck,data,'blake2s');one=hmac.digest(temp,b'\1','blake2s')
        return one,hmac.digest(temp,one+b'\2','blake2s')
    def alternate(si, prologue):
        ei=row[32:64];spr=row[128:160]
        spi=x.x25519(si,bytes([9])+bytes(31));epi=x.x25519(ei,bytes([9])+bytes(31))
        ck=digest(b'Noise_IK_25519_ChaChaPoly_BLAKE2s');hh=digest(digest(ck+prologue)+spr)
        hh=digest(hh+epi);ck,key=hkdf(ck,x.x25519(ei,spr))
        static=c.seal(key,bytes(12),hh,spi);hh=digest(hh+static);ck,key=hkdf(ck,x.x25519(si,spr))
        return epi+static+c.seal(key,bytes(12),hh,row[448:464])
    def dg(number,plain,key=tx):
        header=number.to_bytes(8,'little')
        return header+c.seal(key,bytes(4)+header,header,plain)
    def outer(kind,plain): return bytes([107,1,kind])+plain
    def flip(value,at):
        result=bytearray(value);result[at]^=1;return bytes(result)
    cases=[]
    def add(label,payload,expected=None,authenticated=0,accepted=False):
        cases.append(dict(label=label,payload=payload,reply=expected,authenticated=authenticated,accepted=accepted))
    add('short-outer',b'k\1')
    add('bad-magic',bytes([106,1,48])+init)
    add('bad-version',bytes([107,2,48])+init)
    add('unknown-outer',outer(51,init))
    add('unexpected-response',outer(49,response))
    add('transport-before-handshake',outer(50,dg(0,b'\1early')))
    add('short-handshake',outer(48,init[:95]))
    add('handshake-static-tamper',outer(48,flip(init,32)))
    add('handshake-payload-tamper',outer(48,flip(init,-1)))
    add('valid-IK-wrong-static',outer(48,alternate(digest(b'public unauthorized Kekkai static'),b'John Galt')))
    add('valid-IK-wrong-prologue',outer(48,alternate(row[:32],b'John Galt!')))
    add('valid-IK',outer(48,init),outer(49,response),accepted=True)
    add('repeated-handshake',outer(48,init))
    add('short-datagram',outer(50,dg(0,b'')[:23]))
    add('bad-tag',outer(50,flip(dg(0,b''),-1)))
    add('tampered-counter',outer(50,flip(dg(0,b''),0)))
    add('wrong-direction-key',outer(50,dg(0,b'\1wrong',rx)))
    add('authenticated-empty-inner',outer(50,dg(0,b'')),authenticated=1)
    add('authenticated-unknown-inner',outer(50,dg(1,b'\0')),authenticated=1)
    add('authenticated-pong-unhandled',outer(50,dg(2,b'\3id')),authenticated=1)
    add('authenticated-call-me-maybe-unhandled',outer(50,dg(3,b'\4[]')),authenticated=1)
    add('keepalive-nonempty',outer(50,dg(4,b'\5x')),authenticated=1)
    add('keepalive',outer(50,dg(5,b'\5')),authenticated=1,accepted=True)
    sequence=0
    def reply(label,number,body,kind=1):
        nonlocal sequence
        plain=bytes([kind])+body
        response_plain=bytes([3 if kind==2 else kind])+body
        expected=outer(50,dg(sequence,response_plain,rx));sequence+=1
        add(label,outer(50,dg(number,plain)),expected,authenticated=1,accepted=True)
    reply('data-empty',6,b'')
    add('replay-data',outer(50,dg(6,b'\1')))
    for number,size in [(8,1),(7,31),(9,64),(10,257),(11,1024),(12,1444)]:
        reply('data-'+str(size),number,bytes((i*17+size)%256 for i in range(size)))
    reply('ping-pong',13,b'JUN-757',kind=2)
    add('bad-version-established',bytes([107,2,50])+dg(14,b'\1wrong-version'))
    add('authenticated-unknown-inner-6',outer(50,dg(14,b'\6')),authenticated=1)
    add('wrong-endpoint',outer(50,dg(15,b'\1endpoint')))
    reply('data-after-wrong-endpoint',15,bytes(range(16)))
    add('replay-keepalive',outer(50,dg(5,b'\5')))
    body=bytes(range(65))
    add('tampered-body',outer(50,flip(dg(16,b'\1'+body),9)))
    reply('data-after-tampered-body',16,body)
    add('final-keepalive',outer(50,dg(17,b'\5')),authenticated=1,accepted=True)
    assert len(cases)==40 and sequence==10
    return blob, cases

def exercise(boot,peer,target,out):
    link=load('kekkai_raw_wire',ROOT/'scripts/native_udp_link_peer.py')
    _,cases=fixtures();events=[];violations=[];pre_test=[]
    peer.settimeout(0.1)
    while True:
        try:
            data,address=peer.recvfrom(8192)
            if address!=target: raise ValueError('unexpected pre-test peer')
            pre_test.append(dict(bytes=len(data),hex=data.hex(),sha256=hashlib.sha256(data).hexdigest()))
        except socket.timeout: break
    for index,case in enumerate(cases):
        frame=bytearray(link.packet(case['payload'],ident=index+1))
        if case['label']=='wrong-endpoint':
            struct.pack_into('!H',frame,34,22090);link.fix_udp(frame)
        frame=bytes(frame)
        expected=[]
        if case['reply'] is not None:
            result=bytearray(link.packet(case['reply'],ident=index+1))
            result[:6],result[6:12]=result[6:12],result[:6]
            result[26:30],result[30:34]=result[30:34],result[26:30]
            result[34:36],result[36:38]=result[36:38],result[34:36]
            expected=[bytes(result)]
        before=link.snapshot(boot);peer.sendto(frame,target);replies=[];end=time.monotonic()+30
        while True:
            try:
                data,address=peer.recvfrom(8192)
                if address!=target: raise ValueError('unexpected peer')
                replies.append(data)
            except socket.timeout: pass
            now=link.snapshot(boot)
            if now[84]>before[84]:
                try:
                    while True:
                        data,address=peer.recvfrom(8192)
                        if address!=target: raise ValueError('unexpected peer')
                        replies.append(data)
                except socket.timeout: pass
                break
            if boot.proc.poll() is not None: raise RuntimeError('native guest terminated')
            if time.monotonic()>end: raise TimeoutError('native NIC did not consume '+case['label'])
        stats=struct.unpack('<3I',boot.dump(boot.work+89*4,12))
        # Expectation is independent of native counters; both must agree.
        match=replies==expected
        if not match:violations.append(case['label']+' reply mismatch')
        if now[88]-before[88] != int(not case['accepted']):violations.append(case['label']+' dispatch refusal mismatch')
        events.append(dict(label=case['label'],inputHex=frame.hex(),expectedReplyHex=[v.hex() for v in expected],
            actualReplyHex=[v.hex() for v in replies],match=match,accepted=case['accepted'],authenticated=case['authenticated'],
            before={str(k):before[k] for k in [75,78,83,84,88]},after={str(k):now[k] for k in [75,78,83,84,88]},
            phase=stats[0],keepalives=stats[1],authenticatedPackets=stats[2]))
        (out/'packet-events.json').write_text(json.dumps(dict(preTestFrames=pre_test,events=events,violations=violations),indent=2)+'\n')
    end=time.monotonic()+10
    while boot.W(79)!=2:
        if boot.proc.poll() is not None:raise RuntimeError('native guest terminated during wipe')
        if time.monotonic()>end:raise TimeoutError('native final wipe did not complete')
        time.sleep(0.1)
    final=link.snapshot(boot);stats=struct.unpack('<4I',boot.dump(boot.work+89*4,16))
    low,high=struct.unpack('<2I',boot.dump(boot.work+400,8));address=low+(high<<32)
    if not 0<address<1<<39:raise ValueError('native request region address differs')
    erased={}
    for label,offset,length in [('handshake',0,8192),('datagram',16384,17408)]:
        raw=boot.dump(address+offset,length)
        erased[label]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),allZero=raw==bytes(length))
        if not erased[label]['allZero']:violations.append(label+' not wiped')
    observed=dict(nicStarted=final[74],nativeErrors=final[75],wiped=final[76],canary=final[77],replies=final[78],terminal=final[79],
        rxFrames=final[83],released=final[84],rxErrors=final[87],refused=final[88],phase=stats[0],keepalives=stats[1],authenticatedPackets=stats[2],wireBoundaryChecks=stats[3])
    wanted=dict(nicStarted=1,nativeErrors=0,wiped=1,canary=1,replies=11,terminal=2,rxFrames=40,released=40,rxErrors=0,refused=27,
        phase=2,keepalives=2,authenticatedPackets=sum(c['authenticated'] for c in cases),wireBoundaryChecks=1)
    if observed!=wanted:violations.append('final counters differ')
    return dict(preTestFrames=pre_test,events=events,observed=observed,expected=wanted,erased=erased,violations=violations),not violations
