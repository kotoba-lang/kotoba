"""OperationalSpaceController — task-space torque control.

Mirror of `isaaclab.controllers.OperationalSpaceController` (Isaac Lab 1.x).
Sibling of iter 41 DifferentialIKController:

  - DifferentialIKController: target pose → joint POSITION delta via
    Jacobian damped-least-squares. Pairs with JointPositionAction.
  - OperationalSpaceController: target pose / wrench → joint TORQUE via
    Jacobian transpose. Pairs with JointEffortAction directly.

OSC is the canonical contact-rich manipulation controller — Cartesian
impedance (stiffness × position error + damping × velocity error) →
6-DOF task-space wrench → joint torque via τ = Jᵀ F_task. Optionally
adds gravity compensation and null-space joint regularization for
redundant arms (>6 DoF).

Standard usage:

    cfg = OperationalSpaceControllerCfg(
        target_types=["pose_abs"],
        impedance_mode="fixed",
        motion_stiffness_task=[100, 100, 100, 50, 50, 50],
        motion_damping_ratio_task=[1.0] * 6,
        nullspace_control="position",
    )
    osc = OperationalSpaceController(cfg, num_envs=1, num_dof=7)
    osc.set_command(target_pose=[x,y,z,qx,qy,qz,qw])
    tau = osc.compute(
        ee_pos=current_ee_pos, ee_quat=current_ee_quat,
        ee_lin_vel=ee_lin_vel, ee_ang_vel=ee_ang_vel,
        jacobian=J6n, mass_matrix=M_n_n,
        joint_pos=q, joint_vel=dq,
        nullspace_target_pos=q_default,
    )
    # τ feeds directly into JointEffortAction → articulation

Pure stdlib (math + list-of-lists). Composes with iter 41 utils.math
helpers (inlined here for standalone) + iter 40 JointEffortAction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


# ────────────────────────────────────────────────────────────────────────────
# Cfg
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class OperationalSpaceControllerCfg:
    """Mirror of `isaaclab.controllers.OperationalSpaceControllerCfg`.

    target_types: list of target categories the controller accepts. Each
                  entry one of "pose_abs" / "pose_rel" / "wrench_abs" /
                  "force_abs" / "torque_abs".
    impedance_mode: "fixed" — gains constant from cfg
                    "variable" — gains arrive as part of command vector
    motion_stiffness_task: 6-vec K_p_task (3 linear + 3 angular)
    motion_damping_ratio_task: 6-vec ζ (1.0 = critically damped)
    motion_stiffness_limits / motion_damping_limits: bounds when
        impedance_mode="variable"
    nullspace_control: "none" / "position" — when "position", regularize
                       redundant DoFs toward nullspace_target_pos
    nullspace_stiffness / nullspace_damping_ratio: scalars for the
                       null-space P/D loop
    gravity_compensation: when True, OSC adds the gravity-comp torque
                          τ_g = G(q) (the host supplies this — usually
                          the articulation's `_kernel.gravity_torque`)
    """
    target_types: List[str] = field(default_factory=lambda: ["pose_abs"])
    impedance_mode: str = "fixed"
    motion_stiffness_task: List[float] = field(
        default_factory=lambda: [100.0] * 6,
    )
    motion_damping_ratio_task: List[float] = field(
        default_factory=lambda: [1.0] * 6,
    )
    motion_stiffness_limits: Tuple[float, float] = (0.0, 1000.0)
    motion_damping_limits: Tuple[float, float] = (0.0, 100.0)
    nullspace_control: str = "none"
    nullspace_stiffness: float = 10.0
    nullspace_damping_ratio: float = 1.0
    gravity_compensation: bool = False


# ────────────────────────────────────────────────────────────────────────────
# Math helpers — quaternion + matrix ops (inlined from iter 35 utils.math)
# ────────────────────────────────────────────────────────────────────────────


def _quat_inverse(q: tuple) -> tuple:
    qx, qy, qz, qw = q
    n2 = qx*qx + qy*qy + qz*qz + qw*qw
    if n2 < 1e-24:
        return (0.0, 0.0, 0.0, 1.0)
    inv = 1.0 / n2
    return (-qx*inv, -qy*inv, -qz*inv, qw*inv)


def _quat_mul(q1: tuple, q2: tuple) -> tuple:
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2
    return (
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2,
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
    )


def _axis_angle_vec(q: tuple) -> tuple:
    """Quaternion → axis-angle 3-vec (axis * angle), shortest-arc."""
    qx, qy, qz, qw = q
    if qw < 0.0:
        qx, qy, qz, qw = -qx, -qy, -qz, -qw
    qw = max(-1.0, min(1.0, qw))
    angle = 2.0 * math.acos(qw)
    s = math.sqrt(max(0.0, 1.0 - qw*qw))
    if s < 1e-8:
        return (0.0, 0.0, 0.0)
    inv_s = 1.0 / s
    return (qx*inv_s*angle, qy*inv_s*angle, qz*inv_s*angle)


# ────────────────────────────────────────────────────────────────────────────
# OperationalSpaceController
# ────────────────────────────────────────────────────────────────────────────


class OperationalSpaceController:
    """Task-space impedance + force controller.

    On `compute()`:
      1. Compute pose error e = [pos_err (3-vec); ori_err (axis-angle 3-vec)]
      2. Compute velocity error de = -[ee_lin_vel; ee_ang_vel]  (target rest = 0)
      3. Task-space wrench:
         F_task = K_p · e + K_d · de   (6-vec)
      4. Joint torque via Jacobian transpose:
         τ = Jᵀ · F_task   (n-vec)
      5. Optional null-space joint regularization:
         τ_ns = (I - Jᵀ · J⁺ᵀ) · τ_nullspace
         where τ_nullspace = K_p_ns·(q_target - q) - K_d_ns·dq
      6. Optional gravity compensation: τ += G(q)
    """

    cfg: OperationalSpaceControllerCfg

    def __init__(self, cfg: OperationalSpaceControllerCfg,
                  num_envs: int = 1, num_dof: int = 7):
        if num_envs <= 0:
            raise ValueError(f"num_envs must be > 0; got {num_envs}")
        if num_dof <= 0:
            raise ValueError(f"num_dof must be > 0; got {num_dof}")
        if cfg.impedance_mode not in ("fixed", "variable"):
            raise ValueError(
                f"impedance_mode must be 'fixed' or 'variable'; got {cfg.impedance_mode!r}"
            )
        if cfg.nullspace_control not in ("none", "position"):
            raise ValueError(
                f"nullspace_control must be 'none' or 'position'; got {cfg.nullspace_control!r}"
            )
        if len(cfg.motion_stiffness_task) != 6:
            raise ValueError(
                f"motion_stiffness_task must be 6-vec; got {len(cfg.motion_stiffness_task)}"
            )
        if len(cfg.motion_damping_ratio_task) != 6:
            raise ValueError(
                f"motion_damping_ratio_task must be 6-vec; got {len(cfg.motion_damping_ratio_task)}"
            )
        self.cfg = cfg
        self.num_envs = num_envs
        self.num_dof = num_dof
        # Per-env target pose [px, py, pz, qx, qy, qz, qw] (identity quat default).
        self._target: List[List[float]] = [
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0] for _ in range(num_envs)
        ]
        # Per-env variable gains (overwrites cfg.motion_stiffness_task when set).
        self._variable_stiffness: List[Optional[List[float]]] = [None] * num_envs

    # ── action_dim ───────────────────────────────────────────────────────

    @property
    def action_dim(self) -> int:
        """Length of one command vector.

        pose_abs: 7 (xyz + quat). variable impedance adds 6 (stiffness) +
        6 (damping ratio) = 12. So pose_abs + variable = 19.
        """
        dim = 0
        for tt in self.cfg.target_types:
            if tt == "pose_abs":
                dim += 7
            elif tt == "pose_rel":
                dim += 6  # xyz delta + axis-angle delta
            elif tt == "wrench_abs":
                dim += 6  # force + torque
            elif tt == "force_abs":
                dim += 3
            elif tt == "torque_abs":
                dim += 3
        if self.cfg.impedance_mode == "variable":
            dim += 12   # 6 stiffness + 6 damping ratio
        return dim

    # ── target management ────────────────────────────────────────────────

    def reset(self, env_ids: Optional[List[int]] = None) -> None:
        targets = env_ids if env_ids is not None else list(range(self.num_envs))
        for i in targets:
            self._target[i] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
            self._variable_stiffness[i] = None

    def set_command(
        self,
        command: List[float],
        ee_pos: Optional[List[float]] = None,
        ee_quat: Optional[List[float]] = None,
        env_idx: int = 0,
    ) -> None:
        """Set the target. For pose_abs: command = [px, py, pz, qx, qy, qz, qw].
        For pose_rel: command = [Δx, Δy, Δz, Δax, Δay, Δaz] (axis-angle)
        and ee_pos/ee_quat MUST be supplied.

        When impedance_mode="variable", the last 12 elements are stiffness
        (6) + damping (6); else they're absent.
        """
        if not (0 <= env_idx < self.num_envs):
            raise IndexError(f"env_idx={env_idx} out of [0, {self.num_envs})")
        expected = self.action_dim
        if len(command) != expected:
            raise ValueError(
                f"command must be length {expected} (target_types={self.cfg.target_types}, "
                f"impedance_mode={self.cfg.impedance_mode!r}); got {len(command)}"
            )

        # Variable impedance: split off the last 12 elements as gains.
        if self.cfg.impedance_mode == "variable":
            gains_start = expected - 12
            self._variable_stiffness[env_idx] = list(command[gains_start:])
            command = command[:gains_start]

        # Walk target_types in order; each consumes its sub-segment.
        idx = 0
        for tt in self.cfg.target_types:
            if tt == "pose_abs":
                self._target[env_idx] = list(command[idx:idx + 7])
                idx += 7
            elif tt == "pose_rel":
                if ee_pos is None or ee_quat is None:
                    raise ValueError(
                        "pose_rel requires ee_pos + ee_quat"
                    )
                delta = command[idx:idx + 6]
                self._target[env_idx][0] = ee_pos[0] + delta[0]
                self._target[env_idx][1] = ee_pos[1] + delta[1]
                self._target[env_idx][2] = ee_pos[2] + delta[2]
                # Axis-angle delta → quaternion delta → multiply
                angle = math.sqrt(sum(d*d for d in delta[3:6]))
                if angle < 1e-9:
                    q_delta = (0.0, 0.0, 0.0, 1.0)
                else:
                    ax = (delta[3]/angle, delta[4]/angle, delta[5]/angle)
                    h = angle * 0.5
                    s = math.sin(h)
                    q_delta = (ax[0]*s, ax[1]*s, ax[2]*s, math.cos(h))
                target_q = _quat_mul(q_delta, tuple(ee_quat))
                self._target[env_idx][3:7] = list(target_q)
                idx += 6
            # wrench_abs / force_abs / torque_abs: just skip — these don't
            # change target pose; they'd ride on a future _target_wrench
            # buffer (not exposed in this iter for clarity).
            elif tt == "wrench_abs":
                idx += 6
            elif tt in ("force_abs", "torque_abs"):
                idx += 3

    def get_target(self, env_idx: int = 0) -> List[float]:
        return list(self._target[env_idx])

    # ── compute ──────────────────────────────────────────────────────────

    def compute(
        self,
        ee_pos: List[float],
        ee_quat: List[float],
        ee_lin_vel: List[float],
        ee_ang_vel: List[float],
        jacobian: List[List[float]],
        joint_pos: Optional[List[float]] = None,
        joint_vel: Optional[List[float]] = None,
        mass_matrix: Optional[List[List[float]]] = None,
        gravity_torque: Optional[List[float]] = None,
        nullspace_target_pos: Optional[List[float]] = None,
        env_idx: int = 0,
    ) -> List[float]:
        """Compute the joint torque for the named env.

        Args:
            ee_pos / ee_quat:   current end-effector pose
            ee_lin_vel / ee_ang_vel: current EE velocity (world frame)
            jacobian:    6 × n geometric Jacobian
            joint_pos / joint_vel: required when nullspace_control != "none"
            mass_matrix: n × n (currently unused — reserved for OSC dynamics-
                          consistent variant in a future iter)
            gravity_torque: n-vec G(q) added when cfg.gravity_compensation=True
            nullspace_target_pos: n-vec joint-space target for null-space loop
            env_idx:     per-env target index

        Returns: length-n joint torque vector.
        """
        if len(jacobian) != 6:
            raise ValueError(
                f"jacobian must have 6 rows; got {len(jacobian)}"
            )
        n = len(jacobian[0])
        if n != self.num_dof:
            raise ValueError(
                f"jacobian width {n} != cfg.num_dof {self.num_dof}"
            )

        target = self._target[env_idx]
        t_pos = target[0:3]
        t_quat = target[3:7]

        # 1. Pose error (6-vec).
        pos_err = (
            t_pos[0] - ee_pos[0],
            t_pos[1] - ee_pos[1],
            t_pos[2] - ee_pos[2],
        )
        q_err = _quat_mul(tuple(t_quat), _quat_inverse(tuple(ee_quat)))
        ori_err = _axis_angle_vec(q_err)
        error = [pos_err[0], pos_err[1], pos_err[2],
                  ori_err[0], ori_err[1], ori_err[2]]

        # 2. Velocity error (target rest = 0, so de = -ee_vel).
        d_error = [
            -ee_lin_vel[0], -ee_lin_vel[1], -ee_lin_vel[2],
            -ee_ang_vel[0], -ee_ang_vel[1], -ee_ang_vel[2],
        ]

        # 3. Task-space wrench: F = K_p · e + K_d · de
        # Damping ratio ζ → K_d = 2 · ζ · sqrt(K_p)
        if (
            self.cfg.impedance_mode == "variable"
            and self._variable_stiffness[env_idx] is not None
        ):
            vs = self._variable_stiffness[env_idx]
            kp_task = vs[0:6]
            kd_ratio = vs[6:12]
        else:
            kp_task = self.cfg.motion_stiffness_task
            kd_ratio = self.cfg.motion_damping_ratio_task
        kd_task = [
            2.0 * kd_ratio[i] * math.sqrt(max(0.0, kp_task[i]))
            for i in range(6)
        ]
        F_task = [
            kp_task[i] * error[i] + kd_task[i] * d_error[i]
            for i in range(6)
        ]

        # 4. Joint torque via Jᵀ F_task.
        # Jᵀ shape: n × 6, so τ_i = Σ_k J[k][i] * F_task[k].
        tau = [0.0] * n
        for i in range(n):
            s = 0.0
            for k in range(6):
                s += jacobian[k][i] * F_task[k]
            tau[i] = s

        # 5. Null-space joint regularization (when configured + Jacobian is
        # underdetermined: n > 6).
        if (
            self.cfg.nullspace_control == "position"
            and nullspace_target_pos is not None
            and joint_pos is not None
            and joint_vel is not None
            and n > 6
        ):
            # τ_nullspace: P/D loop toward target joint config.
            kp_ns = self.cfg.nullspace_stiffness
            # K_d_ns from critically-damped formula.
            kd_ns = 2.0 * self.cfg.nullspace_damping_ratio * math.sqrt(max(0.0, kp_ns))
            tau_ns = [
                kp_ns * (nullspace_target_pos[i] - joint_pos[i])
                - kd_ns * joint_vel[i]
                for i in range(n)
            ]
            # Project into null-space: (I - Jᵀ J⁺ᵀ) τ_ns
            # Use damped pseudoinverse J⁺ = Jᵀ (J Jᵀ + λI)⁻¹ for stability.
            # For brevity, project directly via Jᵀ · (J · τ_ns_in_task_space).
            # Actually: null-space projector P_null = I - Jᵀ (J Jᵀ)⁻¹ J
            # Apply to tau_ns: tau_ns_proj = tau_ns - Jᵀ (J Jᵀ)⁻¹ J tau_ns
            # Cheap shortcut: project by removing the J·tau_ns component
            # from tau via Jacobian pseudoinverse-style step.
            tau_ns_proj = _project_to_nullspace(
                jacobian, tau_ns, n, lam=0.05,
            )
            for i in range(n):
                tau[i] += tau_ns_proj[i]

        # 6. Gravity compensation.
        if self.cfg.gravity_compensation and gravity_torque is not None:
            for i in range(min(n, len(gravity_torque))):
                tau[i] += gravity_torque[i]

        return tau


# ────────────────────────────────────────────────────────────────────────────
# Null-space projection helper
# ────────────────────────────────────────────────────────────────────────────


def _project_to_nullspace(
    J: List[List[float]], tau_ns: List[float], n: int, lam: float = 0.05,
) -> List[float]:
    """Project `tau_ns` into the null-space of Jacobian J.

    Formula: P_null = I - Jᵀ (J Jᵀ + λ²I)⁻¹ J
              tau_proj = P_null · tau_ns

    Uses the same Gauss-Jordan 6×6 solve as iter 41 DLS IK for the
    (J Jᵀ + λ²I)⁻¹ inverse (damped for numerical stability near
    singularities).
    """
    # Step 1: J · tau_ns (6-vec)
    Jtau = [0.0] * 6
    for k in range(6):
        s = 0.0
        for i in range(n):
            s += J[k][i] * tau_ns[i]
        Jtau[k] = s
    # Step 2: solve (J Jᵀ + λ²I) y = Jtau via Gauss-Jordan on 6×7.
    lam2 = lam * lam
    A = [[0.0] * 6 for _ in range(6)]
    for i in range(6):
        for j in range(6):
            s = 0.0
            for k in range(n):
                s += J[i][k] * J[j][k]
            A[i][j] = s + (lam2 if i == j else 0.0)
    aug = [list(A[i]) + [Jtau[i]] for i in range(6)]
    for col in range(6):
        piv = col
        max_abs = abs(aug[col][col])
        for r in range(col + 1, 6):
            if abs(aug[r][col]) > max_abs:
                max_abs = abs(aug[r][col])
                piv = r
        if max_abs < 1e-18:
            continue
        if piv != col:
            aug[col], aug[piv] = aug[piv], aug[col]
        pv = aug[col][col]
        for j in range(col, 7):
            aug[col][j] /= pv
        for r in range(6):
            if r == col:
                continue
            f = aug[r][col]
            if abs(f) < 1e-18:
                continue
            for j in range(col, 7):
                aug[r][j] -= f * aug[col][j]
    y = [aug[i][6] for i in range(6)]
    # Step 3: Jᵀ · y (n-vec)
    Jty = [0.0] * n
    for i in range(n):
        s = 0.0
        for k in range(6):
            s += J[k][i] * y[k]
        Jty[i] = s
    # Step 4: tau_proj = tau_ns - Jᵀ y
    return [tau_ns[i] - Jty[i] for i in range(n)]
