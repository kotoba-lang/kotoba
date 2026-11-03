"""FIPS 204 ML-DSA-65 reference in Python, the independent oracle for the native gate.

Dev tool, not part of the library. Standard library only (hashlib SHA-3/SHAKE). It was
checked against the ACVP keyGen, sigGen and sigVer ML-DSA-65 groups before the
`.kotoba` port was written, and tools/gen_gate.py uses it to make the two crafted
signatures in the gate. Not constant time; never use it to protect a secret.
"""
import hashlib
Q=8380417; D=13; TAU=49; LAM=192; G1=1<<19; G2=(Q-1)//32; K=6; L=5; ETA=4; BETA=196; OMEGA=55
def shake256(b,n): return hashlib.shake_256(bytes(b)).digest(n)
def shake128(b,n): return hashlib.shake_128(bytes(b)).digest(n)
def br8(i): return int(f'{i:08b}'[::-1],2)
ZETAS=[pow(1753,br8(i),Q) for i in range(256)]
def ntt(f):
    w=list(f); m=0; ln=128
    while ln>=1:
        st=0
        while st<256:
            m+=1; z=ZETAS[m]
            for j in range(st,st+ln):
                t=z*w[j+ln]%Q; w[j+ln]=(w[j]-t)%Q; w[j]=(w[j]+t)%Q
            st+=2*ln
        ln//=2
    return w
def intt(w):
    w=list(w); m=256; ln=1
    while ln<256:
        st=0
        while st<256:
            m-=1; z=(-ZETAS[m])%Q
            for j in range(st,st+ln):
                t=w[j]; w[j]=(t+w[j+ln])%Q; w[j+ln]=z*(t-w[j+ln])%Q
            st+=2*ln
        ln*=2
    return [x*8347681%Q for x in w]
def pmul(a,b): return [x*y%Q for x,y in zip(a,b)]
def padd(a,b): return [(x+y)%Q for x,y in zip(a,b)]
def psub(a,b): return [(x-y)%Q for x,y in zip(a,b)]
def rej_ntt(seed):
    n=3*168*6
    while True:
        b=shake128(seed,n); out=[]; p=0
        while len(out)<256 and p+3<=n:
            x=b[p]+256*b[p+1]+65536*(b[p+2]&127); p+=3
            if x<Q: out.append(x)
        if len(out)==256: return out
        n+=3*168
