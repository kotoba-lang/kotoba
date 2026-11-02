"""Independent public byte goldens for the native single-session pending owner.

Builds prescribed fixture states, never an application backend, language
resolver, consent authority, session injector or production ID generator.
"""
import hashlib,hmac,importlib.util,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
NOW=1750000000000
TEMPLATES=[b'{"messageType":"request","requestId":"',b'","serviceName":"local-docs","method":"GET","path":"/docs","headers":{},"port":8080,"bodyBase64":""}',b'{"messageType":"response","requestId":"',b'","status":200,"headers":{},"bodyBase64":"TQ=="}']
FULL_SUFFIX=b'","serviceName":"\\u00e9\\u6587\\u66f8\\ud83d\\ude00","method":"GET","path":"/\\u65e5\\u672c\\u8a9e/\\ud83d\\ude00","headers":{},"port":8080,"bodyBase64":""}'
def packed():
    b=bytearray(64)
    for i,v in enumerate([*TEMPLATES,FULL_SUFFIX]):struct.pack_into('<2I',b,16+i*8,126000+len(b),len(v));b+=v
    return bytes(b)
def load(name,p):
    sp=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

def public_channels(font):
    b=font[393216:];d=lambda at:struct.unpack_from('<I',b,at)[0]
    take=lambda at,count:b[d(at):d(at)+count]
    assert d(52)==96 and d(60)==48
    first,response1=take(48,96),take(56,48)
    binding1=struct.pack('<IIQI',0x3142504b,1,1,1)+bytes(4)+take(36,32)+bytes(8)+take(96,32)
    assert len(binding1)==96
    x=load('pending_public_x',ROOT/'lib/org.ietf.x25519/tools/reference.py');c=load('pending_public_c',ROOT/'lib/org.ietf.chacha20Poly1305/tools/reference.py')
    # Public RFC/digest test secrets only. Independent Noise transcript for a
    # same-peer/key/epoch/time reconnection with a different local ephemeral.
    si,ei=take(44,64)[:32],take(44,64)[32:];sr,er=take(176,64)[:32],take(176,64)[32:]
    digest=lambda v:hashlib.blake2s(v).digest()
    def hkdf(ck,v):
        temp=hmac.digest(ck,v,'blake2s');one=hmac.digest(temp,b'\1','blake2s');return one,hmac.digest(temp,one+b'\2','blake2s')
    spi,epi,spr,epr=[x.x25519(k,bytes([9])+bytes(31)) for k in [si,ei,sr,er]]
    ck=digest(b'Noise_IK_25519_ChaChaPoly_BLAKE2s');hh=digest(digest(ck+b'kekkai-node/1 tailnet:default netmap:42')+spr)
    hh=digest(hh+epi);ck,key=hkdf(ck,x.x25519(ei,spr));static=c.seal(key,bytes(12),hh,spi);hh=digest(hh+static)
    ck,key=hkdf(ck,x.x25519(si,spr));body=c.seal(key,bytes(12),hh,b'');hh=digest(hh+body);assert first==epi+static+body
    hh=digest(hh+epr);ck,key=hkdf(ck,x.x25519(er,epi));ck,key=hkdf(ck,x.x25519(er,spi));body=c.seal(key,bytes(12),hh,b'');hh=digest(hh+body)
    binding2=binding1[:64]+hh;assert binding1[:64]==binding2[:64] and binding1[64:]!=hh
    return dict(binding1=binding1,binding2=binding2,first=first,response1=response1,response2=epr+body)

def issued(binding,owner,sequence):return hashlib.blake2s(b'Kekkai pending v1'+binding+struct.pack('<2Q',owner,sequence)).digest()
def message(binding,owner,seq,response=False,full=False):
    at=2 if response else 0;raw=TEMPLATES[at]+issued(binding,owner,seq).hex().encode()+(FULL_SUFFIX if full else TEMPLATES[at+1])
    if full:
        repeat=(1048576-len(raw))//4*4;raw=raw[:-2]+b'A'*repeat+raw[-2:]
    return raw

def slot(binding,owner,seq,now=NOW):
    b=bytearray(512);struct.pack_into('<II3Q',b,0,1,8080,seq,now,now+30000);b[32:128]=binding;b[128:160]=issued(binding,owner,seq)
    struct.pack_into('<3I',b,160,5 if seq==259 else 10,3,7 if seq==259 else 5)
    for tag,text,at in [(3,'é文書😀'.encode() if seq==259 else b'local-docs',176),(4,b'GET',208),(5,'/日本語/😀'.encode() if seq==259 else b'/docs',240)]:b[at:at+32]=hashlib.blake2s(bytes([tag])+text).digest()
    return bytes(b)
def accepted(binding,owner,seq,input_base):
    b=bytearray(slot(binding,owner,seq));struct.pack_into('<2I',b,0,0x3141504b,1);struct.pack_into('<4I',b,272,8080,200,len(message(binding,owner,seq,True)),0);struct.pack_into('<Q',b,288,input_base);return bytes(b)

def goldens(kind,owner,session,input_base,channels):
    b1,b2=channels['binding1'],channels['binding2'];binding=b1 if kind<=3 else b2;page=bytearray(262144);seq=257 if kind<=2 else 259 if kind<=4 else 260 if kind==5 else 261 if kind<=7 else 262
    phase=0 if kind==8 else 2;epoch=2 if kind==8 else 1;now=NOW if kind<=5 else NOW+29999 if kind==6 else NOW+30000
    struct.pack_into('<4I6Q',page,0,0x3150504b,1,0,phase,epoch,now,30000,session,seq,1 if kind in [2,3,6] else 0)
    if phase==2:page[64:160]=binding
    struct.pack_into('<Q',page,160,owner)
    slots={}
    if kind==1:slots={i-1:i for i in range(1,257)}
    elif kind==2:slots={i-1:i for i in range(1,256)}
    elif kind==3:
        slots={i-1:i for i in range(1,255) if i!=128};slots[127]=257;slots[255]=258
    elif kind==5:slots={0:259}
    elif kind==6:slots={1:260}
    struct.pack_into('<I',page,8,len(slots))
    for index,value in slots.items():page[4096+index*512:4096+(index+1)*512]=slot(binding,owner,value)
    if kind in [2,3,6]:page[135168:135680]=accepted(b2 if kind==6 else b1,owner,259 if kind==6 else 256 if kind==2 else 255,input_base)
    if kind==9:page=bytearray(262144)
    io=bytearray(bytes([165])*262144)
    for at,value in [(64,1),(128,256),(192,255)]:io[at:at+64]=issued(b1,owner,value).hex().encode()
    if kind<=3:io[:64]=issued(b1,owner,256 if kind<=2 else 255).hex().encode()
    else:
        io[:96]=channels['first'];io[65536:65584]=channels['response2']
        if kind>=5:io[:64]=issued(b2,owner,259 if kind<=7 else 261).hex().encode()
    if kind>=5:io[256:320]=issued(b2,owner,259).hex().encode()
    if kind>=2:io[73728:74240]=accepted(b2 if kind>=6 else b1,owner,259 if kind>=6 else 256,input_base)
    if kind==1:raw=message(b1,owner,256)
    elif kind==2:raw=message(b1,owner,256,True)
    elif kind in [3,4]:raw=message(b1,owner,255,True)
    elif kind==5:raw=message(b2,owner,259,full=True)
    elif kind in [6,7]:raw=message(b2,owner,259,response=True)
    else:raw=message(b2,owner,261,response=kind==9)
    expected_input=raw+b' '*(1048576-len(raw))+b'Z'
    return dict(pending=bytes(page),io=bytes(io),input=expected_input)
