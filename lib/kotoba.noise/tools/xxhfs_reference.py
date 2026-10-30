"""Noise XX and XXhfs (noise_hfs_spec 025f0f60) in Python, the oracle for the native XXhfs gate.

Dev tool, not part of the library. Python standard library plus the `openssl` command
(4.x) for ML-KEM-768, which this reference calls rather than reimplements:
  keyGen from the FIPS 203 seed d || z: `openssl genpkey -algorithm ML-KEM-768 -pkeyopt hexseed:...`
  deterministic encapsulation with m:   `openssl pkeyutl -encap -pkeyopt hexikme:...`
  decapsulation:                         `openssl pkeyutl -decap`
X25519 and ChaCha20-Poly1305 come from the sibling libraries' Python references
(../../org.ietf.x25519/tools/reference.py, ../../org.ietf.chacha20Poly1305/tools/
reference.py), each checked against its RFC. The classical path is checked here against
the Cacophony XX vector before the hfs path is used (see `self_check`). Not constant
time; never use it to protect a secret.
"""
import hashlib
import hmac
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(os.path.dirname(HERE))
for d in ('org.ietf.x25519', 'org.ietf.chacha20Poly1305'):
    sys.path.insert(0, os.path.join(LIB, d, 'tools'))
import importlib.util  # noqa: E402

