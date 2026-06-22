#!/usr/bin/env python3
"""Continuous-variable (CV) quantum modes for RSA/Shor: how far, measured.

A CV mode (an optical mode / harmonic oscillator) has an in-principle infinite
Fock space; with M modes truncated to d levels each the Hilbert space is
(C^d)^M = C^(d^M). So a few hundred high-dimensional modes could in principle
carry the 2^4096 of RSA-2048's first register. This script measures the catches:

  1. Mode counting: D = d^M, so reaching 2^4096 needs M = 4096 / log2(d) modes.
     (verifies the d -> M trade-off table)
  2. Classical simulation cost: a GAUSSIAN CV system (mean + covariance) costs
     O(M^2) -- efficient -- while a Fock-truncated non-Gaussian system needs d^M
     amplitudes -- exponential. We measure both.
  3. The Gaussian / non-Gaussian dividing line = Wigner negativity. Gaussian
     states (coherent, squeezed) have positive Wigner functions -> classically
     sampleable -> but cannot do Shor. The non-Gaussian states a speedup needs
     (Fock, cat) have NEGATIVE Wigner regions -> exactly what breaks the
     efficient description. The useful regime IS the hard regime.

Run:  python3 cv_quantum.py
"""

import math
import time

import numpy as np


def hr(t):
    print("\n" + "=" * 80)
    print(t)
    print("=" * 80)


# ---------------------------------------------------------------------------
# 1. Mode counting:  D = d^M,  reaching 2^4096 needs M = 4096 / log2(d)
# ---------------------------------------------------------------------------
def demo_mode_counting():
    hr("1. Mode counting: D = d^M, modes needed to reach RSA-2048's 2^4096")
    print("  A higher per-mode dimension d means fewer modes M -- but each bit of")
    print("  per-mode capacity is energy + precision you must actually buy.\n")
    print(f"  {'per-mode dim d':>16} {'bits/mode = log2 d':>18} "
          f"{'modes M for 2^4096':>20}")
    target = 4096
    for d in [2, 10, 100, 1000, 10**6, 2**100]:
        bits = math.log2(d)
        M = math.ceil(target / bits)
        dlabel = f"2^100" if d == 2**100 else f"{d:,}"
        print(f"  {dlabel:>16} {bits:>18.2f} {M:>20}")
    print("\n  Verified: e.g. d=10^6 (a 20-bit-precise single mode) -> ~205 modes.")
    print("  But a 20-bit, low-noise, non-Gaussian-controlled mode held through a")
    print("  deep circuit is extraordinarily hard -- the infinite dimension is not free.")


# ---------------------------------------------------------------------------
# 2. Classical simulation cost: Gaussian O(M^2) vs Fock-truncated d^M
# ---------------------------------------------------------------------------
def haar_interferometer(M, rng):
    """An M-mode passive linear-optical network = Haar-random M x M unitary."""
    z = (rng.standard_normal((M, M)) + 1j * rng.standard_normal((M, M))) / math.sqrt(2)
    q, r = np.linalg.qr(z)
    return q * (np.diag(r) / np.abs(np.diag(r)))


def demo_sim_cost():
    hr("2. Classical simulation cost: Gaussian (linear optics) vs Fock truncation")
    print("  A Gaussian / linear-optical M-mode state evolves by an M x M transfer")
    print("  matrix on the mode amplitudes -- polynomial. A general (non-Gaussian)")
    print("  state truncated to d Fock levels per mode needs d^M amplitudes.\n")
    rng = np.random.default_rng(0)
    print(f"  {'M modes':>8} {'Gaussian linear-optics':>24} "
          f"{'Fock-truncated d=10':>22}")
    for M in [128, 256, 512, 1024, 2048]:
        amp = (rng.standard_normal(M) + 1j * rng.standard_normal(M))
        t0 = time.time()
        U = haar_interferometer(M, rng)
        out = U @ amp                       # apply the interferometer
        dt = time.time() - t0
        fock_log10 = M * math.log10(10)     # log10(10^M) = M
        print(f"  {M:>8} {dt*1e3:>20.1f} ms {('10^%d numbers' % round(fock_log10)):>22}")
    print("\n  Gaussian/linear-optics: milliseconds for thousands of modes (poly).")
    print("  Fock-truncated: 2048 modes -> 10^2048 amplitudes. The efficient CV")
    print("  description is the GAUSSIAN one -- and that is exactly the weak one.")


# ---------------------------------------------------------------------------
# 3. The Gaussian / non-Gaussian dividing line = Wigner negativity
# ---------------------------------------------------------------------------
def psi_coherent(x, x0=0.0, p0=0.0):
    return np.pi ** -0.25 * np.exp(-(x - x0) ** 2 / 2 + 1j * p0 * x)


def psi_fock1(x):
    return np.pi ** -0.25 * math.sqrt(2.0) * x * np.exp(-x ** 2 / 2)


def psi_cat(x, x0=2.5):
    psi = psi_coherent(x, x0) + psi_coherent(x, -x0)
    return psi


def wigner(psi_func, xs, ps):
    """Wigner W(x,p) of a 1-mode pure state from its position wavefunction,
    W(x,p) = (1/pi) int dy psi*(x+y) psi(x-y) e^{2 i p y}."""
    ys = np.linspace(-6, 6, 512)
    dy = ys[1] - ys[0]
    W = np.empty((len(xs), len(ps)))
    for i, x in enumerate(xs):
        ker = np.conj(psi_func(x + ys)) * psi_func(x - ys)     # (len ys,)
        # W(x,p) = (1/pi) * sum_y ker(y) e^{2 i p y} dy
        phase = np.exp(2j * np.outer(ps, ys))                  # (len ps, len ys)
        W[i, :] = (phase @ ker).real * dy / math.pi
    return W


