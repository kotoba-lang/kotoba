#!/usr/bin/env python3
"""Classical waves / complexification: how far does physical interference get you?

The intuition is correct: classical waves (light, sound, images, complex signals)
have phase, coherence and Fourier transforms -- a lens IS an optical FT. So for a
small modulus you can literally read the period off a spectrum analyser. This
script measures where that stops:

  1. A classical power spectrum (what a lens / sound-FFT / interferometer
     produces) of the modexp waveform a^x mod N shows peaks at the period --
     period recovered for small N. Real and runnable.
  2. Estimating the interference sum by complex Monte-Carlo (the "sign / phase
     problem") needs a number of samples that grows with the period r: at k = a*r
     samples the relative error is ~ 1/sqrt(a), INDEPENDENT of r, so to hold the
     error fixed the sample budget must scale with r. Exponential in bit-length.
  3. Mode counting: the spectrum is exactly r-sparse, so a classical M-mode wave
     device needs M >= r resolvable modes. classical wave = C^M, n qubits = C^(2^n).

Complexification is a great representational tool; it is not an exponential
compressor. Run:  python3 classical_wave.py
"""

import math
import random

import numpy as np

from tnshor.numtheory import make_small_order_instance
from tnshor.shor import classical_order, order_from_samples, factor_from_order


def hr(t):
    print("\n" + "=" * 80)
    print(t)
    print("=" * 80)


# ---------------------------------------------------------------------------
# 1. A classical Fourier transform of the modexp waveform recovers the period
# ---------------------------------------------------------------------------
def demo_classical_fft():
    hr("1. Classical FFT of the modexp waveform (small N): the period falls out")
    print("  Treat g(x) = a^x mod N as a real waveform and take its power spectrum")
    print("  |FFT(g)|^2 -- exactly what a lens, an interferometer, or a sound")
    print("  spectrum analyser computes physically. Peaks sit at multiples of Q/r.\n")
    for N, a in [(15, 7), (21, 2), (35, 2)]:
        r = classical_order(a, N)
        Q = 1
        while Q < 8 * N * N:           # enough resolution to separate the peaks
            Q <<= 1
        g = np.array([pow(a, x, N) for x in range(Q)], dtype=float)
        g = g - g.mean()               # drop the DC term so the comb stands out
        spec = np.abs(np.fft.rfft(g)) ** 2
        # collect the spectral peaks and read r off them with the SAME multi-peak
        # continued-fraction step Shor uses (a single peak can be a harmonic s*Q/r
        # with gcd(s,r)>1 -> a divisor; combining peaks recovers r).
        thr = 0.2 * spec[1:].max()
        bins = [b for b in range(1, len(spec)) if spec[b] >= thr]
        r_hat = order_from_samples(bins, {'Q': Q}, N, a)
        fac = factor_from_order(N, a, r_hat) if r_hat else None
        peaks = sorted(set(round(s * Q / r) for s in range(1, r)))[:6]
        print(f"  N={N:>3} a={a}  true r={r:<3} Q={Q:<6} "
              f"spectral peaks @bins {bins[:6]} -> r_hat={r_hat}  factors={fac}")
    print("\n  Yes: for small N a purely classical optical/acoustic FT reads the")
    print("  period. (Generating Q >= r samples of the waveform already costs ~r.)")


# ---------------------------------------------------------------------------
# 2. The sign / phase problem: complex Monte-Carlo variance scales with r
# ---------------------------------------------------------------------------
def mc_peak_relerr(r, Q, k, trials, rng):
    """Monte-Carlo estimate of the s=1 interference peak of the period-r comb.

    Peak coefficient  S = (1/Q) sum_x omega^{m* x} w(x),  w(x)=[r | x],
    m* = Q/r, true value 1/r.  Estimate by sampling k random x.  Returns median
    relative error over `trials`.
    """
    m_star = Q / r
    errs = []
    true = 1.0 / r
    for _ in range(trials):
        xs = rng.integers(0, Q, size=k)
        w = (xs % r == 0)
        terms = np.exp(2j * np.pi * m_star * xs[w] / Q)
        est = terms.sum() / k          # (1/Q) sum -> with uniform sampling /k
        errs.append(abs(est - true) / true)
    return float(np.median(errs))


def demo_sign_problem():
    hr("2. The sign / phase problem: Monte-Carlo samples must scale with r")
    print("  Estimate one interference peak (true height 1/r) by complex Monte-Carlo.")
    print("  Relative error at k = a*r samples is ~ 1/sqrt(a) for EVERY r -- so the")
    print("  sample budget to hold the error fixed grows linearly with the period.\n")
    Q = 1 << 16
    rng = np.random.default_rng(0)
    print(f"  {'r':>5}  " + "  ".join(f"k={al}*r" for al in (1, 4, 16, 64)))
    rows = []
    for r in [16, 32, 64, 128, 256]:
        cells = []
        for al in (1, 4, 16, 64):
            e = mc_peak_relerr(r, Q, al * r, trials=200, rng=rng)
            cells.append(e)
        rows.append((r, cells))
        print(f"  {r:>5}  " + "  ".join(f"{e:>6.2f}" for e in cells))
    print("\n  Each column is ~constant down the rows (error depends on a, not r):")
    print("  k must scale with r to keep accuracy. To resolve the peak AMPLITUDE")
    print("  (1/r) against phase-cancellation noise (1/sqrt k) needs k ~ r^2 -- the")
    print("  full sign problem. Either way it is exponential in the bit-length.")
    return rows


