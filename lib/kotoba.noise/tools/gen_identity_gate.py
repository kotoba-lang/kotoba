#!/usr/bin/env python3
"""Write kotoba/noise/identity_gate.kotoba: the XXhfs handshake with ADR-0001 identities.

Dev tool, not part of the library. Python standard library plus `openssl` 4.x.

    python3 -I tools/gen_identity_gate.py kotoba/noise/identity_gate.kotoba

The handshake is the one tools/gen_xxhfs_gate.py uses (Cacophony XX keys, prologue and
payloads; fixed public-test KEM seeds). Messages 2 and 3 carry identity payloads:
Ed25519 public ++ ML-DSA-65 public ++ both signatures over
"kotoba-noise-pq-identity/v1\\n" ++ h, where h is the handshake hash after that message's
tokens. The expected bytes come from tools/xxhfs_reference.py: Ed25519 through OpenSSL,
which reproduces RFC 8032 test 1 here first, and ML-DSA-65 through
../gov.nist.mlDsa/tools/reference.py, which passed the ACVP groups. The identity seeds
are public test values and must never become operational keys. Bytes are vector
literals; there are no strings.
"""
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('xxhfs_reference', os.path.join(HERE, 'xxhfs_reference.py'))
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
h = bytes.fromhex

t = open(os.path.join(os.path.dirname(HERE), 'test', 'noise', 'cacophony_vectors.edn')).read()
i = t.index('"Noise_XX_25519_ChaChaPoly_SHA256"')
s = t.rfind('{:protocol-name', 0, i); e = t.find('{:protocol-name', i)
blk = t[s:e if e > 0 else len(t)]
f = lambda k: re.search(rf':{k} "([0-9a-f]*)"', blk)[1]
vec = dict(prologue=f('init-prologue'), **{'is': f('init-static'), 'ie': f('init-ephemeral'),
           'rs': f('resp-static'), 're': f('resp-ephemeral')}, hh=f('handshake-hash'),
           msgs=re.findall(r'\{:payload "([0-9a-f]*)"\s*:ciphertext "([0-9a-f]*)"\}', blk))
R.self_check(vec)
w = R.workdir()
pub, sig = R.ed25519(w, h('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60'), b'')
assert pub.hex() == 'd75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a'
assert sig.hex().startswith('e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155')

keys = dict(prologue=h(vec['prologue']), **{k: h(vec[k]) for k in ('is', 'ie', 'rs', 're')})
base = [h(p) for p, _ in vec['msgs'][:5]]
DZ = bytes((3 * i + 1) % 256 for i in range(64)); M = bytes((5 * i + 7) % 256 for i in range(32))
ID = {'i': (bytes((11 * i + 2) % 256 for i in range(32)), bytes((13 * i + 4) % 256 for i in range(32))),
      'r': (bytes((17 * i + 6) % 256 for i in range(32)), bytes((19 * i + 8) % 256 for i in range(32)))}
want = {}
for side, (eds, xi) in ID.items():
    want[side] = R.identity_payload(w, eds, xi, bytes(32))[:1984]
payloads = [base[0], lambda hh: R.identity_payload(w, *ID['r'], hh), lambda hh: R.identity_payload(w, *ID['i'], hh), base[3], base[4]]
kem = R.MLKEM(w)
msgs, hh = R.run('XXhfs', keys, payloads, kem, kem_init=(DZ, None), kem_resp=(None, M))

def lit(b):
    b = list(b)
    if not b:
        return '(vector-i64)'
    parts = [f'(vector-i64 {" ".join(map(str, b[i:i + 64]))})' for i in range(0, len(b), 64)]
    while len(parts) > 1:
        parts = [f'(cat {parts[i]} {parts[i + 1]})' if i + 1 < len(parts) else parts[i] for i in range(0, len(parts), 2)]
    return parts[0]

defs = [f'(defn- g-{n} [] :vector-i64 {lit(b)})' for n, b in
        [('prologue', keys['prologue']), ('is', keys['is']), ('ie', keys['ie']), ('rs', keys['rs']), ('re', keys['re']),
         ('dz', DZ), ('m', M), ('hh', hh), ('p0', base[0]), ('p3', base[3]), ('p4', base[4]),
         ('id-i-ed', ID['i'][0]), ('id-i-xi', ID['i'][1]), ('id-r-ed', ID['r'][0]), ('id-r-xi', ID['r'][1]),
         ('want-i', want['i']), ('want-r', want['r'])] + [(f'c{j}', c) for j, c in enumerate(msgs)]]

