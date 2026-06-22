"""Number-theory helpers for building large-bit-width Shor instances.

The point of these utilities is to *construct* semiprimes ``N = p*q`` of arbitrary
bit-width together with a base ``a`` of a chosen (small) multiplicative order.
That is the only regime in which a tensor network can factor a large N: the bond
dimension is exactly the order ``r``, so ``r`` must be kept small.  Crucially,
finding such a small-order base for a *given* RSA modulus requires already
knowing its factorisation -- which is the whole circularity of the approach.
"""

from __future__ import annotations

import math
import random


def is_prime(n, rounds=40):
    """Deterministic-for-small / Miller-Rabin primality test."""
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d = n - 1
    s = 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for _ in range(rounds):
        a = random.randrange(2, n - 1)
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(s - 1):
            x = (x * x) % n
            if x == n - 1:
                break
        else:
            return False
    return True


def random_prime(bits):
    while True:
        n = random.getrandbits(bits) | (1 << (bits - 1)) | 1
        if is_prime(n):
            return n


def random_prime_1_mod_d(bits, d):
    """Random prime ``p`` of ~``bits`` bits with ``p ≡ 1 (mod d)``.

    Such a prime has an order-``d`` subgroup in ``Z_p^*``.
    """
    if d < 1:
        raise ValueError("d must be >= 1")
    lo = ((1 << (bits - 1)) + d - 1) // d        # smallest k with k*d+1 >= 2^(bits-1)
    hi = ((1 << bits) - 1) // d                   # largest  k with k*d+1 <  2^bits
    if hi < lo:
        raise ValueError(f"no {bits}-bit number ≡ 1 mod {d}")
    for _ in range(400000):
        k = random.randint(lo, hi)
        p = k * d + 1
        if p.bit_length() == bits and is_prime(p):
            return p
    raise RuntimeError(f"no prime of {bits} bits ≡ 1 mod {d} found")


