"""AES (FIPS 197) and AES-GCM (NIST SP 800-38D) in Python, the oracle for the native gate.

Dev tool, not part of the library. Standard library only, written from the two
standards. It reproduces FIPS 197 Appendix C and passes all 316 cases of
test/aes/wycheproof_gcm.cljk (229 valid, 87 invalid). tools/gen_gate.py uses it to
write kotoba/aes/native_gate.kotoba. Not constant time; never use it to protect a
secret.
"""
def _xt(a): return ((a << 1) ^ 0x1B) & 0xFF if a & 0x80 else a << 1
def _mul(a, b):
    r = 0
    while b:
        if b & 1: r ^= a
        a = _xt(a); b >>= 1
    return r
def _inv(a):
    if a == 0: return 0
    r = 1
    for _ in range(254): r = _mul(r, a)
    return r
def _sbox(a):
    b = _inv(a); s = b
    for i in range(1, 5): s ^= ((b << i) | (b >> (8 - i))) & 0xFF
    return s ^ 0x63
SBOX = [_sbox(i) for i in range(256)]

def expand(key):
    nk = len(key) // 4; nr = nk + 6
    w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
    rcon = 1
    for i in range(nk, 4 * (nr + 1)):
        t = list(w[i - 1])
        if i % nk == 0:
            t = [SBOX[b] for b in t[1:] + t[:1]]; t[0] ^= rcon; rcon = _xt(rcon)
        elif nk > 6 and i % nk == 4:
            t = [SBOX[b] for b in t]
        w.append([a ^ b for a, b in zip(w[i - nk], t)])
    return w, nr

def encrypt_block(key, block):
    w, nr = expand(key)
    s = [block[i] ^ w[i // 4][i % 4] for i in range(16)]
    for r in range(1, nr + 1):
        s = [SBOX[b] for b in s]
        s = [s[(i + 4 * (i % 4)) % 16] for i in range(16)]  # ShiftRows (column-major)
        if r != nr:
            out = []
            for c in range(4):
                a = s[4 * c:4 * c + 4]
                out += [_mul(a[0], 2) ^ _mul(a[1], 3) ^ a[2] ^ a[3], a[0] ^ _mul(a[1], 2) ^ _mul(a[2], 3) ^ a[3],
                        a[0] ^ a[1] ^ _mul(a[2], 2) ^ _mul(a[3], 3), _mul(a[0], 3) ^ a[1] ^ a[2] ^ _mul(a[3], 2)]
            s = out
        s = [s[i] ^ w[4 * r + i // 4][i % 4] for i in range(16)]
    return bytes(s)

R = 0xE1 << 120
def gmul(x, y):
    z, v = 0, y
    for i in range(127, -1, -1):
        if (x >> i) & 1: z ^= v
        v = (v >> 1) ^ R if v & 1 else v >> 1
    return z
def ghash(h, data):
    y = 0
    for j in range(0, len(data), 16):
        y = gmul(y ^ int.from_bytes(data[j:j + 16].ljust(16, b'\0'), 'big'), h)
    return y
def _pad(b): return b + bytes((16 - len(b) % 16) % 16)
def _j0(key, iv):
    h = int.from_bytes(encrypt_block(key, bytes(16)), 'big')
    if len(iv) == 12: return h, iv + b'\0\0\0\1'
    s = _pad(iv) + bytes(8) + (8 * len(iv)).to_bytes(8, 'big')
    return h, ghash(h, s).to_bytes(16, 'big')
def _inc32(cb): return cb[:12] + ((int.from_bytes(cb[12:], 'big') + 1) & 0xFFFFFFFF).to_bytes(4, 'big')
def _gctr(key, icb, x):
    out = bytearray(); cb = icb
    for j in range(0, len(x), 16):
        ks = encrypt_block(key, cb); out += bytes(a ^ b for a, b in zip(x[j:j + 16], ks)); cb = _inc32(cb)
    return bytes(out)
def _tag(key, h, j0, aad, ct):
    s = _pad(aad) + _pad(ct) + (8 * len(aad)).to_bytes(8, 'big') + (8 * len(ct)).to_bytes(8, 'big')
    return _gctr(key, j0, ghash(h, s).to_bytes(16, 'big'))
def seal(key, iv, aad, pt):
    if len(key) not in (16, 24, 32) or len(iv) == 0: return None
    h, j0 = _j0(key, iv); ct = _gctr(key, _inc32(j0), pt)
    return ct + _tag(key, h, j0, aad, ct)
def open_(key, iv, aad, sealed):
    if len(key) not in (16, 24, 32) or len(iv) == 0 or len(sealed) < 16: return None
    ct, tag = sealed[:-16], sealed[-16:]
    h, j0 = _j0(key, iv)
    if _tag(key, h, j0, aad, ct) != tag: return None
    return _gctr(key, _inc32(j0), ct)
