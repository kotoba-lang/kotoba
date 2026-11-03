"""Public dynamic-response NIC fixture; learns ID from real native outbound wire.

No product runtime/HTTP service, consent, identity injection or policy evaluator.
"""
import hashlib,hmac,importlib.util,struct,json,base64
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BOOT_LABEL='new-epoch-part0-completes'
TEMPLATES=[b'{"messageType":"request","requestId":"',b'","serviceName":"local-docs","method":"GET","path":"/docs","headers":{},"port":8080,"bodyBase64":""}']
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def protocol(blob,initiator=False):
 d=lambda at:struct.unpack_from('<I',blob,at)[0]
 value=lambda at,count:blob[d(at):d(at)+count]
 x=load('response_public_x',ROOT/'lib/org.ietf.x25519/tools/reference.py');c=load('response_public_c',ROOT/'lib/org.ietf.chacha20Poly1305/tools/reference.py')
 alice,bob=value(44,32),value(40,32);ea=hashlib.blake2s(b'JUN-757 public NIC Alice fresh 44').digest();eb=hashlib.blake2s(b'JUN-757 public NIC Bob fresh 44').digest()
 si,ei,sr,er=(bob,eb,alice,ea) if initiator else (alice,ea,bob,eb)
 spi,epi,spr,epr=[x.x25519(k,bytes([9])+bytes(31)) for k in [si,ei,sr,er]]
 digest=lambda v:hashlib.blake2s(v).digest()
 def hkdf(ck,v):
  temp=hmac.digest(ck,v,'blake2s');one=hmac.digest(temp,b'\1','blake2s');return one,hmac.digest(temp,one+b'\2','blake2s')
 ck=digest(b'Noise_IK_25519_ChaChaPoly_BLAKE2s');hh=digest(digest(ck+b'kekkai-node/1 tailnet:default netmap:44')+spr)
 hh=digest(hh+epi);ck,key=hkdf(ck,x.x25519(ei,spr));part=c.seal(key,bytes(12),hh,spi);hh=digest(hh+part)
 ck,key=hkdf(ck,x.x25519(si,spr));part=c.seal(key,bytes(12),hh,b'');hh=digest(hh+part)
 hh=digest(hh+epr);ck,key=hkdf(ck,x.x25519(er,epi));ck,key=hkdf(ck,x.x25519(er,spi));part=c.seal(key,bytes(12),hh,b'');hh=digest(hh+part);a,b=hkdf(ck,b'')
 assert hh==value(188,32)
 return dict(c=c,incoming=b if initiator else a,outgoing=a if initiator else b,h=hh,peer=value(36,32))

def full_response(ident):
 assert len(ident)==64 and all(c in '0123456789abcdef' for c in ident)
 prefix=b'{"messageType":"response","requestId":"'+ident.encode()+b'","status":200,"headers":{"content-type":"text/plain"},"bodyBase64":"';tail=b'"}'
 used=(1048576-len(prefix)-len(tail))//4*4;raw=prefix+b'A'*used+tail;return raw+b' '*(1048576-len(raw))

def fixtures(small=False,initiator=False):
 assert not small,'response controller qualification retains full1MiB/2048-part corpus'
 ref=load('response_receive_base',ROOT/'lib/kotoba.kekkai/tools/application_receive_reference.py');raw,cases=ref.fixtures(False,initiator);blob=bytearray(raw);keys=protocol(blob,initiator);codec=load('response_part_public',ROOT/'lib/kotoba.kekkai/tools/application_frame_reference.py')
 full=full_response('0'*64)
 for i,row in enumerate(cases):
  if row['label']==BOOT_LABEL:
   row['flags']|=32;row['completed']=None;row['nativeRequest']=True
   struct.pack_into('<II',blob,struct.unpack_from('<I',blob,152)[0]+i*48+16,0,0)
   struct.pack_into('<I',blob,struct.unpack_from('<I',blob,152)[0]+i*48+28,row['flags'])
  if row['label'].startswith('full1MiB-part-'):
   index=int(row['label'].rsplit('-',1)[1]);plain=b'\1'+codec.wire('full',full[index*700:(index+1)*700],index,2048);counter=row['payload'][3:11]
   row['payload']=b'k\1\x32'+counter+keys['c'].seal(keys['incoming'],bytes(4)+counter,counter,plain)
  if row['completed'] is not None and len(row['completed'])==1048576:row['completed']=full
 # Explicit whole allocation handoff bootstrap uses these immutable literals.
 text=bytearray(64)
 for i,value in enumerate(TEMPLATES):struct.pack_into('<2I',text,16+i*8,126000+len(text),len(value));text+=value
 assert not any(blob[126000:126000+len(text)])
 if len(blob)<126000+len(text):blob+=bytes(126000+len(text)-len(blob))
 blob[126000:126000+len(text)]=text
 return bytes(blob),cases

def native_request(raw,keys):
 # Independent decoding of one actual IPv4/UDP Kekkai datagram from the native
 # sender, not memory-derived IDs or a fabricated authenticated frame.
 assert raw[12:14]==b'\x08\x00' and raw[23]==17
 ihl=(raw[14]&15)*4;udp=14+ihl;length=int.from_bytes(raw[udp+4:udp+6],'big');wire=raw[udp+8:udp+length]
 assert wire[:3]==b'k\1\x32';counter=wire[3:11];assert int.from_bytes(counter,'little')==0
 plain=keys['c'].open_(keys['outgoing'],bytes(4)+counter,counter,wire[11:]);assert plain is not None and plain[:1]==b'\1'
 frame=json.loads(plain[1:]);assert frame['version']==1 and frame['messageId']=='request' and frame['partIndex']==0 and frame['partCount']==1
 message=base64.b64decode(frame['payload'],validate=True);value=json.loads(message)
 ident=value['requestId'];assert message==TEMPLATES[0]+ident.encode()+TEMPLATES[1]
 assert len(ident)==64 and all(c in '0123456789abcdef' for c in ident)
 return ident,message

def bind_responses(cases,ident,blob,initiator=False):
 keys=protocol(blob,initiator);codec=load('response_dynamic_codec',ROOT/'lib/kotoba.kekkai/tools/application_frame_reference.py');full=full_response(ident)
 for row in cases:
  if row['label'].startswith('full1MiB-part-'):
   index=int(row['label'].rsplit('-',1)[1]);counter=row['payload'][3:11];plain=b'\1'+codec.wire('full',full[index*700:(index+1)*700],index,2048)
   row['payload']=b'k\1\x32'+counter+keys['c'].seal(keys['incoming'],bytes(4)+counter,counter,plain)
  if row['completed'] is not None and len(row['completed'])==1048576:row['completed']=full
 return full
