#!/usr/bin/env python3
"""Host oracle for the kernel ML-DSA-65 polynomial module (aiueos.mldsa-ntt, JUN-813 stage 2).

Implements FIPS 204 Algorithms 41 and 42 with a table-free zeta (1753^BitRev8(m) mod q), the way the kernel module does, and
checks it against a schoolbook negacyclic product. The QEMU gate compares the guest's polynomials with these values.
"""
Q = 8380417
ZETA = 1753


def brv8(m):
    return int(format(m, "08b")[::-1], 2)


def zeta(m):
    return pow(ZETA, brv8(m), Q)


def ntt(f):
    w = list(f)
    m, length = 0, 128
    while length >= 1:
        for start in range(0, 256, 2 * length):
            m += 1
            z = zeta(m)
            for j in range(start, start + length):
                t = z * w[j + length] % Q
                w[j + length] = (w[j] - t) % Q
                w[j] = (w[j] + t) % Q
        length //= 2
    return w


def intt(f):
    w = list(f)
    m, length = 256, 1
    while length < 256:
        for start in range(0, 256, 2 * length):
            m -= 1
            z = -zeta(m) % Q
            for j in range(start, start + length):
                t = w[j]
                w[j] = (t + w[j + length]) % Q
                w[j + length] = z * (t - w[j + length]) % Q
        length *= 2
    return [x * 8347681 % Q for x in w]


def mul(a, b):
    return [x * y % Q for x, y in zip(a, b)]


def schoolbook(a, b):
    out = [0] * 256
    for i in range(256):
        for j in range(256):
            k = i + j
            if k < 256:
                out[k] = (out[k] + a[i] * b[j]) % Q
            else:
                out[k - 256] = (out[k - 256] - a[i] * b[j]) % Q
    return out


def poly_p():
    return [(i * i * 1237 + i * 91 + 17) % Q for i in range(256)]


def poly_q():
    return [(i * 7919 + 31) % Q for i in range(256)]


def checksum(poly):
    return sum(c * (i + 1) for i, c in enumerate(poly))


def cases():
    p, q = poly_p(), poly_q()
    np_, nq = ntt(p), ntt(q)
    prod = intt(mul(np_, nq))
    assert prod == schoolbook(p, q), "NTT product differs from the schoolbook negacyclic product"
    assert intt(np_) == p, "inverse NTT does not undo the forward NTT"
    return [("ntt-p", np_), ("ntt-q", nq), ("mul", mul(np_, nq)), ("intt-product", prod), ("roundtrip", intt(np_))]


if __name__ == "__main__":
    for name, poly in cases():
        print(name, poly[:4], checksum(poly))
