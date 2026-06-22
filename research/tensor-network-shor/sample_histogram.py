#!/usr/bin/env python3
"""Sample the POST-QFT measurement histogram P(m), then recover r by m/Q ~ s/r.

This is exactly the quantum-Shor readout: measure the control register after the
QFT, collect the histogram (peaks at m ~ s*Q/r), and run continued fractions on a
sample. This script:

  1. Samples P(m) from the simulated post-QFT MPS, overlays the exact P(m), marks
     the s*Q/r peaks, and recovers r + factors N -- the design, working.
  2. Locates the wall precisely: the continued-fraction readout is ~microseconds;
     the cost is PRODUCING a histogram sample, which needs an amplitude of bond
     dimension r (or, classically, knowing r already -- the histogram's peak
     locations literally encode r).

Run:  python3 sample_histogram.py
"""

import math
import random
import time
from fractions import Fraction

import numpy as np

from tnshor.numtheory import make_small_order_instance, random_prime, order_mod_n
from tnshor.scalable import build_shor_mps_exact, factor_scalable, small_control_t
from tnshor.shor import apply_qft_mps_lnn, factor_from_order, order_from_samples


def hr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def exact_post_qft_hist(N, a, t):
    """Exact P(m) over the control register after the QFT (m = 0..Q-1)."""
    Q = 1 << t
    res = np.empty(Q, dtype=np.int64)
    v = 1 % N
    for x in range(Q):
        res[x] = v
        v = (v * a) % N
    P = np.zeros(Q)
    for vv in np.unique(res):
        g = (res == vv).astype(complex)
        G = np.fft.fft(g)               # sum_x g(x) e^{-2pi i mx/Q}
        P += np.abs(G) ** 2
    P /= Q * Q
    P /= P.sum()
    return P


def demo_histogram():
    hr("1. Sample the post-QFT histogram, recover r by m/Q ~ s/r")
    random.seed(11)
    # engineered small order so the whole thing is simulable at large bit-width
    N, a, r, (p, q) = make_small_order_instance(bits=64, order_p=4, order_q=3)
    t = small_control_t(2 * r)
    Q = 1 << t
    print(f"  N = {N} ({N.bit_length()} bit), true r = {r}, control register t = {t}"
          f" (Q = {Q})")

    mps, geom = build_shor_mps_exact(N, a, t=t)
    apply_qft_mps_lnn(mps, t)
    rng = np.random.default_rng(1)
    shots = 4000
    raw = mps.sample(rng, shots=shots)
    ms = np.array([v >> geom['m'] for v in raw])   # control value m

    print(f"\n  expected peaks  s*Q/r  for s=0..{r-1}:")
    print("   ", [round(s * Q / r) for s in range(r)])
    # show the continued-fraction readout on a few sampled m's
    print(f"\n  {'sampled m':>10} {'m/Q':>10} {'CF -> s/r':>12} {'denominator':>12}")
    shown = 0
    for m in sorted(set(int(x) for x in ms)):
        frac = Fraction(m, Q).limit_denominator(min(N, math.isqrt(Q)))
        if frac.denominator > 1:
            print(f"  {m:>10} {m / Q:>10.5f} {str(frac):>12} {frac.denominator:>12}")
            shown += 1
            if shown >= 8:
                break

    r_hat = order_from_samples([int(x) for x in ms], geom, N, a)
    factors = factor_from_order(N, a, r_hat)
    print(f"\n  recovered r = {r_hat}  ->  factors = {factors}  "
          f"(correct: {set(factors or ()) == {p, q}})")
    return N, a, r, t, ms


def demo_where_the_cost_is():
    hr("2. The continued-fraction readout is free; PRODUCING a sample is the wall")
    print("  Split the pipeline and time each half on the case above.\n")
    random.seed(11)
    N, a, r, (p, q) = make_small_order_instance(bits=64, order_p=4, order_q=3)
    t = small_control_t(2 * r)

    t0 = time.time()
    mps, geom = build_shor_mps_exact(N, a, t=t)
    apply_qft_mps_lnn(mps, t)
    rng = np.random.default_rng(0)
    m = (mps.sample(rng, shots=1)[0]) >> geom['m']
    t_produce = time.time() - t0

    t0 = time.time()
    frac = Fraction(int(m), 1 << t).limit_denominator(min(N, math.isqrt(1 << t)))
    t_read = time.time() - t0

    print(f"  producing ONE histogram sample (build + QFT + measure): {t_produce*1e3:8.1f} ms")
    print(f"  continued-fraction readout of that sample:              {t_read*1e6:8.1f} us")
    print(f"  ratio: producing a sample is ~{t_produce/max(t_read,1e-9):.0e}x the readout.")
    print("\n  The readout (m/Q -> s/r) is trivial. The histogram itself costs an")
    print("  amplitude of bond dimension chi = r to simulate -- that is the wall.")


