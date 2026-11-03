"""Independent maximum-frame data using the existing public managed vectors.

No new language evaluator: native code alone interprets the signed literal map.
We replace one public plaintext's first byte with data-kind1 and recompute its
independent incoming ciphertext/outgoing expected hash at the same fixed size.
"""
import hashlib
import importlib.util
from pathlib import Path
import struct
ROOT=Path(__file__).resolve().parents[3]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def fixtures(suite):
    ref=load('frame_bounds_managed',ROOT/'lib/kotoba.kekkai/tools/session_region_reference.py')
    raw,metadata=ref.fixtures(suite)
    if metadata['count']!=1:raise ValueError('maximum suite must contain one case')
    blob=bytearray(raw)
    d=lambda at:struct.unpack_from('<I',blob,at)[0]
    row=d(132)
    c=load('frame_bounds_chacha',ROOT/'lib/org.ietf.chacha20Poly1305/tools/reference.py')
    size=d(row+76);start=(d(row+88)+14)%256
    plain=b'\1'+bytes((i*17+start)%256 for i in range(1,size))
    rx=bytes(blob[d(row+64):d(row+64)+32]);tx=bytes(blob[d(row+60):d(row+60)+32])
    incoming=bytes(8)+c.seal(rx,bytes(12),bytes(8),plain)
    outgoing=bytes(8)+c.seal(tx,bytes(12),bytes(8),plain)
    assert len(incoming)==d(row+72)
    at=d(row+68);blob[at:at+len(incoming)]=incoming
    at=d(row+80);digest=hashlib.blake2s(outgoing).digest();blob[at:at+32]=digest
    metadata['expectedNativeHashes'][1]=digest.hex()
    metadata['frameAdapter']=True;metadata['innerKind']=1;metadata['bodyBytes']=size-1
    metadata['incomingFramedBytes']=len(incoming)+3
    return bytes(blob),metadata
