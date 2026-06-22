#!/usr/bin/env python3
"""Push the tensor-network simulator toward RSA scale -- honestly.

  A. Engineered small-order N: factor large-bit-width semiprimes by simulating
     Shor as an MPS that never forms the 2^n vector.  Works because the period r
     is small (so the bond dimension and the needed control register are small).
     Finding such a base for a *given* modulus needs its factorisation already.

  B. Wall 1 -- random base: r = ord_N(a) ~ Theta(N), so the control|work bond
     chi == r is exponential in the qubit count.

  C. Wall 2 -- the QFT: if you must use the full t = 2 log2 N control register
     (because you do NOT know r is small), the QFT's *intermediate* bond
     dimension explodes ~2^(t/2) even when the input/output are low rank.

  D. Extrapolation of both walls to RSA-2048.

Run:  python3 run_rsa_scale.py
"""

import math
import random
import time

import numpy as np

from tnshor.numtheory import make_small_order_instance, random_prime, order_mod_n
from tnshor.scalable import (
    build_shor_mps_exact, factor_scalable, small_control_t,
)
from tnshor.shor import apply_qft_mps_lnn


def hr(t):
    print("\n" + "=" * 76)
    print(t)
    print("=" * 76)


# ---- A: factor large-bit-width semiprimes (engineered small order) -----------
def demo_break_statevector_wall():
    hr("A. Factoring large N by ~N-qubit Shor, no 2^n vector (engineered small r)")
    print("  The MPS bond dimension is == r.  A state-vector simulator would need")
    print("  2^n complex amplitudes; we use kilobytes.\n")
    print(f"  {'bits(N)':>8} {'N':>40} {'r':>3} {'qubits n':>8} "
          f"{'statevec':>11} {'chi':>4} {'ok':>3} {'sec':>5}")
    random.seed(7)
    rows = []
    for bits, (dp, dq) in [(24, (2, 3)), (48, (2, 3)), (96, (4, 3)),
                           (128, (2, 3)), (160, (2, 3))]:
        N, a, r, (p, q) = make_small_order_instance(bits=bits, order_p=dp, order_q=dq)
        t = small_control_t(2 * r)
        t0 = time.time()
        res = factor_scalable(N, a, t=t, shots=300, seed=1)
        dt = time.time() - t0
        ok = res['success'] and {p, q} == set(res['factors'] or ())
        rows.append((bits, res['n'], res['chi_cut'], ok, dt))
        print(f"  {bits:>8} {N:>40} {r:>3} {res['n']:>8} "
              f"{('2^%d' % res['n']):>11} {res['chi_cut']:>4} "
              f"{'YES' if ok else 'no':>3} {dt:>5.1f}")
    print("\n  A 160-bit N => ~190-qubit Shor circuit, factored on a laptop in seconds.")
    print("  Impossible for any state-vector method; trivial for the MPS when r is small.")
    return rows


# ---- B: random base -> order ~ N --------------------------------------------
def demo_random_order_wall():
    hr("B. Wall 1 -- a random base has order r ~ Theta(N)  (chi = r explodes)")
    print("  Order over the largest of 12 random bases (~ the group exponent lambda(N)).\n")
    print(f"  {'bits(N)':>8} {'N':>12} {'max r = ord_N(a)':>17} {'log2(r)':>8} "
          f"{'log2(N)':>8}")
    random.seed(11)
    rows = []
    for bits in [12, 16, 20, 24, 28, 32]:
        half = bits // 2
        p = random_prime(half)
        q = random_prime(bits - half)
        while q == p:
            q = random_prime(bits - half)
        N = p * q
        best = 1
        for _ in range(12):
            while True:
                a = random.randrange(2, N - 1)
                if math.gcd(a, N) == 1:
                    break
            best = max(best, order_mod_n(a, {p: 1, q: 1}))
        rows.append((bits, best))
        print(f"  {bits:>8} {N:>12} {best:>17} {math.log2(best):>8.2f} "
              f"{math.log2(N):>8.2f}")
    print("\n  log2(r) tracks log2(N): the order (= the bond dimension) is exponential")
    print("  in the qubit count. No small-r handle without knowing p, q first.")
    return rows


# ---- C: the QFT intermediate-bond wall at full register size -----------------
def demo_qft_wall():
    hr("C. Wall 2 -- full-register QFT: intermediate bond dimension explodes")
    print("  Same engineered state (small r=6), but run the QFT over an increasing")
    print("  control register t (what you must do if you do NOT know r is small).\n")
    print(f"  {'t':>4} {'Q=2^t':>10} {'input chi':>10} {'peak bond in QFT':>18}")
    random.seed(3)
    N, a, r, (p, q) = make_small_order_instance(bits=16, order_p=2, order_q=3)
    rows = []
    for t in [8, 10, 12, 14, 16, 18, 20]:
        mps, geom = build_shor_mps_exact(N, a, t=t)
        chi_in = mps.bond_dimensions()[t - 1]
        peak = apply_qft_mps_lnn(mps, t, track=True)
        rows.append((t, peak))
        print(f"  {t:>4} {1 << t:>10} {chi_in:>10} {peak:>18}")
    print("\n  Peak bond ~ 2^(0.6 t): exponential in t even though r=6 and the final")
    print("  state is low rank. The QFT is the bottleneck once t must be large.")
    return rows


