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
    chacha=a.component=='chacha';x25519=a.component=='x25519';ik=a.component=='ik';datagram=a.component=='datagram';ed=a.component=='ed25519';klink=a.component=='kekkai-link';link=a.component=='udp-link' or klink;protocol=ik or datagram or klink;dual=chacha or x25519 or protocol or link or ed
    namespace='aiueos.native.kekkai-link-gate' if klink else ('aiueos.native.udp-link-gate' if link else ('noise.datagram-region-gate' if datagram else ('noise.ik-region-gate' if ik else ('aiueos.native.x25519-region-gate' if x25519 else ('chacha20.region-gate' if chacha else 'noise.blake2s-region-gate')))))
    slug='kekkai-link' if klink else ('udp-link' if link else ('datagram' if datagram else ('ik' if ik else ('x25519' if x25519 else ('chacha20' if chacha else 'blake2s')))))
    mutations=KEKKAI_LINK_MUTATIONS if klink else (UDP_LINK_MUTATIONS if link else (DATAGRAM_MUTATIONS if datagram else (IK_MUTATIONS if ik else (X25519_MUTATIONS if x25519 else (CHACHA_MUTATIONS if chacha else MUTATIONS)))))
    if ed:namespace='aiueos.native.ed25519-region-gate';slug='ed25519';mutations=ED_MUTATIONS
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
        core_bytes=core.read_bytes();state['ownerSource']=pin(core);state['fixtureSource']=pin(fixture)
        if a.mutation and not chacha and not (klink and a.mutation=='kw-duplicate') and not (ed and a.mutation.startswith(('es-','ee-'))):
            old,new=mutations[a.mutation];text=core_bytes.decode()
            if text.count(old)!=1:raise ValueError('mutation is not unique')
            core_bytes=text.replace(old,new).encode()
        files=([('kekkai/wire_region.kotoba',core_bytes),('aiueos/native/kekkai_link_gate.kotoba',fixture.read_bytes())] if klink else ([('aiueos/native/ipv4_udp.kotoba',core_bytes),('aiueos/native/udp_link_gate.kotoba',fixture.read_bytes())] if link else ([('noise/datagram_region.kotoba',core_bytes),('noise/datagram_region_gate.kotoba',fixture.read_bytes())] if datagram else ([('noise/ik_region.kotoba',core_bytes),('noise/ik_region_gate.kotoba',fixture.read_bytes())] if ik else ([('aiueos/x25519.kotoba',core_bytes),('aiueos/native/x25519_region_gate.kotoba',fixture.read_bytes())] if x25519 else
              ([('chacha20/region.kotoba',core_bytes),('chacha20/region_gate.kotoba',fixture.read_bytes())] if chacha else
               [('noise/blake2s_region.kotoba',core_bytes),('noise/blake2s_region_gate.kotoba',fixture.read_bytes())]))))))
        if ed:files=[('aiueos/ed25519_region.kotoba',core_bytes),('aiueos/native/ed25519_region_gate.kotoba',fixture.read_bytes())]
        owner_root='/ed25519-owner' if ed else ('/link-owner' if link else ('/x25519-owner' if x25519 else ('/chacha-owner' if chacha else '/noise-owner')))
        for virtual,raw in files:
            target=stage/owner_root.lstrip('/')/virtual;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        if ed:
            state['dependencySources']={}
            for name in ['ed25519','ed25519_verify','sha512','sha512_stream','gf25519']:
                dep=ROOT/('lib/kotoba.aiueos/os/aiueos/kotoba/aiueos/'+name+'.kotoba')
                state['dependencySources'][str(dep.relative_to(ROOT))]=pin(dep);raw=dep.read_bytes()
                if a.mutation and ((a.mutation.startswith('es-') and name==('sha512' if a.mutation=='es-rotate' else 'sha512_stream')) or (a.mutation.startswith('ee-') and name=='ed25519_verify')):
                    old,new=mutations[a.mutation];text=raw.decode()
                    if text.count(old)!=1:raise ValueError('Ed shared mutation is not unique')
                    raw=text.replace(old,new).encode();state['mutationSource']=dict(name=name,original=pin(dep),mutated=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
                (stage/('os/aiueos/kotoba/aiueos/'+name+'.kotoba')).write_bytes(raw)
        if link:
            dependency=ROOT/'lib/kotoba.aiueos/os/aiueos/native/rtl8139_cplus.kotoba'
            state['dependencySources']={str(dependency.relative_to(ROOT)):pin(dependency)}
            (stage/'link-owner/aiueos/native/rtl8139_cplus.kotoba').write_bytes(dependency.read_bytes())
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
                link_peer=ROOT/('scripts/native_kekkai_link_peer.py' if klink else 'scripts/native_udp_link_peer.py');state['linkPeerObserver']=pin(link_peer)
                state['state']='NATIVE_LINK_RUNNING';save()
                state['linkResult'],link_good=load('native_udp_link_peer',link_peer).exercise(boot,peer,target,out)
            if x25519 or protocol or ed:
                started=time.monotonic();state['state']='NATIVE_RUNNING';save()
                while boot.W(79)==1:
                    if boot.proc.poll() is not None:raise RuntimeError('region guest terminated')
                    state['completedCases']=boot.W(78);save()
                    if time.monotonic()-started>a.execution_seconds:raise TimeoutError('region native execution deadline')
                    time.sleep(2)
            words=struct.unpack('<6I',boot.dump(boot.work+74*4,24))
            if link:raw=b''
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
                if not (observed['nicStarted']==observed['wiped' if klink else 'completed']==observed['canary']==1 and observed['terminal']==2 and observed['nativeErrors']==0):
                    raise AssertionError('link mutation did not complete normally')
                if link_good:raise AssertionError('link mutation escaped real packet controls')
                state['state']='DETECTED_NATIVE_LINK_MUTATION'
            else:
                if not link_good:raise AssertionError('native UDP link/control mismatch: '+str(state['linkResult']['violations']))
                state['state']='PASS_NATIVE_OS_KEKKAI_LINK' if klink else 'PASS_NATIVE_OS_UDP_LINK'
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
    p.add_argument('--component',choices=['blake2s','chacha','x25519','ik','datagram','udp-link','kekkai-link','ed25519'],default='blake2s')
    p.add_argument('--execution-seconds',type=float,default=3600)
    p.add_argument('--mutation',choices=[*MUTATIONS,*CHACHA_MUTATIONS,*X25519_MUTATIONS,*IK_MUTATIONS,*DATAGRAM_MUTATIONS,*UDP_LINK_MUTATIONS,*KEKKAI_LINK_MUTATIONS,*ED_MUTATIONS])
    main(p.parse_args())
