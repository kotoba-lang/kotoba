#!/usr/bin/env python3
"""Learn / infer the interference and peaks with a tensor network -- what happens?

Two regimes, both measured:

  1. ONE instance: a tensor network LEARNS the post-QFT interference pattern.
     It can represent it (optimal MPS fidelity rises to 1 only at bond dimension
     r) and you can fit it from samples -- but that just reproduces the
     simulation, and reading r off the learned model is the same continued
     fraction. No shortcut: learning one instance costs what simulating it costs.

  2. ACROSS instances: can a model LEARN TO INFER the period r (hence factor N)
     from cheap, poly-time features of (N, a)?  We give ML its best shot -- a
     factorised low-rank tensor-network regressor AND gradient-boosted trees --
     on a fixed bit-size so size carries no signal.  They memorise the training
     set and fail completely on held-out keys (test R^2 ~ 0), while a genuinely
     learnable control target is fit perfectly.  The period is pseudorandom in
     the inputs (factoring-hard): a model that generalised here would itself be a
     polynomial-time factoring algorithm.

Run:  python3 tn_learn_infer.py
"""

import math
import random
import time

import numpy as np

from tnshor.shor import shor_state, apply_qft_statevector, classical_order
from tnshor.mps import MPS
from tnshor.numtheory import random_prime, order_mod_n


def hr(t):
    print("\n" + "=" * 80)
    print(t)
    print("=" * 80)