# ---------------------------------------------------------------------------
# 3. Mode counting:  classical wave = C^M,  n qubits = C^(2^n)
# ---------------------------------------------------------------------------
def demo_mode_counting():
    hr("3. Mode counting: how many physical wave modes does the comb need?")
    print("  The post-QFT spectrum is exactly r-sparse (r peaks). A classical wave")
    print("  with M modes lives in C^M; to carry r distinguishable peaks it needs")
    print("  M >= r resolvable modes. n qubits live in C^(2^n).\n")
    print(f"  {'bits(N)':>8} {'period r (~N)':>14} {'wave modes needed':>18} "
          f"{'qubit Hilbert dim':>18}")
    for bits in [16, 32, 64, 1024, 2048]:
        r = f"~2^{bits-1}"
        print(f"  {bits:>8} {r:>14} {('~2^%d' % (bits-1)):>18} {('2^%d' % (3*bits)):>18}")
    print("\n  Complexification doubles storage (Re+Im); it does not shrink the mode")
    print("  count. A random RSA comb needs ~2^(bits-1) classical modes -- exactly")
    print("  the chi = r wall in a different costume.")


def make_plot(sign_rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:  # pragma: no cover
        print(f"\n(matplotlib unavailable: {e}; skipping figure)")
        return None
    fig, ax = plt.subplots(1, 2, figsize=(12.5, 4.8))

    # left: the classical power spectrum a spectrum analyser would see (N=21)
    N, a = 21, 2
    r = classical_order(a, N)
    Q = 1
    while Q < 8 * N * N:
        Q <<= 1
    g = np.array([pow(a, x, N) for x in range(Q)], dtype=float)
    g = g - g.mean()
    spec = np.abs(np.fft.rfft(g)) ** 2
    spec = spec / spec.max()
    ax[0].plot(np.arange(len(spec)), spec, color="navy", lw=0.8)
    for s in range(1, r):
        ax[0].axvline(s * Q / r, color="green", ls=":", lw=0.8)
    ax[0].set_xlim(0, Q // 2)
    ax[0].set_xlabel("frequency bin")
    ax[0].set_ylabel("normalised power |FFT|^2")
    ax[0].set_title(f"Classical spectrum of a^x mod N (N=21, r={r}): peaks at s*Q/r")

    # right: sign-problem -- relative error vs r at fixed k=a*r (flat lines)
    rs = [row[0] for row in sign_rows]
    for j, al in enumerate((1, 4, 16, 64)):
        errs = [row[1][j] for row in sign_rows]
        ax[1].plot(rs, errs, "o-", label=f"k = {al}*r  (~1/sqrt({al}))")
    ax[1].set_xscale("log", base=2)
    ax[1].set_xlabel("period r")
    ax[1].set_ylabel("Monte-Carlo relative error")
    ax[1].set_title("Sign problem: error fixed by k/r, so samples scale with r")
    ax[1].legend(fontsize=8)
    ax[1].grid(alpha=0.3)

    fig.tight_layout()
    out = "classical_wave.png"
    fig.savefig(out, dpi=125)
    print(f"\nFigure written: {out}")
    return out


def main():
    np.set_printoptions(precision=4, suppress=True)
    demo_classical_fft()
    rows = demo_sign_problem()
    demo_mode_counting()
    make_plot(rows)
    hr("Verdict -- can classical physical interference do Shor's order finding?")
    print("""  Your reasoning holds, measured:
    * Classical optics / sound / images DO interfere and Fourier-transform; for
      small N a real power spectrum reads the period straight off.
    * Complexification (Re+Im, phase, FFT) is a powerful representation and gives
      genuine speedups on STRUCTURED data (sparse spectra, low rank, convolution).
    * But it is not an exponential compressor. Sampling the interference (complex
      Monte-Carlo) hits the sign/phase problem: the sample budget grows with r
      (linearly to detect, ~r^2 to resolve the amplitude). And the comb needs r
      resolvable wave modes -- C^M with M ~ r, not C^(2^n) for free.
  The quantum advantage is not "having interference"; it is holding 2^n
  phase-coherent, entangled computation paths in a compact physical system and
  interfering them once with the QFT. Classical waves have the interference but
  not the compact exponential state space -- unless the modexp structure itself
  compresses (small / smooth / low-bond-dimension r), which is the open door and
  the only known classical wins.""")


if __name__ == "__main__":
    main()
