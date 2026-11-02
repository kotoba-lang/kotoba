#!/usr/bin/env python3
"""Compile/boot region crypto or an isolated UDP link under the OS ABI.

Mac observer/stager only. Amu discovers/compiles/packages all guest code;
QEMU executes the region implementation and native KAT/refusal assertions.
Python hashlib/HMAC supply independent public expected bytes, not language
execution or compilation. No physical deployment, identity or app admission.
"""
import argparse
import hashlib
import hmac
import importlib.util
import json
import os
import re
import socket
from pathlib import Path
import struct
import subprocess
import sys
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
OS_SCRIPTS=ROOT/'lib/kotoba.aiueos/os/aiueos/scripts'
MUTATIONS={
 'rotate':('(vp st b (rr (bit-xor (v st b) (v st c)) 7))','(vp st b (rr (bit-xor (v st b) (v st c)) 6))'),
 'final':('(if (= final 1)','(if (= final 0)'),
 'long-key':('(> (ld st 224) 64)','(> (ld st 224) 4096)'),
 'carry':('(put st 228 (+ (ld st 228) 1))','(put st 228 (ld st 228))'),
 'overflow':('(not (and (= (ld st 224) 4294967295) (= (ld st 228) 4294967295)))','true'),
 'phase':('(= (ld st 236) 1)','(or (= (ld st 236) 1) (= (ld st 236) 2))')}
APPLICATION_FRAME_MUTATIONS={
 'aj-count':('(and (>= count 0) (<= count 65536) (>= at 0) (< at end) (<= end count))','(and (>= count 0) (>= at 0) (< at end) (<= end count))'),
 'ac-alias':('(or (= al 0) (= bl 0) (<= (+ a al) b) (<= (+ b bl) a))','true'),
 'ac-version':('(= (natural work input count 1 1) 1)','(<= (natural work input count 1 1) 1)'),
 'ac-pad-bits':('(= (mod b 16) 0)','true'),
 'ac-utf16':('(<= units 160)','(<= units 164)'),
 'ac-wipe':('(clear work 0) ok','ok'),
 'ac-duplicate':('(not= (bit-and mask (i64-shift-left 1 (- kind 1))) 0)','false'),
 'ac-early-output':('(let [ok (admitted work input count)]','(let [ok (do (commit work output capacity 20 0) (admitted work input count))]')}
FRAME_MUTATIONS={
 'mf-keepalive':('(and (= kind 5) (not= bytes 1))','false'),
 'mf-body-offset':('(b io (+ 147457 at))','(b io (+ 147456 at))'),
 'mf-handshake-type':('(if (= (role owner) 1) 48 49)','(if (= (role owner) 1) 48 48)'),
 'mf-work-wipe':('(clear io 147456)','(clear io 147464)'),
 'mf-alias':('(or (<= (+ owner 262144) io) (<= (+ io 262144) owner))','true')}
CHACHA_MUTATIONS={
 'chacha-rotate':('(wp st b (rot (bit-xor (w st b) (w st c)) 7))','(wp st b (rot (bit-xor (w st b) (w st c)) 6))'),
 'chacha-clamp':('67108611','67108863'),
 'chacha-aad':('(do (o/poly-add st value) (aad-count st) 1)','(do (o/poly-add st 0) (aad-count st) 1)'),
 'chacha-padding':('(do (o/poly-add st 0) (pad st (- n 1)))','(do (o/poly-add st 1) (pad st (- n 1)))'),
 'chacha-tag':('(if (>= i 16) diff','(if (>= i 15) diff'),
 'chacha-alias':('(separate input n output capacity)','true'),
 'chacha-early-open':('(mac-end st input input-bytes (- n 16) (o/ld st 468))',
   '(mac-end st input input-bytes (- n 16) (o/ld st 468)) (o/put st 496 0) (o/put st 504 (- n 16)) (crypt st input input-bytes output capacity)'),
 'chacha-input-offset':('(kernel-load-u8-64k input input-bytes (+ (o/ld st 496) (o/ld st 468)))', '(kernel-load-u8-64k input input-bytes (o/ld st 496))'),
 'chacha-output-offset':('(kernel-store-u8-64k output capacity (+ (o/ld st 496) (o/ld st 472))', '(kernel-store-u8-64k output capacity (o/ld st 496)')}
X25519_MUTATIONS={
 'x25519-clamp':('(kernel-load-u8-4k scalar scalar-len 0) 248)', '(kernel-load-u8-4k scalar scalar-len 0) 255)'),
 'x25519-point-mask':('(kernel-load-u8-4k point point-len 31) 127)', '(kernel-load-u8-4k point point-len 31) 63)'),
 'x25519-a24':('(* 121665 (x-limb ws ws-len (x-s-ma) i))', '(* 121666 (x-limb ws ws-len (x-s-ma) i))'),
 'x25519-swap':('(bit-xor kt swap)', '0'),
 'x25519-invert':('(defn- x-inv-bit [t] (if (= t 2) 0 (if (= t 4) 0 1)))', '(defn- x-inv-bit [t] (if (= t 2) 1 (if (= t 4) 0 1)))'),
 'x25519-freeze':('(x-freeze-pass ws ws-len slot 0 (+ 19 (* 0 gate)))', '(x-freeze-pass ws ws-len slot 0 (+ 18 (* 0 gate)))'),
 'x25519-contributory':('(if (= (x-or-bytes out 32 0 (* 0 emitted)) 0) 0 1)', '(if (= (x-or-bytes out 32 0 (* 0 emitted)) 0) 1 1)')}
IK_MUTATIONS={
 'ik-name':('30 69 31 50 115)', '30 69 31 50 114)'),
 'ik-hkdf':('(h/hmac-update-byte (kernel-subregion st 4096 1280 512) 512 2)', '(h/hmac-update-byte (kernel-subregion st 4096 1280 512) 512 3)'),
 'ik-peer':('(or (= (ld st 32) 0) (= (peer-diff st 0 0) 0))', '(or (= (ld st 32) 0) (>= (peer-diff st 0 0) 0))'),
 'ik-premessage':('(if (= (ld st 4) 1) (mix-hash st st 4096 288 320) (mix-hash st st 4096 192 224))',
                  '(if (= (ld st 4) 1) (mix-hash st st 4096 192 224) (mix-hash st st 4096 192 224))'),
 'ik-es':('(if (and (= (dh-mix st 224 288) 1) (= (static-seal st) 1)', '(if (and (= (dh-mix st 160 288) 1) (= (static-seal st) 1)'),
 'ik-transaction':('(if (>= n 0) (commit st 0) 0)', '(commit st 0)'),
 'ik-nonce':('(put st 24 1) (put st 28 0) (put st 36 0)', '(put st 24 1) (put st 28 (ld st 28)) (put st 36 0)'),
 'ik-prefix':('(= (prefix-diff st input input-bytes 0 0) 0)', '(>= (prefix-diff st input input-bytes 0 0) 0)'),
 'ik-split':('(if (= (ld st 4) 1) (do (copy st 2336 352 32) (copy st 128 384 32))',
              '(if (= (ld st 4) 0) (do (copy st 2336 352 32) (copy st 128 384 32))')}
DATAGRAM_MUTATIONS={
 'dg-peer':('(= (peer-diff hs expected 0 0) 0)', '(>= (peer-diff hs expected 0 0) 0)'),
 'dg-aad':('(u64-shift-right counter (* i 8))', '(u64-shift-right 0 (* i 8))'),
 'dg-high-nonce':('(bit-and (u64-shift-right counter (* (- i 4) 8)) 255)', '(if (< i 8) (bit-and (u64-shift-right counter (* (- i 4) 8)) 255) 0)'),
 'dg-duplicate':('(not (= (ld st (+ 128 (* (mod number 2048) 8))) (+ number 1)))', '(not (> (ld st (+ 128 (* (mod number 2048) 8))) (+ number 1)))'),
 'dg-window':('(<= number (- (ld st 16) 2048))', '(< number (- (ld st 16) 2048))'),
 'dg-early-mark':('(do (cipher st 1 (- (ld st 48) 8) (counter input input-bytes))', '(do (put st (+ 128 (* (mod (counter input input-bytes) 2048) 8)) (+ (counter input input-bytes) 1)) (cipher st 1 (- (ld st 48) 8) (counter input input-bytes))'),
 'dg-send-counter':('(put st 8 (+ (ld st 8) 1))', '(put st 8 (+ (ld st 8) 2))'),
 'dg-send-clock':('(put st 8 (+ (ld st 8) 1)) (put st 32 now)', '(put st 8 (+ (ld st 8) 1)) (put st 32 (ld st 32))'),
 'dg-receive-clock':('(put st 40 (+ (ld st 40) 1)) (put st 32 now)', '(put st 40 (+ (ld st 40) 1)) (put st 32 (ld st 32))'),
 'dg-expiry':('(>= (- now (ld st 24)) 180)', '(> (- now (ld st 24)) 180)'),
 'dg-rekey':('(>= (- now (ld st 24)) 120)', '(> (- now (ld st 24)) 120)'),
 'dg-send-limit':('(>= (ld st 8) 9007199254740990)', '(> (ld st 8) 9007199254740990)'),
 'dg-receive-limit':('(>= (ld st 40) 9007199254740990)', '(> (ld st 40) 9007199254740990)'),
 'dg-wire-limit':('(< number 9007199254740990)', '(<= number 9007199254740990)'),
 'dg-state-alias':('(separate st 17408 input input-bytes)', 'true')}
KEKKAI_LINK_MUTATIONS={
 'kw-magic':('(= (b input capacity 0) 107)', '(>= (b input capacity 0) 0)'),
 'kw-version':('(= (b input capacity 1) 1)', '(>= (b input capacity 1) 0)'),
 'kw-duplicate':DATAGRAM_MUTATIONS['dg-duplicate']}
ED_MUTATIONS={
 'ed-message-tail':('(kernel-load-u8-64k message count i)', '(kernel-load-u8-64k message count (if (= i (- count 1)) 0 i))'),
 'ed-prefix':('(if (< i 32) (kernel-load-u8 signature 64 i) (kernel-load-u8 public 32 (- i 32)))', '(if (< i 32) (kernel-load-u8 public 32 i) (kernel-load-u8 signature 64 (- i 32)))'),
 'ed-order':('(if (= (e/prime-order-key (kernel-subregion work 16384 4096 1024) 1024\n                         (kernel-subregion work 16384 0 4096) 4096) 1)', '(if (>= (e/prime-order-key (kernel-subregion work 16384 4096 1024) 1024\n                         (kernel-subregion work 16384 0 4096) 4096) 0)'),
 'ed-wipe':('(if (>= i 16384)', '(if (>= i 16383)'),
 'ed-alias':('(separate work public 32)', 'true'),
 'es-overflow':('(< (stream-ld st 4224) 9223372036854775807)', '(<= (stream-ld st 4224) 9223372036854775807)'),
 'es-rotate':('(u64-shift-right x n)', '(u64-shift-right x (- n 1))'),
 'es-padding':('(do (stream-append st 0) (stream-padding st))', '(do (stream-append st 1) (stream-padding st))'),
 'es-high-length':('(u64-shift-right (stream-ld st 4224) 61)', '(u64-shift-right (stream-ld st 4224) 60)'),
 'es-phase':('(= (stream-ld st 4240) phase)', '(or (= (stream-ld st 4240) phase) (= (stream-ld st 4240) 2))'),
 'ee-scalar':('(and (= oks 1) (= un 1))', '(and (>= oks 0) (= un 1))')}
