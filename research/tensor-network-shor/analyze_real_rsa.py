#!/usr/bin/env python3
"""Analyze ACTUAL RSA with the tensor-network machinery -- honestly.

This does not (and cannot) factor a real RSA key.  Instead it answers, rigorously
and with running code, three questions a cryptanalyst actually cares about:

  1. What would the tensor-network Shor simulation cost on the real RSA Challenge
     sizes (RSA-100 ... RSA-2048)?  (resource wall)
  2. Where is the *empirical* feasibility frontier on genuinely random RSA-form
     keys (random base, full control register -- no engineering)?  (real crossover)
  3. WHICH real RSA keys can this method touch, and how does that compare to the
     classical Pollard p-1 attack?  (the security criterion)

Run:  python3 analyze_real_rsa.py
"""

import math
import random
import time

import numpy as np

from tnshor.scalable import (
    build_shor_mps_exact, factor_scalable, mps_bytes,
)
from tnshor.shor import choose_t, work_qubits
from tnshor.numtheory import (
    random_prime, random_safe_prime, random_smooth_prime, order_mod_n,
    largest_prime_factor, pollard_p_minus_1,
)


def hr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


# ---------------------------------------------------------------------------
# 1. Resource wall on the real RSA Challenge sizes
# ---------------------------------------------------------------------------
RSA_CHALLENGES = [
    # (name, bit-length, classical status)
    ("RSA-100", 330, "factored 1991 (GNFS)"),
    ("RSA-129", 426, "factored 1994"),
    ("RSA-512", 512, "factored 1999 (GNFS)"),
    ("RSA-768", 768, "factored 2009 (GNFS)"),
    ("RSA-250", 829, "factored 2020 (GNFS)"),
    ("RSA-1024", 1024, "OPEN"),
    ("RSA-2048", 2048, "OPEN"),
]


def demo_resource_wall():
    hr("1. Tensor-network Shor cost on the real RSA Challenge sizes")
    print("  Best case for the attacker: chi = r ~ 2^(bits-1) (a maximal-order base).")
    print("  MPS memory = n * 2 * chi^2 * 16 bytes,  n = 3*bits qubits.\n")
    print(f"  {'challenge':>9} {'bits':>5} {'qubits':>7} {'log2(chi)':>9} "
          f"{'log2(bytes)':>11} {'classical status':>22}")
    for name, bits, status in RSA_CHALLENGES:
        n = 3 * bits
        log2_chi = bits - 1
        log2_mem = math.log2(n) + 1 + 2 * log2_chi + 4
        print(f"  {name:>9} {bits:>5} {n:>7} {log2_chi:>9} {log2_mem:>11.0f} "
              f"{status:>22}")
    print("\n  Reference scales: ~2^266 atoms in the observable universe; ~2^155 ns")
    print("  since the Big Bang.  RSA-2048 needs ~2^4108 bytes -- not a hardware")
    print("  problem, a mathematical impossibility for this representation.")