def group(side):
    init = side == 'i'
    me, peer = side, ('r' if init else 'i')
    b = [f'st0 (n/set-kem (n/initialize 3 {"true" if init else "false"} {"(g-is)" if init else "(g-rs)"} '
         f'{"(g-ie)" if init else "(g-re)"} (vector-i64) (g-prologue)) {"(g-dz) (vector-i64)" if init else "(vector-i64) (g-m)"})']
    hs, peer_ok, wrong, tamper, tamper_ed = [], None, None, None, None
    for j in range(5):
        mine = (j % 2 == 0) == init
        if j in (1, 2):   # identity messages
            if mine:
                b += [f't{j} (n/write-tokens st{j})',
                      f'pl{j} (id/payload (g-id-{me}-ed) (g-id-{me}-xi) (n/handshake-hash-now (g-head t{j})))',
                      f'o{j} (n/write-payload (g-head t{j}) (g-tail t{j}) pl{j})']
                hs.append(f'(same? (g-tail o{j}) (g-c{j}))')
            else:
                b += [f't{j} (n/read-tokens st{j} (g-c{j}))',
                      f'h{j} (n/handshake-hash-now (g-head t{j}))',
                      f'o{j} (n/read-payload (g-head t{j}) (g-tail t{j}))']
                peer_ok = f'(id/verify-payload (g-tail o{j}) h{j} (g-want-{peer}))'
                wrong = f'(not (id/verify-payload (g-tail o{j}) h{j} (g-want-{me})))'
                tamper = f'(not (id/verify-payload (g-flip (g-tail o{j}) 3000) h{j} (g-want-{peer})))'
                tamper_ed = f'(not (id/verify-payload (g-flip (g-tail o{j}) 2000) h{j} (g-want-{peer})))'
                hs.append(f'(= (vector-count (g-tail o{j})) (id/payload-size))')
        else:
            op = ('n/write-message' if j == 0 else 'n/transport-encrypt') if mine else ('n/read-message' if j == 0 else 'n/transport-decrypt')
            arg = (f'(g-p{j})' if mine else f'(g-c{j})')
            b.append(f'o{j} ({op} st{j} {arg})')
            if j == 0:
                hs.append(f'(same? (g-tail o0) {"(g-c0)" if mine else "(g-p0)"})')
        b.append(f'st{j + 1} (g-head o{j})')
    tr = [f'(same? (g-tail o3) {"(g-c3)" if (3 % 2 == 0) == init else "(g-p3)"})',
          f'(same? (g-tail o4) {"(g-c4)" if (4 % 2 == 0) == init else "(g-p4)"})']
    return (f'(defn group-{side} [] :i64\n  (let [' + '\n        '.join(b) + ']\n'
            f'    (+ (if (and {" ".join(hs)}) 1 0)\n'
            f'       (if (same? (n/handshake-hash st3) (g-hh)) 2 0)\n'
            f'       (if (and {" ".join(tr)}) 4 0)\n'
            f'       (if {peer_ok} 8 0)\n'
            f'       (if {wrong} 16 0)\n'
            f'       (if {tamper} 32 0)\n'
            f'       (if {tamper_ed} 64 0))))')

src = f''';; noise.identity-gate -- the native XXhfs handshake with ADR-0001 identity payloads
;; (AWAI-102). Generated by tools/gen_identity_gate.py from tools/xxhfs_reference.py
;; (OpenSSL Ed25519, the gov.nist.mlDsa Python reference, OpenSSL ML-KEM-768). Each side
;; signs its identity over h after its message's tokens (write-tokens, then
;; handshake-hash-now, then noise.identity/payload, then write-payload) and verifies
;; the peer's against the identity the host expects. Both groups return 127: 1 the
;; handshake messages byte for byte (signatures included), 2 the handshake hash, 4 the
;; transport messages, 8 the peer's identity verifies, 16 it is refused against a
;; different expected identity, 32 a changed ML-DSA-65 signature byte and 64 a changed
;; Ed25519 signature byte are refused (each signature is checked on its own).
;; The identity seeds are public test values, never operational keys.
(ns noise.identity-gate
  (:require [noise.native :as n] [noise.identity :as id])
  (:export [group-i group-r]))

(defn- cat [p :vector-i64 q :vector-i64] :vector-i64
  (let [np (vector-count p) out (vector-alloc (+ np (vector-count q)))]
    (loop [i 0] (if (= i (vector-count out)) out
      (let [z (vector-assoc! out i (if (< i np) (vector-at p i) (vector-at q (- i np))))] (recur (+ i 1)))))))
(defn- g-slice [v :vector-i64 start :i64 n :i64] :vector-i64
  (loop [i 0 out (vector-alloc n)] (if (= i n) out (recur (+ i 1) (vector-assoc! out i (vector-at v (+ start i)))))))
(defn- g-head [o :vector-i64] :vector-i64 (if (< (vector-count o) (n/state-size)) (vector-i64) (g-slice o 0 (n/state-size))))
(defn- g-tail [o :vector-i64] :vector-i64
  (if (< (vector-count o) (n/state-size)) (vector-i64 -1) (g-slice o (n/state-size) (- (vector-count o) (n/state-size)))))
(defn- g-flip [v :vector-i64 at :i64] :vector-i64
  (if (<= (vector-count v) at) v (let [out (g-slice v 0 (vector-count v))] (vector-assoc! out at (bit-xor (vector-at out at) 1)))))
(defn- same? [p :vector-i64 q :vector-i64] :bool
  (and (= (vector-count p) (vector-count q))
       (loop [i 0] (if (= i (vector-count p)) true (if (= (vector-at p i) (vector-at q i)) (recur (+ i 1)) false)))))

{chr(10).join(defs)}

{group('i')}

{group('r')}
'''
open(sys.argv[1], 'w').write(src)
print('messages', [len(m) for m in msgs])