def prime_factors(n):
    """Distinct prime factors of a small/medium n (trial division + Pollard rho)."""
    fs = set()
    while n % 2 == 0:
        fs.add(2)
        n //= 2
    d = 3
    while d * d <= n and d < (1 << 20):
        while n % d == 0:
            fs.add(d)
            n //= d
        d += 2
    if n > 1:
        if is_prime(n):
            fs.add(n)
        else:
            f = _pollard_rho(n)
            fs |= prime_factors(f)
            fs |= prime_factors(n // f)
    return fs


def _pollard_rho(n):
    if n % 2 == 0:
        return 2
    while True:
        x = random.randrange(2, n)
        y = x
        c = random.randrange(1, n)
        d = 1
        while d == 1:
            x = (x * x + c) % n
            y = (y * y + c) % n
            y = (y * y + c) % n
            d = math.gcd(abs(x - y), n)
        if d != n:
            return d


def order_mod_prime(a, p):
    """Multiplicative order of ``a`` modulo prime ``p`` (needs p-1 factored)."""
    a %= p
    if a == 0:
        raise ValueError("a divisible by p")
    order = p - 1
    for q in prime_factors(p - 1):
        while order % q == 0 and pow(a, order // q, p) == 1:
            order //= q
    return order


def element_of_order(p, d):
    """Return an element of ``Z_p^*`` of order exactly ``d`` (requires d | p-1)."""
    if (p - 1) % d != 0:
        raise ValueError("d must divide p-1")
    cofactor = (p - 1) // d
    for _ in range(100000):
        g = random.randrange(2, p - 1)
        h = pow(g, cofactor, p)
        if h <= 1:
            continue
        if order_mod_prime(h, p) == d:
            return h
    raise RuntimeError("could not find element of requested order")


def crt(residues, moduli):
    """Chinese Remainder Theorem solve."""
    x = 0
    M = 1
    for m in moduli:
        M *= m
    for r, m in zip(residues, moduli):
        Mi = M // m
        x = (x + r * Mi * pow(Mi, -1, m)) % M
    return x


def order_mod_n(a, factorization):
    """Order of ``a`` mod N given the prime factorisation dict {p: exponent}."""
    order = 1
    for p, e in factorization.items():
        pe = p ** e
        # order mod p^e ; for our instances e==1
        op = order_mod_prime(a, p)
        order = order * op // math.gcd(order, op)
    return order


def _v2(n):
    """2-adic valuation of n."""
    v = 0
    while n % 2 == 0:
        n //= 2
        v += 1
    return v


def largest_prime_factor(n):
    return max(prime_factors(n))


def random_safe_prime(bits):
    """Safe prime ``p = 2*p' + 1`` with ``p'`` also prime (strong RSA prime)."""
    while True:
        pp = random_prime(bits - 1)
        p = 2 * pp + 1
        if p.bit_length() == bits and is_prime(p):
            return p


_SMALL_PRIMES = [p for p in range(2, 4096) if is_prime(p)]


def random_smooth_prime(bits, smooth_bound):
    """Prime ``p`` with ``p-1`` ``smooth_bound``-smooth (weak RSA prime).

    Such a prime falls to Pollard's p-1 with bound ``smooth_bound``.
    """
    pool = [p for p in _SMALL_PRIMES if p <= smooth_bound]
    for _ in range(200000):
        m = 2
        while m.bit_length() < bits - 1:
            m *= random.choice(pool)
        m *= 2  # keep p-1 even
        p = m + 1
        if p.bit_length() == bits and is_prime(p):
            return p
    raise RuntimeError("no smooth prime found; raise smooth_bound")


def pollard_p_minus_1(N, B):
    """Classical Pollard p-1 (stage 1).  Returns a nontrivial factor or None.

    Succeeds when some prime factor ``p`` of ``N`` has ``p-1`` ``B``-smooth -- the
    exact weak-key class that the tensor-network 'small order' route also needs.
    """
    a = 2
    for q in _SMALL_PRIMES:
        if q > B:
            break
        qk = q
        while qk * q <= B:
            qk *= q
        a = pow(a, qk, N)
        g = math.gcd(a - 1, N)
        if 1 < g < N:
            return g
    g = math.gcd(a - 1, N)
    return g if 1 < g < N else None


def make_small_order_instance(bits, order_p, order_q):
    """Build a *factorable* ``N = p*q`` (~``bits`` bits) with base ``a``.

    ``a`` has order ``order_p`` mod ``p`` and ``order_q`` mod ``q``, so
    ``r = ord_N(a) = lcm(order_p, order_q)``.  For Shor's `gcd(a^{r/2} ± 1, N)`
    to yield a nontrivial factor we need ``a^{r/2} ≢ -1 (mod N)``, which holds
    iff the two orders have **different 2-adic valuations** (then ``a^{r/2}`` is
    ``-1`` modulo one prime and ``+1`` modulo the other).  Returns
    ``(N, a, r, (p, q))``.
    """
    r = order_p * order_q // math.gcd(order_p, order_q)  # lcm
    if r % 2 != 0:
        raise ValueError("lcm(order_p, order_q) must be even")
    if _v2(order_p) == _v2(order_q):
        raise ValueError(
            "orders must have different 2-adic valuations, else a^(r/2) == -1 mod N "
            "(useless for factoring)")
    half = bits // 2
    for _ in range(2000):
        p = random_prime_1_mod_d(half, order_p)
        q = random_prime_1_mod_d(bits - half, order_q)
        if p == q:
            continue
        ap = element_of_order(p, order_p)
        aq = element_of_order(q, order_q)
        a = crt([ap, aq], [p, q])
        N = p * q
        if (order_mod_n(a, {p: 1, q: 1}) == r and math.gcd(a, N) == 1
                and pow(a, r // 2, N) != N - 1):
            return N, a, r, (p, q)
    raise RuntimeError("failed to build a factorable small-order instance")