def _load(lib, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(LIB, lib, 'tools', 'reference.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
X = _load('org.ietf.x25519', 'x25519_ref')
C = _load('org.ietf.chacha20Poly1305', 'chacha_ref')
NINE = bytes([9]) + bytes(31)

# --- ML-KEM-768 through openssl -----------------------------------------------------
def _run(*args, stdin=None):
    return subprocess.run(['openssl', *args], input=stdin, capture_output=True, check=True).stdout

class MLKEM:
    def __init__(self, workdir):
        self.dir = workdir
    def _key(self, dz):
        pem = os.path.join(self.dir, dz.hex()[:16] + '.pem')
        if not os.path.exists(pem):
            _run('genpkey', '-algorithm', 'ML-KEM-768', '-pkeyopt', 'hexseed:' + dz.hex(), '-out', pem)
        return pem
    def ek(self, dz):
        der = _run('pkey', '-in', self._key(dz), '-pubout', '-outform', 'DER')
        return der[-1184:]
    def _spki(self, ek):
        # the SPKI DER of a generated key, with its 1184-byte key replaced
        template = _run('pkey', '-in', self._key(bytes(64)), '-pubout', '-outform', 'DER')
        path = os.path.join(self.dir, 'ek-' + hashlib.sha256(ek).hexdigest()[:16] + '.der')
        open(path, 'wb').write(template[:-1184] + ek)
        return path
    def encaps(self, ek, m):
        ct = os.path.join(self.dir, 'ct.bin'); ss = os.path.join(self.dir, 'ss.bin')
        _run('pkeyutl', '-encap', '-inkey', self._spki(ek), '-pubin', '-keyform', 'DER',
             '-pkeyopt', 'hexikme:' + m.hex(), '-out', ct, '-secret', ss)
        return open(ct, 'rb').read(), open(ss, 'rb').read()
    def decaps(self, dz, ct):
        cf = os.path.join(self.dir, 'ct-in.bin'); ss = os.path.join(self.dir, 'ss-out.bin')
        open(cf, 'wb').write(ct)
        _run('pkeyutl', '-decap', '-inkey', self._key(dz), '-in', cf, '-secret', ss)
        return open(ss, 'rb').read()

# --- Noise (rev 34) ------------------------------------------------------------------
def hkdf2(ck, ikm):
    temp = hmac.new(ck, ikm, hashlib.sha256).digest()
    o1 = hmac.new(temp, b'\x01', hashlib.sha256).digest()
    return o1, hmac.new(temp, o1 + b'\x02', hashlib.sha256).digest()
def nonce(n): return bytes(4) + n.to_bytes(8, 'little')

class Side:
    PATTERNS = {'XX': ([['e'], ['e', 'ee', 's', 'es'], ['s', 'se']], b'Noise_XX_25519_ChaChaPoly_SHA256'),
                'XXhfs': ([['e', 'e1'], ['e', 'ee', 'ekem1', 's', 'es'], ['s', 'se']],
                          b'Noise_XXhfs_25519+MLKEM768_ChaChaPoly_SHA256')}
    def __init__(self, pattern, initiator, s, e, prologue, kem=None, dz=None, m=None):
        self.msgs, name = self.PATTERNS[pattern]
        self.h = name if len(name) == 32 else hashlib.sha256(name).digest()
        self.ck, self.k, self.n = self.h, None, 0
        self.init, self.s, self.e = initiator, s, e
        self.spub, self.epub = X.x25519(s, NINE), X.x25519(e, NINE)
        self.rs = self.re = self.re1 = None
        self.kem, self.dz, self.m = kem, dz, m
        self.i = 0
        self.mix_hash(prologue)
    def mix_hash(self, d): self.h = hashlib.sha256(self.h + d).digest()
    def mix_key(self, ikm): self.ck, self.k = hkdf2(self.ck, ikm); self.n = 0
    def enc_hash(self, pt):
        if self.k is None:
            ct = pt
        else:
            ct = C.seal(self.k, nonce(self.n), self.h, pt); self.n += 1
        self.mix_hash(ct); return ct
    def dec_hash(self, ct):
        if self.k is None:
            pt = ct
        else:
            pt = C.open_(self.k, nonce(self.n), self.h, ct); assert pt is not None; self.n += 1
        self.mix_hash(ct); return pt
    def dh(self, tok):
        a, b = {'ee': (self.e, self.re), 'es': (self.e, self.rs) if self.init else (self.s, self.re),
                'se': (self.s, self.re) if self.init else (self.e, self.rs)}[tok]
        return X.x25519(a, b)
    def write(self, payload):
        out = b''
        for tok in self.msgs[self.i]:
            if tok == 'e': out += self.epub; self.mix_hash(self.epub)
            elif tok == 's': out += self.enc_hash(self.spub)
            elif tok == 'e1': out += self.enc_hash(self.kem.ek(self.dz))
            elif tok == 'ekem1':
                ct, ss = self.kem.encaps(self.re1, self.m); out += self.enc_hash(ct); self.mix_key(ss)
            else: self.mix_key(self.dh(tok))
        out += self.enc_hash(payload); self._advance(); return out
    def read(self, msg):
        pos = 0
        for tok in self.msgs[self.i]:
            if tok == 'e': self.re = msg[pos:pos + 32]; self.mix_hash(self.re); pos += 32
            elif tok in ('s', 'e1', 'ekem1'):
                n = {'s': 32, 'e1': 1184, 'ekem1': 1088}[tok] + (16 if self.k else 0)
                v = self.dec_hash(msg[pos:pos + n]); pos += n
                if tok == 's': self.rs = v
                elif tok == 'e1': self.re1 = v
                else: self.mix_key(self.kem.decaps(self.dz, v))
            else: self.mix_key(self.dh(tok))
        pt = self.dec_hash(msg[pos:]); self._advance(); return pt
    def _advance(self):
        self.i += 1
        if self.i == len(self.msgs):
            t1, t2 = hkdf2(self.ck, b'')
            self.send, self.recv = (t1, t2) if self.init else (t2, t1)
            self.sn = self.rn = 0
    def t_encrypt(self, pt):
        ct = C.seal(self.send, nonce(self.sn), b'', pt); self.sn += 1; return ct
    def t_decrypt(self, ct):
        pt = C.open_(self.recv, nonce(self.rn), b'', ct); assert pt is not None; self.rn += 1; return pt

def run(pattern, keys, payloads, kem=None, kem_init=None, kem_resp=None):
    """Both sides through the handshake then transport; -> (messages, handshake hash)."""
    i = Side(pattern, True, keys['is'], keys['ie'], keys['prologue'], kem, *(kem_init or (None, None)))
    r = Side(pattern, False, keys['rs'], keys['re'], keys['prologue'], kem, *(kem_resp or (None, None)))
    out = []
    for j, p in enumerate(payloads):
        a, b = (i, r) if j % 2 == 0 else (r, i)
        if j < 3:
            c = a.write(p); assert b.read(c) == p
        else:
            c = a.t_encrypt(p); assert b.t_decrypt(c) == p
        out.append(c)
    assert i.h == r.h
    return out, i.h

def self_check(vector):
    """The classical path must reproduce the Cacophony XX vector byte for byte."""
    keys = dict(prologue=bytes.fromhex(vector['prologue']), **{k: bytes.fromhex(vector[k]) for k in ('is', 'ie', 'rs', 're')})
    msgs, hh = run('XX', keys, [bytes.fromhex(p) for p, _ in vector['msgs']])
    assert [m.hex() for m in msgs] == [c for _, c in vector['msgs']] and hh.hex() == vector['hh']

def workdir():
    return tempfile.mkdtemp(prefix='xxhfs-')
