"""DifferentialIKController — Jacobian-based IK for arm reaching.

Mirror of `isaaclab.controllers.DifferentialIKController` (Isaac Lab 1.x).
Maps a 6-DOF task-space command (pose or position) onto a joint-space delta
via damped least squares (DLS) or Moore-Penrose pseudoinverse over the
articulation Jacobian.

Standard usage:

    cfg = DifferentialIKControllerCfg(
        command_type="pose",          # or "position"
        use_relative_mode=False,      # absolute target in world frame
        ik_method="dls",              # or "pinv"
        ik_params={"lambda_val": 0.05},
    )
    ik = DifferentialIKController(cfg, num_envs=1)
    ik.set_command(command=[x, y, z, qx, qy, qz, qw])
    delta_q = ik.compute(
        ee_pos=current_ee_pos, ee_quat=current_ee_quat, jacobian=J6n,
    )
    # delta_q is a length-n joint position delta — feed into
    # JointPositionAction or apply directly to env.set_joint_positions(q + Δq)

Algorithm (per step):

    1. Decode command to target_pos + target_quat (or identity quat for
       "position"-only)
    2. Compute pose error:
        pos_err = target_pos - ee_pos                          (3-vec)
        ori_err = axis*angle of (target_quat * ee_quat^-1)     (3-vec)
       Stack as a 6-vec [pos_err, ori_err].
    3. Solve J · Δq = error via DLS or pseudoinverse:
        DLS:   Δq = J^T · (J · J^T + λ² · I_6)^-1 · error
        Pinv:  Δq = J^pinv · error  (Moore-Penrose via SVD-like solve;
                                     here implemented as DLS with very
                                     small λ, equivalent for well-conditioned J)

Pure stdlib (math). No numpy. Operates on 6×n matrices stored as
list-of-lists; suitable for n ≤ ~12 (3D arms). For higher-DoF (humanoid)
arms a numpy/torch backend is preferable and can swap in by replacing
`_solve_dls`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional


# ────────────────────────────────────────────────────────────────────────────
# Cfg
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class DifferentialIKControllerCfg:
    """Mirror of `isaaclab.controllers.DifferentialIKControllerCfg`.

    - command_type:    "pose" → 7-element [x,y,z,qx,qy,qz,qw]; full 6-DOF
                       "position" → 3-element [x,y,z]; orientation ignored
    - use_relative_mode: when True, set_command receives a DELTA from
                         current EE pose (matches Isaac Lab's residual
                         teleop convention).
    - ik_method:       "dls" damped-least-squares (default), or "pinv".
    - ik_params:       {"lambda_val": float} for DLS damping. Defaults
                       to 0.05 — bigger = more stable near singularities,
                       slower convergence.
    """
    command_type: str = "pose"
    use_relative_mode: bool = False
    ik_method: str = "dls"
    ik_params: dict = field(default_factory=lambda: {"lambda_val": 0.05})


# ────────────────────────────────────────────────────────────────────────────
# Controller
# ────────────────────────────────────────────────────────────────────────────


class DifferentialIKController:
    """Differential IK controller — per-env target pose buffer + compute().

    Args:
        cfg:       DifferentialIKControllerCfg
        num_envs:  per-env target buffer count (matches isaaclab batched
                   convention; scalar usage = num_envs=1)
    """

    cfg: DifferentialIKControllerCfg

    def __init__(self, cfg: DifferentialIKControllerCfg, num_envs: int = 1):
        if num_envs <= 0:
            raise ValueError(f"num_envs must be > 0; got {num_envs}")
        if cfg.command_type not in ("pose", "position"):
            raise ValueError(
                f"command_type must be 'pose' or 'position'; got {cfg.command_type!r}"
            )
        if cfg.ik_method not in ("dls", "pinv"):
            raise ValueError(
                f"ik_method must be 'dls' or 'pinv'; got {cfg.ik_method!r}"
            )
        self.cfg = cfg
        self.num_envs = num_envs
        # Per-env target pose: [px, py, pz, qx, qy, qz, qw].
        self._target: List[List[float]] = [
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0] for _ in range(num_envs)
        ]

    # ── action_dim ───────────────────────────────────────────────────────

    @property
    def action_dim(self) -> int:
        """Length of one command vector.

        Depends on (command_type, use_relative_mode):

          - pose + absolute:  7 (xyz + quat xyzw)
          - pose + relative:  6 (xyz delta + axis-angle delta)
          - position + *:     3 (xyz)
        """
        if self.cfg.command_type == "pose":
            return 6 if self.cfg.use_relative_mode else 7
        return 3

    # ── target management ────────────────────────────────────────────────

    def reset(self, env_ids: Optional[List[int]] = None) -> None:
        """Clear targets (identity pose at origin) for the named envs (or all)."""
        if env_ids is None:
            env_ids = list(range(self.num_envs))
        for i in env_ids:
            self._target[i] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]

    def set_command(
        self,
        command: List[float],
        ee_pos: Optional[List[float]] = None,
        ee_quat: Optional[List[float]] = None,
        env_idx: int = 0,
    ) -> None:
        """Set the target pose for env_idx.

        - If `use_relative_mode=False` (default): `command` is the absolute
          world-frame target (7-elem for "pose", 3-elem for "position").
        - If `use_relative_mode=True`: `command` is a DELTA added to the
          current EE pose. The position delta is added in world frame; the
          orientation delta (for "pose" mode) is a 3-element axis-angle
          rotation applied as `target_q = q_delta * ee_quat`.

        For relative mode, `ee_pos` and `ee_quat` MUST be supplied.
        """
        if len(command) != self.action_dim:
            raise ValueError(
                f"command must be length {self.action_dim} for "
                f"command_type='{self.cfg.command_type}'; got {len(command)}"
            )
        if not (0 <= env_idx < self.num_envs):
            raise IndexError(f"env_idx={env_idx} out of range [0, {self.num_envs})")

        if self.cfg.use_relative_mode:
            if ee_pos is None or ee_quat is None:
                raise ValueError(
                    "use_relative_mode=True requires ee_pos + ee_quat to set_command"
                )
            target_pos = (
                ee_pos[0] + command[0], ee_pos[1] + command[1], ee_pos[2] + command[2],
            )
            if self.cfg.command_type == "pose":
                # command[3:6] = axis-angle delta rotation
                axang = command[3:6]
                angle = math.sqrt(axang[0]**2 + axang[1]**2 + axang[2]**2)
                if angle < 1e-9:
                    q_delta = (0.0, 0.0, 0.0, 1.0)
                else:
                    ax = (axang[0]/angle, axang[1]/angle, axang[2]/angle)
                    h = angle * 0.5
                    s = math.sin(h)
                    q_delta = (ax[0]*s, ax[1]*s, ax[2]*s, math.cos(h))
                target_quat = _quat_mul(q_delta, tuple(ee_quat))
            else:
                target_quat = tuple(ee_quat)
        else:
            target_pos = (command[0], command[1], command[2])
            if self.cfg.command_type == "pose":
                target_quat = (command[3], command[4], command[5], command[6])
            else:
                # Position-only: keep prior orientation target (identity by default)
                t = self._target[env_idx]
                target_quat = (t[3], t[4], t[5], t[6])

        self._target[env_idx] = [
            target_pos[0], target_pos[1], target_pos[2],
            target_quat[0], target_quat[1], target_quat[2], target_quat[3],
        ]

    def get_target(self, env_idx: int = 0) -> List[float]:
        """Returns the 7-element target pose for env_idx."""
        return list(self._target[env_idx])

    # ── main IK solve ────────────────────────────────────────────────────

    def compute(
        self,
        ee_pos: List[float],
        ee_quat: List[float],
        jacobian: List[List[float]],
        env_idx: int = 0,
    ) -> List[float]:
        """Compute joint-space delta to drive EE → target.

        Args:
            ee_pos:    current EE position [x,y,z]
            ee_quat:   current EE quaternion [qx,qy,qz,qw]
            jacobian:  6×n list-of-lists (rows = task-space DoF in order
                       [vx, vy, vz, wx, wy, wz]; cols = n joints)
            env_idx:   per-env target index

        Returns:
            length-n joint position delta.
        """
        if len(jacobian) != 6:
            raise ValueError(
                f"jacobian must be 6 rows (linear x/y/z + angular x/y/z); "
                f"got {len(jacobian)}"
            )
        n = len(jacobian[0])
        if any(len(row) != n for row in jacobian):
            raise ValueError("jacobian rows must all have the same width")

        # 1. Pose error.
        target = self._target[env_idx]
        t_pos = target[0:3]
        t_quat = target[3:7]
        pos_err = (
            t_pos[0] - ee_pos[0],
            t_pos[1] - ee_pos[1],
            t_pos[2] - ee_pos[2],
        )
        if self.cfg.command_type == "pose":
            # Orientation error = axis-angle of (t_quat * inv(ee_quat))
            q_err = _quat_mul(tuple(t_quat), _quat_inverse(tuple(ee_quat)))
            ori_err = _axis_angle_vec(q_err)
        else:
            ori_err = (0.0, 0.0, 0.0)
        error = [pos_err[0], pos_err[1], pos_err[2],
                 ori_err[0], ori_err[1], ori_err[2]]

        # 2. Solve. Both DLS and pinv use the same DLS solver — for pinv
        # we use a vanishingly small lambda (recovers Moore-Penrose for
        # full-rank J). This keeps the code simple while preserving the
        # API distinction users expect.
        if self.cfg.ik_method == "dls":
            lam = float(self.cfg.ik_params.get("lambda_val", 0.05))
        else:  # pinv
            lam = 1e-6
        delta_q = _solve_dls(jacobian, error, lam, n)
        return delta_q


# ────────────────────────────────────────────────────────────────────────────
# Math helpers (quat + DLS solve)
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
    """Convert quaternion to axis-angle 3-vec (axis * angle).
    Returns the shortest-arc angle (chooses ±q to keep |angle| ≤ π)."""
    qx, qy, qz, qw = q
    if qw < 0.0:
        qx, qy, qz, qw = -qx, -qy, -qz, -qw
    qw = max(-1.0, min(1.0, qw))
    angle = 2.0 * math.acos(qw)
    s = math.sqrt(max(0.0, 1.0 - qw * qw))
    if s < 1e-8:
        return (0.0, 0.0, 0.0)
    inv_s = 1.0 / s
    return (qx * inv_s * angle, qy * inv_s * angle, qz * inv_s * angle)


def _solve_dls(J: List[List[float]], error: List[float],
               lam: float, n: int) -> List[float]:
    """Damped least squares: Δq = J^T (J J^T + λ²I)^-1 error.

    Steps:
      1. A = J J^T + λ²I    (6×6)
      2. b = error          (6-vec)
      3. y = A^-1 b         (6-vec) via Gauss-Jordan
      4. Δq = J^T y         (n-vec)
    """
    lam2 = lam * lam
    # 1. A = J J^T + λ²I.
    A = [[0.0] * 6 for _ in range(6)]
    for i in range(6):
        for j in range(6):
            s = 0.0
            for k in range(n):
                s += J[i][k] * J[j][k]
            A[i][j] = s + (lam2 if i == j else 0.0)
    # 2. Solve A y = error via Gauss-Jordan on augmented 6×7 matrix.
    aug = [list(A[i]) + [error[i]] for i in range(6)]
    for col in range(6):
        # Partial pivot: find max |aug[r][col]| for r ≥ col.
        piv = col
        max_abs = abs(aug[col][col])
        for r in range(col + 1, 6):
            if abs(aug[r][col]) > max_abs:
                max_abs = abs(aug[r][col])
                piv = r
        if max_abs < 1e-18:
            # Singular: zero out this column and continue (DLS damping
            # should prevent this in practice, but be defensive).
            continue
        if piv != col:
            aug[col], aug[piv] = aug[piv], aug[col]
        # Normalize pivot row.
        pv = aug[col][col]
        for j in range(col, 7):
            aug[col][j] /= pv
        # Eliminate other rows.
        for r in range(6):
            if r == col:
                continue
            f = aug[r][col]
            if abs(f) < 1e-18:
                continue
            for j in range(col, 7):
                aug[r][j] -= f * aug[col][j]
    y = [aug[i][6] for i in range(6)]
    # 4. Δq = J^T y.
    delta_q = [0.0] * n
    for k in range(n):
        s = 0.0
        for i in range(6):
            s += J[i][k] * y[i]
        delta_q[k] = s
    return delta_q
