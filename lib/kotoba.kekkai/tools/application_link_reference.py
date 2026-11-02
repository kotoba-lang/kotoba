"""Public encrypted chunk expectations for an isolated native NIC diagnostic."""
import hashlib,hmac,importlib.util,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def fixtures(fault=None):
 if fault:raise ValueError('application NIC faults use the separate codec corpus')
 prior=load('application_managed_data',ROOT/'lib/kotoba.kekkai/tools/frame_link_reference.py');raw,old=prior.fixtures();blob=bytearray(raw)
 codec=load('application_chunk_data',ROOT/'lib/kotoba.kekkai/tools/application_frame_reference.py')
 c=load('application_independent_c',ROOT/'lib/org.ietf.chacha20Poly1305/tools/reference.py');x=load('application_independent_x',ROOT/'lib/org.ietf.x25519/tools/reference.py')
 def d(at):return struct.unpack_from('<I',blob,at)[0]
 def value(at,size):return bytes(blob[d(at):d(at)+size])
 tx,rx=value(100,32),value(104,32)
 def digest(v):return hashlib.blake2s(v).digest()
 def hkdf(ck,data):
  t=hmac.digest(ck,data,'blake2s');a=hmac.digest(t,b'\1','blake2s');return a,hmac.digest(t,a+b'\2','blake2s')
 si=value(44,64)[:32];ei=digest(b'JUN-757 public NIC Alice fresh 44');sr=value(156,64)[:32];er=value(156,64)[32:]
 spi,epi,spr,epr=(x.x25519(k,bytes([9])+bytes(31)) for k in [si,ei,sr,er])
 ck=digest(b'Noise_IK_25519_ChaChaPoly_BLAKE2s');hh=digest(digest(ck+b'kekkai-node/1 tailnet:default netmap:44')+spr)
 hh=digest(hh+epi);ck,key=hkdf(ck,x.x25519(ei,spr));static=c.seal(key,bytes(12),hh,spi);hh=digest(hh+static)
 ck,key=hkdf(ck,x.x25519(si,spr));part=c.seal(key,bytes(12),hh,b'');first44=epi+static+part;hh=digest(hh+part)
 hh=digest(hh+epr);ck,key=hkdf(ck,x.x25519(er,epi));ck,key=hkdf(ck,x.x25519(er,spi));response44=epr+c.seal(key,bytes(12),hh,b'');tx44,rx44=hkdf(ck,b'')
 old={row['label']:row for row in old}
 assert old['valid-44-fresh-key']['payload']==b'k\1\x30'+first44 and old['valid-44-fresh-key']['reply']==b'k\1\x31'+response44
 cases=[]
 def copy(label):
  row=dict(old[label]);row.update(chunk=0,recordHash=bytes(32),encodedBytes=-1);cases.append(row)
 def dg(counter,plain,key):
  h=counter.to_bytes(8,'little');return b'k\1\x32'+h+c.seal(key,bytes(4)+h,h,plain)
 def add(label,payload,event=-1,reply=None,transition=0,phase=2,output=None,chunk=0,recordHash=bytes(32),encodedBytes=-1):
  cases.append(dict(label=label,payload=payload,event=event,reply=reply,transition=transition,phase=phase,output=output,chunk=chunk,recordHash=recordHash,encodedBytes=encodedBytes))
 copy('valid-42-with-invalid-policy-update');copy('repeated-handshake')
 seq=0;number=0;wires=[]
 def packet(label,document,canonical=None,rec=None,epoch=42,transition=0):
  nonlocal seq,number
  itx,irx=(tx,rx) if epoch==42 else (tx44,rx44)
  payload=dg(number,b'\1'+document,itx);number+=1;wires.append(payload)
  reply=dg(seq,b'\1'+canonical,irx) if canonical is not None else None
  if canonical is not None:seq+=1
  add(label,payload,65536+len(document),reply,transition=transition,output=document if reply is None else None,chunk=1 if reply else -1,
      recordHash=digest(rec) if rec else bytes(32),encodedBytes=len(canonical) if canonical is not None else -1)
 request=json.dumps(dict(messageType='request',requestId='demo-1',serviceName='itonami',method='GET',path='/',headers={},port=8080,bodyBase64=''),separators=(',',':')).encode()
 def valid(label,ident,body,index=0,total=1,transform=None,epoch=42,transition=0):
  canonical=codec.wire(ident,body,index,total)
  document=transform(canonical) if transform else canonical
  packet(label,document,canonical,codec.record(ident,body,index,total),epoch,transition)
 valid('chunk-with-real-request-fields','req-1',request)
 valid('700-byte-part','binary',bytes((i*17)%256 for i in range(700)))
 valid('escaped-key-id-and-slash','p/😀',b'\xff',transform=lambda b:b.replace(b'"messageId"',b'"message\\u0049d"').replace(b'/w==',b'\\/w=='))
 valid('ignored-nested-json','unknown',b'{}',transform=lambda b:b[:-1]+b',"ignored":{"x":[true,null,1.25e-2]}}')
 valid('last-of-2048-is-only-a-part','multi',b'last',index=2047,total=2048)
 valid('out-of-order-part-is-not-a-message','multi',b'middle',index=1,total=3)
 valid('160-control-id','\0'*160,b'')
 base=codec.wire('bad',b'f')
 for label,document in [('nonzero-base64-pad-bits',base.replace(b'Zg==',b'Zh==')),('duplicate-required-name',base[:-1]+b',"version":1}'),
  ('wrong-version',base.replace(b'"version":1',b'"version":0')),('bad-unknown-json',base[:-1]+b',"x":[1,]}'),
  ('unpaired-surrogate',base.replace(b'"bad"',b'"\\ud800"'))]:packet(label,document)
 add('replay-original-chunk',wires[0])
 valid('valid-after-chunk-refusals','after',request,transition=4)
 copy('revoked-old-data');copy('revoked-handshake');copy('restored-44-refuses-old-prologue');copy('valid-44-fresh-key');copy('old-ciphertext-before-new-counter-zero')
 seq=0;number=0
 valid('fresh44-application-part','fresh44',request,epoch=44)
 packet('fresh44-invalid-base64',base.replace(b'Zg==',b'Zh=='),epoch=44)
 add('fresh44-replayed-invalid-part',wires[-1])
 valid('fresh44-after-invalid-part','fresh44-next',b'{}',epoch=44)
 table=bytearray(len(cases)*64);table_at=len(blob);blob.extend(table)
 for i,row in enumerate(cases):
  at=table_at+i*64;hash_at=len(blob);blob.extend(row['recordHash'])
  struct.pack_into('<qIIqI4xq',blob,at,row['event'],row['transition'],row['phase'],row['chunk'],hash_at,row['encodedBytes'])
 struct.pack_into('<II',blob,148,len(cases),table_at)
 assert len(blob)<=131072
 return bytes(blob),cases
