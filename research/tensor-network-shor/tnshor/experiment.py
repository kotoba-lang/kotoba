"""Experiments probing the research questions from the design note.

Q3  How does the required bond dimension depend on a, r, p-1, q-1?
Q4  Where does the bond dimension explode -- modular exponentiation, or QFT?
Q5  Can we sample measurements (and recover the period) without the full state?
Q6  Which (N, a) succeed under aggressive truncation, and which fail?
"""

from __future__ import annotations

import math

import numpy as np

from .mps import MPS
from .shor import (
    shor_state, apply_qft_mps, classical_order, order_from_samples,
    factor_from_order,
)


def is_semiprime(N):
    f = []
    n = N
    d = 2
    while d * d <= n:
        while n % d == 0:
            f.append(d)
            n //= d
        d += 1
    if n > 1:
        f.append(n)
    return len(f) == 2 and f[0] != f[1], (f if len(f) == 2 else None)


def analyze(N, a, chi_max=None, eps=0.0, shots=80, seed=0):
    """Full single-instance analysis.  ``chi_max``/``eps`` truncate the QFT."""
    r = classical_order(a, N)
    psi, geom = shor_state(N, a)
    t, m, n = geom['t'], geom['m'], geom['n']

    # Exact MPS of the post-modexp state (no truncation): this is the wavefunction
    # whose entanglement structure we want to characterise.
    mps = MPS.from_statevector(psi, n)
    bonds_modexp = mps.bond_dimensions()
    ent_modexp = mps.entropy_profile()
    cut = t - 1  # bond just after the control register == control|work boundary
    chi_cut = bonds_modexp[cut]
    ent_cut = ent_modexp[cut]

    # Now run the QFT on the control register, optionally truncating.
    peak_qft = apply_qft_mps(mps, t, chi_max=chi_max, eps=eps, track=True)
    bonds_after = mps.bond_dimensions()
    trunc_err = mps.truncation_error

    # Sample the control register and try to recover r + factor N.
    rng = np.random.default_rng(seed)
    raw = mps.sample(rng, shots=shots)
    ys = [v >> m for v in raw]
    r_hat = order_from_samples(ys, geom, N, a)
    factors = factor_from_order(N, a, r_hat) if r_hat else None

    return dict(
        N=N, a=a, r=r, n=n, t=t, m=m,
        chi_modexp_cut=chi_cut,            # == r  (headline result)
        ent_modexp_cut=ent_cut,            # == log2(r)
        max_bond_modexp=max(bonds_modexp),
        peak_bond_qft=peak_qft,
        max_bond_after_qft=max(bonds_after),
        chi_max=chi_max, eps=eps,
        truncation_error=trunc_err,
        r_hat=r_hat,
        success=bool(factors),
        factors=factors,
    )


def bond_sweep(Ns, max_a_per_N=None):
    """For each semiprime N and each valid base a, record period and bond dims.

    Returns a list of rows (dicts) -- exact (untruncated) bond dimensions only.
    """
    rows = []
    for N in Ns:
        ok, _ = is_semiprime(N)
        if not ok:
            continue
        bases = [a for a in range(2, N) if math.gcd(a, N) == 1]
        if max_a_per_N:
            bases = bases[:max_a_per_N]
        for a in bases:
            r = classical_order(a, N)
            psi, geom = shor_state(N, a)
            mps = MPS.from_statevector(psi, geom['n'])
            bonds = mps.bond_dimensions()
            cut = geom['t'] - 1
            rows.append(dict(
                N=N, a=a, r=r, n=geom['n'], t=geom['t'],
                chi_cut=bonds[cut], max_bond=max(bonds),
                ent_cut=mps.entropy_profile()[cut],
            ))
    return rows


def truncation_study(N, a, chi_list, shots=120, seed=0):
    """How small can the bond dimension be before period recovery breaks?

    We compute the exact post-QFT state, then globally recompress it to bond
    dimension ``chi`` (one clean SVD truncation, monotonic in chi) and ask
    whether sampling that compressed state still recovers the order.
    """
    from .shor import order_from_samples, factor_from_order
    r_true = classical_order(a, N)
    psi, geom = shor_state(N, a)
    ex = MPS.from_statevector(psi, geom['n'])
    apply_qft_mps(ex, geom['t'])
    exact = ex.to_statevector()

    out = []
    for chi in chi_list:
        comp = MPS.from_statevector(exact, geom['n'], chi_max=chi)
        got = comp.to_statevector()
        fid = abs(np.vdot(exact, got)) / (np.linalg.norm(exact) * np.linalg.norm(got))
        rng = np.random.default_rng(seed)
        ys = [v >> geom['m'] for v in comp.sample(rng, shots=shots)]
        r_hat = order_from_samples(ys, geom, N, a)
        factors = factor_from_order(N, a, r_hat) if r_hat else None
        out.append(dict(
            chi=chi, r_true=r_true, r_hat=r_hat,
            success=bool(factors), fidelity=float(fid),
            max_bond=comp.max_bond(),
        ))
    return out
