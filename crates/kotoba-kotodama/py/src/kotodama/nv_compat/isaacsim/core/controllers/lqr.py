"""LQR (Linear Quadratic Regulator) for Cartpole — classical optimal control.

Mirrors 40-engine/kami-engine/kami-genesis/src/lqr.rs:
  1. Finite-difference Cartpole step around upright (theta=0) → A (4×4), B (4×1)
  2. Solve discrete-time algebraic Riccati equation by fixed-point iteration
  3. Gain K = (R + B^T P B)^{-1} B^T P A   (1×4 row for scalar control)
  4. Control u(s) = clamp(−K · s, ±max_effort)

stdlib-only.

Note: not part of upstream Isaac Sim's public API; included in nv_compat under
isaacsim.core.api.controllers as a kami-native extension that fills the
"classical baseline controller" gap when an RL-trained policy is not yet
available.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LqrWeights:
    """Diagonal Q (size 4) + scalar R."""
    q_diag: tuple = (1.0, 0.1, 100.0, 1.0)
    r: float = 0.1


@dataclass
class CartpoleConfig:
    """Mirror of kami_genesis::CartpoleConfig (re-defined here so nv_compat
    stays free of any cross-package import on the Rust side)."""
    cart_mass: float = 1.0
    pole_mass: float = 0.1
    pole_half_length: float = 0.25
    gravity: float = 9.81
    force_mag: float = 100.0
    dt: float = 1.0 / 60.0


def _step_one(s: list, action: float, cfg: CartpoleConfig) -> list:
    """One Cartpole step. Same formula as Rust CartpoleState::step."""
    force = max(-cfg.force_mag, min(cfg.force_mag, action))
    x, x_dot, theta, theta_dot = s
    sin_t, cos_t = math.sin(theta), math.cos(theta)
    total_mass = cfg.cart_mass + cfg.pole_mass
    pml = cfg.pole_mass * cfg.pole_half_length
    temp = (force + pml * theta_dot * theta_dot * sin_t) / total_mass
    theta_acc = (cfg.gravity * sin_t - cos_t * temp) / (
        cfg.pole_half_length * (4.0 / 3.0 - cfg.pole_mass * cos_t * cos_t / total_mass)
    )
    x_acc = temp - pml * theta_acc * cos_t / total_mass
    x_dot += cfg.dt * x_acc
    x += cfg.dt * x_dot
    theta_dot += cfg.dt * theta_acc
    theta += cfg.dt * theta_dot
    return [x, x_dot, theta, theta_dot]


def _linearize(cfg: CartpoleConfig, eps: float = 1e-3) -> tuple:
    """Build (A, B) by central finite differences around upright."""
    s0 = [0.0, 0.0, 0.0, 0.0]
    A = [[0.0] * 4 for _ in range(4)]
    for j in range(4):
        sp = list(s0); sm = list(s0)
        sp[j] += eps; sm[j] -= eps
        np_ = _step_one(sp, 0.0, cfg)
        nm_ = _step_one(sm, 0.0, cfg)
        for i in range(4):
            A[i][j] = (np_[i] - nm_[i]) / (2.0 * eps)
    np_ = _step_one(s0, eps, cfg)
    nm_ = _step_one(s0, -eps, cfg)
    B = [(np_[i] - nm_[i]) / (2.0 * eps) for i in range(4)]
    return A, B


def _mm(X: list, Y: list) -> list:
    return [[sum(X[i][k] * Y[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _mT(X: list) -> list:
    return [[X[j][i] for j in range(4)] for i in range(4)]


def _mv(X: list, v: list) -> list:
    return [sum(X[i][k] * v[k] for k in range(4)) for i in range(4)]


def _vT_m(v: list, X: list) -> list:
    return [sum(v[k] * X[k][j] for k in range(4)) for j in range(4)]


def _dot(a: list, b: list) -> float:
    return sum(a[i] * b[i] for i in range(4))


def _ma(X: list, Y: list) -> list:
    return [[X[i][j] + Y[i][j] for j in range(4)] for i in range(4)]


def _ms(X: list, Y: list) -> list:
    return [[X[i][j] - Y[i][j] for j in range(4)] for i in range(4)]


def _outer(a: list, b: list) -> list:
    return [[a[i] * b[j] for j in range(4)] for i in range(4)]


def _max_abs(X: list) -> float:
    return max(abs(X[i][j]) for i in range(4) for j in range(4))


def _solve_dare(A: list, B: list, w: LqrWeights, tol: float, max_iters: int) -> tuple:
    Q = [[0.0] * 4 for _ in range(4)]
    for i in range(4):
        Q[i][i] = w.q_diag[i]
    P = [row[:] for row in Q]
    At = _mT(A)
    iters = 0
    res = float("inf")
    for _ in range(max_iters):
        PA = _mm(P, A)
        Pb = _mv(P, B)              # 4×1
        bTPA = _vT_m(B, PA)         # 1×4
        bTPb = _dot(B, Pb)          # scalar
        s_inv = 1.0 / (w.r + bTPb)
        outer = _outer(Pb, bTPA)
        outer_scaled = [[outer[i][j] * s_inv for j in range(4)] for i in range(4)]
        AtPA = _mm(At, PA)
        AtPB_outer = _mm(At, outer_scaled)
        P_new = _ma(Q, _ms(AtPA, AtPB_outer))
        delta = _max_abs(_ms(P_new, P))
        P = P_new
        iters += 1
        res = delta
        if delta < tol:
            break
    return P, iters, res


@dataclass
class LqrController:
    gain: tuple = (0.0, 0.0, 0.0, 0.0)
    max_effort: float = 100.0
    dare_iters: int = 0
    dare_residual: float = float("inf")

    @staticmethod
    def build(cfg: Optional[CartpoleConfig] = None,
              weights: Optional[LqrWeights] = None) -> "LqrController":
        cfg = cfg or CartpoleConfig()
        weights = weights or LqrWeights()
        A, B = _linearize(cfg)
        P, iters, res = _solve_dare(A, B, weights, tol=1e-6, max_iters=1000)
        PA = _mm(P, A); Pb = _mv(P, B)
        bTPA = _vT_m(B, PA); bTPb = _dot(B, Pb)
        s_inv = 1.0 / (weights.r + bTPb)
        K = tuple(s_inv * bTPA[j] for j in range(4))
        return LqrController(gain=K, max_effort=cfg.force_mag,
                             dare_iters=iters, dare_residual=res)

    def control(self, state: list) -> float:
        """state = [x, x_dot, theta, theta_dot]; returns clamped scalar action."""
        u = -(self.gain[0] * state[0] + self.gain[1] * state[1]
              + self.gain[2] * state[2] + self.gain[3] * state[3])
        return max(-self.max_effort, min(self.max_effort, u))