# ---- D: extrapolation to RSA --------------------------------------------------
def demo_extrapolate_rsa():
    hr("D. Extrapolation to RSA-2048")
    print("  General RSA forces BOTH walls: random base => chi = r ~ N, and the")
    print("  full t = 2*bits register => exploding QFT bond. Best case chi ~ 2^(bits-1).\n")
    print(f"  {'RSA-bits':>9} {'qubits n':>9} {'log2(chi=r)':>12} "
          f"{'log2(MPS bytes)':>16}")
    for bits in [64, 128, 256, 512, 1024, 2048]:
        log2_r = bits - 1
        n = 3 * bits
        log2_mem = math.log2(n) + 1 + 2 * log2_r + 4  # n*2*chi^2*16 bytes
        print(f"  {bits:>9} {n:>9} {log2_r:>12} {log2_mem:>16.0f}")
    print("\n  RSA-2048: chi ~ 2^2047, MPS ~ 2^4108 bytes. The observable universe")
    print("  holds ~2^266 atoms. Classically impossible -- this is RSA's safety.")


def make_plot(random_rows, qft_rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:  # pragma: no cover
        print(f"\n(matplotlib unavailable: {e}; skipping figure)")
        return None

    fig, ax = plt.subplots(1, 3, figsize=(16, 4.6))

    # 1: random-base log2(r) vs bit-width
    bw = [r[0] for r in random_rows]
    log2r = [math.log2(r[1]) for r in random_rows]
    ax[0].plot(bw, log2r, "o-", color="crimson", label="measured log2(r)")
    ax[0].plot(bw, [b - 1 for b in bw], "k--", lw=1, label="~ bits-1")
    ax[0].plot(bw, [math.log2(b) for b in bw], "g--", lw=1, label="poly(log N) (a win)")
    ax[0].set_xlabel("bit-width of N")
    ax[0].set_ylabel("log2(bond dim) = log2(r)")
    ax[0].set_title("Wall 1: random base, chi=r is exponential")
    ax[0].legend(fontsize=8)
    ax[0].grid(alpha=0.3)

    # 2: QFT peak bond vs t
    ts = [r[0] for r in qft_rows]
    peaks = [math.log2(r[1]) for r in qft_rows]
    ax[1].plot(ts, peaks, "s-", color="darkorange", label="log2(peak QFT bond)")
    ax[1].plot(ts, [t / 2 for t in ts], "k--", lw=1, label="~ t/2")
    ax[1].axhline(math.log2(6), color="green", ls=":", label="log2(r)=2.58 (input/output)")
    ax[1].set_xlabel("control register size t")
    ax[1].set_ylabel("log2(bond dim)")
    ax[1].set_title("Wall 2: QFT intermediate bond (r=6 fixed)")
    ax[1].legend(fontsize=8)
    ax[1].grid(alpha=0.3)

    # 3: extrapolated memory
    rbits = [64, 128, 256, 512, 1024, 2048]
    log2mem = [math.log2(3 * b) + 1 + 2 * (b - 1) + 4 for b in rbits]
    ax[2].plot(rbits, log2mem, "D-", color="navy")
    ax[2].axhline(266, color="gray", ls=":", label="atoms in universe (~2^266)")
    ax[2].annotate("RSA-2048\n~2^4108 B", (2048, log2mem[-1]),
                   textcoords="offset points", xytext=(-95, -28), color="navy")
    ax[2].set_xlabel("RSA modulus bit-width")
    ax[2].set_ylabel("log2(MPS memory, bytes)")
    ax[2].set_title("Extrapolated best-case MPS memory")
    ax[2].legend(fontsize=8)
    ax[2].grid(alpha=0.3)

    fig.tight_layout()
    out = "rsa_scale.png"
    fig.savefig(out, dpi=125)
    print(f"\nFigure written: {out}")
    return out


def main():
    np.set_printoptions(precision=4, suppress=True)
    demo_break_statevector_wall()
    rrows = demo_random_order_wall()
    qrows = demo_qft_wall()
    demo_extrapolate_rsa()
    make_plot(rrows, qrows)
    hr("Verdict")
    print("""  * The simulator scales as poly(n)*poly(r): we factored a 160-bit semiprime
    via a ~190-qubit Shor circuit on a laptop -- impossible for any state-vector
    simulator -- because we ENGINEERED r small (the section-6 special-case win).
  * Real RSA hits two exponential walls at once:
      Wall 1  random base => order r ~ N => control|work bond chi = r ~ 2^bits.
      Wall 2  unknown r forces the full t=2*bits QFT, whose intermediate bond
              dimension explodes ~2^(t/2) even for a low-rank input/output.
  * RSA-2048 best case ~ 2^4108 bytes of MPS -- far beyond physical reality.
  * Tensor networks move the wall from 'qubit count' to 'period r' (+ QFT depth).
    RSA stays safe because you cannot obtain a small-r handle, or shrink t,
    without already knowing p and q.""")


if __name__ == "__main__":
    main()