UDP_LINK_MUTATIONS={
 'udp-ip-checksum':('(= (sum frame capacity 14 (+ 14 header) 0) 65535)', '(>= (sum frame capacity 14 (+ 14 header) 0) 0)'),
 'udp-checksum':('(= (sum frame capacity (+ 14 header) (+ 14 total)\n                (+ (be frame capacity 26) (be frame capacity 28) (be frame capacity 30) (be frame capacity 32) 17 (- total header))) 65535)',
                 '(>= (sum frame capacity (+ 14 header) (+ 14 total)\n                (+ (be frame capacity 26) (be frame capacity 28) (be frame capacity 30) (be frame capacity 32) 17 (- total header))) 0)'),
 'udp-fragment':('(bit-and (be frame capacity 20) 49151)', '(bit-and (be frame capacity 20) 40959)')}

ENVELOPE_MUTATIONS={
 'env-authority':('(trusted work authority 0)', '(or (trusted work authority 0) true)'),
 'env-digest':('(digest-matches work input count 0)', '(or (digest-matches work input count 0) true)'),
 'env-signature':('(= (ed/verify', '(<= (ed/verify'),
 'env-duplicate':('(not= (bit-and (get work 80) flag) 0)', 'false'),
 'env-pad-bits':('(= (bit-and c 15) 0)', 'true'),
 'env-spki-pad-bits':('(= (bit-and d 3) 0)', 'true'),
 'env-wipe':('(if (>= i 98304)', '(if (>= i 98303)'),
 'env-alias':('(separate work 98304 input count)', 'true'),
 'env-sha-padding':('(>= (mod size 64) 56)', '(> (mod size 64) 56)'),
 'env-output-refusal':('(commit-payload work output capacity size 0) -1)', '(commit-payload work output capacity size 0) (do (if (> capacity 0) (kernel-store-u8-64k output capacity 0 0) 0) -1))')}

ROSTER_MUTATIONS={
 'rs-self-key':('(same-self-key owner config 0)', '(or (same-self-key owner config 0) true)'),
 'rs-version':('(< (k64 owner 8) (r64 owner 8))', '(and (< (k64 owner 8) (r64 owner 8)) false)'),
 'rs-same-version':('(same-digest owner 0)', '(or (same-digest owner 0) true)'),
 'rs-expiry':('(> (r64 owner (+ 512 (* peer 96) 32)) now)', '(>= (r64 owner (+ 512 (* peer 96) 32)) now)'),
 'rs-status':('(= (r owner (+ 512 (* peer 96) 48)) 1)', '(or (= (r owner (+ 512 (* peer 96) 48)) 1) true)'),
 'rs-self-status':('(= (r owner (+ 512 48)) 1)', '(or (= (r owner (+ 512 48)) 1) true)'),
 'rs-direction':('(if (= direction 0) 0 peer)', '(if (= direction 1) 0 peer)'),
 'rs-port':('(sequence-has (kernel-subregion owner 262144 0 32768) 32768 (r owner (+ record 16)) (r owner (+ record 20)) 5 cap cap-bytes port)', '(or (sequence-has (kernel-subregion owner 262144 0 32768) 32768 (r owner (+ record 16)) (r owner (+ record 20)) 5 cap cap-bytes port) true)'),
 'rs-wipe':('(zero owner 32768 65536) 1)))))', '(zero owner 65536 65536) 1)))))'),
 'rs-epoch':('(= epoch (r64 owner 24))', '(or (= epoch (r64 owner 24)) true)'),
 'rd-utf8':('(utf8 input count 0)', '(or (utf8 input count 0) true)'),
 'rd-duplicate':('(duplicate work input count (+ node 1) key)', '(and (duplicate work input count (+ node 1) key) false)'),
 'rd-overflow':('(if negative 8 7)', '(if negative 8 8)'),
 'rd-wipe':('(do (clear work 0) 0)', '(do (clear work 98304) 0)')}

SESSION_MUTATIONS={
 'ab-transcript':('(b owner (+ 58528 (- i 64)))', '(b owner (+ 58529 (- i 64)))'),
 'ab-generation':('(u64-shift-right (ld owner 32776) (* (- i 8) 8))', '(u64-shift-right (r/version owner 262144) (* (- i 8) 8))'),
 'ab-peer':('(b owner (+ 32832 (- i 24)))', '(b owner (+ 32833 (- i 24)))'),
 'ab-phase':('(= (poll owner 262144 now) 2)', '(>= (poll owner 262144 now) 0)'),
 'ms-self':('(self-match owner 0)', '(or (self-match owner 0) true)'),
 'ms-bind':('(initialize (kernel-subregion owner 262144 33280 8192) 8192 role 1)', '(initialize (kernel-subregion owner 262144 33280 8192) 8192 role 0)'),
 'ms-version':('(decimal owner (r/version owner 262144) 1000000000000000000 false)', '(decimal owner (do (r/version owner 262144) 0) 1000000000000000000 false)'),
 'ms-unicode':('(+ 240 (quot scalar 262144))', '(+ 241 (quot scalar 262144))'),
 'ms-timeout':('(< (- now (ld owner 32800)) 90)', '(<= (- now (ld owner 32800)) 90)'),
 'ms-lifetime':('(not= (d/advice (kernel-subregion owner 262144 41472 17408) 17408 now) 2)', '(or (not= (d/advice (kernel-subregion owner 262144 41472 17408) 17408 now) 2) true)'),
 'ms-ik-wipe':('(clear owner 33280 41472)', '(clear owner 41472 41472)'),
 'ms-stop':('(clear (kernel-subregion owner length 0 262144) 32768 65536)', '(clear (kernel-subregion owner length 0 262144) 65536 65536)'),
 'ms-start-active':('(= (poll owner length now) 0)', '(or (= (poll owner length now) 0) true)'),
 'ms-handshake-transaction':('(and (>= result 0) (= (handshake-commit owner now) 1))', '(and (= (handshake-commit owner now) 1) (>= result 0))'),
 'ms-datagram-transaction':('(if (>= result 0) (copy owner 41472 147456 17408 0) 0)', '(do (copy owner 41472 147456 17408 0) 0)'),
 'ms-early-output':('(if (>= count 0) (do (put owner 32808 now) (output-copy owner output capacity count 0)) 0)', '(if (>= count 0) (do (put owner 32808 now) (output-copy owner output capacity count 0)) (if (> capacity 0) (kernel-store-u8-64k output capacity 0 0) 0))'),
 'ms-output-alias':('(separate owner 262144 output capacity)', '(or (separate owner 262144 output capacity) true)'),
 'mr-wipe':('(zero owner 32768 65536) 1)))))', '(zero owner 65536 65536) 1)))))')}

def pin(path):
    raw=path.read_bytes();return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def x25519_vectors(state):
    owner=ROOT/'lib/org.ietf.x25519'
    corpus=owner/'test/wycheproof/x25519_test.json'
    reference=owner/'tools/reference.py';ref=load('os_x25519_reference',reference)
    state['vectorCorpus']=pin(corpus);state['reference']=pin(reference)
    h=bytes.fromhex;nine=bytes([9])+bytes(31)
    k1=h('a546e36bf0527c9d3b16154b82465edd62144c0ac1fc5a18506a2244ba449ac4')
    u1=h('e6db6867583030db3594c1a424b15f7c726624ec26b3353b10a903a6d0ab1c4c')
    k2=h('4b66e9d4d1b4673c5ad22691957d6af5c11b6421e0ea01d42ca4169e7918ba0d')
    u2=h('e5210f12786811d3f4b7959d0538ae2c31dbe7106fc03c3efc4cd549c715a493')
    alice=h('77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a')
    bob=h('5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb')
    ap=h('8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a')
    bp=h('de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f')
    shared=h('4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742')
    v1=h('c3da55379de9c6908e94ea4df28d084f32eccf03491c71f754b4075577a28552')
    rows=[(k1,u1,v1),(k2,u2,h('95cbde9476e8907d7aade45cb4b873f88b595a68799fa152e6f8f7647aac7957')),
          (alice,nine,ap),(bob,nine,bp),(alice,bp,shared),(bob,ap,shared),
          (nine,nine,h('422c8e7a6227d7bca1350b3e2bb7279f7897b87bb6854b783c60e80311ae3079')),
          (k1,u1[:31]+bytes([u1[31]|128]),v1),(k1,bytes(32),bytes(32)),
          (k1,h('e0eb7a7c3b41b8ae1656e3faf19fc46ada098deb9c32b1fd866205165f49b800'),bytes(32))]
    tests=json.loads(corpus.read_text())
    cases=[t for g in tests['testGroups'] for t in g['tests']]
    if tests['numberOfTests']!=518 or len(cases)!=518 or len({t['tcId'] for t in cases})!=518:
        raise ValueError('X25519 corpus count/IDs differ')
    rows.extend((h(t['private']),h(t['public']),h(t['shared'])) for t in cases)
    blob=bytearray(64+len(rows)*128);blob[:8]=b'X25519G1';struct.pack_into('<I',blob,8,len(rows))
    for i,(key,point,expected) in enumerate(rows):
        if not len(key)==len(point)==len(expected)==32 or ref.x25519(key,point)!=expected:
            raise ValueError('independent X25519 vector disagreement at '+str(i))
        at=64+i*128;blob[at:at+96]=key+point+expected
        struct.pack_into('<II',blob,at+96,i,int(expected!=bytes(32)))
    state['vectorCount']=len(rows);state['wycheproofCases']=len(cases)
    state['contributoryRefusals']=sum(expected==bytes(32) for _,_,expected in rows)
    return bytes(blob),b''.join(expected for _,_,expected in rows),struct.pack('<528I',*(int(v!=bytes(32)) for _,_,v in rows))