def demo_wigner():
    hr("3. Gaussian = efficient but weak; non-Gaussian = strong but Wigner-negative")
    xs = np.linspace(-5, 5, 161)
    ps = np.linspace(-5, 5, 161)
    states = [
        ("coherent (Gaussian)", lambda x: psi_coherent(x, 1.0, 0.0), "efficient / weak"),
        ("Fock |1> (non-Gaussian)", psi_fock1, "needs Fock space"),
        ("cat (non-Gaussian)", lambda x: psi_cat(x, 2.5), "needs Fock space"),
    ]
    print(f"  {'state':>26} {'min Wigner':>12} {'negative?':>10}  classical cost")
    cat_W = None
    for name, f, note in states:
        # normalise the wavefunction on the grid
        norm = math.sqrt(np.trapezoid(np.abs(f(xs)) ** 2, xs))
        W = wigner(lambda x, f=f, n=norm: f(x) / n, xs, ps)
        mn = W.min()
        if name.startswith("cat"):
            cat_W = W
        print(f"  {name:>26} {mn:>12.4f} {('YES' if mn < -1e-3 else 'no'):>10}  "
              f"{('O(M^2) covariance' if mn >= -1e-3 else 'd^M Fock amplitudes')}")
    print("""
  Positive Wigner (Gaussian) = a genuine probability distribution -> classically
  sampleable by Monte-Carlo (Mari-Eisert) -> no quantum speedup. NEGATIVE Wigner
  is necessary for a speedup, and it is exactly what the covariance-matrix
  description cannot hold -- forcing the d^M Fock cost. The CV regime that is
  classically efficient is the one that cannot run Shor; the one that can run
  Shor is the one that is classically hard. Same wall, CV costume.""")
    return xs, ps, cat_W


def make_plot(cat_data):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:  # pragma: no cover
        print(f"\n(matplotlib unavailable: {e}; skipping figure)")
        return None
    fig, ax = plt.subplots(1, 3, figsize=(15.5, 4.6))

    # 1: modes needed vs per-mode dimension d (verifies the trade-off table)
    ds = np.array([2, 4, 16, 256, 2**16, 2**32, 2**64], dtype=float)
    Ms = 4096 / np.log2(ds)
    ax[0].semilogx(ds, Ms, "o-", color="purple")
    ax[0].set_xlabel("per-mode dimension d (log)")
    ax[0].set_ylabel("modes M to reach 2^4096")
    ax[0].set_title("Mode counting: M = 4096 / log2(d)")
    ax[0].grid(alpha=0.3, which="both")

    # 2: Gaussian O(M^2) vs Fock d^M classical cost (log10 numbers)
    Mg = np.array([128, 256, 512, 1024, 2048, 4096], dtype=float)
    gauss = 2 * np.log10(Mg)                # ~ M^2 -> 2 log10 M
    fock = Mg * math.log10(10)              # 10^M -> M
    ax[1].plot(Mg, gauss, "o-", color="seagreen", label="Gaussian ~ M^2")
    ax[1].plot(Mg, fock, "s-", color="crimson", label="Fock d^M (d=10)")
    ax[1].set_xlabel("modes M")
    ax[1].set_ylabel("log10(numbers to store)")
    ax[1].set_title("Efficient CV = Gaussian; non-Gaussian = exponential")
    ax[1].legend(fontsize=8)
    ax[1].grid(alpha=0.3)

    # 3: Wigner of a cat state -- the non-Gaussian negativity (the resource)
    xs, ps, W = cat_data
    vmax = np.abs(W).max()
    im = ax[2].imshow(W.T, origin="lower", extent=[xs[0], xs[-1], ps[0], ps[-1]],
                      cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    ax[2].set_xlabel("x")
    ax[2].set_ylabel("p")
    ax[2].set_title("Cat-state Wigner: blue = NEGATIVE (the speedup resource)")
    fig.colorbar(im, ax=ax[2], fraction=0.046)

    fig.tight_layout()
    out = "cv_quantum.png"
    fig.savefig(out, dpi=125)
    print(f"\nFigure written: {out}")
    return out


def main():
    np.set_printoptions(precision=4, suppress=True)
    demo_mode_counting()
    demo_sim_cost()
    cat_data = demo_wigner()
    make_plot(cat_data)
    hr("Verdict -- CV quantum modes + classical for RSA")
    print("""  Your analysis holds, measured:
    * CV modes can carry a big state physically: D = d^M, so ~200-600 high-d
      modes could in principle hold 2^4096. But classically simulating that needs
      D complex amplitudes regardless -- exponential.
    * The efficiently-simulable CV regime (Gaussian: mean + covariance, O(M^2),
      positive Wigner) is exactly the regime that cannot do Shor. Adding classical
      modes / pixels to it does not make a coherent exponential space.
    * Universal CV computation needs non-Gaussian resources, whose hallmark is
      Wigner negativity -- precisely what defeats the polynomial description and
      what is hard to prepare and hold physically.
  So CV quantum is a real candidate substrate for an exponential entangled state
  space (an alternative to qubits) -- but combining classical modes with it is no
  free pass to RSA-2048. The dividing line, again, is the same resource: the
  thing that gives the speedup (negativity / entanglement / period structure) is
  exactly the thing that is classically expensive to hold.""")


if __name__ == "__main__":
    main()
