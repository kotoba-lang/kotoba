"""Correctness tests: MPS engine vs exact state vector, and full Shor factoring."""

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tnshor import (  # noqa: E402
    MPS, shor_state, apply_qft_mps, apply_qft_statevector,
    classical_order, order_from_samples, factor_from_order,
)
from tnshor.shor import _H, _phase_gate  # noqa: E402


def test_roundtrip():
    rng = np.random.default_rng(0)
    n = 6
    psi = rng.standard_normal(2 ** n) + 1j * rng.standard_normal(2 ** n)
    psi /= np.linalg.norm(psi)
    mps = MPS.from_statevector(psi, n)
    assert np.allclose(mps.to_statevector(), psi, atol=1e-10)
    print("roundtrip OK   max_bond =", mps.max_bond())


def test_gates_match():
    rng = np.random.default_rng(1)
    n = 5
    psi = rng.standard_normal(2 ** n) + 1j * rng.standard_normal(2 ** n)
    psi /= np.linalg.norm(psi)
    mps = MPS.from_statevector(psi, n)

    # apply H on qubit 2 and a long-range controlled-phase between 0 and 4
    mps.apply_1q(2, _H)
    mps.apply_2q_long(0, 4, _phase_gate(math.pi / 3))

    # reference on the state vector
    ref = psi.reshape([2] * n)
    H = _H
    ref = np.tensordot(H, ref, axes=([1], [2]))
    ref = np.moveaxis(ref, 0, 2)
    G = _phase_gate(math.pi / 3)
    ref = np.tensordot(G, ref, axes=([2, 3], [0, 4]))   # in_c, in_t = sites 0,4
    ref = np.moveaxis(ref, [0, 1], [0, 4])
    ref = ref.reshape(-1)
    assert np.allclose(mps.to_statevector(), ref, atol=1e-9)
    print("gate match OK")


def test_qft_match():
    N, a = 15, 7
    psi, geom = shor_state(N, a)
    ref = apply_qft_statevector(psi, geom)
    mps = MPS.from_statevector(psi, geom['n'])
    apply_qft_mps(mps, geom['t'])
    got = mps.to_statevector()
    # global phase / fidelity
    fid = abs(np.vdot(ref, got)) / (np.linalg.norm(ref) * np.linalg.norm(got))
    assert fid > 1 - 1e-9, fid
    print(f"QFT match OK   fidelity = {fid:.12f}")


def test_sampling_distribution():
    N, a = 15, 7
    psi, geom = shor_state(N, a)
    mps = MPS.from_statevector(psi, geom['n'])
    apply_qft_mps(mps, geom['t'])
    exact = np.abs(mps.to_statevector()) ** 2
    rng = np.random.default_rng(2)
    shots = 40000
    samples = mps.sample(rng, shots=shots)
    hist = np.bincount(samples, minlength=len(exact)) / shots
    # total variation distance should be small
    tv = 0.5 * np.sum(np.abs(hist - exact))
    assert tv < 0.05, tv
    print(f"sampling OK   total-variation = {tv:.4f}")


def test_full_shor():
    N, a = 15, 7
    r_true = classical_order(a, N)
    psi, geom = shor_state(N, a)
    mps = MPS.from_statevector(psi, geom['n'])
    apply_qft_mps(mps, geom['t'])
    rng = np.random.default_rng(3)
    # control register = top t qubits => measured int // 2^m
    raw = mps.sample(rng, shots=60)
    ys = [v >> geom['m'] for v in raw]
    r = order_from_samples(ys, geom, N, a)
    assert r == r_true, (r, r_true)
    factors = factor_from_order(N, a, r)
    assert factors and factors[0] * factors[1] == N
    print(f"full Shor OK   N={N} a={a} r={r} -> {factors}")


if __name__ == "__main__":
    test_roundtrip()
    test_gates_match()
    test_qft_match()
    test_sampling_distribution()
    test_full_shor()
    print("\nALL TESTS PASSED")
