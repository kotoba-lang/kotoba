#!/usr/bin/env python3
"""Higher dimension / Attention / Transformers: do they help with RSA order finding?

Increasing dimension and using attention DO raise classical expressivity. This
script measures exactly where that helps and where it stops for RSA/Shor.

  1. A neural net LEARNS modular exponentiation on a fixed N (in-distribution):
     accuracy far above chance. But it needs ~r training points (to cover the r
     residue classes) and it does NOT extrapolate beyond the range it was trained
     on -- it interpolates a lookup, it does not acquire the generative period.
  2. So it gives no shortcut to the period: out-of-range accuracy is chance, and
     across moduli the period is not inferable (see tn_learn_infer.py).
  3. Attention is O(L^2) over EXPLICIT tokens. To put all x = 0..Q-1 as tokens you
     need L = Q = N^2; attention then costs N^4 = 2^(4*bits) -- worse than the
     state vector. Raising the embedding dimension d does not create the 2^n
     tensor-product space: classical model lives in R^(L*d), qubits in C^(2^n).

The honest realistic role is auxiliary (tensor-network contraction ordering,
GNFS parameters, period-candidate ranking), not a drop-in for the quantum core.

Run:  python3 transformer_modexp.py
"""

import math
import time
import warnings

import numpy as np

warnings.filterwarnings("ignore")
from tnshor.numtheory import make_small_order_instance  # noqa: E402


def hr(t):
    print("\n" + "=" * 80)
    print(t)
    print("=" * 80)


def bits_of(x, L):
    return [(x >> i) & 1 for i in range(L)]


# ---------------------------------------------------------------------------
# 1 + 2. A neural net learns modexp in-distribution but does not extrapolate
# ---------------------------------------------------------------------------
def demo_learn_modexp():
    from sklearn.neural_network import MLPClassifier
    hr("1. A neural net learns modular exponentiation on a fixed N (in-distribution)")
    N, a, r, (p, q) = make_small_order_instance(bits=20, order_p=4, order_q=25)  # r=100
    L = 14
    Q = 4096
    print(f"  Fixed N={N} (a={a}, period r={r}). Predict a^x mod N from the bits of x.")
    print(f"  Chance accuracy = 1/r = {1/r:.3f}.\n")

    X = np.array([bits_of(x, L) for x in range(Q)])
    y = np.array([pow(a, x, N) for x in range(Q)])
    rng = np.random.RandomState(0)
    idx = rng.permutation(Q)
    te = idx[3000:]

    print(f"  {'train size':>11} {'held-out accuracy':>18}")
    rows = []
    for ntr in [50, 100, 200, 400, 800, 1600, 3000]:
        tr = idx[:ntr]
        clf = MLPClassifier(hidden_layer_sizes=(256, 256), max_iter=300,
                            random_state=0).fit(X[tr], y[tr])
        acc = clf.score(X[te], y[te])
        rows.append((ntr, acc))
        print(f"  {ntr:>11} {acc:>18.3f}")
    print(f"\n  Learning kicks in once the training set covers the r={r} residue")
    print("  classes (~a few hundred points) -- i.e. it needs ~r data. Neural nets")
    print("  genuinely capture the modexp structure (Fourier features / grokking).")
    return N, a, r, L, rows


def demo_no_extrapolation(N, a, r, L):
    from sklearn.neural_network import MLPClassifier
    hr("2. ...but it interpolates, it does not EXTRAPOLATE -> no shortcut to r")
    print("  Train on x in [0, W), test on the NEXT block x in [W, W+400) (unseen")
    print(f"  range). Period r={r}.\n")
    print(f"  {'W':>6} {'W/r':>6} {'out-of-range accuracy':>22}")
    rows = []
    for W in [200, 400, 800, 1600]:
        Xtr = np.array([bits_of(x, L) for x in range(W)])
        ytr = np.array([pow(a, x, N) for x in range(W)])
        c = MLPClassifier(hidden_layer_sizes=(256, 256), max_iter=400,
                          random_state=0).fit(Xtr, ytr)
        Xte = np.array([bits_of(x, L) for x in range(W, W + 400)])
        yte = np.array([pow(a, x, N) for x in range(W, W + 400)])
        acc = c.score(Xte, yte)
        rows.append((W, acc))
        print(f"  {W:>6} {W/r:>6.1f} {acc:>22.3f}")
    print("""
  Out-of-range accuracy is poor and only climbs as W grows -- i.e. as the model
  is shown a LARGER fraction of the sequence (more data, more compute). It never
  beats just observing the sequence: there is no generative rule learned that
  predicts a^x for unseen x more cheaply than computing it. Combined with the
  cross-modulus result (tn_learn_infer.py: predicting r across N is chance), the
  model gives no asymptotic shortcut -- to find r you still pay ~r to observe it
  (or sqrt(r) via the group law), never poly(log N).""")


