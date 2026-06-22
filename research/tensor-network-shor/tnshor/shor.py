"""Shor order-finding: exact wavefunction construction + classical post-processing.

The order-finding routine prepares

    |psi> = (1/sqrt(Q)) * sum_{x=0}^{Q-1} |x>_control |a^x mod N>_work

with ``Q = 2^t`` and then applies a Quantum Fourier Transform to the control
register.  Measuring the control register yields ``y ~ s*Q/r`` from which the
order ``r = ord_N(a)`` is recovered by continued fractions, and finally the
factors of ``N`` by ``gcd(a^{r/2} +/- 1, N)``.

Key structural fact (the thing the tensor-network experiments probe):  the only
entanglement created by modular exponentiation lives across the control|work
cut, and its Schmidt rank there equals the number of distinct residues of
``a^x mod N`` -- i.e. exactly the period ``r``.  So the bond dimension required
at that cut is ``r``, not ``2^(#qubits)``.
"""

from __future__ import annotations

import math
from fractions import Fraction

import numpy as np

from .mps import MPS


# --------------------------------------------------------------------- helpers
def classical_order(a, N):
    """Brute-force multiplicative order ord_N(a) (ground truth for small N)."""
    if math.gcd(a, N) != 1:
        return None
    x, r = a % N, 1
    while x != 1:
        x = (x * a) % N
        r += 1
        if r > N:
            return None
    return r


def choose_t(N):
    """Control-register size with Q = 2^t >= N^2 (the standard choice)."""
    return 2 * math.ceil(math.log2(N))


def work_qubits(N):
    return math.ceil(math.log2(N))


# ----------------------------------------------------------- wavefunction build
def shor_state(N, a, t=None):
    """Exact state vector |x>|a^x mod N> *before* the QFT, plus geometry info."""
    if t is None:
        t = choose_t(N)
    m = work_qubits(N)
    Q = 1 << t
    M = 1 << m
    n = t + m
    psi = np.zeros(1 << n, dtype=complex)
    for x in range(Q):
        val = pow(a, x, N)
        psi[x * M + val] += 1.0
    psi /= math.sqrt(Q)
    return psi, dict(t=t, m=m, n=n, Q=Q, M=M)


# ------------------------------------------------------------------- QFT (gates)
def _phase_gate(theta):
    """Controlled-phase as a 2-qubit gate (diagonal): diag(1,1,1,e^{i theta})."""
    g = np.eye(4, dtype=complex)
    g[3, 3] = np.exp(1j * theta)
    return g.reshape(2, 2, 2, 2)


_H = (1 / math.sqrt(2)) * np.array([[1, 1], [1, -1]], dtype=complex)