def check_chacha(words,raw,out,state):
    path=ROOT/'lib/org.ietf.chacha20Poly1305/tools/reference.py'
    reference=load('region_chacha_reference',path);state['reference']=pin(path)
    if reference.block(bytes(range(32)),1,bytes.fromhex('000000090000004a00000000')).hex()!=('10f1e7e4d13b5915500fdd1fa32071c4c7d1f4c733c068030422aa9ac3d46c4e'
      'd2826446079faa0914c2d705d98b02a2b5129cd1de164eb9cbd083e8a2503c4e'):raise ValueError('RFC block reference differs')
    rfckey=bytes.fromhex('85d6be7857556d337f4452fe42d506a80103808afb0db2fd4abff6af4149f51b')
    rfcmsg=b'Cryptographic Forum Research Group'
    if reference.poly1305(rfckey,rfcmsg).hex()!='a8061dc1305136c6c22b8baf0c0127a9':raise ValueError('RFC Poly1305 reference differs')
    key=bytes((i*3+7)%256 for i in range(32));nonce=bytes((i*5+11)%256 for i in range(32,56))
    plaintext=lambda n:bytes((i*17+3)%256 for i in range(n));aad=lambda n:bytes((i*11+5)%256 for i in range(n))
    frames=[]
    for size in [12,24]:
        for n in [1024,4096,16383,65511,65519]:
            frames.append((reference.seal if size==12 else reference.xseal)(key,nonce[:size],aad(8),plaintext(n)))
    for size in [12,24]:
        k=key if size==12 else reference.hchacha20(key,nonce[:16]);iv=nonce[:12] if size==12 else bytes(4)+nonce[16:]
        for counter in [0,1,2147483647,4294967295]:frames.append(reference.block(k,counter,iv))
    for variant in [0,1]:
        for n in range(258):frames.append(reference.poly1305(key if variant==0 else bytes([255])*32,plaintext(n)))
    frames.append(reference.poly1305(rfckey,rfcmsg))
    for size in [12,24]:
        for n in range(258):frames.append((reference.seal if size==12 else reference.xseal)(key,nonce[:size],aad((n*7)%65),plaintext(n)))
    if len(frames)!=1051:raise ValueError('reference case count differs')
    expected=b''.join(hashlib.blake2s(frame).digest() for frame in frames)
    (out/'expected-frame-hashes.bin').write_bytes(expected)
    mismatches=[i for i in range(1051) if raw[i*32:i*32+32]!=expected[i*32:i*32+32]]
    observed=dict(knownPoly1305Answer=words[0],nativeAssertionFailures=words[1],guardsCompleted=words[2],canary=words[3],frameHashCount=words[4],completed=words[5],mismatchedFrameHashes=mismatches)
    return observed,words==(1,0,1,1,1051,1) and not mismatches

