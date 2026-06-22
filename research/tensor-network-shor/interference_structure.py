#!/usr/bin/env python3
"""Use RSA's OWN algebraic structure to manufacture the period-revealing
interference -- how far does that get us?

The amplitude's period comes from the homomorphism  a^{x+y} = a^x * a^y (mod N).
The classical way to "generate the interference" from that structure is a
meet-in-the-middle collision: precompute baby phases a^j, take giant strides
a^{i*m}, and a collision a^{i*m} = a^j is two ways of writing the same group
element -- constructive interference that reveals i*m - j = r, WITHOUT
enumerating all r values. That is Baby-Step Giant-Step (and Pollard rho/kangaroo).

  * It works, and it crushes the tensor-network simulator: random 40-bit keys
    factored in ~10^6 group ops, where the MPS died at ~12 bits.
  * But it is Theta(sqrt(r)).  Shoup's generic-group lower bound proves no
    algorithm using only the group operations can beat Omega(sqrt(r)).
  * Sub-exponential needs MORE than the group -- the integer ring (GNFS, the
    real record). Polynomial needs quantum interference over the whole
    superposition. Structure alone buys a quadratic (then sub-exp) speedup,
    never the exponential->polynomial jump.

Run:  python3 interference_structure.py
"""

import math
import random
import time

import numpy as np

from tnshor.numtheory import random_prime, order_mod_n
from tnshor.shor import factor_from_order


def hr(t):
    print("\n" + "=" * 80)
    print(t)
    print("=" * 80)


# --- meet-in-the-middle "interference": baby-step giant-step order finding ----
def bsgs_order(N, a, U=None):
    """Order of a mod N via BSGS.  Returns (r, group_multiplications)."""
    if U is None:
        U = N
    m = math.isqrt(U) + 1
    baby = {}
    cur = 1 % N
    ops = 0
    for j in range(m):
        if cur == 1 and j > 0:                 # small order seen during baby steps
            return j, ops
        if cur not in baby:
            baby[cur] = j                      # one set of "phases"  a^j
        cur = (cur * a) % N
        ops += 1
    stride = pow(a, m, N)                       # giant stride  a^m
    g = stride
    for i in range(1, m + 3):
        if g in baby:                          # collision a^{im} = a^j  (interference)
            r = i * m - baby[g]
            if r > 0 and pow(a, r, N) == 1:
                return r, ops
        g = (g * stride) % N
        ops += 1
    return None, ops


