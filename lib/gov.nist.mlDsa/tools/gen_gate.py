#!/usr/bin/env python3
"""Write kotoba/mldsa/native_gate.kotoba from the NIST ACVP ML-DSA vectors.

Dev tool, not part of the library. Standard library only.

    python3 -I tools/gen_gate.py <ACVP-Server gen-val/json-files> kotoba/mldsa/native_gate.kotoba

Source: usnistgov/ACVP-Server commit 975de31eb83d87039ec88934fdc47d8c312b892d,
ML-DSA-keyGen-FIPS204, ML-DSA-sigGen-FIPS204 and ML-DSA-sigVer-FIPS204
internalProjection.json. Hex is lowercased; long values are embedded as SHA3-256
digests. The two crafted signatures come from tools/reference.py.
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reference
from reference import *

SRC, OUT = sys.argv[1], sys.argv[2]
j=json.load(open(os.path.join(SRC,'ML-DSA-keyGen-FIPS204','internalProjection.json')))
t=[t for g in j['testGroups'] if g['parameterSet']=='ML-DSA-65' for t in g['tests'] if t['tcId']==26][0]
pk,sk=keygen(bytes.fromhex(t['seed']))
mu=mu_of(pk,b'native gate crafted')
sig=sign_mu(sk,mu,bytes(32)); assert verify_mu(pk,mu,sig)
hb=list(sig[3248:]); idx=0; done=False
for i in range(K):
    if hb[OMEGA+i]-idx>=2:
        hb[idx],hb[idx+1]=hb[idx+1],hb[idx]; done=True; break
    idx=hb[OMEGA+i]
assert done
bad_order=bytes(list(sig[:3248])+hb); assert not verify_mu(pk,mu,bad_order)
# z over the bound: sign_mu with the z test dropped, keep the first candidate that fails only it
def sign_z_over(sk,mu,rnd):
    rho,key,tr,s1,s2,t0=sk_decode(sk)
    s1h=[ntt(x) for x in s1]; s2h=[ntt(x) for x in s2]; t0h=[ntt(x) for x in t0]; A=expand_a(rho)
    rpp=shake256(list(key)+list(rnd)+list(mu),64); kap=0
    while True:
        y=[[ (G1-x)%Q for x in unpack(shake256(list(rpp)+[(kap+r)&255,(kap+r)>>8],640),0,20)] for r in range(L)]
        w=[intt(p) for p in matvec(A,[ntt(p) for p in y])]
        ct=shake256(list(mu)+sum((pack([high(x) for x in p],4) for p in w),[]),48)
        ch=ntt(sample_in_ball(ct))
        z=[padd(a,intt(pmul(ch,x))) for a,x in zip(y,s1h)]
        wm=[psub(a,intt(pmul(ch,x))) for a,x in zip(w,s2h)]
        kap+=L
        if inf(z)<G1-BETA or max(abs(low(x)) for p in wm for x in p)>=G2-BETA: continue
        ct0=[intt(pmul(ch,x)) for x in t0h]
        h=[[int(high(a)!=high((a+b)%Q)) for a,b in zip(pa,pb)] for pa,pb in zip(wm,ct0)]
        if inf(ct0)>=G2 or sum(map(sum,h))>OMEGA: continue
        hb=[0]*(OMEGA+K); idx=0
        for i in range(K):
            for jj in range(256):
                if h[i][jj]: hb[idx]=jj; idx+=1
            hb[OMEGA+i]=idx
        return bytes(list(ct)+sum((pack([(G1-cent(x,Q)) for x in p],20) for p in z),[])+hb)
z_over=sign_z_over(sk,mu,bytes(32))
assert not verify_mu(pk,mu,z_over)
# without the z bound the reference accepts it: proves the case isolates that check
reference.BETA=-10**9
assert verify_mu(pk,mu,z_over); reference.BETA=BETA
CRAFTED={'mu':mu.hex(),'hint_order':bad_order.hex(),'z_over':z_over.hex()}

H=lambda h: hashlib.sha3_256(bytes.fromhex(h)).hexdigest()
def load(n):
    j=json.load(open(os.path.join(SRC,f'ML-DSA-{n}-FIPS204','internalProjection.json')))
    return {(g['tgId'],t['tcId']):(g,t) for g in j['testGroups'] if g['parameterSet']=='ML-DSA-65' for t in g['tests']}
kg,sg,sv=load('keyGen'),load('sigGen'),load('sigVer')
L=[''';; mldsa.native-gate -- FIPS 204 ML-DSA-65 known answers from the NIST ACVP-Server
;; vectors (gen-val/json-files/ML-DSA-*-FIPS204, commit 975de31e), run by a loaderless
;; static image built from ../gov.nist.sha3/kotoba/sha3/core.kotoba and
;; kotoba/mldsa/core.kotoba (README "Native gate" composes the three bodies; JUN-352 P1b).
;;
;; main returns a bitmask, 31 is a pass:
;;   1 keyGen tc 26, 27: SHA3-256 of pk and of sk equal those of the ACVP values
;;   2 sigGen: pure deterministic (tg 3 tc 41), internal deterministic (tg 10 tc 147),
;;     pure hedged (tg 15 tc 214), external-mu hedged (tg 21 tc 301); SHA3-256 of
;;     the signature equals that of the ACVP signature
;;   4 sigVer: pure tg 3 tc 43 (valid) and 38 (modified hint); external-mu tg 9
;;     tc 121 (valid), 126 (modified z) and 129 (modified hint); internal tg 10
;;     tc 137 (modified hint); and two signatures under the keyGen tc 26 key made with an
;;     independent Python reference: one with two hint indices of a row swapped, and
;;     one that passes every check except ||z|| < gamma1 - beta
;;   8 the NTT table is 1753^BitRev8(i) mod q; keyGen / sign / verify round trip,
;;     and a changed message, context or signature byte does not verify
;;  16 wrong lengths, values outside 0..255 and a context over 255 bytes are refused
;; Long values are compared by SHA3-256 digest, so this gate relies on the SHA-3 gate.
(ns mldsa.native-gate
  (:export [main]))

(defn- g-nib [c :i64] :i64 (if (<= c 57) (- c 48) (- c 87)))
(defn- g-unhex [s :string] :vector-i64
  (let [b (vector-i64-from-bytes (string-to-utf8 s)) n (quot (vector-count b) 2)]
    (loop [i 0 out (vector-alloc n)]
      (if (= i n) out
        (recur (+ i 1) (vector-assoc! out i (+ (* 16 (g-nib (vector-at b (* 2 i)))) (g-nib (vector-at b (+ (* 2 i) 1))))))))))
(defn- g-digest [v :vector-i64] :string (hex (sha3-256 v)))
(defn- g-slice [v :vector-i64 start :i64 n :i64] :vector-i64
  (loop [i 0 out (vector-alloc n)] (if (= i n) out (recur (+ i 1) (vector-assoc! out i (vector-at v (+ start i)))))))
(defn- g-set [v :vector-i64 at :i64 x :i64] :vector-i64
  (let [out (g-slice v 0 (vector-count v))] (vector-assoc! out at x)))
(defn- g-empty? [v :vector-i64] :bool (= (vector-count v) 0))
(defn- g-zero32 [] :vector-i64 (loop [i 0 out (vector-alloc 32)] (if (= i 32) out (recur (+ i 1) (vector-assoc! out i 0)))))
''']
def s(name,h): L.append(f'(defn- {name} [] :string "{h.lower()}")')
for tc in (26,27):
    g,t=kg[(2,tc)]; s(f'g-kg{tc}-seed',t['seed']); s(f'g-kg{tc}-hpk',H(t['pk'])); s(f'g-kg{tc}-hsk',H(t['sk']))
for tg,tc in ((3,41),(10,147),(15,214),(21,301)):
    g,t=sg[(tg,tc)]; p=f'g-sg{tc}'
    s(p+'-sk',t['sk']); s(p+'-hsig',H(t['signature']))
    if 'rnd' in t: s(p+'-rnd',t['rnd'])
    if 'message' in t: s(p+'-m',t['message'])
    if 'context' in t: s(p+'-ctx',t['context'])
    if 'mu' in t: s(p+'-mu',t['mu'])
exp={}
for tg,tc in ((3,43),(3,38),(9,121),(9,126),(9,129),(10,137)):
    g,t=sv[(tg,tc)]; p=f'g-sv{tc}'; exp[tc]=t['testPassed']
    s(p+'-pk',t['pk']); s(p+'-sig',t['signature'])
    if 'message' in t: s(p+'-m',t['message'])
    if 'context' in t: s(p+'-ctx',t['context'])
    if 'mu' in t: s(p+'-mu',t['mu'])
c=CRAFTED
s('g-cr-mu',c['mu']); s('g-cr-order',c['hint_order']); s('g-cr-zover',c['z_over'])
assert exp=={43:True,38:False,121:True,126:False,129:False,137:False}, exp
L.append('''
(defn- g-keygen-one [seed :string hpk :string hsk :string] :bool
  (let [out (keygen (g-unhex seed))]
    (and (= (vector-count out) 5984) (= (g-digest (g-slice out 0 1952)) hpk) (= (g-digest (g-slice out 1952 4032)) hsk))))
(defn- g-keygen [] :bool
  (and (g-keygen-one (g-kg26-seed) (g-kg26-hpk) (g-kg26-hsk))
       (g-keygen-one (g-kg27-seed) (g-kg27-hpk) (g-kg27-hsk))))

(defn- g-siggen [] :bool
  (and (= (g-digest (sign (g-unhex (g-sg41-sk)) (g-unhex (g-sg41-m)) (g-unhex (g-sg41-ctx)) (g-zero32))) (g-sg41-hsig))
       (= (g-digest (sign-internal (g-unhex (g-sg147-sk)) (g-unhex (g-sg147-m)) (g-zero32))) (g-sg147-hsig))
       (= (g-digest (sign (g-unhex (g-sg214-sk)) (g-unhex (g-sg214-m)) (g-unhex (g-sg214-ctx)) (g-unhex (g-sg214-rnd)))) (g-sg214-hsig))
       (= (g-digest (sign-mu (g-unhex (g-sg301-sk)) (g-unhex (g-sg301-mu)) (g-unhex (g-sg301-rnd)))) (g-sg301-hsig))))

(defn- g-sigver [] :bool
  (and (verify (g-unhex (g-sv43-pk)) (g-unhex (g-sv43-m)) (g-unhex (g-sv43-ctx)) (g-unhex (g-sv43-sig)))
       (not (verify (g-unhex (g-sv38-pk)) (g-unhex (g-sv38-m)) (g-unhex (g-sv38-ctx)) (g-unhex (g-sv38-sig))))
       (verify-mu (g-unhex (g-sv121-pk)) (g-unhex (g-sv121-mu)) (g-unhex (g-sv121-sig)))
       (not (verify-mu (g-unhex (g-sv126-pk)) (g-unhex (g-sv126-mu)) (g-unhex (g-sv126-sig))))
       (not (verify-mu (g-unhex (g-sv129-pk)) (g-unhex (g-sv129-mu)) (g-unhex (g-sv129-sig))))
       (not (verify-internal (g-unhex (g-sv137-pk)) (g-unhex (g-sv137-m)) (g-unhex (g-sv137-sig))))
       (let [pk (g-slice (keygen (g-unhex (g-kg26-seed))) 0 1952) mu (g-unhex (g-cr-mu))]
         (and (not (verify-mu pk mu (g-unhex (g-cr-order)))) (not (verify-mu pk mu (g-unhex (g-cr-zover))))))))

(defn- g-br8 [i :i64] :i64
  (loop [k 0 x i r 0] (if (= k 8) r (recur (+ k 1) (quot x 2) (+ (* 2 r) (rem x 2))))))
(defn- g-pow1753 [e :i64] :i64
  (loop [k 0 r 1] (if (= k e) r (recur (+ k 1) (rem (* r 1753) 8380417)))))
(defn- g-round-trip [] :bool
  (let [kp (keygen (g-unhex (g-kg26-seed))) pk (g-slice kp 0 1952) sk (g-slice kp 1952 4032)
        m (g-unhex (g-sv43-m)) ctx (g-unhex (g-sv43-ctx)) rnd (g-unhex (g-sg214-rnd))
        sig (sign sk m ctx rnd)]
    (and (= (vector-count sig) 3309) (verify pk m ctx sig)
         (= (g-digest (sign sk m ctx rnd)) (g-digest sig))
         (not (verify pk (g-set m 3 (bit-xor (vector-at m 3) 1)) ctx sig))
         (not (verify pk m (g-set ctx 0 (bit-xor (vector-at ctx 0) 1)) sig))
         (not (verify pk m ctx (g-set sig 10 (bit-xor (vector-at sig 10) 1))))
         (not (verify pk m ctx (g-set sig 1000 (bit-xor (vector-at sig 1000) 1))))
         (verify-internal pk (g-unhex (g-sv43-m)) (sign-internal sk (g-unhex (g-sv43-m)) rnd)))))
(defn- g-tables [] :bool
  (and (loop [i 0] (if (= i 256) true (if (= (vector-at (zetas) i) (g-pow1753 (g-br8 i))) (recur (+ i 1)) false)))
       (g-round-trip)))

(defn- g-refusals [] :bool
  (let [seed (g-unhex (g-kg26-seed)) sk (g-unhex (g-sg41-sk)) m (g-unhex (g-sg41-m)) ctx (g-unhex (g-sg41-ctx))
        pk (g-unhex (g-sv43-pk)) sig (g-unhex (g-sv43-sig)) vm (g-unhex (g-sv43-m)) vctx (g-unhex (g-sv43-ctx))
        long-ctx (loop [i 0 out (vector-alloc 256)] (if (= i 256) out (recur (+ i 1) (vector-assoc! out i 7))))]
    (and (g-empty? (keygen (g-slice seed 0 31))) (g-empty? (keygen (g-set seed 0 256)))
         (g-empty? (sign (g-slice sk 0 4031) m ctx (g-zero32)))
         (g-empty? (sign sk m long-ctx (g-zero32)))
         (g-empty? (sign sk m ctx (g-slice (g-zero32) 0 31)))
         (g-empty? (sign sk (g-set m 0 -1) ctx (g-zero32)))
         (not (verify (g-slice pk 0 1951) vm vctx sig))
         (not (verify pk vm vctx (g-slice sig 0 3308)))
         (not (verify pk vm long-ctx sig))
         (verify pk vm vctx sig))))

(defn main [] :i64
  (+ (if (g-keygen) 1 0) (if (g-siggen) 2 0) (if (g-sigver) 4 0) (if (g-tables) 8 0) (if (g-refusals) 16 0)))
''')
open(OUT,'w').write('\n'.join(L))
