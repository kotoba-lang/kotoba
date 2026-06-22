"""Validate the gate-free scalable MPS construction + large-bit-width factoring."""

import math
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tnshor import shor_state, classical_order  # noqa: E402
from tnshor.scalable import (  # noqa: E402
    build_shor_mps_exact, factor_scalable, small_control_t,
)
from tnshor.numtheory import (  # noqa: E402
    make_small_order_instance, order_mod_n, random_safe_prime,
    random_smooth_prime, pollard_p_minus_1, is_prime, largest_prime_factor,
)


def test_direct_build_matches_statevector():
    for N, a in [(15, 7), (15, 2), (21, 2), (21, 5), (33, 2), (35, 2)]:
        if math.gcd(a, N) != 1:
            continue
        psi, geom = shor_state(N, a)
        mps, g2 = build_shor_mps_exact(N, a, t=geom['t'])
        got = mps.to_statevector()
        fid = abs(np.vdot(psi, got)) / (np.linalg.norm(psi) * np.linalg.norm(got))
        assert fid > 1 - 1e-10, (N, a, fid)
        # control|work bond must equal the period
        r = classical_order(a, N)
        assert mps.bond_dimensions()[geom['t'] - 1] == r, (N, a, r)
    print("direct build == statevector, and chi@cut == r   OK")


def test_scalable_factor_small():
    res = factor_scalable(15, 7, shots=80, seed=1)
    assert res['success'] and res['factors'][0] * res['factors'][1] == 15
    print(f"scalable factor N=15 OK -> {res['factors']}  (n={res['n']} qubits)")


def test_large_bitwidth_engineered():
    random.seed(12345)
    # 48-bit semiprime, small engineered order -> ~60-qubit Shor, no 2^n vector.
    N, a, r, (p, q) = make_small_order_instance(bits=48, order_p=2, order_q=3)
    assert order_mod_n(a, {p: 1, q: 1}) == r
    res = factor_scalable(N, a, t=small_control_t(2 * r), shots=240, seed=2,
                          verbose=True)
    assert res['n'] > 55, res['n']                 # far beyond statevector reach
    assert res['success'], (N, a, r, res['r_hat'])
    f1, f2 = res['factors']
    assert f1 * f2 == N and {f1, f2} == {p, q}
    print(f"large engineered: N={N} ({N.bit_length()} bit) a={a} r={r} "
          f"n={res['n']} qubits chi={res['chi_cut']} -> {res['factors']}  OK")


def test_real_rsa_helpers():
    random.seed(2026)
    # safe prime: (p-1)/2 is prime; smooth prime: p-1 is 4096-smooth
    sp = random_safe_prime(24)
    assert is_prime(sp) and is_prime((sp - 1) // 2)
    wk = random_smooth_prime(24, 4096)
    assert is_prime(wk) and largest_prime_factor(wk - 1) <= 4096
    # Pollard p-1: breaks a smooth-prime semiprime, fails on a safe-prime one
    Nw = random_smooth_prime(24, 4096) * random_smooth_prime(24, 4096)
    f = pollard_p_minus_1(Nw, B=8000)
    assert f and 1 < f < Nw and Nw % f == 0
    Ns = random_safe_prime(24) * random_safe_prime(24)
    assert pollard_p_minus_1(Ns, B=8000) is None
    print("real-RSA helpers: safe/smooth primes + Pollard p-1 reach   OK")


if __name__ == "__main__":
    test_direct_build_matches_statevector()
    test_scalable_factor_small()
    test_large_bitwidth_engineered()
    test_real_rsa_helpers()
    print("\nALL SCALABLE TESTS PASSED")