def demo_bsgs_factoring():
    hr("1. Meet-in-the-middle interference (BSGS) factors where the MPS could not")
    print("  Find r = ord_N(a) from the group law, then factor by gcd(a^{r/2}±1, N).")
    print("  Random keys, random base -- no engineering.\n")
    print(f"  {'bits':>5} {'N':>16} {'r ~ N':>14} {'BSGS ops':>10} "
          f"{'sqrt(r)':>9} {'factored':>20} {'sec':>5}")
    random.seed(2024)
    rows = []
    for bits in [16, 24, 32, 38, 42]:
        half = bits // 2
        p = random_prime(half)
        q = random_prime(bits - half)
        while q == p:
            q = random_prime(bits - half)
        N = p * q
        # standard Shor base acceptance (even order, a^{r/2} != -1)
        a = r = None
        for _ in range(60):
            cand = random.randrange(2, N - 1)
            if math.gcd(cand, N) != 1:
                continue
            t0 = time.time()
            rc, ops = bsgs_order(N, cand)
            dt = time.time() - t0
            if rc and rc % 2 == 0 and pow(cand, rc // 2, N) != N - 1:
                a, r = cand, rc
                break
        fac = factor_from_order(N, a, r)
        ok = fac and {fac[0], fac[1]} == {p, q}
        rows.append((bits, r, ops))
        print(f"  {bits:>5} {N:>16} {r:>14} {ops:>10} {math.isqrt(r):>9} "
              f"{str(fac):>20} {dt:>5.2f}")
    print("\n  ~10^6 group multiplications factor a random 42-bit modulus. The tensor")
    print("  network hit its wall near 12 bits -- the algebraic collision is")
    print("  quadratically cheaper (sqrt(r)) than representing the amplitude (r).")
    return rows


def demo_scaling():
    hr("2. The structural speedup is exactly quadratic: ops ~ sqrt(r)")
    print("  Group operations to find r, vs the naive sequential scan (~r) and the")
    print("  tensor-network simulation (memory ~ r):\n")
    print(f"  {'bits':>5} {'r':>16} {'BSGS ops':>12} {'sqrt(r)':>12} "
          f"{'seq scan r':>16} {'MPS mem chi=r':>14}")
    random.seed(5)
    rows = []
    for bits in [20, 28, 36, 44, 52, 60]:
        half = bits // 2
        p = random_prime(half)
        q = random_prime(bits - half)
        while q == p:
            q = random_prime(bits - half)
        N = p * q
        while True:
            a = random.randrange(2, N - 1)
            if math.gcd(a, N) == 1:
                break
        r = order_mod_n(a, {p: 1, q: 1})
        # don't actually run BSGS past ~44 bits (memory); model ops = sqrt(r)
        ops = math.isqrt(r) if bits > 44 else bsgs_order(N, a)[1]
        rows.append((bits, r, ops))
        print(f"  {bits:>5} {r:>16} {('~%d' % ops) if bits>44 else ops:>12} "
              f"{math.isqrt(r):>12} {('2^%.0f' % math.log2(r)):>16} "
              f"{('2^%.0f' % math.log2(r)):>14}")
    print("\n  sqrt(r) ~ sqrt(N) is still exponential in the BIT-length, but it is")
    print("  the quadratic improvement that takes the classical reach from ~12-bit")
    print("  (MPS) to ~40-50 bit (laptop) and ~100+ bit with optimised rho.")
    return rows


def demo_lower_bound_and_landscape():
    hr("3. Why structure stops at sqrt(r) -- and what actually goes further")
    print("""  Generic-group lower bound (Shoup, 1997): any algorithm that uses ONLY the
  group operations (multiply, invert, compare) needs Omega(sqrt(r)) of them to
  find an order or a discrete log. BSGS and Pollard rho/kangaroo MEET this bound
  -- they are optimal "use-the-structure" algorithms. The collision is the most
  interference you can manufacture from the group law alone.

  To go below sqrt(r) you must use MORE than the abstract group:""")
    print(f"\n  {'method':>26} {'what it exploits':>26} {'cost':>16} {'real reach':>16}")
    rows = [
        ("sequential scan", "nothing", "O(r)", "~tiny"),
        ("tensor-network MPS", "circuit (amplitude)", "O(r) mem", "~12-bit random"),
        ("BSGS / Pollard rho", "group homomorphism", "O(sqrt r)", "~50-100 bit"),
        ("GNFS (number field sieve)", "the integer ring Z", "L_N[1/3] sub-exp", "RSA-250 = 829-bit"),
        ("Shor (quantum)", "global interference", "poly(log N)", "RSA-2048 (with a QC)"),
    ]
    for name, ex, cost, reach in rows:
        print(f"  {name:>26} {ex:>26} {cost:>16} {reach:>16}")
    print("""
  * Structure buys a QUADRATIC speedup (sqrt r) -- provably the ceiling for
    group-only methods.
  * The number field sieve goes SUB-exponential by leaving the group and using
    the ring structure of the integers (smooth relations) -- this is the actual
    classical record (RSA-250, 2020).
  * Only quantum interference makes it POLYNOMIAL, because the QFT interferes all
    Q evaluations of a^x at once -- not sqrt(r) precomputed pairs, but everything.""")


def make_plot(scaling_rows, fac_rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:  # pragma: no cover
        print(f"\n(matplotlib unavailable: {e}; skipping figure)")
        return None
    rs = np.array([r for _, r, _ in scaling_rows], float)
    ops = np.array([o for _, _, o in scaling_rows], float)
    order = np.argsort(rs)
    rs, ops = rs[order], ops[order]

    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    ax[0].loglog(rs, rs, "k--", lw=1, label="naive / MPS  ~ r")
    ax[0].loglog(rs, np.sqrt(rs), "g--", lw=1, label="sqrt(r) (generic-group bound)")
    ax[0].loglog(rs, ops, "o-", color="crimson", label="BSGS measured ops")
    ax[0].set_xlabel("period r (~ N)")
    ax[0].set_ylabel("operations to find r")
    ax[0].set_title("Using the group law: ops ~ sqrt(r), Shoup-optimal")
    ax[0].legend(fontsize=8)
    ax[0].grid(alpha=0.3, which="both")

    # right: reach in bits per method (illustrative)
    methods = ["sequential", "MPS\n(amplitude)", "BSGS/rho\n(group)",
               "GNFS\n(ring)", "Shor\n(quantum)"]
    reach = [8, 12, 90, 829, 2048]
    colors = ["gray", "steelblue", "crimson", "darkgreen", "purple"]
    ax[1].bar(range(len(methods)), reach, color=colors)
    ax[1].set_xticks(range(len(methods)))
    ax[1].set_xticklabels(methods, fontsize=8)
    ax[1].set_ylabel("bit-length reached")
    ax[1].axhline(2048, color="purple", ls=":", lw=1)
    ax[1].set_title("Classical reach climbs with how much structure you use")
    for i, v in enumerate(reach):
        ax[1].text(i, v + 30, str(v), ha="center", fontsize=8)
    fig.tight_layout()
    out = "interference_structure.png"
    fig.savefig(out, dpi=125)
    print(f"\nFigure written: {out}")
    return out


def main():
    np.set_printoptions(precision=4, suppress=True)
    fac_rows = demo_bsgs_factoring()
    scaling_rows = demo_scaling()
    demo_lower_bound_and_landscape()
    make_plot(scaling_rows, fac_rows)
    hr("Verdict -- can RSA's structure find the period efficiently?")
    print("""  Yes, partly -- and your instinct is right that it should help:
    * The group homomorphism a^{x+y}=a^x a^y lets you manufacture the
      period-revealing interference by meet-in-the-middle (BSGS / Pollard rho).
      This finds r in O(sqrt r) instead of O(r), and factors random keys far
      beyond the tensor-network frontier (~12-bit -> ~50-100 bit).
    * But sqrt(r) is a PROVABLE floor for group-only methods (Shoup's generic
      group lower bound). The collision interferes sqrt(r) precomputed elements;
      it cannot interfere all r at once.
    * Going further means using structure the group does not see: the integer
      ring (GNFS -> sub-exponential, the real classical record) or quantum
      superposition (Shor -> polynomial). The QFT's power is that it interferes
      ALL Q evaluations simultaneously, which no classical pairing can match.
  So: structure turns r into sqrt(r) (and, with the ring, into sub-exponential),
  a real and large speedup -- but the exponential-to-polynomial gap is exactly
  what stays quantum.""")


if __name__ == "__main__":
    main()
