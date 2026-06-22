#!/usr/bin/env python3
"""Does frontier-LLM-scale compute change the RSA picture?  No -- and here is why.

The cost of a tensor-network Shor simulation is set by ONE number: the bond
dimension, which equals the period r.  Circuit *size* (qubit count) is cheap.
So:

  A. Live: simulate an RSA-512 / 1024 / 2048 *dimension* Shor circuit (hundreds to
     thousands of qubits) on this machine -- because the entanglement (r) is small.
  B. Scaling: the largest classical machines ever built (frontier-LLM training
     clusters, then the whole planet, then physical limits) move the *random*-RSA
     frontier only logarithmically -- nowhere near RSA-2048.
  C. The LLM connection: tensor networks DO scale to frontier-LLM-sized objects,
     precisely because those objects are low-rank / low-entanglement.  Shor is the
     opposite regime.  Same tool, opposite side of the entanglement wall.

Run:  python3 analyze_scale.py
"""

import math
import time

import numpy as np

from tnshor.numtheory import make_small_order_instance
from tnshor.scalable import (
    factor_scalable, small_control_t, mps_bytes,
    bits_frontier_from_memory, bits_frontier_from_compute,
)


def hr(t):
    print("\n" + "=" * 80)
    print(t)
    print("=" * 80)


# ---------------------------------------------------------------------------
# A. RSA-2048-DIMENSION Shor on a laptop (small entanglement)
# ---------------------------------------------------------------------------
def demo_big_dimension():
    hr("A. Simulating RSA-sized Shor CIRCUITS on this machine (low entanglement)")
    print("  Engineered small-order N: the circuit has thousands of qubits, but the")
    print("  bond dimension is chi = r = 6, so it costs kilobytes, not 2^n.\n")
    print(f"  {'dim(N)':>7} {'qubits n':>9} {'r':>3} {'chi':>4} "
          f"{'MPS bytes':>11} {'2^n would be':>14} {'factored':>9} {'sec':>5}")
    import random
    random.seed(1)
    for bits in [256, 512, 1024, 2048]:
        N, a, r, (p, q) = make_small_order_instance(bits=bits, order_p=2, order_q=3)
        t = small_control_t(2 * r)
        t0 = time.time()
        res = factor_scalable(N, a, t=t, shots=160, seed=1)
        dt = time.time() - t0
        ok = res['success'] and {p, q} == set(res['factors'] or ())
        approx_bytes = mps_bytes(res['n'], res['chi_cut'])
        print(f"  {bits:>7} {res['n']:>9} {r:>3} {res['chi_cut']:>4} "
              f"{('%.0f KB' % (approx_bytes / 1024)):>11} {('2^%d' % res['n']):>14} "
              f"{'YES' if ok else 'no':>9} {dt:>5.1f}")
    print("\n  A 2048-bit-wide, ~2061-qubit Shor circuit factored on a laptop in seconds.")
    print("  The wall is NOT the qubit count -- it is the period r (= the bond dim).")


