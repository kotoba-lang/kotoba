"""RFC 8439 ChaCha20, Poly1305 and AEAD_CHACHA20_POLY1305 in Python, the oracle for the native gate.

Dev tool, not part of the library. Standard library only, written from RFC 8439
sections 2.1-2.8. It reproduces the RFC's published values, and OpenSSL 4.0.3 agreed
(`enc -chacha20` on section 2.4.2, `mac POLY1305` on 2.5.2 and Appendix A.3 #5-#9).
tools/gen_gate.py uses it to write kotoba/chacha20/native_gate.kotoba. Not constant
time; never use it to protect a secret.
"""
M32 = 0xFFFFFFFF
def rotl(x, n): return ((x << n) | (x >> (32 - n))) & M32
def qr(s, a, b, c, d):
    s[a] = (s[a] + s[b]) & M32; s[d] = rotl(s[d] ^ s[a], 16)
    s[c] = (s[c] + s[d]) & M32; s[b] = rotl(s[b] ^ s[c], 12)
    s[a] = (s[a] + s[b]) & M32; s[d] = rotl(s[d] ^ s[a], 8)
    s[c] = (s[c] + s[d]) & M32; s[b] = rotl(s[b] ^ s[c], 7)
def le32(b, o): return int.from_bytes(b[o:o + 4], 'little')
def block(key, counter, nonce):
    s = [0x61707865, 0x3320646e, 0x79622d32, 0x6b206574] + [le32(key, 4 * i) for i in range(8)] + [counter] + [le32(nonce, 4 * i) for i in range(3)]
    w = list(s)
    for _ in range(10):
        qr(w, 0, 4, 8, 12); qr(w, 1, 5, 9, 13); qr(w, 2, 6, 10, 14); qr(w, 3, 7, 11, 15)
        qr(w, 0, 5, 10, 15); qr(w, 1, 6, 11, 12); qr(w, 2, 7, 8, 13); qr(w, 3, 4, 9, 14)
    return b''.join(((w[i] + s[i]) & M32).to_bytes(4, 'little') for i in range(16))
def encrypt(key, counter, nonce, data):
    out = bytearray()
    for j in range(0, len(data), 64):
        ks = block(key, counter + j // 64, nonce)
        out += bytes(a ^ b for a, b in zip(data[j:j + 64], ks))
    return bytes(out)
def poly1305(key, msg):
    r = int.from_bytes(key[:16], 'little') & 0x0ffffffc0ffffffc0ffffffc0fffffff
    s = int.from_bytes(key[16:], 'little'); p = (1 << 130) - 5; acc = 0
    for j in range(0, len(msg), 16):
        n = int.from_bytes(msg[j:j + 16] + b'\x01', 'little')
        acc = (acc + n) * r % p
    return ((acc + s) & ((1 << 128) - 1)).to_bytes(16, 'little')
def pad16(b): return bytes((16 - len(b) % 16) % 16)
def mac_data(aad, ct): return aad + pad16(aad) + ct + pad16(ct) + len(aad).to_bytes(8, 'little') + len(ct).to_bytes(8, 'little')
def seal(key, nonce, aad, pt):
    otk = block(key, 0, nonce)[:32]; ct = encrypt(key, 1, nonce, pt)
    return ct + poly1305(otk, mac_data(aad, ct))
def open_(key, nonce, aad, sealed):
    ct, tag = sealed[:-16], sealed[-16:]
    if poly1305(block(key, 0, nonce)[:32], mac_data(aad, ct)) != tag: return None
    return encrypt(key, 1, nonce, ct)
