#!/usr/bin/env python3
"""Write kotoba/noise/xxhfs_gate.kotoba: known answers for the native XXhfs handshake.

Dev tool, not part of the library. Python standard library plus `openssl` 4.x.

    python3 -I tools/gen_xxhfs_gate.py kotoba/noise/xxhfs_gate.kotoba

No published vectors exist for Noise_XXhfs_25519+MLKEM768_ChaChaPoly_SHA256, so the
expected bytes come from tools/xxhfs_reference.py, an independent Python Noise that uses
OpenSSL for ML-KEM-768. Its classical path is first required to reproduce the Cacophony
XX vector (test/noise/cacophony_vectors.edn) byte for byte. The XXhfs run reuses that
vector's X25519 keys, prologue and payloads, with fixed public-test KEM seeds, so only
the hfs tokens differ. Bytes are vector literals; there are no strings.
"""
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('xxhfs_reference', os.path.join(HERE, 'xxhfs_reference.py'))
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)

t = open(os.path.join(os.path.dirname(HERE), 'test', 'noise', 'cacophony_vectors.edn')).read()
i = t.index('"Noise_XX_25519_ChaChaPoly_SHA256"')
s = t.rfind('{:protocol-name', 0, i); e = t.find('{:protocol-name', i)
blk = t[s:e if e > 0 else len(t)]
f = lambda k: re.search(rf':{k} "([0-9a-f]*)"', blk)[1]
vec = dict(prologue=f('init-prologue'), **{'is': f('init-static'), 'ie': f('init-ephemeral'),
           'rs': f('resp-static'), 're': f('resp-ephemeral')}, hh=f('handshake-hash'),
           msgs=re.findall(r'\{:payload "([0-9a-f]*)"\s*:ciphertext "([0-9a-f]*)"\}', blk))
R.self_check(vec)  # the oracle's classical path matches Cacophony XX

h = bytes.fromhex
keys = dict(prologue=h(vec['prologue']), **{k: h(vec[k]) for k in ('is', 'ie', 'rs', 're')})
payloads = [h(p) for p, _ in vec['msgs'][:5]]
DZ = bytes((3 * i + 1) % 256 for i in range(64))   # initiator's e1 keyGen seed d || z
M = bytes((5 * i + 7) % 256 for i in range(32))    # responder's ekem1 encapsulation m
kem = R.MLKEM(R.workdir())
msgs, hh = R.run('XXhfs', keys, payloads, kem, kem_init=(DZ, None), kem_resp=(None, M))
assert len(msgs[0]) == 32 + 1184 + len(payloads[0])  # e and e1 travel in clear
assert len(msgs[1]) == 32 + (1088 + 16) + (32 + 16) + len(payloads[1]) + 16

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
         ('dz', DZ), ('m', M), ('hh', hh)] + [(f'p{j}', p) for j, p in enumerate(payloads)] + [(f'c{j}', c) for j, c in enumerate(msgs)]]

def group(side):
    init = side == 'i'
    b = [f'st0 (n/set-kem (n/initialize 3 {"true" if init else "false"} {"(g-is)" if init else "(g-rs)"} '
         f'{"(g-ie)" if init else "(g-re)"} (vector-i64) (g-prologue)) {"(g-dz) (vector-i64)" if init else "(vector-i64) (g-m)"})',
         f'bad-turn (g-empty? ({"n/read-message" if init else "n/write-message"} st0 (g-c0)))',
         # the KEM token refuses without its input: same side, no set-kem
         f'no-kem (g-empty? ({"n/write-message" if init else "n/read-message"} '
         f'(n/initialize 3 {"true" if init else "false"} {"(g-is)" if init else "(g-rs)"} {"(g-ie)" if init else "(g-re)"} (vector-i64) (g-prologue)) '
         f'{"(g-p0)" if init else "(g-c0)"}))' if init else
         f'no-kem (g-empty? (n/write-message (g-head (n/read-message (n/initialize 3 false (g-rs) (g-re) (vector-i64) (g-prologue)) (g-c0))) (g-p1)))']
    hs, tr, tamper = [], [], None
    for j in range(len(msgs)):
        mine = (j % 2 == 0) == init
        op = ('n/write-message' if j < 3 else 'n/transport-encrypt') if mine else ('n/read-message' if j < 3 else 'n/transport-decrypt')
        b.append(f'o{j} ({op} st{j} {"(g-p%d)" % j if mine else "(g-c%d)" % j})')
        b.append(f'st{j + 1} (g-head o{j})')
        want = f'(g-c{j})' if mine else f'(g-p{j})'
        (hs if j < 3 else tr).append(f'(same? (g-tail o{j}) {want})')
        if not mine and tamper is None and j > 0:
            tamper = f'(g-empty? ({op} st{j} (g-flip (g-c{j}) 40)))'
    return (f'(defn group-{side} [] :i64\n  (let [' + '\n        '.join(b) + ']\n'
            f'    (+ (if (and {" ".join(hs)}) 1 0)\n'
            f'       (if (same? (n/handshake-hash st3) (g-hh)) 2 0)\n'
            f'       (if (and {" ".join(tr)}) 4 0)\n'
            f'       (if {tamper} 8 0)\n'
            f'       (if bad-turn 16 0)\n'
            f'       (if no-kem 32 0))))')

src = f''';; noise.xxhfs-gate -- known answers for the native Noise_XXhfs_25519+MLKEM768_ChaChaPoly_SHA256
;; (AWAI-102, docs/ADR-0001). Generated by tools/gen_xxhfs_gate.py from
;; tools/xxhfs_reference.py, an independent Python Noise with OpenSSL ML-KEM-768 whose
;; classical path reproduces the Cacophony XX vector first. Each group replays the
;; handshake and two transport messages from one side. Both groups return 63: 1 the
;; handshake messages, 2 the handshake hash, 4 the transport messages, 8 a changed byte
;; in the first received encrypted message is refused (byte 40 lies in ekem1 or s),
;; 16 a message out of turn is refused, 32 a KEM token without its input is refused.
(ns noise.xxhfs-gate
  (:require [noise.native :as n])
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
  (let [out (g-slice v 0 (vector-count v))] (vector-assoc! out at (bit-xor (vector-at out at) 1))))
(defn- same? [p :vector-i64 q :vector-i64] :bool
  (and (= (vector-count p) (vector-count q))
       (loop [i 0] (if (= i (vector-count p)) true (if (= (vector-at p i) (vector-at q i)) (recur (+ i 1)) false)))))
(defn- g-empty? [v :vector-i64] :bool (= (vector-count v) 0))

{chr(10).join(defs)}

{group('i')}

{group('r')}
'''
open(sys.argv[1], 'w').write(src)
print('messages', [len(m) for m in msgs], 'hh', hh.hex()[:16])