def main(a):
    out=a.output.resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False)
    app_link=a.component=='application-link';app=a.component=='application-frame';frame=a.component=='frame';mlink=a.component=='managed-link' or app_link;chacha=a.component=='chacha';x25519=a.component=='x25519';ik=a.component=='ik';datagram=a.component=='datagram';ed=a.component=='ed25519';envelope=a.component=='envelope';roster=a.component=='roster';session=a.component=='session' or mlink or frame;klink=a.component=='kekkai-link';link=a.component=='udp-link' or klink or mlink;protocol=ik or datagram or klink;dual=chacha or x25519 or protocol or link or ed or envelope or roster or session or app
    namespace='aiueos.native.kekkai-link-gate' if klink else ('aiueos.native.udp-link-gate' if link else ('noise.datagram-region-gate' if datagram else ('noise.ik-region-gate' if ik else ('aiueos.native.x25519-region-gate' if x25519 else ('chacha20.region-gate' if chacha else 'noise.blake2s-region-gate')))))
    slug='kekkai-link' if klink else ('udp-link' if link else ('datagram' if datagram else ('ik' if ik else ('x25519' if x25519 else ('chacha20' if chacha else 'blake2s')))))
    mutations=KEKKAI_LINK_MUTATIONS if klink else (UDP_LINK_MUTATIONS if link else (DATAGRAM_MUTATIONS if datagram else (IK_MUTATIONS if ik else (X25519_MUTATIONS if x25519 else (CHACHA_MUTATIONS if chacha else MUTATIONS)))))
    if ed:namespace='aiueos.native.ed25519-region-gate';slug='ed25519';mutations=ED_MUTATIONS
    if envelope:namespace='kekkai.envelope-region-gate';slug='envelope';mutations=ENVELOPE_MUTATIONS
    if roster:namespace='kekkai.roster-region-gate';slug='roster';mutations=ROSTER_MUTATIONS
    if session:namespace='kekkai.session-region-gate';slug='session';mutations=SESSION_MUTATIONS
    if app:namespace='kekkai.application-frame-gate';slug='application-frame';mutations=APPLICATION_FRAME_MUTATIONS
    if frame:namespace='kekkai.frame-bounds-gate';slug='frame';mutations={}
    if mlink:namespace='kekkai.frame-link-gate';slug='managed-link';mutations=FRAME_MUTATIONS
    if app_link:namespace='kekkai.application-link-gate';slug='application-link';mutations={}
    if frame and a.session_suite not in ['handshake-responder','handshake-initiator','transport-responder','transport-initiator']:
        raise ValueError('frame component requires a maximum-size suite')
    if a.mutation and a.mutation not in mutations:raise ValueError('mutation/component differ')
    state=dict(schema='kekkai.os-region-'+slug+'.v1',state='STAGING',mutation=a.mutation,
               calls=[],physicalDeployment=False,appInstallQualified=False,
               productUserABIQualified=False,existingABIExportsRetained=True,
               observer=pin(Path(__file__)),pythonVersion=sys.version.split()[0])
    def save():(out/'receipt.json').write_text(json.dumps(state,indent=2)+'\n')
    save()
    try:
        sys.path.insert(0,str(OS_SCRIPTS))
        builder=load('region_kernel_builder',OS_SCRIPTS/'build-native-kernel-macos.py')
        a.compiler=a.compiler.resolve(strict=True)
        builder.verify_compiler(a.compiler,a.compiler_sha256)
        for name in ['packager','qemu','firmware']:
            path=getattr(a,name).resolve(strict=True);setattr(a,name,path)
            if pin(path)['sha256']!=getattr(a,name+'_sha256'):raise ValueError(name+' pin differs')
        baseline=a.source_stage.resolve(strict=True);lock=(baseline/'kernel.ksl').read_bytes()
        if hashlib.sha256(lock).hexdigest()!=a.source_lock_sha256:raise ValueError('baseline lock pin differs')
        state['compiler']=pin(a.compiler);state['baselineLockSHA256']=a.source_lock_sha256
        stage=out/'source';stage.mkdir();roots=[];entry=None
        if not lock.startswith(b'KSL1\n'):raise ValueError('baseline lock format')
        for line in lock.decode().splitlines()[1:]:
            kind,value=line.split(' ',1)
            if kind=='entry':entry=value
            elif kind=='root':roots.append(value)
            elif kind=='file':
                digest,virtual=value.split(' ',1);p=Path(virtual)
                if not p.is_absolute() or '..' in p.parts:raise ValueError('baseline path')
                raw=(baseline/virtual.lstrip('/')).read_bytes()
                if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('baseline source drift')
                target=stage/virtual.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
            else:raise ValueError('unknown lock record')
        if entry!='/os/aiueos/native/usb-update-test-entry.kotoba':raise ValueError('unexpected baseline entry')
        source=(stage/entry.lstrip('/')).read_text()
        before='''(defn main [] :i64
  ;; The root explicitly selects the image's private GOP/Browser profile.
  ;; PCI/GOP/font sealing happens before any Kotoba body receives a region.
  (let [width (kernel-framebuffer-width)
        registered (kernel-register-value-domain 73)
        published (kernel-publish-current-domain 73)
        enabled (kernel-value-enable-user)]
    (if (and (> width 0) (> registered 0) (= published 73) (= enabled 1))
      (fixture/run) 0)))'''
        for old,new in [
          ('aiueos.native.usb-update-test-entry','aiueos.native.kekkai-'+slug+'-region-entry'),
          ('[aiueos.native.usb-update-probe :as fixture]','['+namespace+' :as fixture]'),
          (before,'(defn main [] :i64\n  (fixture/run))')]:
            if source.count(old)!=1:raise ValueError('baseline entry changed')
            source=source.replace(old,new)
        entry='/os/aiueos/native/kekkai-'+slug+'-region-entry.kotoba'
        (stage/entry.lstrip('/')).write_text(source)
        core=ROOT/('lib/kotoba.kekkai/kotoba/kekkai/wire_region.kotoba' if klink else ('lib/kotoba.aiueos/os/aiueos/native/ipv4_udp.kotoba' if link else ('lib/kotoba.noise/kotoba/noise/datagram_region.kotoba' if datagram else ('lib/kotoba.noise/kotoba/noise/ik_region.kotoba' if ik else ('lib/kotoba.aiueos/os/aiueos/kotoba/x25519.kotoba' if x25519 else ('lib/org.ietf.chacha20Poly1305/kotoba/chacha20/region.kotoba' if chacha else 'lib/kotoba.noise/kotoba/noise/blake2s_region.kotoba'))))))
        fixture=ROOT/('lib/kotoba.aiueos/os/aiueos/native/kekkai_link_gate.kotoba' if klink else ('lib/kotoba.aiueos/os/aiueos/native/udp_link_gate.kotoba' if link else ('lib/kotoba.noise/tools/datagram_region_gate.kotoba' if datagram else ('lib/kotoba.noise/tools/ik_region_gate.kotoba' if ik else ('lib/kotoba.aiueos/os/aiueos/native/x25519_region_gate.kotoba' if x25519 else ('lib/org.ietf.chacha20Poly1305/tools/region_gate.kotoba' if chacha else 'lib/kotoba.noise/tools/blake2s_region_gate.kotoba'))))))
        if ed:core=ROOT/'lib/kotoba.aiueos/os/aiueos/kotoba/aiueos/ed25519_region.kotoba';fixture=ROOT/'lib/kotoba.aiueos/os/aiueos/native/ed25519_region_gate.kotoba'
        if envelope:core=ROOT/'lib/kotoba.kekkai/kotoba/kekkai/envelope_region.kotoba';fixture=ROOT/'lib/kotoba.kekkai/tools/envelope_region_gate.kotoba'
        if roster:core=ROOT/'lib/kotoba.kekkai/kotoba/kekkai/roster_region.kotoba';fixture=ROOT/'lib/kotoba.kekkai/tools/roster_region_gate.kotoba'
        if session:core=ROOT/'lib/kotoba.kekkai/kotoba/kekkai/session_region.kotoba';fixture=ROOT/'lib/kotoba.kekkai/tools/session_region_gate.kotoba'
        if mlink:core=ROOT/'lib/kotoba.kekkai/kotoba/kekkai/frame_region.kotoba';fixture=ROOT/'lib/kotoba.kekkai/tools/frame_link_gate.kotoba'
        if frame:core=ROOT/'lib/kotoba.kekkai/kotoba/kekkai/frame_region.kotoba';fixture=ROOT/'lib/kotoba.kekkai/tools/frame_bounds_gate.kotoba'
        if app:core=ROOT/'lib/kotoba.kekkai/kotoba/kekkai/application_frame_region.kotoba';fixture=ROOT/'lib/kotoba.kekkai/tools/application_frame_gate.kotoba'
        if app_link:core=ROOT/'lib/kotoba.kekkai/kotoba/kekkai/application_frame_region.kotoba';fixture=ROOT/'lib/kotoba.kekkai/tools/application_link_gate.kotoba'
        core_bytes=core.read_bytes();state['ownerSource']=pin(core);state['fixtureSource']=pin(fixture)
        if a.mutation and not (app and a.mutation.startswith('aj-')) and not chacha and not (klink and a.mutation=='kw-duplicate') and not (ed and a.mutation.startswith(('es-','ee-'))) and not (roster and a.mutation.startswith('rd-')) and not (session and a.mutation.startswith('mr-')):
            old,new=mutations[a.mutation];text=core_bytes.decode()
            if text.count(old)!=1:raise ValueError('mutation is not unique')
            core_bytes=text.replace(old,new).encode()
        files=([('kekkai/wire_region.kotoba',core_bytes),('aiueos/native/kekkai_link_gate.kotoba',fixture.read_bytes())] if klink else ([('aiueos/native/ipv4_udp.kotoba',core_bytes),('aiueos/native/udp_link_gate.kotoba',fixture.read_bytes())] if link else ([('noise/datagram_region.kotoba',core_bytes),('noise/datagram_region_gate.kotoba',fixture.read_bytes())] if datagram else ([('noise/ik_region.kotoba',core_bytes),('noise/ik_region_gate.kotoba',fixture.read_bytes())] if ik else ([('aiueos/x25519.kotoba',core_bytes),('aiueos/native/x25519_region_gate.kotoba',fixture.read_bytes())] if x25519 else
              ([('chacha20/region.kotoba',core_bytes),('chacha20/region_gate.kotoba',fixture.read_bytes())] if chacha else
               [('noise/blake2s_region.kotoba',core_bytes),('noise/blake2s_region_gate.kotoba',fixture.read_bytes())]))))))
        if ed:files=[('aiueos/ed25519_region.kotoba',core_bytes),('aiueos/native/ed25519_region_gate.kotoba',fixture.read_bytes())]
        if envelope:files=[('kekkai/envelope_region.kotoba',core_bytes),('kekkai/envelope_region_gate.kotoba',fixture.read_bytes())]
        if roster:files=[('kekkai/roster_region.kotoba',core_bytes),('kekkai/roster_region_gate.kotoba',fixture.read_bytes())]
        if session:files=[('kekkai/session_region.kotoba',core_bytes),('kekkai/session_region_gate.kotoba',fixture.read_bytes())]
        if mlink:files=[('kekkai/frame_region.kotoba',core_bytes),('kekkai/frame_link_gate.kotoba',fixture.read_bytes())]
        if frame:files=[('kekkai/frame_region.kotoba',core_bytes),('kekkai/frame_bounds_gate.kotoba',fixture.read_bytes())]
        if app:files=[('kekkai/application_frame_region.kotoba',core_bytes),('kekkai/application_frame_gate.kotoba',fixture.read_bytes())]
        if app_link:files=[('kekkai/application_frame_region.kotoba',core_bytes),('kekkai/application_link_gate.kotoba',fixture.read_bytes())]
        owner_root='/ed25519-owner' if ed else ('/link-owner' if link else ('/x25519-owner' if x25519 else ('/chacha-owner' if chacha else '/noise-owner')))
        if envelope:owner_root='/envelope-owner'
        if roster:owner_root='/roster-owner'
        if session:owner_root='/session-owner'
        if app:owner_root='/application-owner'
        for virtual,raw in files:
            target=stage/owner_root.lstrip('/')/virtual;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        if app:
            state['dependencySources']={}
            for virtual,relative in [('/json-owner/kotoba/json/region.kotoba','lib/kotoba.json/src/kotoba/json/region.kotoba'),('/edn-owner/kotoba/edn/region.kotoba','lib/kotoba.edn/src/kotoba/edn/region.kotoba'),('/noise-owner/noise/blake2s_region.kotoba','lib/kotoba.noise/kotoba/noise/blake2s_region.kotoba')]:
                dep=ROOT/relative;state['dependencySources'][relative]=pin(dep);raw=dep.read_bytes()
                if a.mutation and a.mutation.startswith('aj-') and relative=='lib/kotoba.json/src/kotoba/json/region.kotoba':
                    old,new=mutations[a.mutation];text=raw.decode()
                    if text.count(old)!=1:raise ValueError('JSON cursor mutation is not unique')
                    raw=text.replace(old,new).encode()
                target=stage/virtual.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
            roots+=['/json-owner','/edn-owner','/noise-owner']
        if session:
            state['dependencySources']={}
            dependencies=[('/roster-owner/kekkai/roster_region.kotoba','lib/kotoba.kekkai/kotoba/kekkai/roster_region.kotoba'),
                ('/roster-owner/kekkai/envelope_region.kotoba','lib/kotoba.kekkai/kotoba/kekkai/envelope_region.kotoba'),
                ('/edn-owner/kotoba/edn/region.kotoba','lib/kotoba.edn/src/kotoba/edn/region.kotoba'),
                ('/os/aiueos/native/legacy_crypto_kat.kotoba','lib/kotoba.aiueos/os/aiueos/native/legacy_crypto_kat.kotoba'),
                ('/x25519-owner/aiueos/x25519.kotoba','lib/kotoba.aiueos/os/aiueos/kotoba/x25519.kotoba')]
            if mlink or frame:
                dependencies += [('/session-owner/kekkai/'+name+'.kotoba','lib/kotoba.kekkai/'+folder+'/'+name+'.kotoba') for name,folder in [('session_region','kotoba/kekkai'),('wire_region','kotoba/kekkai'),('session_region_gate','tools')]]
            if app_link:
                dependencies += [('/session-owner/kekkai/frame_region.kotoba','lib/kotoba.kekkai/kotoba/kekkai/frame_region.kotoba'),('/json-owner/kotoba/json/region.kotoba','lib/kotoba.json/src/kotoba/json/region.kotoba')]
                roots.append('/json-owner')
            if mlink:
                dependencies.append(('/link-owner/aiueos/native/ipv4_udp.kotoba','lib/kotoba.aiueos/os/aiueos/native/ipv4_udp.kotoba'))
                roots.append('/link-owner')
            for name in ['ed25519','ed25519_verify','sha512','sha512_stream','gf25519','ed25519_region','lib/sha256_stream']:
                dependencies.append(('/os/aiueos/kotoba/aiueos/'+name+'.kotoba','lib/kotoba.aiueos/os/aiueos/kotoba/aiueos/'+name+'.kotoba'))
            for name in ['ik_region','datagram_region','blake2s_region']:
                dependencies.append(('/noise-owner/noise/'+name+'.kotoba','lib/kotoba.noise/kotoba/noise/'+name+'.kotoba'))
            for name in ['region','region_ops','aead_region']:
                dependencies.append(('/chacha-owner/chacha20/'+name+'.kotoba','lib/org.ietf.chacha20Poly1305/kotoba/chacha20/'+name+'.kotoba'))
            for virtual,relative in dependencies:
                dep=ROOT/relative;state['dependencySources'][relative]=pin(dep);raw=dep.read_bytes()
                if relative=='lib/kotoba.kekkai/kotoba/kekkai/roster_region.kotoba' and a.mutation and a.mutation.startswith('mr-'):
                    old,new=mutations[a.mutation];text=raw.decode()
                    if text.count(old)!=1:raise ValueError('managed roster mutation is not unique')
                    raw=text.replace(old,new).encode();state['mutationSource']=dict(name=relative,original=pin(dep),mutated=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
                target=stage/virtual.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
            roots+=['/roster-owner','/edn-owner','/x25519-owner','/noise-owner','/chacha-owner']
        if ed or envelope or roster:
            state['dependencySources']={}
            for name in ['ed25519','ed25519_verify','sha512','sha512_stream','gf25519']:
                dep=ROOT/('lib/kotoba.aiueos/os/aiueos/kotoba/aiueos/'+name+'.kotoba')
                state['dependencySources'][str(dep.relative_to(ROOT))]=pin(dep);raw=dep.read_bytes()
                if a.mutation and ((a.mutation.startswith('es-') and name==('sha512' if a.mutation=='es-rotate' else 'sha512_stream')) or (a.mutation.startswith('ee-') and name=='ed25519_verify')):
                    old,new=mutations[a.mutation];text=raw.decode()
                    if text.count(old)!=1:raise ValueError('Ed shared mutation is not unique')
                    raw=text.replace(old,new).encode();state['mutationSource']=dict(name=name,original=pin(dep),mutated=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
                (stage/('os/aiueos/kotoba/aiueos/'+name+'.kotoba')).write_bytes(raw)
            if envelope or roster:
                for name in ['ed25519_region','lib/sha256_stream']:
                    dep=ROOT/('lib/kotoba.aiueos/os/aiueos/kotoba/aiueos/'+name+'.kotoba')
                    state['dependencySources'][str(dep.relative_to(ROOT))]=pin(dep)
                    target=stage/('os/aiueos/kotoba/aiueos/'+name+'.kotoba');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(dep.read_bytes())
            if roster:
                extra=[('/roster-owner/kekkai/envelope_region.kotoba','lib/kotoba.kekkai/kotoba/kekkai/envelope_region.kotoba'),
                       ('/edn-owner/kotoba/edn/region.kotoba','lib/kotoba.edn/src/kotoba/edn/region.kotoba'),
                       ('/os/aiueos/native/legacy_crypto_kat.kotoba','lib/kotoba.aiueos/os/aiueos/native/legacy_crypto_kat.kotoba')]
                for virtual,relative in extra:
                    dep=ROOT/relative;state['dependencySources'][relative]=pin(dep);raw=dep.read_bytes()
                    if relative=='lib/kotoba.edn/src/kotoba/edn/region.kotoba' and a.mutation and a.mutation.startswith('rd-'):
                        old,new=mutations[a.mutation];text=raw.decode()
                        if text.count(old)!=1:raise ValueError('EDN mutation is not unique')
                        raw=text.replace(old,new).encode();state['mutationSource']=dict(name=relative,original=pin(dep),mutated=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
                    target=stage/virtual.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
                roots.append('/edn-owner')
        if link:
            dependency=ROOT/'lib/kotoba.aiueos/os/aiueos/native/rtl8139_cplus.kotoba'
            state.setdefault('dependencySources',{})[str(dependency.relative_to(ROOT))]=pin(dependency)
            target=stage/'link-owner/aiueos/native/rtl8139_cplus.kotoba';target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(dependency.read_bytes())
        if chacha or protocol:
            state['regionProfileSources']={}
            for name in ['region_ops.kotoba','aead_region.kotoba']:
                original=ROOT/'lib/org.ietf.chacha20Poly1305/kotoba/chacha20'/name
                state['regionProfileSources'][name]=pin(original)
                raw=original.read_bytes()
                if chacha and a.mutation and name==('region_ops.kotoba' if a.mutation in ('chacha-rotate','chacha-clamp') else 'aead_region.kotoba'):
                    old,new=mutations[a.mutation];text=raw.decode()
                    if text.count(old)!=1:raise ValueError('profile mutation is not unique')
                    raw=text.replace(old,new).encode()
                    state['mutationSource']=dict(name=name,original=pin(original),mutated=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
                target=stage/'chacha-owner/chacha20'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        if chacha or protocol:
            secondary=ROOT/'lib/kotoba.noise/kotoba/noise/blake2s_region.kotoba';state['secondaryOwnerSource']=pin(secondary)
            target=stage/'noise-owner/noise/blake2s_region.kotoba';target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(secondary.read_bytes())
            if chacha:roots.append('/noise-owner')
        if protocol:
            state['dependencySources']={}
            dependencies=[('/x25519-owner','aiueos/x25519.kotoba','lib/kotoba.aiueos/os/aiueos/kotoba/x25519.kotoba')]
            if datagram or klink:dependencies.append(('/noise-owner','noise/ik_region.kotoba','lib/kotoba.noise/kotoba/noise/ik_region.kotoba'))
            for root,virtual,relative in dependencies:
                dependency=ROOT/relative;state['dependencySources'][relative]=pin(dependency)
                target=stage/root.lstrip('/')/virtual;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(dependency.read_bytes())
                if root!=owner_root:roots.append(root)
            if klink:
                dependencies_more=[('noise/datagram_region.kotoba','lib/kotoba.noise/kotoba/noise/datagram_region.kotoba'),('aiueos/native/ipv4_udp.kotoba','lib/kotoba.aiueos/os/aiueos/native/ipv4_udp.kotoba')]
                for virtual,relative in dependencies_more:
                    dependency=ROOT/relative;state['dependencySources'][relative]=pin(dependency)
                    raw=dependency.read_bytes()
                    if virtual=='noise/datagram_region.kotoba' and a.mutation=='kw-duplicate':
                        old,new=mutations[a.mutation];text=raw.decode()
                        if text.count(old)!=1:raise ValueError('datagram link mutation is not unique')
                        raw=text.replace(old,new).encode()
                        state['mutationSource']=dict(name=relative,original=pin(dependency),mutated=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
                    target=stage/'link-owner'/virtual;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
            roots.append('/chacha-owner')
        roots.append(owner_root);flags=[v for r in roots for v in ('--source-path',r)]
        payload=a.payload.resolve(strict=True)
        if pin(payload)['sha256']!=a.payload_sha256:raise ValueError('boot payload pin differs')
        (stage/('boot-font.bin' if dual else 'boot-payload.bin')).write_bytes(payload.read_bytes())
        state['bootPayload']=None if dual else pin(payload)
        if dual:
            if app:
                reference=ROOT/'lib/kotoba.kekkai/tools/application_frame_reference.py'
                blob,app_cases=load('application_public_frames',reference).fixtures();state['cases']=app_cases
                state['referenceSources']={str(reference.relative_to(ROOT)):pin(reference)}
                font=bytearray(payload.read_bytes());end=393216+len(blob)
                if len(font)!=524288 or end>len(font) or any(font[393216:end]):raise ValueError('application diagnostic tail unavailable')
                font[393216:end]=blob;(stage/'boot-font.bin').write_bytes(font)
                (out/'application-vectors.bin').write_bytes(blob);state['vectorData']=pin(out/'application-vectors.bin')
            if session:
                reference=ROOT/('lib/kotoba.kekkai/tools/frame_link_reference.py' if mlink else 'lib/kotoba.kekkai/tools/session_region_reference.py')
                if app_link:reference=ROOT/'lib/kotoba.kekkai/tools/application_link_reference.py'
                if frame:reference=ROOT/'lib/kotoba.kekkai/tools/frame_bounds_reference.py'
                if mlink:
                    blob,network_cases=load('managed_link_reference',reference).fixtures(a.mutation)
                    session_cases={'count':len(network_cases),'publicSeedsOnly':True,'syntheticNow':1750000000,'targetedFault':a.mutation,'labels':[row['label'] for row in network_cases]}
                elif frame:blob,session_cases=load('frame_bounds_reference',reference).fixtures(a.session_suite)
                else:blob,session_cases=load('managed_session_reference',reference).fixtures(a.session_suite,a.mutation)
                state['referenceSources']={str(q.relative_to(ROOT)):pin(q) for q in [reference,OS_SCRIPTS/'check-native-ed25519-qemu.py',OS_SCRIPTS/'check-native-consent-qemu.py',ROOT/'lib/org.ietf.x25519/tools/reference.py',ROOT/'lib/org.ietf.chacha20Poly1305/tools/reference.py']}
                if mlink or frame:state['referenceSources']['lib/kotoba.kekkai/tools/session_region_reference.py']=pin(ROOT/'lib/kotoba.kekkai/tools/session_region_reference.py')
                if app_link:
                    for dep in ['lib/kotoba.kekkai/tools/frame_link_reference.py','lib/kotoba.kekkai/tools/application_frame_reference.py']:state['referenceSources'][dep]=pin(ROOT/dep)
                state['cases']=session_cases
                font=bytearray(payload.read_bytes());end=393216+len(blob)
                if len(font)!=524288 or end>len(font) or any(font[393216:end]):raise ValueError('session diagnostic tail unavailable')
                font[393216:end]=blob;(stage/'boot-font.bin').write_bytes(font)
                (out/'session-vectors.bin').write_bytes(blob);state['vectorData']=pin(out/'session-vectors.bin')
            if roster:
                reference=ROOT/'lib/kotoba.kekkai/tools/roster_region_reference.py'
                blob,roster_cases=load('roster_public_reference',reference).fixtures(a.roster_suite,a.mutation)
                state['referenceSources']={str(q.relative_to(ROOT)):pin(q) for q in [reference,OS_SCRIPTS/'check-native-ed25519-qemu.py',OS_SCRIPTS/'check-native-consent-qemu.py',ROOT/'lib/kotoba.kekkai/test/fixtures/netmap.signed.edn']}
                state['cases']=roster_cases
                font=bytearray(payload.read_bytes());end=393216+len(blob)
                if len(font)!=524288 or end>len(font) or any(font[393216:end]):raise ValueError('roster diagnostic tail unavailable')
                font[393216:end]=blob;(stage/'boot-font.bin').write_bytes(font)
                (out/'roster-vectors.bin').write_bytes(blob);state['vectorData']=pin(out/'roster-vectors.bin')
            if envelope:
                reference=ROOT/'lib/kotoba.kekkai/tools/envelope_region_reference.py'
                blob,env_returns,env_final,env_cases=load('envelope_public_reference',reference).fixtures()
                state['referenceSources']={str(q.relative_to(ROOT)):pin(q) for q in [reference,OS_SCRIPTS/'check-native-consent-qemu.py',OS_SCRIPTS/'check-native-ed25519-qemu.py',ROOT/'lib/kotoba.kekkai/test/fixtures/netmap.signed.edn']}
                state['cases']=env_cases
                font=bytearray(payload.read_bytes());end=393216+len(blob)
                if len(font)!=524288 or end>len(font) or any(font[393216:end]):raise ValueError('envelope diagnostic tail unavailable')
                font[393216:end]=blob;(stage/'boot-font.bin').write_bytes(font)
                (out/'envelope-vectors.bin').write_bytes(blob);(out/'expected-envelope-returns.bin').write_bytes(env_returns);(out/'expected-final-payload.bin').write_bytes(env_final)
                state['vectorData']=pin(out/'envelope-vectors.bin')
            if ed:
                reference=OS_SCRIPTS/'ed25519-region-reference.py'
                blob,ed_hashes,ed_returns,ed_cases=load('ed_public_reference',reference).fixtures()
                state['referenceSources']={str(q.relative_to(ROOT)):pin(q) for q in [reference,OS_SCRIPTS/'check-native-consent-qemu.py',OS_SCRIPTS/'check-native-ed25519-qemu.py',ROOT/'lib/org.ietf.ed25519/test/wycheproof/ed25519_test.json',ROOT/'lib/kotoba.kekkai/test/fixtures/netmap.signed.edn']}
                state['cases']=ed_cases
                font=bytearray(payload.read_bytes());end=393216+len(blob)
                if len(font)!=524288 or end>len(font) or any(font[393216:end]):raise ValueError('Ed diagnostic tail unavailable')
                font[393216:end]=blob;(stage/'boot-font.bin').write_bytes(font)
                (out/'ed-vectors.bin').write_bytes(blob);(out/'expected-sha512.bin').write_bytes(ed_hashes);(out/'expected-ed-returns.bin').write_bytes(ed_returns)
                state['vectorData']=pin(out/'ed-vectors.bin')
            if protocol:
                reference=ROOT/('lib/kotoba.noise/tools/datagram_region_reference.py' if datagram else 'lib/kotoba.noise/tools/ik_region_reference.py')
                blob,expected_ik,descriptions=load('ik_public_reference',reference).fixtures()
                state['referenceSources']={str(p.relative_to(ROOT)):pin(p) for p in [reference,ROOT/'lib/kotoba.noise/test/noise/cacophony_vectors.edn',
                    ROOT/'lib/org.ietf.x25519/tools/reference.py',ROOT/'lib/org.ietf.chacha20Poly1305/tools/reference.py']}
                if datagram:state['referenceSources']['lib/kotoba.noise/tools/ik_region_reference.py']=pin(ROOT/'lib/kotoba.noise/tools/ik_region_reference.py')
                state['cases']=descriptions
                font=bytearray(payload.read_bytes());end=393216+len(blob)
                if len(font)!=524288 or end>len(font) or any(font[393216:end]):raise ValueError('IK diagnostic tail is unavailable')
                font[393216:end]=blob;(stage/'boot-font.bin').write_bytes(font)
                (out/'ik-vectors.bin').write_bytes(blob);(out/('expected-datagram-records.bin' if datagram else 'expected-ik-records.bin')).write_bytes(expected_ik)
                state['vectorData']=pin(out/'ik-vectors.bin')
            if x25519:
                blob,expected_x,expected_returns=x25519_vectors(state)
                # Public diagnostic data goes in the pinned font's unused tail;
                # its existing header/glyphs/firmware remain byte-identical.
                font=bytearray(payload.read_bytes());end=393216+len(blob)
                if len(font)!=524288 or end>len(font) or any(font[393216:end]):
                    raise ValueError('X25519 diagnostic vector tail is unavailable')
                font[393216:end]=blob
                (stage/'boot-font.bin').write_bytes(font)
                (out/'x25519-vectors.bin').write_bytes(blob)
                state['vectorData']=pin(out/'x25519-vectors.bin')
                (out/'expected-x25519.bin').write_bytes(expected_x)
                (out/'expected-returns.bin').write_bytes(expected_returns)
            state['bootFont']=pin(stage/'boot-font.bin')
            user=ROOT/'lib/kotoba.aiueos/os/aiueos/native/itonami-local-model-user-v3.kotoba'
            (stage/'boot-user-source.kotoba').write_bytes(user.read_bytes());state['diagnosticUserSource']=pin(user)
            state['userCodeExecuted']=False
        fd=os.open(stage,os.O_RDONLY|os.O_DIRECTORY)
        if fd!=3:os.dup2(fd,3);os.close(fd)
        def run(label,argv):
            p=subprocess.run([str(a.compiler),*argv],cwd=stage,env={'PATH':'/nonexistent'},pass_fds=(3,),capture_output=True,timeout=180)
            for suffix,raw in [('stdout',p.stdout),('stderr',p.stderr)]: (out/(label+'.'+suffix)).write_bytes(raw)
            state['calls'].append(dict(label=label,argv=argv,exit=p.returncode,stdout=p.stdout.decode(errors='replace'),stderr=p.stderr.decode(errors='replace')));save()
            if p.returncode or p.stderr:raise RuntimeError(label+': '+p.stderr.decode(errors='replace')[:1000])
            return p.stdout
        if dual:
            for name in ['boot-user.elf','boot-user.reproduced.elf']:
                run('compile-'+name,['compile','boot-user-source.kotoba','--target','x86_64-aiueos-user-v5','--output',name])
            if pin(stage/'boot-user.elf')!=pin(stage/'boot-user.reproduced.elf'):raise ValueError('user image reproduction differs')
            for name in ['boot-user-slot.bin','boot-user-slot.reproduced.bin']:
                run('package-'+name,['package-aiueos-user-payload','boot-user.elf','--output',name,'--version','v4'])
            if pin(stage/'boot-user-slot.bin')!=pin(stage/'boot-user-slot.reproduced.bin'):raise ValueError('user slot reproduction differs')
            state['diagnosticUserELF']=pin(stage/'boot-user.elf');state['diagnosticUserSlot']=pin(stage/'boot-user-slot.bin')
        modules=run('modules',['modules',entry,*flags]);graph={}
        for line in modules.decode().splitlines():
            namespace,virtual=line.split(' ',1)
            if not namespace or not virtual.startswith('/') or virtual in graph:raise ValueError('module graph shape')
            graph[virtual]=pin(stage/virtual.lstrip('/'))['sha256']
        state['sourceGraph']=graph
        current='KSL1\nentry '+entry+'\n'+''.join('root '+r+'\n' for r in roots)+''.join('file '+s+' '+p+'\n' for p,s in sorted(graph.items()))
        (stage/'region.ksl').write_text(current)
        compile_args=['compile',entry,'--target','x86_64-aiueos-kernel-v3','--artifact','image','--fuel','9007199254740991',*flags,'--source-lock','region.ksl','--source-lock-sha256',hashlib.sha256(current.encode()).hexdigest()]
        for name in ['KERNEL.ELF','KERNEL.reproduced.ELF']:run('compile-'+name,[*compile_args,'--output',name])
        if (stage/'KERNEL.ELF').read_bytes()!=(stage/'KERNEL.reproduced.ELF').read_bytes():raise ValueError('kernel reproduction differs')
        for name in ['BOOTX64.EFI','BOOTX64.reproduced.EFI']:
            boot_args=['--font','boot-font.bin','--user-slot','boot-user-slot.bin'] if dual else ['--payload','boot-payload.bin']
            run('package-'+name,['package-aiueos-boot','KERNEL.ELF','--output',name,*boot_args,'--pci-resources','v1'])
        if (stage/'BOOTX64.EFI').read_bytes()!=(stage/'BOOTX64.reproduced.EFI').read_bytes():raise ValueError('EFI reproduction differs')
        efi=stage/'BOOTX64.EFI';kernel=stage/'KERNEL.ELF'
        cmd=[sys.executable,str(OS_SCRIPTS/'build-native-media-macos.py'),'--amu-source',str(a.amu_source.resolve(strict=True)),
             '--compiler-image',str(a.compiler),'--compiler-sha256',a.compiler_sha256,'--packager-image',str(a.packager),
             '--packager-sha256',a.packager_sha256,'--efi',str(efi),'--efi-sha256',pin(efi)['sha256'],'--output',str(out/'media')]
        media_run=subprocess.run(cmd,capture_output=True,timeout=180)
        (out/'media.stdout').write_bytes(media_run.stdout);(out/'media.stderr').write_bytes(media_run.stderr)
        if media_run.returncode:raise RuntimeError('native media build failed: '+media_run.stderr.decode(errors='replace')[:1000])
        media=out/'media/awai-native.img'
        if not media.exists():raise ValueError('native media output missing')
        state['state']='COMPILED_NOT_BOOTED';save()
        media_before=pin(media)
        keys=load('region_qemu_observer',OS_SCRIPTS/'check-native-keystore-qemu.py')
        state['qemuHelper']=pin(OS_SCRIPTS/'check-native-keystore-qemu.py')
        boot=keys.Boot.__new__(keys.Boot)
        peer=None
        try:
            extra=['-serial','file:serial.log','-debugcon','file:debug.log','-d','int,cpu_reset','-D','qemu-debug.log']
            if roster or session:extra+=['-qmp','unix:roster-qmp.sock,server=on,wait=off']
            if link:
                peer=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);peer.bind(('127.0.0.1',0))
                with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as reservation:
                    reservation.bind(('127.0.0.1',0));target=('127.0.0.1',reservation.getsockname()[1])
                state['loopbackPeer']=dict(host=peer.getsockname(),qemu=target)
                extra+=['-netdev',f'dgram,id=klink,local.type=inet,local.host=127.0.0.1,local.port={target[1]},remote.type=inet,remote.host=127.0.0.1,remote.port={peer.getsockname()[1]}',
                        '-device','rtl8139,netdev=klink,mac=52:54:00:12:34:56,addr=0x4']
            keys.Boot.__init__(boot,SimpleNamespace(kernel=kernel,efi=efi,media=media,qemu=a.qemu,firmware=a.firmware),out,'region-crypto',None,
                               extra=extra,first_frame_seconds=a.first_frame_seconds)
            if link:
                link_peer=ROOT/('scripts/native_application_link_peer.py' if app_link else ('scripts/native_managed_link_peer.py' if mlink else ('scripts/native_kekkai_link_peer.py' if klink else 'scripts/native_udp_link_peer.py')));state['linkPeerObserver']=pin(link_peer)
                if mlink:state['linkPeerDependencies']={'scripts/native_udp_link_peer.py':pin(ROOT/'scripts/native_udp_link_peer.py')}
                state['state']='NATIVE_LINK_RUNNING';save()
                peer_module=load('native_udp_link_peer',link_peer)
                state['linkResult'],link_good=peer_module.exercise(boot,peer,target,out,a.mutation) if mlink else peer_module.exercise(boot,peer,target,out)
            if x25519 or protocol or ed or envelope or roster or session or app:
                started=time.monotonic();state['state']='NATIVE_RUNNING';save()
                while boot.W(79)==1:
                    if boot.proc.poll() is not None:raise RuntimeError('region guest terminated')
                    if envelope or roster or session or app:
                        log=out/'qemu-debug.log'
                        traps=re.findall(rb'v=06 [^\n]*IP=0008:([0-9a-f]+)',log.read_bytes()) if log.exists() else []
                        if any(0x100000<=int(pc,16)<0x400000 for pc in traps):
                            state['nativeInvalidOpcodePCs']=[pc.decode() for pc in traps];save()
                            raise RuntimeError('native region guest halted on an invalid opcode; not a bounded refusal')
                    state['completedCases']=boot.W(78)
                    if roster or session:
                        state['nativeProgress']=list(struct.unpack('<13I',boot.dump(boot.work+74*4,52)))
                    save()
                    if time.monotonic()-started>a.execution_seconds:raise TimeoutError('region native execution deadline')
                    time.sleep(2)
            words=struct.unpack('<6I',boot.dump(boot.work+74*4,24))
            if link:raw=b''
            elif app:
                low,high,other_low,other_high=struct.unpack('<4I',boot.dump(boot.work+400,16));address=low+(high<<32);other=other_low+(other_high<<32)
                if not (0<address<1<<39 and 0<other<1<<39 and (address+262144<=other or other+262144<=address)):raise ValueError('application test owners overlap')
                raw=boot.dump(address,8192);n=app_cases['count'];app_known_answers=boot.W(91);app_cursor_guards=boot.W(92);app_cursor_failures=boot.W(93)
                for name,offset,size in [('returns',196608,n*16),('hashes',229376,n*32),('assertions',163840,n*4),('output',65536,65537)]:
                    (out/('native-application-'+name+'.bin')).write_bytes(boot.dump(other+offset,size))
            elif roster or session:
                low,high=struct.unpack('<2I',boot.dump(boot.work+400,8));address=low+(high<<32)
                if not 0<address<1<<39:raise ValueError('native roster request address differs')
                raw=boot.dump(address,65536)
                (out/'native-roster-transient.bin').write_bytes(boot.dump(address+65536,196608))
                roster_trace=boot.dump(boot.work+1024,2816)
                roster_extra=boot.dump(boot.work+82*4,20)
                if session:
                    low,high=struct.unpack('<2I',boot.dump(boot.work+408,8));other_address=low+(high<<32)
                    if not 0<other_address<1<<39 or not (address+262144<=other_address or other_address+262144<=address):raise ValueError('managed owner and caller IO allocations overlap')
                    session_counts=struct.unpack('<2I',boot.dump(boot.work+80*4,8))
                    if not link and not frame:
                        binding_counts=boot.dump(boot.work+97*4,12)
                        (out/'native-session-application-binding-counts.bin').write_bytes(binding_counts)
                        session_binding_counts=struct.unpack('<3I',binding_counts)
                    if not 0<=session_counts[0]<=2048 or not 0<=session_counts[1]<=1024:raise ValueError('managed trace count exceeds its allocation')
                    (out/'native-session-returns.bin').write_bytes(boot.dump(other_address+(229376 if frame else 196608),session_counts[0]*16))
                    (out/'native-session-hashes.bin').write_bytes(boot.dump(other_address+(216064 if frame else 229376),session_counts[1]*32))
                    (out/'native-session-output.bin').write_bytes(boot.dump(other_address+(73728 if frame else 65536),65538 if frame else 65536))
            elif envelope:
                low,high=struct.unpack('<2I',boot.dump(boot.work+400,8));address=low+(high<<32)
                if not 0<address<1<<39:raise ValueError('native envelope request address differs')
                raw=boot.dump(boot.work+4096,len(env_returns))
                (out/'native-envelope-work.bin').write_bytes(boot.dump(address,98304))
                (out/'native-final-payload.bin').write_bytes(boot.dump(address+196608,65536))
                env_legacy=boot.W(80)
            elif ed:
                low,high=struct.unpack('<2I',boot.dump(boot.work+400,8));address=low+(high<<32)
                if not 0<address<1<<39:raise ValueError('native Ed request address differs')
                raw=boot.dump(address+131072,65536)
                (out/'native-ed-work-after-guards.bin').write_bytes(boot.dump(address,16384))
                (out/'native-ed-counts.bin').write_bytes(boot.dump(boot.work+320,12))
            elif protocol:raw=boot.dump(boot.work+4096,(39 if datagram else 95)*32)
            elif dual:
                lo,hi=struct.unpack('<2I',boot.dump(boot.work+400,8));address=lo+(hi<<32)
                if not 0<address<1<<39:raise ValueError('native output region address differs')
                if x25519:
                    raw=boot.dump(address,528*32)
                    native_returns=boot.dump(address+20000,528*4)
                    (out/'native-returns.bin').write_bytes(native_returns)
                else:raw=boot.dump(address+4096,1051*32)
            else:raw=boot.dump(boot.work+keys.native_regions.WINDOW_BYTES,303*32)
        except BaseException:
            if hasattr(boot,'proc') and boot.proc.poll() is None:
                (out/'failure-context.bin').write_bytes(boot.dump(boot.work,8192))
                if klink:(out/'failure-native-context.bin').write_bytes(boot.dump(0x408000,512))
                boot.send('info registers');state['failureRegisters']=boot.drain();save()
            if hasattr(boot,'proc'):
                state['qemuExitCode']=boot.proc.poll()
                (out/'failure-qemu.log').write_text(boot.drain());save()
            raise
        finally:
            if hasattr(boot,'proc'):boot.quit()
            if peer is not None:peer.close()
        (out/'native-digests.bin').write_bytes(raw)
        if pin(media)!=media_before:raise ValueError('fixture medium changed during QEMU boot')
        state['mediaUnchanged']=True
        if link:
            state['observed']=state['linkResult']['observed']
            state['artifacts']={n:pin(p) for n,p in [('kernel',kernel),('efi',efi),('media',media),('qemu',a.qemu),('firmware',a.firmware)]}
            if a.mutation:
                observed=state['observed']
                if not (observed['nicStarted']==observed['wiped' if klink or mlink else 'completed']==observed['canary']==1 and observed['terminal']==2 and (mlink or observed['nativeErrors']==0)):
                    raise AssertionError('link mutation did not complete normally')
                if mlink:
                    wanted=state['linkResult']['expected']
                    required=['rxFrames','released','rxErrors','transitions','shapeAndTransportGuards','outerHeaderProbes','rosterVersion','rosterGeneration']
                    if any(observed[k]!=wanted[k] for k in required):raise AssertionError('managed link fault did not finish all lifecycle/shape controls')
                if link_good:raise AssertionError('link mutation escaped real packet controls')
                state['state']='DETECTED_NATIVE_LINK_MUTATION'
            else:
                if not link_good:raise AssertionError('native UDP link/control mismatch: '+str(state['linkResult']['violations']))
                state['state']='PASS_NATIVE_OS_APPLICATION_LINK' if app_link else ('PASS_NATIVE_OS_MANAGED_LINK' if mlink else ('PASS_NATIVE_OS_KEKKAI_LINK' if klink else 'PASS_NATIVE_OS_UDP_LINK'))
            state['kernelReproduced']=True;state['efiReproduced']=True;save();print(state['state'],json.dumps(state['observed']));return
        if ed:
            (out/'native-ed-records.bin').write_bytes(raw)
            sha_bad=[i for i in range(264) if raw[i*64:(i+1)*64]!=ed_hashes[i*64:(i+1)*64]]
            old_sha_bad=[i for i in range(262) if raw[18432+i*64:18432+(i+1)*64]!=ed_hashes[i*64:(i+1)*64]]
            count=len(ed_returns)//4
            ed_bad=[i for i in range(count) if raw[36864+i*4:36864+(i+1)*4]!=ed_returns[i*4:(i+1)*4]]
            old_ed=load('ed_published_legacy',OS_SCRIPTS/'check-native-ed25519-qemu.py')
            legacy_expected=b''.join(bytes.fromhex(old_ed.CASES[i][1]+old_ed.SIGS[i][1]) for i in range(3))
            legacy_match=raw[49152:49152+288]==legacy_expected
            wiped=(out/'native-ed-work-after-guards.bin').read_bytes()==bytes(16384)
            counts=struct.unpack('<3I',(out/'native-ed-counts.bin').read_bytes())
            observed=dict(streamHashes=counts[0],legacyCases=counts[1],streamGuards=counts[2],legacyCompleted=words[0],nativeAssertionFailures=words[1],guardsCompleted=words[2],canary=words[3],caseCount=words[4],completed=words[5],streamHashMismatches=sha_bad,legacyHashMismatches=old_sha_bad,signatureMismatches=ed_bad,legacyKeySignaturesMatch=legacy_match,finalWorkWiped=wiped)
            state['observed']=observed;state['artifacts']={n:pin(q) for n,q in [('kernel',kernel),('efi',efi),('media',media),('qemu',a.qemu),('firmware',a.firmware)]}
            good=counts==(264,3,1) and words==(1,0,1,1,count,2) and not sha_bad and not old_sha_bad and not ed_bad and legacy_match and wiped
            if a.mutation:
                if words[2:]!=(1,1,count,2):raise AssertionError('Ed mutant did not complete bounded controls')
                if good:raise AssertionError('Ed mutation escaped native controls')
                state['state']='DETECTED_NATIVE_MUTATION'
            else:
                if not good:raise AssertionError('native raw Ed/SHA512 mismatch: '+str(observed))
                state['state']='PASS_NATIVE_OS_REGION_ED25519_SHA512'
            state['kernelReproduced']=True;state['efiReproduced']=True;save();print(state['state'],json.dumps(observed));return
        if envelope:
            (out/'native-envelope-returns.bin').write_bytes(raw);count=len(env_returns)//4
            mismatches=[i for i in range(count) if raw[i*4:(i+1)*4]!=env_returns[i*4:(i+1)*4]]
            work_zero=(out/'native-envelope-work.bin').read_bytes()==bytes(98304)
            final_equal=(out/'native-final-payload.bin').read_bytes()==env_final
            observed=dict(shapeGuardCount=words[0],nativeAssertionFailures=words[1],guardsCompleted=words[2],canary=words[3],caseCount=words[4],completed=words[5],legacyCases=env_legacy,returnMismatches=mismatches,finalWorkWiped=work_zero,finalPayloadEquals=final_equal)
            state['observed']=observed;state['artifacts']={n:pin(q) for n,q in [('kernel',kernel),('efi',efi),('media',media),('qemu',a.qemu),('firmware',a.firmware)]}
            good=words==(10,0,1,1,count,2) and env_legacy==3 and not mismatches and work_zero and final_equal
            if a.mutation:
                if words[0]!=10 or words[2:]!=(1,1,count,2) or env_legacy!=3:raise AssertionError('envelope mutant did not complete bounded controls')
                if good:raise AssertionError('envelope mutation escaped native controls')
                state['state']='DETECTED_NATIVE_MUTATION'
            else:
                if not good:raise AssertionError('native envelope/control mismatch: '+str(observed))
                state['state']='PASS_NATIVE_OS_SIGNED_ENVELOPE'
            state['kernelReproduced']=True;state['efiReproduced']=True;save();print(state['state'],json.dumps(observed));return
        if app:
            (out/'native-application-work.bin').write_bytes(raw)
            pairs=list(struct.iter_unpack('<qq',(out/'native-application-returns.bin').read_bytes()));hashes=(out/'native-application-hashes.bin').read_bytes();expected=bytes.fromhex(''.join(app_cases['expectedHashes']))
            errors=list(struct.unpack('<%dI'%app_cases['count'],(out/'native-application-assertions.bin').read_bytes()))
            state['observed']=dict(sharedKnownAnswers=app_known_answers,cursorGuards=app_cursor_guards,cursorAssertionFailures=app_cursor_failures,caseCount=words[0],nativeErrors=words[1],guardsCompleted=words[2],canary=words[3],completed=words[4],terminal=words[5],returnPairs=pairs,returnPairsMatch=all(a==b for a,b in pairs),hashesMatch=hashes==expected,caseAssertions=errors,workWiped=raw==bytes(8192))
            good=app_known_answers==1 and app_cursor_guards==12 and app_cursor_failures==0 and words==(app_cases['count'],0,1,1,app_cases['count'],2) and state['observed']['returnPairsMatch'] and state['observed']['hashesMatch'] and not any(errors) and state['observed']['workWiped']
            if a.mutation:
                if (words[0],*words[2:])!=(app_cases['count'],1,1,app_cases['count'],2) or app_known_answers!=1 or app_cursor_guards!=12 or not state['observed']['workWiped']:raise AssertionError('application fault did not complete normally')
                if good or not words[1]:raise AssertionError('application fault survived')
                state['state']='DETECTED_NATIVE_APPLICATION_FRAME_MUTATION'
            else:
                if not good:raise AssertionError('native application codec differs: '+str(state['observed']))
                state['state']='PASS_NATIVE_OS_APPLICATION_FRAME'
            state['artifacts']={n:pin(q) for n,q in [('kernel',kernel),('efi',efi),('media',media),('qemu',a.qemu),('firmware',a.firmware)]}
            state['kernelReproduced']=True;state['efiReproduced']=True;save();print(state['state'],json.dumps(state['observed']));return
        if frame:
            (out/'native-session-state.bin').write_bytes(raw)
            pairs=list(struct.iter_unpack('<qq',(out/'native-session-returns.bin').read_bytes()))
            hashes=(out/'native-session-hashes.bin').read_bytes();expected=bytes.fromhex(''.join(state['cases']['expectedNativeHashes']))
            state['observed']=dict(guards=words[0],nativeErrors=words[1],guardsCompleted=words[2],canary=words[3],caseCount=words[4],terminal=words[5],eventPairs=pairs,eventPairsMatch=all(a==b for a,b in pairs),hashCount=session_counts[1],hashesMatch=hashes==expected,sessionWiped=raw[32768:]==bytes(32768),transientWiped=(out/'native-roster-transient.bin').read_bytes()==bytes(196608))
            good=words==(6,0,1,1,1,2) and state['observed']['eventPairsMatch'] and state['observed']['hashesMatch'] and state['observed']['sessionWiped'] and state['observed']['transientWiped'] and session_counts[1]==2
            if not good:raise AssertionError('native framed bounds differ: '+str(state['observed']))
            state['artifacts']={n:pin(q) for n,q in [('kernel',kernel),('efi',efi),('media',media),('qemu',a.qemu),('firmware',a.firmware)]}
            state['state']='PASS_NATIVE_OS_MANAGED_FRAME_BOUNDS';state['kernelReproduced']=True;state['efiReproduced']=True;save();print(state['state'],json.dumps(state['observed']));return
        if session:
            (out/'native-session-state.bin').write_bytes(raw)
            returns=(out/'native-session-returns.bin').read_bytes();hashes=(out/'native-session-hashes.bin').read_bytes();pairs=list(struct.iter_unpack('<qq',returns))
            case_count=state['cases']['count'];expected_hashes=bytes.fromhex(''.join(state['cases']['expectedNativeHashes']))
            case_assertions=list(struct.unpack('<%dI'%case_count,roster_trace[512:512+case_count*4]))
            state['observed']=dict(nativeAssertionFailures=words[1],completed=words[5],caseCount=words[4],guards=words[0],guardsCompleted=words[2],canary=words[3],
                transientWiped=(out/'native-roster-transient.bin').read_bytes()==bytes(196608),sessionWiped=raw[32768:65536]==bytes(32768),
                ownerAndCallerIODisjoint=True,returnPairs=pairs,returnPairsMatch=all(a==e for a,e in pairs),hashCount=session_counts[1],hashesMatch=hashes==expected_hashes,caseAssertions=case_assertions,
                applicationBindingCases=session_binding_counts[0],applicationBindingRefusals=session_binding_counts[1],applicationBindingCopies=session_binding_counts[2])
            state['artifacts']={n:pin(q) for n,q in [('kernel',kernel),('efi',efi),('media',media),('qemu',a.qemu),('firmware',a.firmware)]}
            good=words==(30,0,1,1,case_count,2) and state['observed']['transientWiped'] and raw[32768:65536]==bytes(32768) and state['observed']['returnPairsMatch'] and state['observed']['hashesMatch'] and not any(case_assertions) and session_counts[1]==case_count*2 and session_binding_counts==(case_count,case_count*6,case_count*3)
            if a.mutation:
                if (words[0],words[2],words[3],words[4],words[5])!=(30,1,1,case_count,2) or session_counts[1]!=case_count*2:raise AssertionError('managed fault did not normally complete')
                if session_binding_counts!=(case_count,case_count*6,case_count*3):raise AssertionError('managed fault did not complete all binding cases/refusals/copies')
                if good or words[1]==0:raise AssertionError('managed fault survived')
                state['state']='DETECTED_NATIVE_MANAGED_SESSION_MUTATION'
            else:
                if not good:raise AssertionError('native managed session differs: '+str(state['observed']))
                state['state']='PASS_NATIVE_OS_MANAGED_SESSION'
            state['kernelReproduced']=True;state['efiReproduced']=True;save();print(state['state'],json.dumps(state['observed']));return
        if roster:
            (out/'native-roster-state.bin').write_bytes(raw)
            transient_zero=(out/'native-roster-transient.bin').read_bytes()==bytes(196608)
            trace=roster_trace
            (out/'native-roster-trace.bin').write_bytes(trace)
            extra=struct.unpack('<5I',roster_extra)
            count=state['cases']['count'];edn_count=state['cases']['ednCount']
            results=list(struct.unpack('<%dI'%count,trace[:count*4]))
            edn_results=list(struct.unpack('<%dI'%edn_count,trace[512:512+edn_count*4]))
            assertions=list(struct.unpack('<%dI'%count,trace[2048:2048+count*4]))
            edn_assertions=list(struct.unpack('<%dI'%edn_count,trace[2560:2560+edn_count*4]))
            expected=[row['expected'] for row in state['cases']['roster']]
            expected_edn=[row['expected'] for row in state['cases']['edn']]
            header=struct.unpack_from('<I4xQQQIIII',raw)
            identity_ok=raw[96:160].hex()==state['cases']['existingPayloadSHA512'] and raw[160:192].hex()==state['cases']['existingAuthorityHex']
            def span(record,field):
                at,size=struct.unpack_from('<2I',raw,record+field)
                return raw[at:at+size] if 16384<=at<=32768 and 0<=size<=32768-at else None
            flat_nodes=[(17,b'n-laptop',0,1,0),(51,b'n-gw',1757776000,1,1),(85,b'n-rogue',1749996400,0,1),(34,b'n-server',1757776000,1,1)]
            flat_ok=header[:7]==(0x31524e4b,42,1750000000,1,1,4,3) and 0<header[7]<=16384 and span(0,48)==b'default'
            for i,(key,node,expiry,status,has_expiry) in enumerate(flat_nodes):
                at=512+i*96
                flat_ok=flat_ok and raw[at:at+32]==bytes([key])*32 and struct.unpack_from('<Q',raw,at+32)[0]==expiry and struct.unpack_from('<2I',raw,at+48)==(status,has_expiry) and span(at,40)==node
            for i,peer in enumerate([1,2,3]):
                at=8192+i*32
                flat_ok=flat_ok and struct.unpack_from('<2I',raw,at)==(0,peer) and span(at,8)==(b'[:overlay]' if i==0 else b'[:overlay :ssh]') and span(at,16)==(b'[:any]' if i==0 else b'[22 443]')
            state['observed']=dict(nativeAssertionFailures=words[1],caseCount=words[4],completed=words[5],transientWiped=transient_zero,
                guards=words[0],canary=words[3],ednCompleted=extra[0],suiteCompleted=extra[1],existingFixtureCompleted=extra[2],
                results=results,ednResults=edn_results,caseAssertions=assertions,ednAssertions=edn_assertions,
                resultsMatch=results==expected,ednResultsMatch=edn_results==expected_edn,
                rosterHeader=list(header),sessionWiped=raw[32768:65536]==bytes(32768),independentIdentityMatches=identity_ok,independentRosterFieldsMatch=flat_ok)
            state['artifacts']={n:pin(q) for n,q in [('kernel',kernel),('efi',efi),('media',media),('qemu',a.qemu),('firmware',a.firmware)]}
            good=words==(8,0,1,1,count,2) and transient_zero and results==expected and edn_results==expected_edn and not any(assertions+edn_assertions) and extra[:3]==(edn_count,1,1) and identity_ok and flat_ok and raw[32768:65536]==bytes(32768)
            if a.mutation:
                if (words[0],words[2],words[3],words[4],words[5])!=(8,1,1,count,2) or extra[:3]!=(edn_count,1,1):raise AssertionError('roster mutation did not normally complete')
                if good:raise AssertionError('roster mutation survived')
                state['state']='DETECTED_NATIVE_ROSTER_MUTATION'
            else:
                if not good:raise AssertionError('native roster assertions or readback differ: '+str(state['observed']))
                state['state']='PASS_NATIVE_OS_ROSTER'
            state['kernelReproduced']=True;state['efiReproduced']=True;save();print(state['state'],json.dumps(state['observed']));return
        if protocol:
            count=39 if datagram else 95
            (out/('native-datagram-records.bin' if datagram else 'native-ik-records.bin')).write_bytes(raw)
            mismatch=[i for i in range(count) if raw[i*32:i*32+32]!=expected_ik[i*32:i*32+32]]
            observed=dict(cacophonyAnswer=words[0],nativeAssertionFailures=words[1],guardsCompleted=words[2],canary=words[3],recordCount=words[4],completed=words[5],mismatchedRecords=mismatch)
            state['observed']=observed;state['artifacts']={n:pin(p) for n,p in [('kernel',kernel),('efi',efi),('media',media),('qemu',a.qemu),('firmware',a.firmware)]}
            good=words==(1,0,1,1,count,2) and not mismatch
            if a.mutation:
                if words[2:]!=(1,1,count,2):raise AssertionError('protocol mutant did not complete bounded controls')
                if good:raise AssertionError('IK mutation escaped native controls')
                state['state']='DETECTED_NATIVE_MUTATION'
            else:
                if not good:raise AssertionError('native IK/control mismatch: '+str(observed))
                state['state']='PASS_NATIVE_OS_REGION_DATAGRAM' if datagram else 'PASS_NATIVE_OS_REGION_IK'
            state['kernelReproduced']=True;state['efiReproduced']=True;save();print(state['state'],json.dumps(observed));return
        if x25519:
            (out/'native-x25519.bin').write_bytes(raw)
            mismatch=[i for i in range(528) if raw[i*32:i*32+32]!=expected_x[i*32:i*32+32]]
            returns=[i for i in range(528) if native_returns[i*4:i*4+4]!=expected_returns[i*4:i*4+4]]
            observed=dict(outputMismatchCases=words[0],returnMismatchCases=words[1],inputMutationCases=words[2],
                          canaryFailures=words[3],caseCount=words[4],completed=words[5],
                          independentOutputMismatches=mismatch,independentReturnMismatches=returns)
            state['observed']=observed;state['artifacts']={n:pin(p) for n,p in [('kernel',kernel),('efi',efi),('media',media),('qemu',a.qemu),('firmware',a.firmware)]}
            good=words==(0,0,0,0,528,2) and not mismatch and not returns
            if a.mutation:
                if words[2:]!=(0,0,528,2):raise AssertionError('X25519 mutant did not complete bounded controls')
                if good:raise AssertionError('X25519 mutation escaped native controls')
                state['state']='DETECTED_NATIVE_MUTATION'
            else:
                if not good:raise AssertionError('native X25519/control mismatch: '+str(observed))
                state['state']='PASS_NATIVE_OS_REGION_X25519'
            state['kernelReproduced']=True;state['efiReproduced']=True;save()
            print(state['state'],json.dumps({**observed,'independentOutputMismatches':len(mismatch),'independentReturnMismatches':len(returns)}));return
        if chacha:
            observed,good=check_chacha(words,raw,out,state)
            state['observed']=observed;state['artifacts']={n:pin(p) for n,p in [('kernel',kernel),('efi',efi),('media',media),('qemu',a.qemu),('firmware',a.firmware)]}
            if a.mutation:
                if words[3:]!=(1,1051,1):raise AssertionError('mutation did not complete bounded native controls')
                if good:raise AssertionError('mutation escaped native controls')
                state['state']='DETECTED_NATIVE_MUTATION'
            else:
                if not good:raise AssertionError('native chacha/control mismatch: '+str(observed))
                state['state']='PASS_NATIVE_OS_REGION_CHACHA20_POLY1305'
            state['kernelReproduced']=True;state['efiReproduced']=True;save();print(state['state'],json.dumps(observed));return
        if hashlib.blake2s(b'abc').hexdigest()!='508c5e8c327c14e2e1a72ba34eeb452f37458b209ed63a294d999b4c86675982':raise ValueError('reference KAT differs')
        if hmac.digest(b'',b'','blake2s').hex()!='eaf4bb25938f4d20e72656bbbc7a9bf63c0c18537333c35bdb67db1402661acd':raise ValueError('reference HMAC KAT differs')
        pattern=lambda n:bytes((i*17+3)%256 for i in range(n))
        expected=[hashlib.blake2s(pattern(n)).digest() for n in range(258)]
        expected.extend([hashlib.blake2s(b'abc').digest(),hashlib.blake2s(pattern(65536)).digest(),hashlib.blake2s(pattern(1048576)).digest()])
        for kn in [0,32,64,65,100,4096]:
            key=bytes((i*29+11)%256 for i in range(kn))
            for n in [0,1,63,64,65,257,4096]:expected.append(hmac.digest(key,pattern(n),'blake2s'))
        expected=b''.join(expected);(out/'expected-digests.bin').write_bytes(expected)
        mismatches=[i for i in range(303) if raw[i*32:i*32+32]!=expected[i*32:i*32+32]]
        observed=dict(knownAnswerMask=words[0],operationErrors=words[1],guardMask=words[2],canaryMask=words[3],digestCount=words[4],completed=words[5],mismatchedDigests=mismatches)
        state['observed']=observed;state['artifacts']={n:pin(p) for n,p in [('kernel',kernel),('efi',efi),('media',media),('qemu',a.qemu),('firmware',a.firmware)]}
        good=words==(3,0,1023,1,303,1) and not mismatches
        if a.mutation:
            if words[1]!=0 or words[3:]!=(1,303,1):raise AssertionError('mutation did not complete bounded native controls')
            if good:raise AssertionError('mutation escaped native controls')
            state['state']='DETECTED_NATIVE_MUTATION'
        else:
            if not good:raise AssertionError('native digest/control mismatch: '+str(observed))
            state['state']='PASS_NATIVE_OS_REGION_BLAKE2S_HMAC'
        state['kernelReproduced']=True;state['efiReproduced']=True;save();print(state['state'],json.dumps(observed))
    except BaseException as error:
        state['failure']=type(error).__name__+': '+str(error);save();raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['compiler','packager','amu-source','source-stage','payload','qemu','firmware','output']:p.add_argument('--'+name,type=Path,required=True)
    for name in ['compiler-sha256','packager-sha256','source-lock-sha256','payload-sha256','qemu-sha256','firmware-sha256']:p.add_argument('--'+name,required=True)
    p.add_argument('--first-frame-seconds',type=float,default=240)
    p.add_argument('--component',choices=['blake2s','chacha','x25519','ik','datagram','udp-link','kekkai-link','ed25519','envelope','roster','session','managed-link','frame','application-frame','application-link'],default='blake2s')
    p.add_argument('--execution-seconds',type=float,default=3600)
    p.add_argument('--roster-suite',choices=['policy','bounds','faults'],default='policy')
    p.add_argument('--session-suite',choices=['policy','handshake-responder','handshake-initiator','transport-responder','transport-initiator','faults'],default='policy')
    p.add_argument('--mutation',choices=[*APPLICATION_FRAME_MUTATIONS,*FRAME_MUTATIONS,*MUTATIONS,*CHACHA_MUTATIONS,*X25519_MUTATIONS,*IK_MUTATIONS,*DATAGRAM_MUTATIONS,*UDP_LINK_MUTATIONS,*KEKKAI_LINK_MUTATIONS,*ED_MUTATIONS,*ENVELOPE_MUTATIONS,*ROSTER_MUTATIONS,*SESSION_MUTATIONS])
    main(p.parse_args())
