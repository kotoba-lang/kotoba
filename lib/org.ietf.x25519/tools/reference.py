"""RFC 7748 X25519 in Python (big integers), the oracle for the native gate.

Dev tool, not part of the library. Standard library only. Written from RFC 7748
section 5; it reproduces the RFC's published values, and OpenSSL 4.0.3
`pkeyutl -derive` agreed on section 5.2's second vector and section 6.1's
shared secret. tools/gen_gate.py uses it to write kotoba/x25519/native_gate.kotoba.
Not constant time; never use it to protect a secret.
"""
P = 2**255 - 19
A24 = 121665
def clamp(k):
    k = bytearray(k); k[0] &= 248; k[31] &= 127; k[31] |= 64; return bytes(k)
def x25519(k, u):
    k = int.from_bytes(clamp(k), 'little')
    x1 = int.from_bytes(u, 'little') & ((1 << 255) - 1)
    x2, z2, x3, z3, swap = 1, 0, x1, 1, 0
    for t in range(254, -1, -1):
        kt = (k >> t) & 1
        swap ^= kt
        if swap: x2, x3, z2, z3 = x3, x2, z3, z2
        swap = kt
        A = (x2 + z2) % P; AA = A * A % P; B = (x2 - z2) % P; BB = B * B % P; E = (AA - BB) % P
        C = (x3 + z3) % P; D = (x3 - z3) % P; DA = D * A % P; CB = C * B % P
        x3 = (DA + CB) ** 2 % P; z3 = x1 * (DA - CB) ** 2 % P
        x2 = AA * BB % P; z2 = E * (AA + A24 * E) % P
    if swap: x2, x3, z2, z3 = x3, x2, z3, z2
    return (x2 * pow(z2, P - 2, P) % P).to_bytes(32, 'little')