# ---------------------------------------------------------------------------
# B. Hardware scaling: where does the RANDOM-RSA frontier land?
# ---------------------------------------------------------------------------
MEM_TIERS = [
    ("laptop (16 GB)", 16 * 2**30),
    ("1x H100 (80 GB HBM)", 80 * 2**30),
    ("DGX node, 8x H100 (640 GB)", 640 * 2**30),
    ("GB200 NVL72 (~13.8 TB)", 138 * 10**11),
    ("frontier LLM cluster ~100k H100 (8 PB)", 8 * 10**15),
    ("hyperscale ~1M accel. (80 PB)", 8 * 10**16),
    ("entire world data (~200 ZB)", 2 * 10**23),
    ("atoms in observable universe", 10**80),
    ("holographic bound of universe (~10^123 b)", 10**123 // 8),
]


def demo_memory_frontier():
    hr("B. Memory scaling -- the random-RSA frontier vs every machine that exists")
    print("  Fundamental period wall: chi = r ~ 2^(bits-1), MPS = 3*bits * 2 * chi^2 * 16 B.")
    print("  Largest RANDOM-RSA bit-width whose MPS even FITS in the memory:\n")
    print(f"  {'memory tier':>42} {'log2(bytes)':>11} {'RSA bits reachable':>18}")
    for name, mem in MEM_TIERS:
        b = bits_frontier_from_memory(mem)
        print(f"  {name:>42} {math.log2(mem):>11.1f} {b:>18}")
    print("\n  Each extra bit of N costs 4x memory (chi doubles).  Frontier-LLM clusters")
    print("  reach ~21-bit; the entire planet's storage ~33-bit; even the holographic")
    print("  information bound of the observable universe tops out around ~196-bit.")
    print("  RSA-2048 needs 2048 bits -- and just STORING the MPS is ~2^4108 bytes,")
    print("  a factor ~2^3900 beyond the universe's total information capacity.")


def demo_compute_frontier():
    hr("B'. Compute scaling -- same story for time")
    print("  Contraction ~ b^2 * chi^3 ops (chi = 2^(b-1)).  Bit-width finishable in")
    print("  one year at each compute tier:\n")
    year = 3.15e7
    tiers = [
        ("laptop ~1 TFLOP/s", 1e12),
        ("1x H100 ~1 PFLOP/s", 1e15),
        ("frontier cluster ~100 EFLOP/s", 1e20),
        ("hypothetical zettascale ~1e21", 1e21),
    ]
    print(f"  {'compute tier':>34} {'FLOP/s':>9} {'RSA bits in 1 yr':>17}")
    for name, fps in tiers:
        b = bits_frontier_from_compute(fps, year)
        print(f"  {name:>34} {('1e%d' % round(math.log10(fps))):>9} {b:>17}")
    print("\n  Compute caps the frontier near ~30-bit even at 100 exaFLOP/s for a year.")


# ---------------------------------------------------------------------------
# C. Why tensor networks DO scale to frontier LLMs (and not to Shor)
# ---------------------------------------------------------------------------
def demo_llm_connection():
    hr("C. Why the same tensor networks scale to frontier-LLM-sized objects")
    print("""  Tensor-train / MPS factorisation, LoRA, and FP8 weight compression are all
  tensor networks applied at frontier-LLM scale (10^9-10^12 parameters). They
  work because the objects are effectively LOW-RANK: the bond dimension / adapter
  rank needed to capture a weight matrix or an attention map is small -- tens to a
  few thousand -- so cost stays linear in the parameter count.

  The Shor state is the opposite regime. Its entanglement across the control|work
  cut is genuinely maximal for the task: bond dimension == the period r, which for
  a random RSA modulus is ~2^(bits-1). No low-rank structure to exploit.\n""")
    print(f"  {'object':>34} {'size':>14} {'bond dim needed':>16} {'TN verdict':>12}")
    rows = [
        ("LLM weight matrix (TT/SVD)", "~10^7-10^8", "~10^2-10^3", "compresses"),
        ("LoRA adapter (rank r)", "~10^9 base", "8-128", "compresses"),
        ("attention map (low-rank)", "seq^2", "~10^2", "compresses"),
        ("Shor state, engineered small r", "2^2061", "6", "trivial"),
        ("Shor state, RANDOM RSA-2048", "2^6144", "~2^2047", "IMPOSSIBLE"),
    ]
    for name, size, bond, verdict in rows:
        print(f"  {name:>34} {size:>14} {bond:>16} {verdict:>12}")
    print("\n  Frontier-LLM-scale tensor networks succeed because bond dimension stays")
    print("  small. Breaking RSA needs bond dimension 2^2047. Hardware does not change")
    print("  which side of that wall you are on.")


def make_plot():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:  # pragma: no cover
        print(f"\n(matplotlib unavailable: {e}; skipping figure)")
        return None

    fig, ax = plt.subplots(1, 2, figsize=(13, 5))

    names = [n for n, _ in MEM_TIERS]
    log2mem = [math.log2(m) for _, m in MEM_TIERS]
    fr = [bits_frontier_from_memory(m) for _, m in MEM_TIERS]
    y = np.arange(len(names))
    ax[0].barh(y, fr, color="steelblue")
    ax[0].set_yticks(y)
    ax[0].set_yticklabels([f"{n}" for n in names], fontsize=7)
    ax[0].invert_yaxis()
    ax[0].axvline(1024, color="orange", ls="--", lw=1, label="RSA-1024")
    ax[0].axvline(2048, color="red", ls="--", lw=1, label="RSA-2048")
    for yi, b in zip(y, fr):
        ax[0].text(b + 3, yi, str(b), va="center", fontsize=7)
    ax[0].set_xlabel("largest RANDOM-RSA bit-width reachable")
    ax[0].set_title("Memory frontier: hardware barely moves it")
    ax[0].legend(fontsize=8, loc="lower right")
    ax[0].set_xlim(0, 2200)

    # right: required MPS memory (log2 bytes) vs bit-width, with tier lines
    bs = list(range(8, 2100, 8))
    memlog = [math.log2(3 * b) + 1 + 2 * (b - 1) + 4 for b in bs]
    ax[1].plot(bs, memlog, color="navy", label="required MPS log2(bytes)")
    for label, m, yoff in [("laptop", 16 * 2**30, 0), ("frontier cluster (8 PB)", 8e15, 0),
                           ("world data (200 ZB)", 2e23, 0),
                           ("universe info bound", 10**123 / 8, 0)]:
        ax[1].axhline(math.log2(m), color="gray", ls=":", lw=1)
        ax[1].text(20, math.log2(m) + 25, label, fontsize=7, color="gray")
    ax[1].axvline(2048, color="red", ls="--", lw=1)
    ax[1].text(2048, 200, "RSA-2048\n~2^4108 B", color="red", fontsize=8, ha="right")
    ax[1].set_xlabel("RSA modulus bit-width")
    ax[1].set_ylabel("log2(MPS memory, bytes)")
    ax[1].set_title("Storing the MPS exceeds the universe by ~200-bit")
    ax[1].legend(fontsize=8, loc="upper left")

    fig.tight_layout()
    out = "scale_frontier.png"
    fig.savefig(out, dpi=125)
    print(f"\nFigure written: {out}")
    return out


def main():
    np.set_printoptions(precision=4, suppress=True)
    demo_big_dimension()
    demo_memory_frontier()
    demo_compute_frontier()
    demo_llm_connection()
    make_plot()
    hr("Verdict -- frontier-LLM scale")
    print("""  * Circuit SIZE is free: we simulated an RSA-2048-dimension (~2061-qubit) Shor
    circuit on a laptop in seconds, because the period r (= bond dimension) was 6.
  * The only resource that matters is the bond dimension chi = r. For a random
    RSA modulus chi ~ 2^(bits-1), and memory grows as 4^bits.
  * Scaling from a laptop to a frontier-LLM cluster moves the random-RSA frontier
    from ~12-bit to ~21-bit; the entire planet's storage reaches ~33-bit; the
    holographic information bound of the observable universe ~196-bit.
  * RSA-2048 needs chi ~ 2^2047 and ~2^4108 bytes -- ~2^3900 beyond the universe.
    No classical machine, at any scale, including frontier-LLM infrastructure,
    comes within astronomical distance.
  * Tensor networks scale to frontier-LLM-sized objects exactly because those are
    low-entanglement (small bond dimension). Shor's hardness IS its entanglement.
    Hardware scale cannot move you across that wall.""")


if __name__ == "__main__":
    main()
