"""Public document input/expected bytes, not a reassembly/runtime evaluator."""
import json,struct


def documents():
    rows=[]
    def add(name,raw,expected,used=None,mode=0,at=0):
        rows.append(dict(name=name,raw=raw,expected=int(expected),used=len(raw) if used is None else used,mode=mode,at=at))
    for raw in [b'null',b'true',b'false',b'0',b'-0',b'1.25e-12',b'[]',b'{}',b'""',b'"\\/"',b'"\\ud83d\\ude00"',
                '"漢😀"'.encode(),b' {"a":[null,true,false,1.2e3,{"b":"x"}],"a":0} \n',b'['*64+b'0'+b']'*64]:
        add('valid-'+str(len(rows)),raw,True)
    for raw in [b'',b' ',b'nullx',b'01',b'-01',b'+1',b'1.',b'.1',b'1e',b'1e+',b'-',b'NaN',b'Infinity',b'undefined',
                b'[1,]',b'{"a":1,}',b'{a:1}',b'{"a" 1}',b'"\x01"',b'"\\x20"',b'"\\ud800"',b'"\\udc00"',
                b'"\\ud800\\u0000"',b'"\xc0\xaf"',b'"\xed\xa0\x80"',b'"\xf4\x90\x80\x80"',b'"\x80"',b'"\xe6\xbc"',
                b'"\\u123"',b'"\\',b'"no end',b'/*x*/0',b'\xef\xbb\xbf0',b'['*65+b'0'+b']'*65]:
        add('invalid-'+str(len(rows)),raw,False)
    add('one-MiB-string',b'',True,1048576,1)
    add('one-MiB-whitespace-then-zero',b'0',True,1048576,2,1048575)
    add('one-MiB-trailing-garbage',b'x',False,1048576,1,1048575)
    add('one-MiB-overflow-real-view',b'',False,1048577,1)
    add('utf8-across-64KiB', '😀'.encode(),True,1048576,1,65535)
    add('escape-across-64KiB',b'\\ud83d\\ude00',True,1048576,1,65535)
    add('bad-utf8-across-64KiB',b'\xf0\x80\x80\x80',False,1048576,1,65535)
    add('truncated-last-scalar',b'\xf0\x9f',False,1048576,1,1048573)
    add('truncated-last-escape',b'\\ud83d',False,1048576,1,1048569)
    table=bytearray(16+len(rows)*32);table[:8]=b'KARDOC01';struct.pack_into('<I',table,8,len(rows));data=bytearray()
    for i,row in enumerate(rows):
        struct.pack_into('<7I',table,16+i*32,len(table)+len(data),len(row['raw']),row['used'],row['expected'],row['mode'],row['at'],i)
        data.extend(row['raw'])
    blob=bytes(table+data)
    assert len(blob)<49152
    return blob,[{k:v for k,v in r.items() if k!='raw'} for r in rows]


def payload(size):
    raw=bytearray((97+i%26 for i in range(size)))
    if size:raw[0]=34
    if size>1:raw[-1]=34
    return bytes(raw)