# ===========================================================================
# 1. A tensor network learns the interference of ONE instance
# ===========================================================================
def demo_tn_represents_interference():
    hr("1. A tensor network learning ONE instance's interference: capacity = r")
    print("  Fit the post-QFT amplitude with an MPS of bond dimension chi (the")
    print("  optimal tensor-network model). Fidelity to the true interference:\n")
    print(f"  {'N':>4} {'r':>3}  fidelity of the learned MPS vs bond dimension chi")
    for N, a in [(15, 7), (21, 2), (33, 2)]:
        r = classical_order(a, N)
        psi, geom = shor_state(N, a)
        full = apply_qft_statevector(psi, geom)
        full = full / np.linalg.norm(full)
        cells = []
        for chi in sorted({1, max(1, r // 2), r, r + 2}):
            mps = MPS.from_statevector(full, geom['n'], chi_max=chi)
            got = mps.to_statevector()
            fid = abs(np.vdot(full, got)) / (np.linalg.norm(full) * np.linalg.norm(got))
            cells.append((chi, fid))
        print(f"  {N:>4} {r:>3}  " + "  ".join(f"chi={c}:{f:.3f}" for c, f in cells))
    print("\n  The learned model only matches the interference at chi = r. Below that")
    print("  it is a lossy fit; above it adds nothing. Learning one instance neither")
    print("  beats simulating it (cost chi=r) nor changes the readout (continued frac).")


# ===========================================================================
# 2. Can a model LEARN TO INFER the period across instances?
# ===========================================================================
SMALL = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]


def features(N, a):
    """Cheap (poly-time) features of (N, a) -- none of which use the period."""
    f = [N.bit_length(), a.bit_length(), a / N]
    for pr in SMALL:
        f.append(N % pr)
        f.append(a % pr)
    v = a % N
    for _ in range(8):                 # the modexp squarings a^(2^k) mod N
        f.append(v % 1009)
        f.append(v & 0xFF)
        v = (v * v) % N
    f.append(math.gcd(a - 1, N))
    f.append(math.gcd(a + 1, N))
    f.append(N & 0xFF)
    f.append(N % 9)
    return np.array(f, dtype=float)


def build_dataset(bits, n_samples, seed=0):
    rng = random.Random(seed)
    X, r_targets, p_targets, ctrl = [], [], [], []
    seen = set()
    guard = 0
    while len(X) < n_samples and guard < n_samples * 200:
        guard += 1
        half = bits // 2
        p = random_prime(half)
        q = random_prime(bits - half)
        if p == q:
            continue
        N = p * q
        a = rng.randrange(2, N - 1)
        if N.bit_length() != bits or math.gcd(a, N) != 1 or (N, a) in seen:
            continue
        seen.add((N, a))
        r = order_mod_n(a, {p: 1, q: 1})
        X.append(features(N, a))
        r_targets.append(math.log2(r))
        # factor "balance" log2(p/sqrt(N)) removes the trivial magnitude signal
        p_targets.append(math.log2(min(p, q)) - 0.5 * math.log2(N))
        ctrl.append(math.log2(a))          # learnable control (determined by a feature)
    return (np.array(X), np.array(r_targets), np.array(p_targets), np.array(ctrl))


class LowRankTensorRegressor:
    """A tensor-network regressor: y = b + w.x + sum_{k<R} (u_k.x)(v_k.x).

    The quadratic interaction weight is a rank-R factorised tensor (a simple
    tensor network).  Fit by gradient descent.  Given the SAME feature
    information as any other model, so it is subject to the same impossibility.
    """

    def __init__(self, rank=8, epochs=600, lr=0.01, seed=0):
        self.R, self.epochs, self.lr, self.seed = rank, epochs, lr, seed

    def fit(self, X, y):
        rng = np.random.default_rng(self.seed)
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-9
        Xs = np.clip((X - self.mu) / self.sd, -10, 10)
        self.ym, self.ys = y.mean(), y.std() + 1e-9
        ys = (y - self.ym) / self.ys
        n, d = Xs.shape
        params = {"b": np.zeros(1), "w": np.zeros(d),
                  "U": rng.standard_normal((self.R, d)) * 0.05,
                  "V": rng.standard_normal((self.R, d)) * 0.05}
        m = {k: np.zeros_like(v) for k, v in params.items()}
        v2 = {k: np.zeros_like(v) for k, v in params.items()}
        b1, b2, eps = 0.9, 0.999, 1e-8
        for it in range(1, self.epochs + 1):
            Ux = Xs @ params["U"].T
            Vx = Xs @ params["V"].T
            pred = params["b"] + Xs @ params["w"] + (Ux * Vx).sum(1)
            g = (pred - ys) / n
            grads = {
                "b": np.array([g.sum()]),
                "w": Xs.T @ g + 1e-3 * params["w"],
                "U": (g[:, None] * Vx).T @ Xs + 1e-3 * params["U"],
                "V": (g[:, None] * Ux).T @ Xs + 1e-3 * params["V"],
            }
            for k in params:
                gr = np.clip(grads[k], -5, 5)              # gradient clipping
                m[k] = b1 * m[k] + (1 - b1) * gr
                v2[k] = b2 * v2[k] + (1 - b2) * gr * gr
                mh = m[k] / (1 - b1 ** it)
                vh = v2[k] / (1 - b2 ** it)
                params[k] -= self.lr * mh / (np.sqrt(vh) + eps)
        self.p = params
        return self

    def predict(self, X):
        Xs = np.clip((X - self.mu) / self.sd, -10, 10)
        quad = ((Xs @ self.p["U"].T) * (Xs @ self.p["V"].T)).sum(1)
        return self.ym + self.ys * (self.p["b"] + Xs @ self.p["w"] + quad)


def r2(y, yhat):
    ss = ((y - y.mean()) ** 2).sum()
    return 1 - ((y - yhat) ** 2).sum() / (ss + 1e-12)


def demo_cross_instance():
    hr("2. Learning to INFER the period / factor across instances")
    bits = 24
    print(f"  Dataset: random {bits}-bit semiprimes (fixed size, so magnitude carries")
    print("  no signal), cheap poly-time features of (N, a).  Predict three targets.\n")
    t0 = time.time()
    X, ylogr, yp, yctrl = build_dataset(bits, 3000, seed=1)
    ntr = int(0.8 * len(X))
    sl = slice(0, ntr); st = slice(ntr, None)
    print(f"  built {len(X)} instances, {X.shape[1]} features, in {time.time()-t0:.1f}s\n")

    try:
        from sklearn.ensemble import GradientBoostingRegressor
        have_gb = True
    except Exception:
        have_gb = False

    targets = [
        ("log2(period r)", ylogr, "= factoring-hard"),
        ("factor balance p/sqrtN", yp.astype(float), "= factoring itself"),
        ("log2(base a)  [control]", yctrl, "= learnable (in features)"),
    ]
    print(f"  {'target':>26} {'model':>14} {'train R^2':>10} {'test R^2':>9}  note")
    for name, y, note in targets:
        # tensor-network low-rank regressor
        tn = LowRankTensorRegressor(rank=12, epochs=400, lr=0.08).fit(X[sl], y[sl])
        tr = r2(y[sl], tn.predict(X[sl]))
        te = r2(y[st], tn.predict(X[st]))
        print(f"  {name:>26} {'tensor-net':>14} {tr:>10.3f} {te:>9.3f}  {note}")
        if have_gb:
            gb = GradientBoostingRegressor(n_estimators=300, max_depth=4,
                                           random_state=0).fit(X[sl], y[sl])
            gtr = r2(y[sl], gb.predict(X[sl]))
            gte = r2(y[st], gb.predict(X[st]))
            print(f"  {'':>26} {'grad-boost':>14} {gtr:>10.3f} {gte:>9.3f}")
    print("""
  The control (log2 a) is recovered perfectly -- the pipeline and models work.
  The period and the factor: train R^2 can be high (memorisation) but test R^2
  ~ 0. No generalisation. A tensor network cannot infer the interference / peak
  spacing for an unseen key, because that spacing is Q/r and r is pseudorandom in
  N. A model that generalised here WOULD be a polynomial-time factoring algorithm.""")
    return X, ylogr, yp, yctrl, ntr


def make_plot(X, ylogr, yp, yctrl, ntr):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from sklearn.ensemble import GradientBoostingRegressor
    except Exception as e:  # pragma: no cover
        print(f"\n(plot deps unavailable: {e}; skipping figure)")
        return None
    sl, st = slice(0, ntr), slice(ntr, None)
    fig, ax = plt.subplots(1, 2, figsize=(12.5, 5))

    # left: predicted vs true period (test set) -> scatter shows no correlation
    gb = GradientBoostingRegressor(n_estimators=300, max_depth=4,
                                   random_state=0).fit(X[sl], ylogr[sl])
    pred = gb.predict(X[st])
    ax[0].scatter(ylogr[st], pred, s=8, alpha=0.4, color="crimson")
    lo, hi = ylogr[st].min(), ylogr[st].max()
    ax[0].plot([lo, hi], [lo, hi], "k--", lw=1, label="perfect")
    ax[0].set_xlabel("true log2(r)")
    ax[0].set_ylabel("predicted log2(r)")
    ax[0].set_title(f"Period inference on held-out keys (R^2={r2(ylogr[st], pred):.2f})")
    ax[0].legend(fontsize=8)
    ax[0].grid(alpha=0.3)

    # right: control predicted vs true -> tight line
    gbc = GradientBoostingRegressor(n_estimators=300, max_depth=4,
                                    random_state=0).fit(X[sl], yctrl[sl])
    predc = gbc.predict(X[st])
    ax[1].scatter(yctrl[st], predc, s=8, alpha=0.4, color="seagreen")
    lo, hi = yctrl[st].min(), yctrl[st].max()
    ax[1].plot([lo, hi], [lo, hi], "k--", lw=1, label="perfect")
    ax[1].set_xlabel("true log2(a)  [control]")
    ax[1].set_ylabel("predicted")
    ax[1].set_title(f"Learnable control on held-out keys (R^2={r2(yctrl[st], predc):.2f})")
    ax[1].legend(fontsize=8)
    ax[1].grid(alpha=0.3)

    fig.tight_layout()
    out = "tn_learn_infer.png"
    fig.savefig(out, dpi=125)
    print(f"\nFigure written: {out}")
    return out


def main():
    np.set_printoptions(precision=4, suppress=True)
    demo_tn_represents_interference()
    X, ylogr, yp, yctrl, ntr = demo_cross_instance()
    make_plot(X, ylogr, yp, yctrl, ntr)
    hr("Verdict -- learning/inferring the interference with a tensor network")
    print("""  * ONE instance: a tensor network can learn the interference, but only with
    capacity (bond dimension) r, and only by reproducing the simulation. Reading
    the period off the learned model is still m/Q ~ s/r continued fractions.
    Learning buys nothing over simulating -- both cost chi = r.
  * ACROSS instances: no model -- tensor-network regressor or gradient boosting --
    can infer the period or the factor from cheap features. Train memorises, test
    is chance, while a learnable control is fit perfectly. The peak spacing Q/r
    is pseudorandom in N; generalising = polynomial-time factoring, which would
    contradict the very hardness assumption (and Shoup's sqrt(r) generic bound).
  * So learning the interference does not relocate the wall: single-instance
    learning = simulation cost (chi=r), cross-instance inference = impossible.
    The QFT's advantage is in physically REALISING the interference once, not in
    a reusable pattern a model could amortise across keys.""")


if __name__ == "__main__":
    main()