def rej_bounded(seed):
    n=136*2
    while True:
        b=shake256(seed,n); out=[]; p=0
        while len(out)<256 and p<n:
            z=b[p]; p+=1
            for h in (z%16, z//16):
                if h<9 and len(out)<256: out.append((4-h)%Q)
        if len(out)==256: return out
        n+=136
def expand_a(rho): return [[rej_ntt(rho+bytes([s,r])) for s in range(L)] for r in range(K)]
def matvec(A,v): 
    out=[]
    for r in range(K):
        acc=[0]*256
        for s in range(L): acc=padd(acc,pmul(A[r][s],v[s]))
        out.append(acc)
    return out
def cent(x,m): # x mod+- m, m even
    r=x%m
    return r-m if r>m//2 else r
def power2round(r):
    r0=cent(r%Q,1<<D); return ((r%Q-r0)>>D, r0)
def decompose(r):
    rp=r%Q; r0=cent(rp,2*G2)
    if rp-r0==Q-1: return 0, r0-1
    return (rp-r0)//(2*G2), r0
def high(r): return decompose(r)[0]
def low(r): return decompose(r)[1]
def use_hint(h,r):
    r1,r0=decompose(r)
    if h and r0>0: return (r1+1)%16
    if h and r0<=0: return (r1-1)%16
    return r1
def pack(vals,bits):
    buf=0;nb=0;out=[]
    for v in vals:
        buf|=v<<nb; nb+=bits
        while nb>=8: out.append(buf&255); buf>>=8; nb-=8
    return out
def unpack(b,start,bits,n=256):
    out=[];buf=0;nb=0;i=start
    while len(out)<n:
        if nb>=bits: out.append(buf&((1<<bits)-1)); buf>>=bits; nb-=bits
        else: buf|=b[i]<<nb; i+=1; nb+=8
    return out
def inf(v): return max(abs(cent(x,Q)) for p in v for x in p)
def keygen(xi):
    h=shake256(list(xi)+[K,L],128); rho,rhop,key=h[:32],h[32:96],h[96:]
    A=expand_a(rho)
    s1=[rej_bounded(rhop+bytes([r,0])) for r in range(L)]
    s2=[rej_bounded(rhop+bytes([r+L,0])) for r in range(K)]
    t=[padd(intt(x),y) for x,y in zip(matvec(A,[ntt(s) for s in s1]),s2)]
    t1=[[power2round(x)[0] for x in p] for p in t]; t0=[[power2round(x)[1] for x in p] for p in t]
    pk=list(rho)+sum((pack(p,10) for p in t1),[])
    tr=shake256(pk,64)
    sk=list(rho)+list(key)+list(tr)+sum((pack([(ETA-cent(x,Q)) for x in p],4) for p in s1+s2),[])+sum((pack([(1<<12)-x for x in p],13) for p in t0),[])
    return bytes(pk),bytes(sk)
def sample_in_ball(ct):
    n=136
    while True:
        b=shake256(ct,n); s=int.from_bytes(b[:8],'little'); c=[0]*256; p=8; ok=True
        for i in range(256-TAU,256):
            while True:
                if p>=n: ok=False; break
                j=b[p]; p+=1
                if j<=i: break
            if not ok: break
            c[i]=c[j]; c[j]=1 if ((s>>(i+TAU-256))&1)==0 else Q-1
        if ok: return c
        n+=136
def sk_decode(sk):
    rho,key,tr=sk[:32],sk[32:64],sk[64:128]
    s=[[ (ETA-x)%Q for x in unpack(sk,128+128*i,4)] for i in range(L+K)]
    t0=[[ ((1<<12)-x)%Q for x in unpack(sk,128+128*(L+K)+416*i,13)] for i in range(K)]
    return rho,key,tr,s[:L],s[L:],t0
def sign_mu(sk,mu,rnd):
    rho,key,tr,s1,s2,t0=sk_decode(sk)
    s1h=[ntt(x) for x in s1]; s2h=[ntt(x) for x in s2]; t0h=[ntt(x) for x in t0]; A=expand_a(rho)
    rpp=shake256(list(key)+list(rnd)+list(mu),64); kap=0
    while True:
        y=[[ (G1-x)%Q for x in unpack(shake256(list(rpp)+[(kap+r)&255,(kap+r)>>8],640),0,20)] for r in range(L)]
        w=[intt(p) for p in matvec(A,[ntt(p) for p in y])]
        w1=[[high(x) for x in p] for p in w]
        ct=shake256(list(mu)+sum((pack(p,4) for p in w1),[]),LAM//4)
        ch=ntt(sample_in_ball(ct))
        cs1=[intt(pmul(ch,x)) for x in s1h]; cs2=[intt(pmul(ch,x)) for x in s2h]
        z=[padd(a,b) for a,b in zip(y,cs1)]
        wm=[psub(a,b) for a,b in zip(w,cs2)]
        r0=[[low(x) for x in p] for p in wm]
        kap+=L
        if inf(z)>=G1-BETA or max(abs(x) for p in r0 for x in p)>=G2-BETA: continue
        ct0=[intt(pmul(ch,x)) for x in t0h]
        h=[[int(high(a)!=high((a+b)%Q)) for a,b in zip(pa,pb)] for pa,pb in zip(wm,ct0)]  # MakeHint(-ct0, w-cs2+ct0)
        if inf(ct0)>=G2 or sum(map(sum,h))>OMEGA: continue
        hb=[0]*(OMEGA+K); idx=0
        for i in range(K):
            for j in range(256):
                if h[i][j]: hb[idx]=j; idx+=1
            hb[OMEGA+i]=idx
        return bytes(list(ct)+sum((pack([(G1-cent(x,Q)) for x in p],20) for p in z),[])+hb)
def verify_mu(pk,mu,sig):
    if len(pk)!=1952 or len(sig)!=3309: return False
    rho=pk[:32]; t1=[unpack(pk,32+320*i,10) for i in range(K)]
    ct=sig[:48]; z=[[ (G1-x)%Q for x in unpack(sig,48+640*i,20)] for i in range(L)]
    hb=sig[3248:]; h=[[0]*256 for _ in range(K)]; idx=0
    for i in range(K):
        if hb[OMEGA+i]<idx or hb[OMEGA+i]>OMEGA: return False
        first=idx
        while idx<hb[OMEGA+i]:
            if idx>first and hb[idx-1]>=hb[idx]: return False
            h[i][hb[idx]]=1; idx+=1
    if any(hb[i]!=0 for i in range(idx,OMEGA)): return False
    if inf(z)>=G1-BETA: return False
    A=expand_a(rho); ch=ntt(sample_in_ball(ct))
    az=matvec(A,[ntt(p) for p in z])
    w=[intt(psub(a,pmul(ch,ntt([x*(1<<D)%Q for x in t])))) for a,t in zip(az,t1)]
    w1=[[use_hint(hh,x) for hh,x in zip(ph,p)] for ph,p in zip(h,w)]
    return shake256(list(mu)+sum((pack(p,4) for p in w1),[]),48)==bytes(ct)
def mu_of(pk_or_tr,mp,is_tr=False):
    tr=pk_or_tr if is_tr else shake256(pk_or_tr,64)
    return shake256(list(tr)+list(mp),64)