def demo_sparsity_is_a_red_herring():
    hr("3. 'The histogram is sparse (r peaks) -- can't we just sample it cheaply?'")
    print("  No: a distribution whose support locations s*Q/r ARE the unknown r is")
    print("  not cheap to sample. To write down / evaluate P(m) you need the period")
    print("  structure; to draw a sample without it you must simulate the amplitude.\n")
    print(f"  {'bits(N)':>8} {'r':>10} {'#peaks':>7} {'Q (bins)':>12} "
          f"{'sim cost chi=r':>14}")
    random.seed(7)
    # a few random keys: r ~ N, so 'few peaks' still means chi = r ~ N
    for bits in [12, 16, 20, 24]:
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
        rr = order_mod_n(a, {p: 1, q: 1})
        Q = 1 << (2 * bits)
        print(f"  {bits:>8} {rr:>10} {rr:>7} {('2^%d' % (2*bits)):>12} "
              f"{('2^%.0f' % math.log2(rr)):>14}")
    print("\n  The peak COUNT is r and the simulation cost is r -- the same number.")
    print("  Sparsity does not help when the support is exactly what you are solving for.")


def make_plot(N, a, r, t, ms):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:  # pragma: no cover
        print(f"\n(matplotlib unavailable: {e}; skipping figure)")
        return None
    Q = 1 << t
    P = exact_post_qft_hist(N, a, t)
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))

    # left: exact P(m) with sampled histogram overlay + peak markers
    ax[0].plot(np.arange(Q), P, color="navy", lw=0.8, label="exact P(m)")
    hist, edges = np.histogram(ms, bins=Q, range=(0, Q), density=True)
    ax[0].plot(np.arange(Q), hist, color="orange", lw=0.6, alpha=0.7,
               label=f"sampled ({len(ms)} shots)")
    for s in range(r):
        ax[0].axvline(s * Q / r, color="green", ls=":", lw=0.7)
    ax[0].set_xlabel("measured control value m")
    ax[0].set_ylabel("probability")
    ax[0].set_title(f"Post-QFT histogram: r={r} peaks at s*Q/r")
    ax[0].legend(fontsize=8)

    # right: zoom on the first few peaks
    zoom = int(3.5 * Q / r)
    ax[1].plot(np.arange(zoom), P[:zoom], color="navy", lw=1.0, label="exact P(m)")
    for s in range(4):
        mloc = s * Q / r
        if mloc < zoom:
            ax[1].axvline(mloc, color="green", ls=":", lw=1)
            ax[1].text(mloc, ax[1].get_ylim()[1] * 0.9, f"s={s}", fontsize=8,
                       ha="center", color="green")
    ax[1].set_xlabel("measured control value m (zoom)")
    ax[1].set_ylabel("probability")
    ax[1].set_title("m/Q ~ s/r  ->  continued fractions -> r")
    ax[1].legend(fontsize=8)

    fig.tight_layout()
    out = "post_qft_histogram.png"
    fig.savefig(out, dpi=130)
    print(f"\nFigure written: {out}")
    return out


def main():
    np.set_printoptions(precision=4, suppress=True)
    N, a, r, t, ms = demo_histogram()
    demo_where_the_cost_is()
    demo_sparsity_is_a_red_herring()
    make_plot(N, a, r, t, ms)
    hr("Verdict")
    print("""  * The readout you described works exactly: sample the post-QFT histogram,
    apply m/Q ~ s/r + continued fractions, recover r, factor N. We did it for a
    64-bit modulus (engineered small r) by simulating the histogram directly.
  * That readout step is essentially free (microseconds, O(polylog)).
  * The cost is producing histogram samples. Each sample is drawn from the
    post-QFT amplitude, whose bond dimension is exactly r. The peaks sit at
    s*Q/r, so the histogram's very support encodes r: you cannot write down or
    sample P(m) without either knowing r or simulating an amplitude of size r.
  * For a random RSA base r ~ N -> the histogram has ~N peaks at unknown
    locations and costs ~N to simulate. The sparsity (few peaks) does not help,
    because locating the peaks IS finding r.
  * Quantum advantage lives precisely here: a quantum computer PREPARES and
    SAMPLES this histogram physically in poly(log N) time via interference,
    never enumerating the amplitude. Classically, producing one honest sample is
    the exponential step -- the continued-fraction readout never was.""")


if __name__ == "__main__":
    main()
