"""Scalable Shor: build the order-finding wavefunction as an MPS *directly*.

The pre-QFT state  |psi> = (1/sqrt(Q)) sum_x |x>|a^x mod N>  is built without ever
forming the 2^n state vector.  The construction is an exact finite-state automaton
threaded along the qubit chain:

* Control sites (MSB first): the bond carries the running partial product
  ``a^(prefix) mod N``.  Reading control bit ``i`` (weight ``2^(t-1-i)``) multiplies
  by ``g_i = a^(2^(t-1-i)) mod N`` when the bit is 1.  Every partial product lies in
  the cyclic subgroup <a> of size ``r``, so the bond dimension is <= r.
* The control|work boundary bond therefore has dimension exactly ``r`` -- the period.
* Work sites: emit the bits of the residue ``a^x mod N`` MSB first; the bond carries
  the not-yet-emitted low bits, collapsing to dimension 1 at the end.

Cost is O((t+m) * r^2) memory and time -- polynomial in the qubit count and in the
period.  Large bit-width N is reachable *iff* r stays small.
"""

from __future__ import annotations

import math

import numpy as np

from .mps import MPS
from .shor import (
    choose_t, work_qubits, apply_qft_mps_lnn, order_from_samples,
    factor_from_order,
)


def build_shor_mps_exact(N, a, t=None):
    """Exact MPS of |x>|a^x mod N> with bond dimension <= r.  No 2^n vector."""
    if t is None:
        t = choose_t(N)
    m = work_qubits(N)
    inv_sqrt2 = 1.0 / math.sqrt(2.0)
    tensors = []

    # ---- control register: bond label = running partial product a^(prefix) mod N
    labels = [1 % N]
    Dl = 1
    for i in range(t):
        e = t - 1 - i
        g = pow(a, 1 << e, N)               # multiply by this if bit i is set
        out_labels = []
        out_index = {}
        entries = []
        for l, p in enumerate(labels):
            for x in (0, 1):
                p2 = p if x == 0 else (p * g) % N
                j = out_index.get(p2)
                if j is None:
                    j = len(out_labels)
                    out_index[p2] = j
                    out_labels.append(p2)
                entries.append((l, x, j))
        Dr = len(out_labels)
        A = np.zeros((Dl, 2, Dr), dtype=complex)
        for (l, x, j) in entries:
            A[l, x, j] = inv_sqrt2
        tensors.append(A)
        labels, Dl = out_labels, Dr

    # bond now carries the full residue p = a^x mod N (Dl == r distinct values)
    # ---- work register: emit residue bits MSB first; bond = remaining low bits
    for j in range(m):
        rem = m - j                         # bits still encoded in the label
        topbit = rem - 1                    # position (within label) to emit now
        out_labels = []
        out_index = {}
        entries = []
        for l, lab in enumerate(labels):
            y = (lab >> topbit) & 1
            low = lab & ((1 << topbit) - 1)
            k = out_index.get(low)
            if k is None:
                k = len(out_labels)
                out_index[low] = k
                out_labels.append(low)
            entries.append((l, y, k))
        Dr = len(out_labels)
        A = np.zeros((Dl, 2, Dr), dtype=complex)
        for (l, y, k) in entries:
            A[l, y, k] = 1.0
        tensors.append(A)
        labels, Dl = out_labels, Dr

    assert Dl == 1, f"work register did not close to bond 1 (got {Dl})"
    geom = dict(t=t, m=m, n=t + m, Q=1 << t, M=1 << m)
    return MPS(tensors), geom


def small_control_t(r_bound, slack=5):
    """Control-register size that resolves a period up to ``r_bound`` by continued
    fractions (Q = 2^t >= ~ (r_bound^2) * 2^slack).  Far smaller than 2*log2(N)
    when r is known to be small -- the whole point of the engineered regime."""
    return 2 * max(1, r_bound).bit_length() + slack


