#!/usr/bin/env python3
"""The LEARNING framing: learn the periodic pattern of a^x mod N and let a model
identify the amplitude peaks (at y ~ s*Q/r) to read off the order r.

This takes that design at face value and asks what it costs.  A learner can touch
the problem through exactly three channels; we measure each:

  1. OBSERVE the pattern sequentially  -> must see Theta(r) values before the
     period is even witnessed (first repeat of a^x is at x = r).
  2. QUERY the pattern at random x      -> a residue collision (birthday / Pollard
     rho) appears after Theta(sqrt(r)) queries and reveals a multiple of r.
  3. Fit a tensor-network MODEL of the amplitude distribution -> its capacity
     (bond dimension) must reach r to represent the r-peak comb.

All three scale with the period r, which is ~N for a random RSA base.  The one
genuinely easy step -- turning a true measurement sample into r by continued
fractions -- presupposes a sample from the real amplitude, i.e. the thing that is
hard to produce.  Learning renames the wall; it does not move it.

Run:  python3 learn_period.py
"""

import math
import random
import time

import numpy as np

from tnshor.numtheory import (
    random_prime, order_mod_n, make_small_order_instance,
)
from tnshor.scalable import build_shor_mps_exact, factor_scalable, small_control_t


def hr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


# --- channel 1 & 2: observe / query the pattern ----------------------------
def first_repeat_window(N, a):
    """Sequential observations until the period is witnessed (== r)."""
    seen = set()
    x, v = 0, 1 % N
    while v not in seen:
        seen.add(v)
        x += 1
        v = (v * a) % N
    return x


def birthday_collision(N, a, r, rng, cap=5_000_000):
    """Random queries until a residue collision reveals a multiple of r (~sqrt r)."""
    seen = {}
    n = 0
    span = 4 * r + 8
    while n < cap:
        x = rng.randrange(0, span)
        v = pow(a, x, N)
        n += 1
        if v in seen and seen[v] != x:
            return n
        seen[v] = x
    return None


def demo_observation_walls():
    hr("1+2. Learning by observing / querying the amplitude pattern")
    print("  How much of the pattern must a learner see to pin down the period r?\n")
    print(f"  {'bits':>5} {'N':>14} {'r = order':>12} "
          f"{'seq window':>11} {'random queries':>15} {'sqrt(r)':>9}")
    random.seed(11)
    rows = []
    for bits in [10, 12, 14, 16, 18, 20, 22]:
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
        W = first_repeat_window(N, a)
        rng = random.Random(7)
        bdays = [birthday_collision(N, a, r, rng) for _ in range(25)]
        bavg = sum(bdays) / len(bdays)
        rows.append((bits, r, W, bavg))
        print(f"  {bits:>5} {N:>14} {r:>12} {W:>11} {bavg:>15.0f} "
              f"{math.sqrt(r):>9.0f}")
    print("\n  Sequential learning needs Theta(r) data; the smartest query strategy")
    print("  (birthday / Pollard rho) needs Theta(sqrt(r)).  Both are exponential in")
    print("  the bit-width -- a random RSA key has r ~ N.")
    return rows


# --- channel 3: a learned tensor-network MODEL of the amplitudes ------------
def captured_weight(N, a, t, chi):
    """Fraction of the amplitude a capacity-``chi`` tensor-network model captures.

    The QFT is unitary on the control register, so it leaves the control|work
    Schmidt spectrum unchanged: it equals sqrt(K_v) over the r residues v, where
    K_v = #{x < Q : a^x = v}.  A bond-dimension-chi model keeps the chi largest
    branches, capturing sum(top-chi K_v) / Q of the probability.
    """
    Q = 1 << t
    counts = {}
    v = 1 % N
    for _ in range(Q):
        counts[v] = counts.get(v, 0) + 1
        v = (v * a) % N
    ks = sorted(counts.values(), reverse=True)   # weight per Schmidt branch
    return sum(ks[:chi]) / Q, len(ks)


