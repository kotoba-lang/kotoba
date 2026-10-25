# CPU dequant oracle for the :gpu/compute K-quant dot guests (verify/native/gpu). Python because it is a
# TEST ORACLE beside numpy, not operations tooling (AGENTS.md kbb-first is for tooling); a .cljk twin is debt.
# GGUF tensor directory + CPU dequant reference for the native kdot types,
# including Prism PQ2_0/PTQ1_0 and Qwen3.8 BF16 projections.
# Prints "name type offset(bytes, absolute in file) dims" and writes a reference dot.
import struct, sys, numpy as np, json
def read_gguf_dir(path):
    f=open(path,'rb'); r=f.read
    def u32(): return struct.unpack('<I',r(4))[0]
    def u64(): return struct.unpack('<Q',r(8))[0]
    def s():
        n=u64(); return r(n).decode()
    def val(t):
        if t in (0,1): return struct.unpack('<B' if t==0 else '<b',r(1))[0]
        if t in (2,3): return struct.unpack('<H' if t==2 else '<h',r(2))[0]
        if t in (4,5): return struct.unpack('<I' if t==4 else '<i',r(4))[0]
        if t==6: return struct.unpack('<f',r(4))[0]
        if t==7: return struct.unpack('<B',r(1))[0]
        if t==8: return s()
        if t==9:
            et=u32(); n=u64(); return [val(et) for _ in range(n)]
        if t in (10,11): return struct.unpack('<Q' if t==10 else '<q',r(8))[0]
        if t==12: return struct.unpack('<d',r(8))[0]
        raise ValueError(t)
    assert r(4)==b'GGUF'; ver=u32(); nt=u64(); nkv=u64()
    kv={}
    for _ in range(nkv):
        k=s(); t=u32(); kv[k]=val(t)
    align=kv.get('general.alignment',32)
    tensors=[]
    for _ in range(nt):
        name=s(); nd=u32(); dims=[u64() for _ in range(nd)]; typ=u32(); off=u64()
        tensors.append((name,typ,off,dims))
    pos=f.tell(); data_start=(pos+align-1)//align*align
    return kv,tensors,data_start