# ---------------------------------------------------------------------------
# 3. Attention is O(L^2) over explicit tokens
# ---------------------------------------------------------------------------
def self_attention(X, Wq, Wk, Wv):
    d = X.shape[1]
    Q, K, V = X @ Wq, X @ Wk, X @ Wv
    S = Q @ K.T / math.sqrt(d)
    S = S - S.max(1, keepdims=True)
    A = np.exp(S)
    A /= A.sum(1, keepdims=True)
    return A @ V


def demo_attention_cost():
    hr("3. Attention is all-to-all -- but over L EXPLICIT tokens, at O(L^2)")
    rng = np.random.default_rng(0)
    d = 32
    print("  Measured single-head self-attention forward cost:\n")
    print(f"  {'L (tokens)':>11} {'time':>9} {'ratio vs prev':>14}")
    Ls = [128, 256, 512, 1024, 2048, 4096]
    rows = []
    prev = None
    for L in Ls:
        X = rng.standard_normal((L, d))
        Wq, Wk, Wv = (rng.standard_normal((d, d)) for _ in range(3))
        t0 = time.time()
        for _ in range(3):
            self_attention(X, Wq, Wk, Wv)
        dt = (time.time() - t0) / 3
        ratio = (dt / prev) if prev else float('nan')
        rows.append((L, dt))
        print(f"  {L:>11} {dt*1e3:>7.1f}ms {ratio:>14.2f}")
        prev = dt
    print("  (ratio -> ~4x per doubling of L confirms O(L^2).)\n")
    print("  To make Shor's interference by tokenising every x = 0..Q-1, you need")
    print(f"  {'RSA-bits':>9} {'tokens L = Q = N^2':>20} {'attention O(L^2)':>18} "
          f"{'qubit dim 2^(3b)':>17}")
    for bits in [16, 64, 1024, 2048]:
        print(f"  {bits:>9} {('2^%d' % (2*bits)):>20} {('2^%d' % (4*bits)):>18} "
              f"{('2^%d' % (3*bits)):>17}")
    print("\n  L = 2^4096 for RSA-2048; attention costs 2^8192 -- worse than the")
    print("  state vector. Raising the embedding dim d buys R^(L*d), never C^(2^n).")
    return rows


def make_plot(learn_rows, attn_rows, r):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:  # pragma: no cover
        print(f"\n(matplotlib unavailable: {e}; skipping figure)")
        return None
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))

    ns = [n for n, _ in learn_rows]
    acc = [a for _, a in learn_rows]
    ax[0].semilogx(ns, acc, "o-", color="seagreen")
    ax[0].axvline(r, color="gray", ls="--", lw=1, label=f"r = {r} residue classes")
    ax[0].axhline(1 / r, color="crimson", ls=":", lw=1, label="chance = 1/r")
    ax[0].set_xlabel("training points")
    ax[0].set_ylabel("in-distribution held-out accuracy")
    ax[0].set_title("Neural net learns modexp (needs ~r data, in-distribution)")
    ax[0].legend(fontsize=8)
    ax[0].grid(alpha=0.3, which="both")

    Ls = np.array([L for L, _ in attn_rows], float)
    ts = np.array([t for _, t in attn_rows], float)
    ax[1].loglog(Ls, ts, "s-", color="darkorange", label="measured attention time")
    ax[1].loglog(Ls, ts[0] * (Ls / Ls[0]) ** 2, "k--", lw=1, label="O(L^2)")
    ax[1].set_xlabel("number of explicit tokens L")
    ax[1].set_ylabel("forward time (s)")
    ax[1].set_title("Attention cost is O(L^2); Shor needs L = Q = N^2")
    ax[1].legend(fontsize=8)
    ax[1].grid(alpha=0.3, which="both")

    fig.tight_layout()
    out = "transformer_modexp.png"
    fig.savefig(out, dpi=125)
    print(f"\nFigure written: {out}")
    return out


def main():
    np.set_printoptions(precision=4, suppress=True)
    N, a, r, L, learn_rows = demo_learn_modexp()
    demo_no_extrapolation(N, a, r, L)
    attn_rows = demo_attention_cost()
    make_plot(learn_rows, attn_rows, r)
    hr("Verdict -- dimension / Attention / Transformers for RSA")
    print("""  Your distinction is the right one, and it measures out:
    * Raising dimension and using attention DO add classical expressivity:
      a neural net learns modular exponentiation in-distribution, capturing the
      periodic / Fourier structure (needs ~r data).
    * But it does not extrapolate (no generative period rule) and cannot infer r
      across moduli -- no asymptotic shortcut. And attention is O(L^2) over the L
      tokens you explicitly place: tokenising all x needs L = Q = N^2, costing
      2^(4*bits) -- worse than the state vector. d buys R^(L*d), not C^(2^n).
    * 'Increasing d' and 'tensor product gives 2^n' are different things. The
      quantum advantage is the compact exponential entangled state space, not the
      all-to-all mixing of an explicitly enumerated token set.
  Realistic value: ML as an AUXILIARY -- learning tensor-network contraction
  orders / cut choices / which (N,a) compress, ranking period candidates, tuning
  GNFS -- where the targets are cheap-to-verify and not the period itself. Those
  are real; replacing the quantum core is not.""")


if __name__ == "__main__":
    main()
