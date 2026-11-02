"""Public schema vectors and independent output goldens; no policy evaluator.

Only builds declared valid records / explicit refusals. Does not parse arbitrary
messages, resolve language imports, run a backend, or authorize operations.
"""
import json,struct
SIZE=1048576
FIELDS=['messageType','requestId','serviceName','method','path','headers','port','bodyBase64','status']
HEADERS=['accept','content-type','if-none-match','range','content-length','etag','last-modified','content-range']

def quoted(value):return json.dumps(value,ensure_ascii=True,separators=(',',':')).encode()
def units(value):return len(value.encode('utf-16-le'))//2

def valid(kind=1,changes=None,heads=None,large=0,full=False):
    values={'messageType':'request' if kind==1 else 'response','requestId':'12345678-1234-1234-1234-123456789abc'}
    if kind==1:values.update(serviceName='local-docs',method='GET',path='/docs?q=1',headers=heads or {},port=8080,bodyBase64='')
    else:values.update(status=200,headers=heads or {},bodyBase64='')
    values.update(changes or {});record=bytearray(4096);raw=bytearray(b'{');header_mask=0;root_mask=0
    for index,(name,value) in enumerate(values.items()):
        if index:raw+=b','
        raw+=quoted(name)+b':'
        start=len(raw)
        if name=='headers':
            raw+=b'{'
            for i,(key,text) in enumerate(value.items()):
                if i:raw+=b','
                raw+=quoted(key)+b':'
                at=len(raw);raw+=quoted(text);h=HEADERS.index(key.lower());header_mask|=1<<h
                struct.pack_into('<4I',record,256+h*16,at,len(raw),units(text),0)
            raw+=b'}'
        elif isinstance(value,str):raw+=quoted(value)
        else:raw+=str(value).encode()
        if name in FIELDS:
            f=FIELDS.index(name);root_mask|=1<<f
            struct.pack_into('<4I',record,64+f*16,start,len(raw),units(value) if isinstance(value,str) else 0,0)
    raw+=b'}'
    if large:
        start,end,_,_=struct.unpack_from('<4I',record,64+7*16);at=start+1
        assert raw[at:end-1]==b''
        raw[at:at]=b'A'*large
        for offset in [64+i*16 for i in range(9)]+[256+i*16 for i in range(8)]:
            begin,finish,u,z=struct.unpack_from('<4I',record,offset)
            if begin>=at:begin+=large;finish+=large
            elif finish>at:finish+=large;u+=large
            struct.pack_into('<4I',record,offset,begin,finish,u,z)
    if full:raw+=b' '*(SIZE-len(raw))
    decoded=(large//4*3) if large else {'':0,'TQ==':1,'TWE=':2,'TWFu':3}.get(values['bodyBase64'],0)
    struct.pack_into('<4I',record,0,0x314d504b,1,kind,len(raw))
    struct.pack_into('<4I',record,24,values['port'] if kind==1 else values['status'],decoded,header_mask,root_mask)
    return bytes(raw),bytes(record)

def fixtures():
    cases=[]
    def good(label,kind=1,**kw):
        raw,record=valid(kind,**kw);cases.append(dict(label=label,raw=raw,record=record,expected=kind,work=8192,capacity=SIZE,out=4096,used=len(raw),alias=0,processed=True))
    def bad(label,raw,**kw):
        row=dict(label=label,raw=raw,record=None,expected=-1,work=8192,capacity=SIZE,out=4096,used=len(raw),alias=0,processed=True);row.update(kw);cases.append(row)
    good('request-empty');good('response-empty',2)
    good('request-all-headers',heads={'Accept':'text/plain','content-type':'application/json','if-none-match':'"abc"','range':'bytes=0-9'})
    good('response-all-headers',2,heads={'content-type':'text/plain','content-length':'2','etag':'abc','last-modified':'Wed, 01 Jan 2025 00:00:00 GMT','content-range':'bytes 0-1/2'})
    for body in ['TQ==','TWE=','TWFu']:good('base64-'+body,changes={'bodyBase64':body})
    good('unicode-ids',changes={'requestId':'a😀/日本語','serviceName':'日本語','path':'/日本語/😀'})
    good('extension-method',changes={'method':"CUSTOM!#$%&'*+-.^_`|~"})
    good('long-id-no-invented-limit',changes={'requestId':'r'*70000})
    good('long-header-no-invented-limit',heads={'accept':'x'*70000})
    for kind in [1,2]:
        good(f'large-body-{kind}',kind,large=70000)
        # Exact1MiB JSON, >512KiB decoded body, including all message overhead.
        raw,_=valid(kind);length=((SIZE-len(raw))//4)*4
        good(f'full-one-MiB-{kind}',kind,large=length,full=True)
    good('header-tab',heads={'accept':'a\tb'});good('max-port',changes={'port':65535});good('min-port',changes={'port':1})
    good('min-status',2,changes={'status':100});good('max-status',2,changes={'status':599})
    # Escaped known names and strings, same semantic spans adjusted explicitly.
    raw,rec=valid(changes={'requestId':'abc','bodyBase64':'TQ=='})
    escaped=raw.replace(b'"messageType"',b'"message\\u0054ype"').replace(b'"TQ=="',b'"T\\u0051=="')
    rec=bytearray(rec)
    for offset in [64+i*16 for i in range(9)]:
        begin,end,u,z=struct.unpack_from('<4I',rec,offset)
        if begin:begin+=5;end+=5
        if offset==64+7*16:end+=5
        struct.pack_into('<4I',rec,offset,begin,end,u,z)
    struct.pack_into('<I',rec,12,len(escaped));cases.append(dict(cases[0],label='escaped-name-base64',raw=escaped,record=bytes(rec),used=len(escaped)))
    base,_=valid()
    negatives={
      'missing':base.replace(b',"port":8080',b''),
      'duplicate':base[:-1]+b',"requestId":"b"}',
      'escaped-duplicate':base[:-1]+b',"request\\u0049d":"b"}',
      'wrong-variant':base[:-1]+b',"status":200}',
      'wrong-message-type':base.replace(b'"request"',b'"response"'),
      'not-object':b'[]','empty-object':b'{}','trailing':base+b' x','trailing-comma':base[:-1]+b',}',
      'empty-id':base.replace(quoted('12345678-1234-1234-1234-123456789abc'),b'""'),
      'id-number':base.replace(quoted('12345678-1234-1234-1234-123456789abc'),b'12'),
      'lone-surrogate':base.replace(b'"local-docs"',b'"\\ud800"'),
      'bad-utf8':base.replace(b'"local-docs"',b'"\xc0\x80"'),
      'port-zero':base.replace(b'8080',b'0'),'port-over':base.replace(b'8080',b'65536'),
      'port-string':base.replace(b'8080',b'"8080"'),'port-exponent':base.replace(b'8080',b'8.08e3'),
      'port-leading-zero':base.replace(b'8080',b'08080'),'port-negative':base.replace(b'8080',b'-1'),
      'bad-method':base.replace(b'"GET"',b'"GET \\r"'),
      'network-path':base.replace(quoted('/docs?q=1'),b'"//evil.test/x"'),
      'absolute-url':base.replace(quoted('/docs?q=1'),b'"https://evil.test/x"'),
      'backslash-path':base.replace(quoted('/docs?q=1'),b'"/a\\\\b"'),
      'newline-path':base.replace(quoted('/docs?q=1'),b'"/a\\n"'),
      'headers-array':base.replace(b'"headers":{}',b'"headers":[]'),
      'header-unallowed':base.replace(b'"headers":{}',b'"headers":{"authorization":"x"}'),
      'header-response-only':base.replace(b'"headers":{}',b'"headers":{"etag":"x"}'),
      'header-control':base.replace(b'"headers":{}',b'"headers":{"accept":"a\\u0001b"}'),
      'header-number':base.replace(b'"headers":{}',b'"headers":{"accept":1}'),
      'header-duplicate-case':base.replace(b'"headers":{}',b'"headers":{"accept":"a","Accept":"b"}'),
      'header-duplicate-escaped':base.replace(b'"headers":{}',b'"headers":{"accept":"a","a\\u0063cept":"b"}'),
      'header-crlf':base.replace(b'"headers":{}',b'"headers":{"accept":"a\\r\\nb"}'),
      'header-nul':base.replace(b'"headers":{}',b'"headers":{"accept":"a\\u0000b"}'),
      'header-del':base.replace(b'"headers":{}',b'"headers":{"accept":"a\\u007fb"}'),
      'deep-unknown':base[:-1]+b',"extra":'+b'['*64+b'0'+b']'*64+b'}',
    }
    for label,raw in negatives.items():bad(label,raw)
    bad('response-request-only-header',valid(2)[0].replace(b'"headers":{}',b'"headers":{"accept":"x"}'))
    for value in ['A','AA','AAA','A===','====','TR==','TWF=','AA=A','TQ==AAAA','TQ=','TQ===','TQ== ','TQ-_','😀']:
        bad('invalid-base64-'+value,base.replace(b'"bodyBase64":""',b'"bodyBase64":'+quoted(value)))
    for value in [99,600,-1]:bad('invalid-status-'+str(value),valid(2)[0].replace(b'"status":200',b'"status":'+str(value).encode()))
    for key,kw in [('short-work',{'work':8191}),('short-input',{'capacity':SIZE-1}),('short-output',{'out':4095}),('too-large-output',{'out':65537}),('negative-count',{'used':-1}),('over-count',{'used':SIZE+1}),('work-input-alias',{'alias':1}),('out-input-alias',{'alias':2}),('work-output-alias',{'alias':3})]:bad(key,base,processed=False,**kw)
    row=dict(cases[0],label='output-max',out=65536);cases.append(row)
    cases.append(dict(cases[0],label='work-tail',work=8193))
    cases.append(dict(cases[0],label='input-tail',capacity=SIZE+1))
    # Unknown root fields syntax checked but grant no effect. Existing spans remain.
    raw,rec=valid();raw=raw[:-1]+b',"unknown":{"nested":[true,false,null,1.2e-3]}}';rec=bytearray(rec);struct.pack_into('<I',rec,12,len(raw));cases.append(dict(cases[0],label='unknown-root-data',raw=raw,record=bytes(rec),used=len(raw)))
    return cases

def packed():
    cases=fixtures();header=bytearray(32+80*len(cases));struct.pack_into('<4I',header,0,0x314d534b,1,len(cases),32);data=bytearray(header)
    public=[]
    for i,row in enumerate(cases):
        raw=row['raw'];prefix=raw;suffix=b'';repeat=0
        # Public fixture compression only; guest expands literal ASCII 'A'/'r'/'x'.
        longest=max([(raw.find(bytes([ch])*1000),ch) for ch in [65,114,120]],key=lambda x:-1 if x[0]<0 else len(raw[x[0]:])-len(raw[x[0]:].lstrip(bytes([x[1]]))))
        at,ch=longest
        if at>=0:
            repeat=len(raw[at:])-len(raw[at:].lstrip(bytes([ch])));prefix,suffix=raw[:at],raw[at+repeat:]
        prefix_at=len(data);data+=prefix;suffix_at=len(data);data+=suffix
        struct.pack_into('<6I4q2I',data,32+i*80,prefix_at,len(prefix),suffix_at,len(suffix),repeat,ch if repeat else 0,row['used'],row['expected'],row['capacity'],row['out'],row['work'],row['alias'])
        public.append({k:v for k,v in row.items() if k not in ['raw','record']})
    assert len(data)<=49152,len(data)
    return bytes(data),cases,public