# ---------------------------------------------------------------------------
# 2. Empirical feasibility frontier on genuinely RANDOM RSA-form keys
# ---------------------------------------------------------------------------
def demo_random_frontier(mem_budget_gb=2.0):
    hr("2. Empirical frontier: genuinely random keys, random base, full register")
    print("  No engineering: random primes, random base, full t = 2*log2(N).")
    print(f"  Attempt the real MPS Shor when the estimated memory < {mem_budget_gb} GB.\n")
    print(f"  {'bits':>5} {'N':>16} {'r=ord_N(a)':>12} {'log2(r)':>8} "
          f"{'est.mem':>10} {'result':>22}")
    random.seed(2024)
    for bits in [8, 10, 12, 14, 16, 20, 24]:
        half = bits // 2
        p = random_prime(half)
        q = random_prime(bits - half)
        while q == p:
            q = random_prime(bits - half)
        N = p * q
        # standard Shor base acceptance: r even and a^{r/2} != -1 (retry otherwise)
        a = r = None
        for _ in range(50):
            cand = random.randrange(2, N - 1)
            if math.gcd(cand, N) != 1:
                continue
            rc = order_mod_n(cand, {p: 1, q: 1})
            if rc % 2 == 0 and pow(cand, rc // 2, N) != N - 1:
                a, r = cand, rc
                break
        if a is None:
            continue
        t = choose_t(N)
        n = t + work_qubits(N)
        # cost is dominated by chi = r (build) and ~2^(0.6 t) (QFT)
        chi_est = max(r, int(2 ** (0.6 * t)))
        est = mps_bytes(n, chi_est)
        est_gb = est / 1e9
        if est_gb <= mem_budget_gb:
            t0 = time.time()
            res = factor_scalable(N, a, t=t, shots=200, seed=1)
            dt = time.time() - t0
            ok = res['success'] and {p, q} == set(res['factors'] or ())
            result = f"{'FACTORED' if ok else 'failed'} {dt:.1f}s peak={res['peak_bond_qft']}"
        else:
            result = f"infeasible (~{est_gb:.0e} GB)"
        print(f"  {bits:>5} {N:>16} {r:>12} {math.log2(r):>8.2f} "
              f"{est_gb:>9.2f}G {result:>22}")
    print("\n  The frontier is ~10 bits on a laptop (a few GB): a *random* key's order")
    print("  is ~N, so chi=r AND the full-t QFT bond both blow the budget almost at")
    print("  once. This is the honest reach on real (un-engineered) RSA-form numbers.")


# ---------------------------------------------------------------------------
# 3. Which real keys are vulnerable?  vs classical Pollard p-1
# ---------------------------------------------------------------------------
def analyze_key(label, p, q):
    N = p * q
    lam = math.lcm(p - 1, q - 1)
    lpf = max(largest_prime_factor(p - 1), largest_prime_factor(q - 1))
    # order of a few random bases (typical r for this key)
    random.seed(99)
    best = 1
    for _ in range(8):
        while True:
            a = random.randrange(2, N - 1)
            if math.gcd(a, N) == 1:
                break
        best = max(best, order_mod_n(a, {p: 1, q: 1}))
    # classical attack
    t0 = time.time()
    fac = pollard_p_minus_1(N, B=70000)
    dt = time.time() - t0
    print(f"\n  {label}: N = {N} ({N.bit_length()} bit)")
    print(f"    largest prime factor of p-1 / q-1 : {lpf}  ({lpf.bit_length()} bit)")
    print(f"    typical random-base order r        : {best}  (log2 = {math.log2(best):.1f})")
    print(f"    => tensor-network chi = r          : ~2^{math.log2(best):.0f}  "
          f"({'feasible' if best < 5000 else 'INFEASIBLE'})")
    print(f"    classical Pollard p-1 (B=70000)    : "
          f"{'FACTORED ' + str(fac) if fac else 'failed'}  ({dt*1000:.0f} ms)")


def demo_vulnerability():
    hr("3. Which real RSA keys are vulnerable?  (tensor-network vs Pollard p-1)")
    print("  Two 64-bit keys: a STRONG one (safe primes) and a WEAK one (smooth p-1).")
    random.seed(7)
    # strong: safe primes p = 2p'+1
    ps, qs = random_safe_prime(32), random_safe_prime(32)
    while qs == ps:
        qs = random_safe_prime(32)
    analyze_key("STRONG (safe primes)", ps, qs)
    # weak: p-1, q-1 are 4096-smooth
    pw, qw = random_smooth_prime(32, 4096), random_smooth_prime(32, 4096)
    while qw == pw:
        qw = random_smooth_prime(32, 4096)
    analyze_key("WEAK   (smooth p-1)  ", pw, qw)
    print("""
  Reading:
   * STRONG key: every nontrivial base's order is divisible by a ~31-bit prime
     (p' or q'), so chi = r >= 2^31 (typically ~2^61) -- infeasible -- AND
     Pollard p-1 fails (no smooth p-1 to exploit).
   * WEAK key: p-1 is smooth, so Pollard p-1 factors it in milliseconds -- no
     quantum simulation involved. The tensor-network 'small order' route needs a
     base built from p and q (circular), so it adds NOTHING over Pollard here.
   * Net: the method's reach on real RSA = the classical smooth-key reach. Keys
     generated with safe / strong primes (the standard) are immune to both.""")


def main():
    np.set_printoptions(precision=4, suppress=True)
    demo_resource_wall()
    demo_random_frontier()
    demo_vulnerability()
    hr("Conclusion -- analyzing actual RSA")
    print("""  * On the real RSA Challenge sizes the tensor-network Shor simulation needs
    astronomically impossible memory (RSA-2048 ~ 2^4108 bytes): no break.
  * On genuinely random RSA-form keys the honest laptop frontier is ~10 bits,
    because a random base has order r ~ N and the bond dimension is chi = r.
  * The only large keys the method can touch are those with a small-order base,
    which either requires already knowing p, q (circular) or a smooth p-1/q-1
    that classical Pollard p-1 already breaks for free.
  => Tensor networks do not provide a new attack on properly generated RSA.
     They re-express the hardness as 'the period r is exponentially large',
     which is exactly why RSA is secure.""")


if __name__ == "__main__":
    main()
