"""Public application/1 fixture bytes; native code alone parses/adjudicates.

JSON is constructed as test input, not used to evaluate native outputs or
policy. Known record fields supply independent whole-output BLAKE2s hashes.
"""
import base64,hashlib,hmac,json,struct

def wire(ident='part',body=b'{}',index=0,total=1):
    return json.dumps(dict(version=1,messageId=ident,partIndex=index,partCount=total,payload=base64.b64encode(body).decode()),ensure_ascii=False,separators=(',',':')).encode()

def record(ident='part',body=b'{}',index=0,total=1):
    out=bytearray(2048);text=ident.encode();units=len(ident.encode('utf-16-le'))//2
    struct.pack_into('<6I',out,0,0x3146504b,len(text),units,index,total,len(body));out[64:64+len(text)]=text;out[704:704+len(body)]=body
    return bytes(out)

def fixtures():
    rows=[]
    def add(label,data,expected=None,op=0,used=None,capacity=65536,work=8192,alias=0,pad=False):
        success=expected is not None
        result=1 if success and op==0 else (len(expected) if success else -1)
        if used is None:used=65536 if pad else len(data)
        shape=work>=8192 and used<=65536 and capacity<=65536 and not alias and (capacity>=2048 if op==0 else used==2048)
        rows.append(dict(label=label,data=data,op=op,used=used,capacity=capacity,work=work,alias=alias,pad=int(pad),expected=result,
            hash=hashlib.blake2s(expected).digest() if success else bytes(32),outputBytes=len(expected) if success else 0,wiped=int(shape)))
    def good(label,ident='part',body=b'{}',index=0,total=1):
        packet=wire(ident,body,index,total);raw=record(ident,body,index,total)
        add('decode-'+label,packet,raw);add('encode-'+label,raw,packet,op=1)
    good('empty-body',body=b'')
    for size in [1,2,3,31,64,257,699,700]:good('body-'+str(size),body=bytes((i*17+size)%256 for i in range(size)))
    good('last-of-2048',index=2047,total=2048)
    good('160-ascii',ident='a'*160)
    good('160-bmp',ident='漢'*160)
    good('160-astral-units',ident='😀'*80)
    good('160-controls',ident='\0'*160,body=bytes((i*17)%256 for i in range(700)))
    good('id-json-escapes',ident='"\\/\b\f\n\r\t\0\x1f😀')
    base=wire();base_record=record()
    add('whitespace-65536',b' \t\n'+base,base_record,pad=True)
    prefix=base[:-1]+b',"unknown":['
    count=(65536-len(prefix)-3)//2
    array=prefix+b'0,'*count+b'0]}'
    add('maximum-sibling-array',prefix,base_record,pad=2)
    add('escaped-required-name',base.replace(b'"version"',b'"versi\\u006fn"'),base_record)
    add('escaped-id',base.replace(b'"part"',b'"p\\u0061rt"'),base_record)
    add('escaped-base64',base.replace(b'e30=',b'\\u0065\\u0033\\u0030\\u003d'),base_record)
    add('json-escaped-slash',wire(body=b'\xff').replace(b'/w==',b'\\/w=='),record(body=b'\xff'))
    add('unknown-mixed-values',base[:-1]+b',"ignored":{"a":[null,true,false,1.5e+2,-2.5e-1,{"x":"\\/"}]}}',base_record)
    add('unknown-duplicates',base[:-1]+b',"x":1,"x":2}',base_record)
    add('depth64',base[:-1]+b',"x":'+b'['*63+b'0'+b']'*63+b'}',base_record)
    add('depth65-refusal',base[:-1]+b',"x":'+b'['*64+b'0'+b']'*64+b'}')
    for label,packet in [
        ('empty',b''),('array-root',b'[]'),('missing',b'{}'),('trailing',base+b'x'),('comment',b';x\n'+base),('nbsp','\u00a0'.encode()+base),
        ('trailing-comma',base[:-1]+b',}'),('missing-colon',base.replace(b'"version":',b'"version" ')),
        ('duplicate',base[:-1]+b',"version":1}'),('escaped-duplicate',base[:-1]+b',"versi\\u006fn":1}'),
        ('version0',base.replace(b':1,',b':0,',1)),('version2',base.replace(b':1,',b':2,',1)),('version-float',base.replace(b':1,',b':1.0,',1)),
        ('index-negative',base.replace(b'"partIndex":0',b'"partIndex":-1')),('index-float',base.replace(b'"partIndex":0',b'"partIndex":0e0')),
        ('index-count',wire(index=1)),('count0',wire(total=0)),('count2049',wire(total=2049)),('index-huge',wire(index=2147483648,total=2048)),
        ('empty-id',wire(ident='')),('161-ascii',wire(ident='a'*161)),('162-astral',wire(ident='😀'*81)),
        ('high-surrogate',base.replace(b'"part"',b'"\\ud800"')),('low-surrogate',base.replace(b'"part"',b'"\\udc00"')),
        ('invalid-utf8',base.replace(b'"part"',b'"\xc0\xaf"')),('raw-control',base.replace(b'"part"',b'"p\x01"')),
        ('701-bytes',wire(body=bytes(701))),('payload-number',base.replace(b'"e30="',b'0')),
        ('pad-bits-one',wire(body=b'f').replace(b'Zg==',b'Zh==')),('pad-bits-two',wire(body=b'fo').replace(b'Zm8=',b'Zm9=')),
        ('missing-pad',wire(body=b'f').replace(b'Zg==',b'Zg')),('extra-after-pad',wire(body=b'f').replace(b'Zg==',b'Zg==AAAA')),
        ('base64-space',base.replace(b'e30=',b'e 30=')),('base64-url',wire(body=b'\xff').replace(b'/w==',b'_w==')),
        ('bad-escape',base.replace(b'"part"',b'"\\x20"')),('bad-unicode',base.replace(b'"part"',b'"\\uZZZZ"')),
        ('bad-unknown-array',base[:-1]+b',"x":[1,]}'),('bad-unknown-object',base[:-1]+b',"x":{"a":1,}}')]:add('reject-'+label,packet)
    for number in [b'+1',b'01',b'.1',b'1.',b'-',b'1e',b'1e-',b'NaN',b'Infinity',b'undefined',b'truex',b'nullx']:
        add('unknown-number-'+number.decode(),base[:-1]+b',"x":'+number+b'}')
    for capacity in [0,2047]:add('decode-short-'+str(capacity),base,capacity=capacity)
    add('decode-count-overflow',base,used=65537)
    add('decode-capacity-overflow',base,capacity=65537)
    add('decode-short-work',base,work=8191)
    for alias in [1,2,3]:add('decode-alias-'+str(alias),base,alias=alias)
    for at,val,label in [(0,0,'magic'),(4,0,'id-empty'),(4,641,'id-overflow'),(8,159,'units'),(12,1,'index'),(16,2049,'parts'),(20,701,'body')]:
        raw=bytearray(base_record);struct.pack_into('<I',raw,at,val);add('encode-invalid-'+label,bytes(raw),op=1)
    raw=bytearray(base_record);raw[64]=255;add('encode-invalid-utf8',bytes(raw),op=1)
    for count in [2047,2049]:add('encode-shape-count-'+str(count),base_record,op=1,used=count)
    add('encode-short-output',base_record,op=1,capacity=len(base)-1)
    add('encode-short-work',base_record,op=1,work=8191)
    for alias in [1,2,3]:add('encode-alias-'+str(alias),base_record,op=1,alias=alias)
    header=bytearray(64);header[:8]=b'KAPPF001';table=bytearray(len(rows)*80);pool=bytearray()
    def put(data):
        if not data:return 0
        pos=pool.find(data)
        if pos<0:pos=len(pool);pool.extend(data)
        return 64+len(table)+pos
    struct.pack_into('<II',header,8,len(rows),64)
    header[16:48]=hmac.digest(bytes([11])*20,b'Hi There','blake2s')
    edn=b'{:a 1}';struct.pack_into('<II',header,48,put(edn),len(edn))
    metadata=[]
    for i,row in enumerate(rows):
        at=i*80
        struct.pack_into('<4I3q4I',table,at,row['op'],put(row['data']),len(row['data']),row['pad'],row['used'],row['capacity'],row['expected'],row['work'],row['alias'],row['wiped'],row['outputBytes'])
        # Hashes are separate immutable pool data to keep each row80 bytes.
        struct.pack_into('<I',table,at+56,put(row['hash']))
        metadata.append({k:v for k,v in row.items() if isinstance(v,(str,int))}|{'inputSHA256':hashlib.sha256(row['data']).hexdigest(),'expectedHash':row['hash'].hex()})
    blob=bytes(header+table+pool)
    assert len(blob)<=131072,len(blob)
    return blob,dict(count=len(rows),cases=metadata,expectedHashes=[r['hash'].hex() for r in rows],publicDataOnly=True,codecOnly=True)
