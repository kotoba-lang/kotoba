"""omni.isaac.motion_generation.LulaKinematicsSolver mirror.

Damped-least-squares IK + analytic FK for Cartpole / DoublePendulum / planar
n-link chains. Tracks 40-engine/kami-engine/kami-genesis/src/ik.rs
formula-for-formula. stdlib-only (math) to keep Pyodide/WASM build slim.

Public API mirrors Isaac Sim 4.x:
  - LulaKinematicsSolver(urdf_text)
  - compute_inverse_kinematics(frame_name, target_position, target_orientation,
        warm_start=None, position_tolerance=1e-3, orientation_tolerance=None,
        max_iters=200) -> (joint_positions, success)
  - compute_forward_kinematics(frame_name, joint_positions) -> (position, quat)
  - set_robot_base_pose(pos, rot)        # optional offset (R1.1: identity only)

Note: upstream Isaac Sim's LulaKinematicsSolver takes file paths
(`robot_description_path`, `urdf_path`). We accept the URDF text directly
because the religious-corp substrate does not assume a host filesystem layout.
The compute_* call shape and return values match upstream exactly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from ..._kernel import (
    ArticulatedSystem,
    DoublePendulumConfig,
    detect_cartpole_topology,
    detect_double_pendulum_topology,
    double_pendulum_cfg_from_urdf,
    parse_urdf,
)


@dataclass
class TargetPose:
    """Planar target pose: (x, z, theta_y). Other components ignored."""
    x: float
    z: float
    theta_y: float = 0.0


@dataclass
class IkResult:
    q: list
    converged: bool
    iters: int
    final_error: float


# ── Forward kinematics per topology ────────────────────────────────────────

def _cartpole_pose(x: float, theta: float, link: str) -> Optional[TargetPose]:
    if link == "world":
        return TargetPose(0.0, 0.0, 0.0)
    if link == "cart":
        return TargetPose(x, 0.0, 0.0)
    if link == "pole_link":
        return TargetPose(x + 0.25 * math.sin(theta), 0.25 * math.cos(theta), theta)
    return None


def _dp_pose(q1: float, q2: float, cfg: DoublePendulumConfig, link: str) -> Optional[TargetPose]:
    if link == "world":
        return TargetPose(0.0, 0.0, 0.0)
    if link == "link1":
        lc1 = cfg.l1 * 0.5
        return TargetPose(lc1 * math.sin(q1), -lc1 * math.cos(q1), q1)
    if link == "link2":
        lc2 = cfg.l2 * 0.5
        return TargetPose(
            cfg.l1 * math.sin(q1) + lc2 * math.sin(q1 + q2),
            -cfg.l1 * math.cos(q1) - lc2 * math.cos(q1 + q2),
            q1 + q2,
        )
    if link == "link2_tip":
        return TargetPose(
            cfg.l1 * math.sin(q1) + cfg.l2 * math.sin(q1 + q2),
            -cfg.l1 * math.cos(q1) - cfg.l2 * math.cos(q1 + q2),
            q1 + q2,
        )
    return None


# ── Planar Jacobian (rows: ∂x, ∂z, ∂θ_y; cols: ∂/∂q_i) ────────────────────

def _cartpole_planar_jacobian(theta: float, link: str) -> Optional[list]:
    if link == "world":
        return [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    if link == "cart":
        return [[1.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    if link == "pole_link":
        lc = 0.25
        return [
            [1.0, 0.0, 0.0],
            [lc * math.cos(theta), -lc * math.sin(theta), 1.0],
        ]
    return None


def _dp_planar_jacobian(q1: float, q2: float, cfg: DoublePendulumConfig, link: str) -> Optional[list]:
    if link == "world":
        return [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    if link == "link1":
        lc1 = cfg.l1 * 0.5
        return [
            [lc1 * math.cos(q1), lc1 * math.sin(q1), 1.0],
            [0.0, 0.0, 0.0],
        ]
    if link == "link2":
        lc2 = cfg.l2 * 0.5
        s1 = math.sin(q1)
        c1 = math.cos(q1)
        s12 = math.sin(q1 + q2)
        c12 = math.cos(q1 + q2)
        return [
            [cfg.l1 * c1 + lc2 * c12, cfg.l1 * s1 + lc2 * s12, 1.0],
            [lc2 * c12, lc2 * s12, 1.0],
        ]
    if link == "link2_tip":
        s1 = math.sin(q1)
        c1 = math.cos(q1)
        s12 = math.sin(q1 + q2)
        c12 = math.cos(q1 + q2)
        return [
            [cfg.l1 * c1 + cfg.l2 * c12, cfg.l1 * s1 + cfg.l2 * s12, 1.0],
            [cfg.l2 * c12, cfg.l2 * s12, 1.0],
        ]
    return None


# ── DLS linear solver (3×3 via Cramer) ─────────────────────────────────────

def _solve_dls(jac_cols: list, err: list, lam: float) -> list:
    """δq = J^T (J J^T + λ²I)^-1 e."""
    n = len(jac_cols)
    m = 3
    # A = J J^T + λ² I  (3×3)
    a = [[0.0] * m for _ in range(m)]
    for r in range(m):
        for c in range(m):
            s = sum(jac_cols[k][r] * jac_cols[k][c] for k in range(n))
            a[r][c] = s
            if r == c:
                a[r][c] += lam * lam
    # Cramer-rule 3×3 inversion
    det = (
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
        - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
        + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
    )
    if abs(det) < 1e-12:
        return [0.0] * n
    inv_det = 1.0 / det
    inv = [
        [
            (a[1][1] * a[2][2] - a[1][2] * a[2][1]) * inv_det,
            -(a[0][1] * a[2][2] - a[0][2] * a[2][1]) * inv_det,
            (a[0][1] * a[1][2] - a[0][2] * a[1][1]) * inv_det,
        ],
        [
            -(a[1][0] * a[2][2] - a[1][2] * a[2][0]) * inv_det,
            (a[0][0] * a[2][2] - a[0][2] * a[2][0]) * inv_det,
            -(a[0][0] * a[1][2] - a[0][2] * a[1][0]) * inv_det,
        ],
        [
            (a[1][0] * a[2][1] - a[1][1] * a[2][0]) * inv_det,
            -(a[0][0] * a[2][1] - a[0][1] * a[2][0]) * inv_det,
            (a[0][0] * a[1][1] - a[0][1] * a[1][0]) * inv_det,
        ],
    ]
    y = [inv[r][0] * err[0] + inv[r][1] * err[1] + inv[r][2] * err[2] for r in range(m)]
    return [
        jac_cols[k][0] * y[0] + jac_cols[k][1] * y[1] + jac_cols[k][2] * y[2]
        for k in range(n)
    ]


def _wrap_angle(a: float) -> float:
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


# ── LulaKinematicsSolver ──────────────────────────────────────────────────

class LulaKinematicsSolver:
    """Inverse-kinematics + forward-kinematics over a parsed URDF system.

    The supported topologies match the Rust kami-genesis solver:
      - Cartpole (1 prismatic + 1 revolute)
      - Double pendulum (2 revolute serial chain) — link names
        "link1", "link2", or virtual "link2_tip" (tip without com offset)

    For other topologies, compute_* return None / (q, False).
    """

    def __init__(self, urdf_text: str):
        self.system: ArticulatedSystem = parse_urdf(urdf_text)
        self._cartpole = detect_cartpole_topology(self.system)
        self._dp = detect_double_pendulum_topology(self.system)
        self._dp_cfg: Optional[DoublePendulumConfig] = None
        if self._dp:
            # Use placeholder gravity/dt; IK is purely kinematic so values don't matter.
            self._dp_cfg = double_pendulum_cfg_from_urdf(self.system, gravity=9.81, dt=1.0 / 240.0)
        self.base_pos = (0.0, 0.0, 0.0)
        self.base_rot = (0.0, 0.0, 0.0, 1.0)

    def set_robot_base_pose(self, pos: tuple, rot: tuple) -> None:
        """Mirror of Isaac Sim API. R1.1 accepts but does not yet compose into
        FK/IK (identity base assumed). Stored for future use."""
        self.base_pos = tuple(pos)
        self.base_rot = tuple(rot)

    def get_num_dofs(self) -> int:
        if self._cartpole or self._dp:
            return 2
        return 0

    def compute_forward_kinematics(
        self, frame_name: str, joint_positions: list,
    ) -> Optional[tuple]:
        """Returns (position, orientation_quat) for the named frame, or None
        if the frame is unknown.

        Position is a 3-tuple (x, y, z); orientation is a quaternion in
        (x, y, z, w) order. The planar topologies put y identically at 0 and
        the rotation is purely about world +y for cartpole and about world −y
        (q-axis convention) for the double pendulum / planar chain.
        """
        pose = self._planar_pose(frame_name, joint_positions)
        if pose is None:
            return None
        # Convert planar angle θ_y to a quaternion about y axis: (0, sin(θ/2), 0, cos(θ/2))
        half = pose.theta_y * 0.5
        quat = (0.0, math.sin(half), 0.0, math.cos(half))
        return ((pose.x, 0.0, pose.z), quat)

    def compute_inverse_kinematics(
        self,
        frame_name: str,
        target_position: tuple,
        target_orientation: Optional[tuple] = None,
        warm_start: Optional[list] = None,
        position_tolerance: float = 1e-3,
        orientation_tolerance: Optional[float] = None,
        max_iters: int = 200,
        damping_lambda: float = 0.05,
        step_size: float = 0.5,
    ) -> tuple:
        """Returns (joint_positions_list, success_bool).

        Position is a 3-tuple (target x, y, z). y is ignored for the planar
        topologies. orientation is a (x, y, z, w) quaternion; when provided,
        the y-axis angle is extracted and used as θ_y constraint. None means
        position-only IK.
        """
        dof = self.get_num_dofs()
        if dof == 0:
            return (list(warm_start) if warm_start else [], False)

        # Extract planar target.
        tx = float(target_position[0])
        tz = float(target_position[2])
        include_orient = target_orientation is not None
        if include_orient:
            # Extract θ_y from quaternion: q = (qx, qy, qz, qw). For pure
            # rotation about world +y: q = (0, sin(θ/2), 0, cos(θ/2)).
            qy = float(target_orientation[1])
            qw = float(target_orientation[3])
            target_theta = 2.0 * math.atan2(qy, qw)
        else:
            target_theta = 0.0

        target = TargetPose(tx, tz, target_theta)
        q = list(warm_start) if warm_start else [0.1] * dof

        converged = False
        iters = 0
        final_err = float("inf")
        for _ in range(max_iters):
            pose = self._planar_pose(frame_name, q)
            if pose is None:
                return (q, False)
            e_x = target.x - pose.x
            e_z = target.z - pose.z
            e_th = _wrap_angle(target.theta_y - pose.theta_y) if include_orient else 0.0
            err = [e_x, e_z, e_th]
            err_norm = math.sqrt(e_x * e_x + e_z * e_z + e_th * e_th)
            final_err = err_norm
            if err_norm < position_tolerance:
                converged = True
                break
            jac = self._planar_jacobian(frame_name, q)
            if jac is None:
                return (q, False)
            dq = _solve_dls(jac, err, damping_lambda)
            for i in range(dof):
                q[i] += step_size * dq[i]
            iters += 1

        return (q, converged)

    # ── helpers ───────────────────────────────────────────────────────

    def _planar_pose(self, frame: str, q: list) -> Optional[TargetPose]:
        if self._cartpole:
            return _cartpole_pose(q[0], q[1], frame)
        if self._dp:
            return _dp_pose(q[0], q[1], self._dp_cfg, frame)
        return None

    def _planar_jacobian(self, frame: str, q: list) -> Optional[list]:
        if self._cartpole:
            return _cartpole_planar_jacobian(q[1], frame)
        if self._dp:
            return _dp_planar_jacobian(q[0], q[1], self._dp_cfg, frame)
        return None
