#!/usr/bin/env python3
"""Write kotoba/noise/native_gate.kotoba from the Cacophony vectors.

Dev tool, not part of the library. Standard library only.

    python3 -I tools/gen_native_gate.py kotoba/noise/native_gate.kotoba

test/noise/cacophony_vectors.edn holds the official Noise known answers (from
centromere/cacophony, the set snow and other implementations test against). This
takes the three 25519_ChaChaPoly_SHA256 vectors (NN, XX, IK). Each fixes both sides'
static and ephemeral keys, so every ciphertext is reproducible byte for byte.
Messages alternate senders from the initiator, through the handshake and on into
transport. Bytes are vector literals of at most 64 items; there are no strings.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(os.path.dirname(HERE), 'test', 'noise', 'cacophony_vectors.edn')).read()
h = bytes.fromhex

def vector(name):
    i = t.index(f'"{name}"')
    s = t.rfind('{:protocol-name', 0, i)
    e = t.find('{:protocol-name', i)
    blk = t[s:e if e > 0 else len(t)]
    field = lambda k: (re.search(rf':{k} "([0-9a-f]*)"', blk) or [None, None])[1]
    msgs = re.findall(r'\{:payload "([0-9a-f]*)"\s*:ciphertext "([0-9a-f]*)"\}', blk)
    return dict(prologue=field('init-prologue'), init_static=field('init-static'), init_eph=field('init-ephemeral'),
                resp_static=field('resp-static'), resp_eph=field('resp-ephemeral'), init_rs=field('init-remote-static'),
                hh=field('handshake-hash'), msgs=msgs)

PATTERNS = [('nn', 0, 2), ('xx', 1, 3), ('ik', 2, 2), ('ikb', 4, 2)]
def lit(b):
    b = list(b)
    if not b:
        return '(vector-i64)'
    parts = [f'(vector-i64 {" ".join(map(str, b[i:i + 64]))})' for i in range(0, len(b), 64)]
    while len(parts) > 1:
        parts = [f'(cat {parts[i]} {parts[i + 1]})' if i + 1 < len(parts) else parts[i] for i in range(0, len(parts), 2)]
    return parts[0]

defs, groups = [], []
for name, code, hs_count in PATTERNS:
    v = vector('Noise_IK_25519_ChaChaPoly_BLAKE2s' if code == 4 else f'Noise_{name.upper()}_25519_ChaChaPoly_SHA256')
    assert v['msgs'] and v['hh'] and len(v['prologue']) > 0
    for k in ('prologue', 'init_static', 'init_eph', 'resp_static', 'resp_eph', 'hh'):
        if v[k]:
            defs.append(f'(defn- g-{name}-{k.replace("_", "-")} [] :vector-i64 {lit(h(v[k]))})')
    for j, (p, c) in enumerate(v['msgs']):
        defs.append(f'(defn- g-{name}-p{j} [] :vector-i64 {lit(h(p))})')
        defs.append(f'(defn- g-{name}-c{j} [] :vector-i64 {lit(h(c))})')
    for side in ('i', 'r'):
        init = side == 'i'
        s = f'(g-{name}-init-static)' if init else f'(g-{name}-resp-static)'
        if name == 'nn':
            s = '(vector-i64)'
        e = f'(g-{name}-init-eph)' if init else f'(g-{name}-resp-eph)'
        rs = '(vector-i64)'
        if code in (2, 4) and init:
            # the initiator knows the responder's static public key (derived from its private key)
            rs = f'(x/public-key (g-{name}-resp-static))'
        binds = [f'st0 (n/initialize {code} {"true" if init else "false"} {s} {e} {rs} (g-{name}-prologue))',
                 f'bad-turn (g-empty? ({"n/read-message" if init else "n/write-message"} st0 (g-{name}-c0)))']
        hs_ok, tr_ok, tamper = [], [], None
        for j in range(len(v['msgs'])):
            mine = (j % 2 == 0) == init
            hs = j < hs_count
            if mine:
                op = 'n/write-message' if hs else 'n/transport-encrypt'
                binds.append(f'o{j} ({op} st{j} (g-{name}-p{j}))')
                check = f'(same? (g-tail o{j}) (g-{name}-c{j}))'
            else:
                op = 'n/read-message' if hs else 'n/transport-decrypt'
                binds.append(f'o{j} ({op} st{j} (g-{name}-c{j}))')
                check = f'(same? (g-tail o{j}) (g-{name}-p{j}))'
                # the first message of NN and XX travels before any key exists and is not
                # authenticated (Noise section 7), so tampering is tested on the first
                # received message that is encrypted
                if tamper is None and (j > 0 or code in (2, 4)):
                    tamper = f'(g-empty? ({op} st{j} (g-flip (g-{name}-c{j}) (- (vector-count (g-{name}-c{j})) 1))))'
            binds.append(f'st{j + 1} (g-head o{j})')
            (hs_ok if hs else tr_ok).append(f'(= (vector-count o{j}) (+ (n/state-size) (vector-count {"(g-%s-c%d)" % (name, j) if mine else "(g-%s-p%d)" % (name, j)}))) {check}')
        body = (f'(defn group-{name}-{side} [] :i64\n  (let [' + '\n        '.join(binds) + ']\n'
                f'    (+ (if (and {" ".join(hs_ok)}) 1 0)\n'
                f'       (if (same? (n/handshake-hash st{hs_count}) (g-{name}-hh)) 2 0)\n'
                f'       (if (and {" ".join(tr_ok) if tr_ok else "true"}) 4 0)\n'
                f'       (if {tamper} 8 0)\n'
                f'       (if bad-turn 16 0))))')
        groups.append((f'{name}-{side}', body))

src = f''';; noise.native-gate -- Cacophony known answers for the native Noise
;; (NN / XX / IK SHA256 and IK BLAKE2s, AWAI-102 / JUN-757). Generated by
;; tools/gen_native_gate.py from test/noise/cacophony_vectors.edn. Each group replays
;; one pattern from one side: it writes / encrypts that side's messages and compares
;; the published ciphertext, and reads / decrypts the peer's and compares the payload.
;; Every group returns 31: 1 the handshake messages, 2 the handshake hash, 4 the
;; transport messages, 8 a changed byte in the first received encrypted message is
;; refused (the first NN / XX message is sent before any key and is not authenticated),
;; 16 a message out of turn is refused. Bytes are vector literals.
(ns noise.native-gate
  (:require [noise.native :as n] [x25519.core :as x])
  (:export [{" ".join("group-" + g for g, _ in groups)}]))

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
  (let [out (g-slice v 0 (vector-count v))] (vector-assoc! out at (bit-xor (vector-at out at) 1))))
(defn- same? [p :vector-i64 q :vector-i64] :bool
  (and (= (vector-count p) (vector-count q))
       (loop [i 0] (if (= i (vector-count p)) true (if (= (vector-at p i) (vector-at q i)) (recur (+ i 1)) false)))))
(defn- g-empty? [v :vector-i64] :bool (= (vector-count v) 0))

{chr(10).join(defs)}

{(chr(10) + chr(10)).join(b for _, b in groups)}
'''
open(sys.argv[1], 'w').write(src)
print('groups', [g for g, _ in groups])