def demo_model_capacity():
    hr("3. Fitting a tensor-network model of the amplitude pattern")
    print("  The QFT-output amplitude is a comb of r peaks. Its Schmidt rank at the")
    print("  control|work cut is exactly r, so a capacity-chi model captures only the")
    print("  top chi of r equally-weighted branches -- fraction ~chi/r of the amplitude.\n")
    print(f"  {'r':>3}  amplitude captured vs model capacity chi  (faithful at chi=r)")
    random.seed(5)
    for dp, dq in [(2, 3), (4, 3), (4, 5), (2, 9)]:
        N, a, r, (p, q) = make_small_order_instance(bits=18, order_p=dp, order_q=dq)
        t = small_control_t(2 * r)
        caps = sorted({1, max(1, r // 4), max(1, r // 2), r, 2 * r})
        cells = []
        for chi in caps:
            w, rank = captured_weight(N, a, t, chi)
            cells.append((chi, w))
        print(f"  {r:>3}  " + "  ".join(f"chi={c}:{w*100:3.0f}%" for c, w in cells))
    print("\n  Capacity below r loses a proportional chunk of the amplitude; only at")
    print("  chi = r is the pattern represented in full.  Capacity == bond dim == r.")


# --- the one easy step, and its hidden cost --------------------------------
def demo_sample_to_r():
    hr("Aside: turning a TRUE amplitude sample into r is trivial -- if you have one")
    random.seed(2)
    N, a, r, (p, q) = make_small_order_instance(bits=24, order_p=2, order_q=3)
    t = small_control_t(2 * r)
    t0 = time.time()
    res = factor_scalable(N, a, t=t, shots=8, seed=1)
    dt = time.time() - t0
    print(f"  N={N} (24-bit), true r={r}.  From {8} genuine QFT samples, continued")
    print(f"  fractions recover r and factor N -> {res['factors']}  in {dt:.2f}s.")
    print("  But each 'genuine sample' is drawn from the simulated amplitude, whose")
    print("  bond dimension is r.  The peak-identification is free; PRODUCING a real")
    print("  amplitude sample is the wall (chi=r), and so is observing it (Theta(sqrt r)).")


def make_plot(obs_rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:  # pragma: no cover
        print(f"\n(matplotlib unavailable: {e}; skipping figure)")
        return None

    rs = np.array([r for _, r, _, _ in obs_rows], dtype=float)
    seq = np.array([w for _, _, w, _ in obs_rows], dtype=float)
    bday = np.array([b for _, _, _, b in obs_rows], dtype=float)
    order = np.argsort(rs)
    rs, seq, bday = rs[order], seq[order], bday[order]

    fig, ax = plt.subplots(1, 2, figsize=(12.5, 4.8))
    ax[0].loglog(rs, seq, "o-", color="crimson", label="sequential observation (=r)")
    ax[0].loglog(rs, bday, "s-", color="steelblue", label="random query / birthday (~sqrt r)")
    ax[0].loglog(rs, rs, "k--", lw=1, label="r")
    ax[0].loglog(rs, np.sqrt(rs), "g--", lw=1, label="sqrt(r)")
    ax[0].set_xlabel("period r")
    ax[0].set_ylabel("data needed to learn the period")
    ax[0].set_title("Learning the pattern: sample complexity is Theta(sqrt r) at best")
    ax[0].legend(fontsize=8)
    ax[0].grid(alpha=0.3, which="both")

    # right: capacity wall -- bond dimension to represent the amplitude == r
    rr = np.array([6, 12, 20, 30, 42, 56, 72, 90])
    ax[1].plot(rr, rr, "o-", color="purple", label="model capacity needed (= r)")
    ax[1].plot(rr, np.log2(rr), "g--", lw=1, label="poly(log) capacity (a win)")
    ax[1].set_xlabel("period r")
    ax[1].set_ylabel("bond dimension / model capacity")
    ax[1].set_title("Representing the amplitude comb needs capacity = r")
    ax[1].legend(fontsize=8)
    ax[1].grid(alpha=0.3)

    fig.tight_layout()
    out = "learn_period.png"
    fig.savefig(out, dpi=125)
    print(f"\nFigure written: {out}")
    return out


def main():
    np.set_printoptions(precision=4, suppress=True)
    rows = demo_observation_walls()
    demo_model_capacity()
    demo_sample_to_r()
    make_plot(rows)
    hr("Verdict -- can a learned model beat the wall?")
    print("""  The learning design is sound -- it just runs into the same number from three
  sides at once:
    * Observing the pattern to witness its period costs Theta(r) data.
    * Querying it cleverly (birthday / Pollard rho) costs Theta(sqrt r) -- this IS
      the best classical period-finder, and it is exactly the sub-exponential
      regime, never polynomial.
    * A tensor-network model of the amplitude needs bond-dimension capacity r.
  Identifying the peaks from a genuine amplitude sample is trivial (continued
  fractions, O(1) samples) -- but producing a genuine sample is the hard part.
  Learning relocates 'find r' into 'see / store / sample something of size r'.
  For a random RSA base r ~ N, so every route is exponential.

  Where learning genuinely helps: a STRUCTURED period (smooth r) is detectable
  from few samples -- that is the Pollard p-1 / rho regime, which good RSA keys
  already avoid.  Quantum Shor is different in kind: the QFT interferes all Q
  evaluations of a^x at once, so it never has to observe Theta(r) of the pattern.
  A classical learner only sees samples, and samples of a period-r signal carry
  at most O(sqrt r) worth of period information.""")


if __name__ == "__main__":
    main()