def apply_qft_mps(mps, t, chi_max=None, eps=0.0, track=False):
    """Apply a QFT over the first ``t`` sites of ``mps`` (the control register).

    Sites 0..t-1 are the control qubits with site 0 = MSB.  Returns the peak bond
    dimension reached during the transform when ``track`` is set.
    """
    peak = mps.max_bond()
    for j in range(t):
        mps.apply_1q(j, _H)
        for k in range(j + 1, t):
            theta = math.pi / (2 ** (k - j))
            mps.apply_2q_long(j, k, _phase_gate(theta), chi_max=chi_max, eps=eps)
            if track:
                peak = max(peak, mps.max_bond())
    # QFT outputs the transform in bit-reversed order; reverse via swap network.
    for i in range(t // 2):
        mps.apply_2q_long(i, t - 1 - i, MPS._SWAP, chi_max=chi_max, eps=eps)
        if track:
            peak = max(peak, mps.max_bond())
    return peak


def _cphase_swap(theta):
    """Controlled-phase(theta) followed by SWAP, as one 2-qubit gate.

    Matrix (basis 00,01,10,11):  00->00, 01->10, 10->01, 11->e^{i theta}*11.
    """
    w = np.exp(1j * theta)
    g = np.array([[1, 0, 0, 0],
                  [0, 0, 1, 0],
                  [0, 1, 0, 0],
                  [0, 0, 0, w]], dtype=complex)
    return g.reshape(2, 2, 2, 2)


def apply_qft_mps_lnn(mps, t, chi_max=None, eps=0.0, track=False):
    """QFT over the first ``t`` sites using only nearest-neighbor gates.

    "Rotate-and-swap" schedule: each logical qubit is Hadamard'd and then walked
    to the far end via combined controlled-phase + SWAP gates, picking up its
    rotation against every partner on the way.  This costs O(t^2) adjacent 2-qubit
    gates (vs O(t^3) for an explicit swap network) and leaves the output in
    natural (already bit-reversed) order.  Faithful to the full QFT.
    """
    peak = mps.max_bond()
    for i in range(t):
        # the next unprocessed qubit is currently at position 0
        mps.apply_1q(0, _H)
        for step in range(t - 1 - i):
            theta = math.pi / (2 ** (step + 1))
            mps.apply_2q(step, _cphase_swap(theta), chi_max=chi_max, eps=eps)
            if track:
                peak = max(peak, mps.max_bond())
    return peak


def qft_matrix(t):
    Q = 1 << t
    w = np.exp(2j * math.pi / Q)
    j = np.arange(Q)
    F = w ** np.outer(j, j) / math.sqrt(Q)
    return F


def apply_qft_statevector(psi, geom):
    """Reference QFT on the control register of the full state vector."""
    t, m, M = geom['t'], geom['m'], geom['M']
    F = qft_matrix(t)
    psi = psi.reshape(1 << t, M)
    psi = F @ psi
    return psi.reshape(-1)


# --------------------------------------------------------- classical post-process
def continued_fraction_order(y, Q, N):
    """Recover candidate order from a measured control value ``y`` (~ s*Q/r).

    The denominator bound is ``min(N, floor(sqrt(Q)))``.  A convergent ``p/q`` of
    ``y/Q`` equals ``s/r`` only when ``r < sqrt(Q)`` (so the ``1/(2Q)`` measurement
    error is below ``1/(2 r^2)``).  For the standard register size ``Q >= N^2`` this
    bound is just ``N`` (classic Shor); for a small control register tuned to a
    small known period it correctly becomes ``~sqrt(Q)``.
    """
    if y == 0:
        return None
    bound = min(N, math.isqrt(Q))
    frac = Fraction(y, Q).limit_denominator(bound)
    r = frac.denominator
    return r if r > 0 else None


def order_from_samples(samples, geom, N, a):
    """Recover the order ``r`` from measurement samples (textbook post-processing).

    Each sample's continued-fraction denominator is a candidate.  We keep only
    *verified* candidates (``a^cand == 1 mod N``) and combine divisor-candidates
    via lcm, returning the smallest period consistent with the data.  Shor only
    needs a single good sample, so the minimum verified candidate is the order.
    """
    Q = geom['Q']
    verified = set()
    raw = []
    for y in samples:
        cand = continued_fraction_order(int(y), Q, N)
        if cand and 1 < cand <= N:
            raw.append(cand)
            if pow(a, cand, N) == 1:
                verified.add(cand)
    if verified:
        return min(verified)
    # No single denominator was itself a period: try lcm of pairs of raw
    # candidates (they may be proper divisors r/gcd(s,r)).
    raw = sorted(set(raw))
    best = None
    for i in range(len(raw)):
        for j in range(i, len(raw)):
            l = raw[i] * raw[j] // math.gcd(raw[i], raw[j])
            if l <= N and pow(a, l, N) == 1:
                best = l if best is None else min(best, l)
    return best


def factor_from_order(N, a, r):
    """Return a nontrivial factor pair of N given order r, or None."""
    if r is None or r % 2 != 0:
        return None
    g = pow(a, r // 2, N)
    if g == N - 1:           # a^{r/2} == -1 mod N -> useless
        return None
    p = math.gcd(g - 1, N)
    q = math.gcd(g + 1, N)
    for f in (p, q):
        if 1 < f < N and N % f == 0:
            return (f, N // f)
    return None