KV=np.array([-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113],dtype=np.float32)
def f16(b): return np.frombuffer(b,dtype=np.float16)[0].astype(np.float32)
def deq_iq4xs(blk):
    d=f16(blk[0:2]); sh=struct.unpack('<H',blk[2:4])[0]; sl=blk[4:8]; qs=np.frombuffer(blk[8:136],dtype=np.uint8)
    out=np.zeros(256,np.float32)
    for ib in range(8):
        ls=((sl[ib//2]>>(4*(ib%2)))&0xf)|(((sh>>(2*ib))&3)<<4); dl=np.float32(d*(ls-32))
        q=qs[16*ib:16*ib+16]; out[32*ib:32*ib+16]=dl*KV[q&0xf]; out[32*ib+16:32*ib+32]=dl*KV[q>>4]
    return out
def q4k_scales(sc):
    scales=np.zeros(8,np.int32); mins=np.zeros(8,np.int32)
    for j in range(8):
        if j<4: scales[j]=sc[j]&63; mins[j]=sc[j+4]&63
        else: scales[j]=(sc[j+4]&0xf)|((sc[j-4]>>6)<<4); mins[j]=(sc[j+4]>>4)|((sc[j]>>6)<<4)
    return scales,mins
def deq_q5k(blk):
    d=f16(blk[0:2]); dmin=f16(blk[2:4]); scales,mins=q4k_scales(np.frombuffer(blk[4:16],dtype=np.uint8))
    qh=np.frombuffer(blk[16:48],dtype=np.uint8); qs=np.frombuffer(blk[48:176],dtype=np.uint8)
    out=np.zeros(256,np.float32)
    for g in range(4):  # 64-value groups
        lo=qs[32*g:32*g+32]&0xf; hi=qs[32*g:32*g+32]>>4
        b_lo=((qh>>(2*g))&1)<<4; b_hi=((qh>>(2*g+1))&1)<<4
        j0=2*g; j1=2*g+1
        out[64*g:64*g+32]=d*scales[j0]*(lo|b_lo).astype(np.float32)-dmin*mins[j0]
        out[64*g+32:64*g+64]=d*scales[j1]*(hi|b_hi).astype(np.float32)-dmin*mins[j1]
    return out
def deq_q6k(blk):
    ql=np.frombuffer(blk[0:128],dtype=np.uint8); qh=np.frombuffer(blk[128:192],dtype=np.uint8)
    sc=np.frombuffer(blk[192:208],dtype=np.int8); d=f16(blk[208:210])
    out=np.zeros(256,np.float32)
    for g in range(2):  # 128-value halves
        qlg=ql[64*g:64*g+64]; qhg=qh[32*g:32*g+32]; scg=sc[8*g:8*g+8]
        for l in range(32):
            q1=((qlg[l]&0xf)|(((qhg[l]>>0)&3)<<4))-32
            q2=((qlg[l+32]&0xf)|(((qhg[l]>>2)&3)<<4))-32
            q3=((qlg[l]>>4)|(((qhg[l]>>4)&3)<<4))-32
            q4=((qlg[l+32]>>4)|(((qhg[l]>>6)&3)<<4))-32
            out[128*g+l]=d*scg[l//16]*q1; out[128*g+32+l]=d*scg[2+l//16]*q2
            out[128*g+64+l]=d*scg[4+l//16]*q3; out[128*g+96+l]=d*scg[6+l//16]*q4
    return out
# Q8_0 (8) / Q4_0 (2) / F16 (1), iteration 53: 32-value blocks (34 B / 18 B) or none (2 B/value), so a row is
# ceil(cols/32) blocks and cols need not be a 256-multiple (Qwen2.5-0.5B: 896). BLOCK32 is the native unit the
# main loop uses for these types; the deq_*(256-group) forms below are the 8-block wrappers for callers that
# want the K-quant shape (272 / 144 / 512 B per 256 values, block_bytes_of() in the kernels).
def deq_q8_0_32(b):
    return (f16(b[0:2])*np.frombuffer(b[2:34],dtype=np.int8).astype(np.float32)).astype(np.float32)
def deq_q4_0_32(b):
    d=f16(b[0:2]); qs=np.frombuffer(b[2:18],dtype=np.uint8)
    return np.concatenate([d*((qs&0xf).astype(np.float32)-8), d*((qs>>4).astype(np.float32)-8)]).astype(np.float32)
def deq_f16_32(b): return np.frombuffer(b[0:64],dtype=np.float16).astype(np.float32)
def deq_bf16_32(b): return (np.frombuffer(b[0:64],dtype='<u2').astype(np.uint32)<<16).view(np.float32)
def deq_pq2_0_128(b):
    d=f16(b[0:2]); q=np.frombuffer(b[2:34],dtype=np.uint8); out=np.empty(128,np.float32)
    for i in range(4): out[i::4]=d*(((q>>(2*i))&3).astype(np.float32)-1)
    return out
def deq_ptq1_0_128(b):
    out=np.empty(128,np.float32); d=f16(b[26:28]); qs=np.frombuffer(b[:24],dtype=np.uint8); qh=np.frombuffer(b[24:26],dtype=np.uint8)
    for e in range(128):
        if e<80: v=int(qs[e&15]); n=e>>4
        elif e<120: t=e-80; v=int(qs[16+(t&7)]); n=t>>3
        else: t=e-120; v=int(qh[t&1]); n=t>>1
        for _ in range(n): v=(v*3)&255
        out[e]=d*(((v*3)>>8)-1)
    return out
# Q4_1 (3) / Q5_0 (6) / Q5_1 (7), iteration 53b: 20 / 22 / 24 B per 32 values (ggml-common.h block_q4_1 / block_q5_0 /
# block_q5_1). Nibble order as Q4_0 (low nibbles = values 0..15, high nibbles = 16..31); the 5th bit of value j is bit j
# of the little-endian u32 qh (dequantize_row_q5_0: xh_0 = (qh >> j) << 4, xh_1 = (qh >> (j + 12)) & 0x10). Q4_1 / Q5_1
# are d*q + m, Q5_0 is d*(q - 16). `check_q5x_against_dense_ref()` asserts these agree bit for bit with dense_ref.py's.
def _q5_nibbles_32(qh,qs):
    j=np.arange(16); lo=(qs&0xf)|(((qh>>j)&1)<<4); hi=(qs>>4)|(((qh>>(j+16))&1)<<4)
    return np.concatenate([lo,hi]).astype(np.float32)
def deq_q4_1_32(b):
    d=f16(b[0:2]); m=f16(b[2:4]); qs=np.frombuffer(b[4:20],dtype=np.uint8)
    return (d*np.concatenate([(qs&0xf).astype(np.float32),(qs>>4).astype(np.float32)])+m).astype(np.float32)
def deq_q5_0_32(b):
    d=f16(b[0:2]); qh=int(struct.unpack('<I',b[2:6])[0]); qs=np.frombuffer(b[6:22],dtype=np.uint8).astype(np.int64)
    return (d*(_q5_nibbles_32(qh,qs)-16)).astype(np.float32)
def deq_q5_1_32(b):
    d=f16(b[0:2]); m=f16(b[2:4]); qh=int(struct.unpack('<I',b[4:8])[0]); qs=np.frombuffer(b[8:24],dtype=np.uint8).astype(np.int64)
    return (d*_q5_nibbles_32(qh,qs)+m).astype(np.float32)
def deq_q4_1(blk): return np.concatenate([deq_q4_1_32(blk[20*i:20*i+20]) for i in range(8)])
def deq_q5_0(blk): return np.concatenate([deq_q5_0_32(blk[22*i:22*i+22]) for i in range(8)])
def deq_q5_1(blk): return np.concatenate([deq_q5_1_32(blk[24*i:24*i+24]) for i in range(8)])
def check_q5x_against_dense_ref(raw_by_type):
    """raw_by_type: {3|6|7: bytes of >= 1 block}. Returns the number of blocks compared (0 = nothing compared, not a pass);
    raises AssertionError when kdot_ref's 32-value dequant and dense_ref.py's (the llama-server-matched oracle) differ in
    any value (both compared as f32 -- dense_ref returns f64 of the same f16 * int arithmetic)."""
    import importlib.util, os
    spec=importlib.util.spec_from_file_location('dense_ref_mod',os.path.join(os.path.dirname(os.path.abspath(__file__)),'dense_ref.py'))
    src=open(spec.origin).read(); ns={}
    # dense_ref.py runs its CLI at import; pull only the dequant definitions (everything before the BLOCK table).
    head=src[:src.index('BLOCK = {')]; head=head[head.index('# ---- dequant'):]
    exec("import numpy as np\nimport kdot_ref as g\n"+head,ns)
    n=0
    for typ,raw in raw_by_type.items():
        bb,mine=BLOCK32[typ]; theirs={3:ns['deq_q4_1'],6:ns['deq_q5_0'],7:ns['deq_q5_1']}[typ]
        nb=len(raw)//bb; assert nb>=1,(typ,len(raw))
        a=np.stack([mine(raw[i*bb:(i+1)*bb]) for i in range(nb)])
        b=theirs(np.frombuffer(raw[:nb*bb],dtype=np.uint8).reshape(nb,bb)).astype(np.float32)
        assert a.shape==b.shape and np.array_equal(a.view(np.uint32),b.view(np.uint32)),("kdot_ref vs dense_ref differ for type",typ,np.max(np.abs(a-b)))
        n+=nb
    return n
def deq_q8_0(blk): return np.concatenate([deq_q8_0_32(blk[34*i:34*i+34]) for i in range(8)])
def deq_q4_0(blk): return np.concatenate([deq_q4_0_32(blk[18*i:18*i+18]) for i in range(8)])
def deq_f16(blk): return np.frombuffer(blk[0:512],dtype=np.float16).astype(np.float32)
BLOCK={1:(512,deq_f16),2:(144,deq_q4_0),8:(272,deq_q8_0),13:(176,deq_q5k),14:(210,deq_q6k),23:(136,deq_iq4xs),3:(160,deq_q4_1),6:(176,deq_q5_0),7:(192,deq_q5_1),142:(34,deq_pq2_0_128),143:(28,deq_ptq1_0_128)}
BLOCK32={1:(64,deq_f16_32),2:(18,deq_q4_0_32),8:(34,deq_q8_0_32),3:(20,deq_q4_1_32),6:(22,deq_q5_0_32),7:(24,deq_q5_1_32),30:(64,deq_bf16_32)}
def row_geometry(typ,cols):
    """(block bytes, dequant, blocks per row): the native unit -- 32-value blocks for BLOCK32 types, else 256."""
    if typ in BLOCK32:
        bb,deq=BLOCK32[typ]; assert cols%32==0,(typ,cols); return bb,deq,cols//32
    bb,deq=BLOCK[typ]; unit=128 if typ in (142,143) else 256; assert cols%unit==0,(typ,cols); return bb,deq,cols//unit
if __name__=='__main__':
    path=sys.argv[1]; names=sys.argv[2:]
    kv,tensors,ds=read_gguf_dir(path)
    print("data_start",ds)
    f=open(path,'rb')
    if not names:   # directory listing: name type dims (types per the ggml enum: 0 F32 1 F16 2 Q4_0 3 Q4_1 6 Q5_0 7 Q5_1 8 Q8_0 12..14 Q4_K..Q6_K 23 IQ4_XS)
        for name,typ,off,dims in tensors: print(name,typ,dims)
        from collections import Counter; print("types",dict(Counter(t[1] for t in tensors)))
    for name,typ,off,dims in tensors:
        if name in names:
            cols,rows=dims[0],dims[1]; bb,deq,nb=row_geometry(typ,cols); rowbytes=nb*bb
            print(name,typ,ds+off,dims,"bytes",rows*rowbytes)
            if typ in (3,6,7):   # the new dequants must agree with dense_ref.py's on this tensor's first row (all its blocks)
                f.seek(ds+off); print(name,"q5x-check blocks agreeing with dense_ref.py:",check_q5x_against_dense_ref({typ:f.read(rowbytes)}))
            rng=np.random.default_rng(11); x=rng.standard_normal(cols).astype(np.float32); x.tofile(name.replace('.','_')+'.x.f32')
            f.seek(ds+off); raw=f.read(rows*rowbytes)
            nref=min(rows,64)  # reference for the first 64 rows (CPU dequant is slow)
            ref=np.zeros(nref,np.float64)
            for r in range(nref):
                row=np.concatenate([deq(raw[r*rowbytes+b*bb:r*rowbytes+(b+1)*bb]) for b in range(nb)])
                ref[r]=np.dot(row.astype(np.float64),x.astype(np.float64))
            np.save(name.replace('.','_')+'.ref.npy',ref)
            # the same dot against the activation nex_ops.comp's quant_q8 hands the int8 kdots (per 32 values:
            # scale = max|x| / 127, q = round(x / scale)) -- what an int8 kernel should reproduce to f32 accumulation
            # error; the gap between .ref and .refq is the activation quantization itself, not the kernel (tick 55).
            xb=x.reshape(-1,32); sc=np.abs(xb).max(axis=1,keepdims=True)/np.float32(127)
            xq=(np.where(sc>0,np.rint(xb/np.where(sc>0,sc,1)),0)*sc).astype(np.float32).reshape(-1)
            refq=np.zeros(nref,np.float64)
            for r in range(nref):
                row=np.concatenate([deq(raw[r*rowbytes+b*bb:r*rowbytes+(b+1)*bb]) for b in range(nb)])
                refq[r]=np.dot(row.astype(np.float64),xq.astype(np.float64))
            np.save(name.replace('.','_')+'.refq.npy',refq)