def factor_scalable(N, a, t=None, chi_max=None, shots=200, seed=0, verbose=False):
    """Full scalable Shor: build MPS, QFT, sample, recover order, factor.

    ``t`` is the control-register size.  Default ``2*ceil(log2 N)`` is the size a
    *general* RSA instance needs (period could be ~N).  When the period is known
    to be small, pass a small ``t`` (see :func:`small_control_t`): the QFT is then
    cheap and its intermediate bond dimension stays small.  Never allocates a 2^n
    vector.  Returns a result dict.
    """
    mps, geom = build_shor_mps_exact(N, a, t=t)
    bonds = mps.bond_dimensions()
    cut = geom['t'] - 1
    chi_cut = bonds[cut]
    if verbose:
        print(f"  built MPS: n={geom['n']} qubits, control|work bond chi={chi_cut}")
    peak = apply_qft_mps_lnn(mps, geom['t'], chi_max=chi_max, track=True)
    if verbose:
        print(f"  QFT done: peak bond during transform = {peak}")
    rng = np.random.default_rng(seed)
    ys = [v >> geom['m'] for v in mps.sample(rng, shots=shots)]
    r_hat = order_from_samples(ys, geom, N, a)
    factors = factor_from_order(N, a, r_hat) if r_hat else None
    return dict(
        N=N, a=a, n=geom['n'], t=geom['t'], m=geom['m'],
        chi_cut=chi_cut, peak_bond_qft=peak,
        r_hat=r_hat, factors=factors, success=bool(factors),
        max_bond_final=mps.max_bond(),
    )


# ----------------------------------------------------------- resource modelling
def mps_bytes(n, chi, dtype_bytes=16):
    """Memory for an n-site qubit MPS at uniform bond dimension chi."""
    return n * 2 * chi * chi * dtype_bytes


def random_rsa_memory(bits):
    """Fundamental MPS memory (bytes) to run Shor on a *random* ``bits``-bit RSA
    modulus: chi = r ~ 2^(bits-1), n = 3*bits sites.  This is the irreducible
    period wall (an ideal QFT-free method still needs chi = r)."""
    n = 3 * bits
    chi = 1 << (bits - 1)
    return mps_bytes(n, chi)


def bits_frontier_from_memory(mem_bytes):
    """Largest random-RSA bit-width whose MPS fits in ``mem_bytes`` (period wall)."""
    lo, hi = 1, 1 << 16
    while lo < hi:
        mid = (lo + hi + 1) // 2
        # log2 of memory to avoid building giant ints
        log2_mem = math.log2(3 * mid) + 1 + 2 * (mid - 1) + 4
        if log2_mem <= math.log2(mem_bytes):
            lo = mid
        else:
            hi = mid - 1
    return lo


def bits_frontier_from_compute(flops_per_s, seconds):
    """Largest random-RSA bit-width whose contraction (~b^2 * chi^3 ops, chi=2^(b-1))
    finishes within the given compute budget."""
    budget_log2 = math.log2(flops_per_s) + math.log2(seconds)
    lo, hi = 1, 1 << 16
    while lo < hi:
        mid = (lo + hi + 1) // 2
        ops_log2 = 2 * math.log2(mid) + 3 * (mid - 1)
        if ops_log2 <= budget_log2:
            lo = mid
        else:
            hi = mid - 1
    return lo


def rsa_resource_estimate(bit_width, r):
    """Resource estimate to run scalable Shor on an N of ``bit_width`` bits with
    period ``r`` (chi == r).  Returns a dict of human-readable figures."""
    m = bit_width
    t = 2 * bit_width
    n = t + m
    chi = r
    raw = mps_bytes(n, chi)
    return dict(
        bit_width=bit_width, n_qubits=n, chi=chi,
        log2_chi=math.log2(r) if r > 0 else 0.0,
        mps_bytes_log2=(math.log2(raw) if raw > 0 else 0.0),
        mps_bytes=raw,
    )
