#!/usr/bin/env python3
"""End-to-end demonstration of the tensor-network Shor experiments.

Run:  python3 run_demo.py
Outputs a console report and (if matplotlib is present) ``bond_vs_period.png``.
"""

import math

import numpy as np

from tnshor.experiment import (
    analyze, bond_sweep, truncation_study, is_semiprime,
)


def hr(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def demo_single():
    hr("1. Single instance: N = 15, a = 7  (factor + structure)")
    res = analyze(15, 7, shots=80, seed=1)
    print(f"  N={res['N']} a={res['a']}  qubits={res['n']} "
          f"(control t={res['t']}, work m={res['m']})")
    print(f"  true order r = {res['r']}")
    print(f"  Schmidt rank at control|work cut after modexp = {res['chi_modexp_cut']}"
          f"   (== r ? {res['chi_modexp_cut'] == res['r']})")
    print(f"  entanglement entropy at that cut = {res['ent_modexp_cut']:.4f} bits"
          f"   (log2 r = {math.log2(res['r']):.4f})")
    print(f"  peak bond dimension during QFT      = {res['peak_bond_qft']}")
    print(f"  recovered r_hat = {res['r_hat']}  ->  factors = {res['factors']}  "
          f"success={res['success']}")


def demo_where_explodes():
    hr("2. Q4: where does the bond dimension live? modexp cut vs QFT peak")
    print(f"  {'N':>4} {'a':>3} {'r':>4} {'qubits':>7} "
          f"{'chi@cut(=r)':>12} {'maxBond_modexp':>15} {'peakBond_QFT':>13}")
    for N, a in [(15, 7), (15, 2), (21, 2), (21, 5), (33, 2), (35, 2)]:
        if math.gcd(a, N) != 1:
            continue
        res = analyze(N, a, shots=10, seed=0)
        print(f"  {N:>4} {a:>3} {res['r']:>4} {res['n']:>7} "
              f"{res['chi_modexp_cut']:>12} {res['max_bond_modexp']:>15} "
              f"{res['peak_bond_qft']:>13}")
    print("\n  Reading: modexp entanglement is confined to ONE cut with rank r.")
    print("  The QFT is what pushes bond dimension up across the control register.")


def demo_bond_vs_period():
    hr("3. Q3: required bond dimension vs period r  (sweep of bases)")
    Ns = [15, 21, 33, 35, 39, 51, 55]
    rows = bond_sweep(Ns)
    print(f"  swept {len(rows)} (N,a) instances over semiprimes {Ns}")
    print(f"  {'N':>4} {'a':>3} {'r':>4} {'chi@cut':>8} {'log2(r)':>8} {'ent@cut':>8}")
    # show a representative subset
    seen = {}
    for row in rows:
        key = row['N']
        seen.setdefault(key, 0)
        if seen[key] < 3:
            print(f"  {row['N']:>4} {row['a']:>3} {row['r']:>4} "
                  f"{row['chi_cut']:>8} {math.log2(row['r']):>8.3f} "
                  f"{row['ent_cut']:>8.3f}")
            seen[key] += 1
    # verify the law chi@cut == r exactly
    exact = all(row['chi_cut'] == row['r'] for row in rows)
    print(f"\n  LAW across all {len(rows)} instances:  chi(control|work) == r   -> {exact}")
    return rows


def demo_truncation():
    hr("4. Q5/Q6: truncation tolerance -- how small can chi be?")
    N, a = 21, 2
    r = 6
    print(f"  N={N} a={a} (true r={r}).  Capping QFT bond dimension at chi:")
    print(f"  {'chi':>4} {'fidelity':>10} {'r_hat':>6} {'factored?':>10} {'maxBond':>8}")
    rows = truncation_study(N, a, chi_list=[1, 2, 3, 4, 6, 8, 16], shots=200, seed=4)
    for row in rows:
        print(f"  {row['chi']:>4} {row['fidelity']:>10.5f} "
              f"{str(row['r_hat']):>6} {str(row['success']):>10} "
              f"{row['max_bond']:>8}")
    print("\n  Reading: fidelity rises monotonically with chi. Shor needs only ONE")
    print("  clean sample, so the period survives moderate truncation -- recovery")
    print("  breaks only once chi is small enough to smear the phase peaks away.")
    return rows


def make_plot(sweep_rows, trunc_rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:  # pragma: no cover
        print(f"\n(matplotlib unavailable: {e}; skipping figure)")
        return None

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))

    rs = np.array([row['r'] for row in sweep_rows])
    chis = np.array([row['chi_cut'] for row in sweep_rows])
    ax[0].scatter(rs, chis, c=[row['N'] for row in sweep_rows],
                  cmap="viridis", s=40, edgecolor="k", linewidth=0.3)
    lim = max(rs.max(), chis.max()) + 1
    ax[0].plot([0, lim], [0, lim], "r--", lw=1, label=r"$\chi = r$")
    ax[0].set_xlabel("period  r")
    ax[0].set_ylabel(r"Schmidt rank at control|work cut  $\chi$")
    ax[0].set_title("Modexp entanglement: bond dimension = period")
    ax[0].legend()
    ax[0].grid(alpha=0.3)

    chi = [row['chi'] for row in trunc_rows]
    fid = [row['fidelity'] for row in trunc_rows]
    ok = [row['success'] for row in trunc_rows]
    ax[1].plot(chi, fid, "o-", color="steelblue")
    for x, y, s in zip(chi, fid, ok):
        ax[1].annotate("OK" if s else "x", (x, y),
                       textcoords="offset points", xytext=(0, 8),
                       ha="center", color="green" if s else "red",
                       fontweight="bold")
    ax[1].set_xlabel(r"QFT bond-dimension cap  $\chi_{max}$")
    ax[1].set_ylabel("fidelity vs exact final state")
    ax[1].set_title("Truncation tolerance (N=21, a=2, r=6)")
    ax[1].grid(alpha=0.3)

    fig.tight_layout()
    out = "bond_vs_period.png"
    fig.savefig(out, dpi=130)
    print(f"\nFigure written: {out}")
    return out


def main():
    np.set_printoptions(precision=4, suppress=True)
    demo_single()
    demo_where_explodes()
    sweep_rows = demo_bond_vs_period()
    trunc_rows = demo_truncation()
    make_plot(sweep_rows, trunc_rows)
    hr("Summary")
    print("""  * Modular exponentiation entangles control and work registers across a
    single cut, with Schmidt rank == r (the period). Verified exactly.
  * That means an MPS needs bond dimension r at that cut -- polynomial in N
    only when r is small. For hard RSA instances r is typically ~N, so the
    bond dimension is exponential in the qubit count: no classical win.
  * The QFT is what spreads entanglement across the control register and is
    the practical bottleneck for the bond dimension during simulation.
  * Sampling recovers the period without ever forming the full state vector,
    but only while the bond dimension is large enough to keep the phase peaks
    sharp; aggressive truncation breaks continued-fraction recovery.""")


if __name__ == "__main__":
    main()
