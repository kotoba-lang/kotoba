"""Command generators — random task targets per env.

Mirror of `isaaclab.envs.mdp.commands` (Isaac Lab 1.x). Each generator
produces a per-env command vector (random goal pose for arm reach,
random velocity for locomotion, etc.) and resamples on a configured
interval.

Standard usage:

    cmd_cfg = UniformVelocityCommandCfg(
        asset_name="robot", resampling_time_range=(2.0, 5.0),
        ranges=Ranges(lin_vel_x=(-1.0, 1.0), lin_vel_y=(-0.5, 0.5),
                       ang_vel_z=(-1.0, 1.0)),
    )
    cmd = UniformVelocityCommand(cfg=cmd_cfg, num_envs=4, seed=0)
    cmd.reset(env_ids=[0, 1, 2, 3])
    obs_cmd = cmd.command       # [[vx, vy, wz], ...] per env (shape (num_envs, 3))
    cmd.update(dt=0.01)         # resamples envs whose timer expired

Integration with `ManagerBasedRLEnv`: the env stores active generators
in `env._commands[name] = generator.command` (a list-per-env). The
existing `mdp.generated_commands(env, command_name)` obs term reads
from that dict, so wiring a generator into an observation group is:

    obs_groups = {
        "policy": ObsGroup(terms={
            "joint_pos": ObsTerm(mdp.joint_pos_rel),
            "vel_cmd":   ObsTerm(mdp.generated_commands,
                                 params={"command_name": "velocity"}),
        }),
    }

then in env.reset_managed() / env.step_managed() the host calls
`cmd.update(dt)` and writes `env._commands["velocity"] = cmd.command`.

Pure stdlib. Reuses the LCG from algos.cem for cross-trainer determinism.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ...algos.cem import _Lcg


# ────────────────────────────────────────────────────────────────────────────
# Base + null
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class CommandCfgBase:
    """Base cfg shared by every CommandGenerator.

    `resampling_time_range = (min_s, max_s)` — uniformly sample the period
    over this range per env; on resample, the timer is re-drawn.
    `debug_vis` is a stub for downstream marker visualization.
    """
    asset_name: str = "robot"
    resampling_time_range: tuple = (2.0, 5.0)
    debug_vis: bool = False


class CommandGeneratorBase:
    """Abstract base. Subclasses MUST implement:

      - `command_dim` property         — int, length of each per-env vector
      - `_resample(env_ids)`           — fill `_command[i]` with a fresh sample
                                          for each i in env_ids

    Base owns:
      - `_command[env_idx]`            — list[float] current command per env
      - `_timer[env_idx]`              — seconds remaining until next resample
      - `_period[env_idx]`             — current resample period (for stats)
      - num_resamples_total            — counter for diagnostics
    """

    def __init__(self, cfg: CommandCfgBase, num_envs: int, seed: int = 0):
        if num_envs <= 0:
            raise ValueError(f"num_envs must be > 0; got {num_envs}")
        self.cfg = cfg
        self.num_envs = num_envs
        self._rngs: List[_Lcg] = [_Lcg(seed + 1000 * i) for i in range(num_envs)]
        self._command: List[List[float]] = [
            [0.0] * self.command_dim for _ in range(num_envs)
        ]
        self._timer: List[float] = [0.0] * num_envs
        self._period: List[float] = [0.0] * num_envs
        self.num_resamples_total: int = 0

    # ── subclass hooks ──────────────────────────────────────────────────

    @property
    def command_dim(self) -> int:
        raise NotImplementedError("subclass must define command_dim")

    def _resample(self, env_ids: List[int]) -> None:
        """Fill self._command[i] for each i in env_ids with a fresh sample."""
        raise NotImplementedError("subclass must implement _resample")

    # ── public API ──────────────────────────────────────────────────────

    @property
    def command(self) -> List[List[float]]:
        """Current per-env command vector list."""
        return [list(c) for c in self._command]

    @property
    def timer(self) -> List[float]:
        return list(self._timer)

    def reset(self, env_ids: Optional[List[int]] = None) -> None:
        """Force-resample the named envs (or all envs when env_ids is None).

        Resets each env's resample timer to a freshly-sampled period.
        """
        if env_ids is None:
            env_ids = list(range(self.num_envs))
        self._resample(env_ids)
        for i in env_ids:
            self._period[i] = self._sample_period(self._rngs[i])
            self._timer[i] = self._period[i]
        self.num_resamples_total += len(env_ids)

    def update(self, dt: float) -> List[int]:
        """Decrement timers; resample any env whose timer reaches zero.

        Returns the list of env_ids that resampled this update — useful for
        downstream callers that want to hook resample events (e.g. marker
        viz refresh).
        """
        resampled: List[int] = []
        for i in range(self.num_envs):
            self._timer[i] -= dt
            if self._timer[i] <= 0.0:
                resampled.append(i)
                self._period[i] = self._sample_period(self._rngs[i])
                self._timer[i] = self._period[i]
        if resampled:
            self._resample(resampled)
            self.num_resamples_total += len(resampled)
        return resampled

    def _sample_period(self, rng: _Lcg) -> float:
        lo, hi = self.cfg.resampling_time_range
        return lo + (hi - lo) * rng.next_u01()

    # ── env-integration helper ──────────────────────────────────────────

    def wire_to_env(self, env: Any, command_name: str) -> None:
        """Register `self.command` under `env._commands[command_name]` so
        that `mdp.generated_commands(env, command_name=...)` returns it.

        The env must expose a `_commands` dict (ManagerBasedRLEnv does so
        out of the box). Call this once per ctor; subsequent `update()`
        calls write into the same dict slot so the obs term always sees
        the freshest command.
        """
        if not hasattr(env, "_commands"):
            env._commands = {}
        env._commands[command_name] = list(self._command)
        # Re-publish the same reference each step by storing a writeback
        # hook on the generator (env is responsible for invoking it post-
        # update). The hook is documented for env subclasses to call.
        self._wireup = (env, command_name)

    def push_to_env(self) -> None:
        """If wire_to_env was called, refresh env._commands[name] with the
        latest command. No-op when not wired."""
        wireup = getattr(self, "_wireup", None)
        if wireup is None:
            return
        env, name = wireup
        env._commands[name] = self.command


# ────────────────────────────────────────────────────────────────────────────
# Concrete generators
# ────────────────────────────────────────────────────────────────────────────


class NullCommand(CommandGeneratorBase):
    """Empty 0-dim command. Used as a placeholder when an env needs to
    register a generator name but has no actual command (e.g. pure
    classification tasks)."""

    @property
    def command_dim(self) -> int:
        return 0

    def _resample(self, env_ids: List[int]) -> None:
        for i in env_ids:
            self._command[i] = []


@dataclass
class UniformVelocityRanges:
    """Per-component uniform ranges for UniformVelocityCommand."""
    lin_vel_x: tuple = (-1.0, 1.0)
    lin_vel_y: tuple = (-0.5, 0.5)
    lin_vel_z: tuple = (0.0, 0.0)
    ang_vel_z: tuple = (-1.0, 1.0)


@dataclass
class UniformVelocityCommandCfg(CommandCfgBase):
    """Cfg for UniformVelocityCommand (locomotion).

    Command vector layout per env: `[lin_vel_x, lin_vel_y, lin_vel_z, ang_vel_z]`
    — 4 floats, matches Isaac Lab's quadruped task convention.
    """
    ranges: UniformVelocityRanges = field(default_factory=UniformVelocityRanges)
    # Probability of issuing a zero-velocity (standing) command per resample.
    # 0 = always non-zero; 0.1 = 10% standing.
    rel_standing_envs: float = 0.0


class UniformVelocityCommand(CommandGeneratorBase):
    """Random 4-DOF velocity commands for locomotion tasks.

    On each resample, draws `[vx, vy, vz, wz]` uniformly from the cfg ranges,
    or zeros if the env was selected as "standing" with probability
    `cfg.rel_standing_envs`.
    """
    cfg: UniformVelocityCommandCfg  # type narrowing

    @property
    def command_dim(self) -> int:
        return 4

    def _resample(self, env_ids: List[int]) -> None:
        cfg: UniformVelocityCommandCfg = self.cfg  # type: ignore[assignment]
        for i in env_ids:
            rng = self._rngs[i]
            # Standing-zero coin flip.
            if cfg.rel_standing_envs > 0.0 and rng.next_u01() < cfg.rel_standing_envs:
                self._command[i] = [0.0, 0.0, 0.0, 0.0]
                continue
            self._command[i] = [
                _uniform(rng, cfg.ranges.lin_vel_x),
                _uniform(rng, cfg.ranges.lin_vel_y),
                _uniform(rng, cfg.ranges.lin_vel_z),
                _uniform(rng, cfg.ranges.ang_vel_z),
            ]


@dataclass
class UniformPose3DRanges:
    """Box ranges for UniformPose3DCommand (arm reach target)."""
    pos_x: tuple = (0.3, 0.7)
    pos_y: tuple = (-0.3, 0.3)
    pos_z: tuple = (0.2, 0.6)
    # Roll / pitch / yaw target ranges in radians.
    roll: tuple = (-3.14159, 3.14159)
    pitch: tuple = (-1.5708, 1.5708)
    yaw: tuple = (-3.14159, 3.14159)


@dataclass
class UniformPose3DCommandCfg(CommandCfgBase):
    """Cfg for UniformPose3DCommand (arm reaching).

    Command vector layout: `[pos_x, pos_y, pos_z, qx, qy, qz, qw]` — 7 floats.
    """
    ranges: UniformPose3DRanges = field(default_factory=UniformPose3DRanges)
    # When True, sample only position; orientation is identity (q=(0,0,0,1)).
    position_only: bool = False


class UniformPose3DCommand(CommandGeneratorBase):
    """Random 6-DOF target pose for arm reaching / pick-and-place. Command
    vector is `[pos_x, pos_y, pos_z, qx, qy, qz, qw]` (7 floats).

    Orientation is built by composing per-axis Euler rotations from the cfg
    ranges. When `cfg.position_only` is True, orientation is fixed to
    identity (useful for tasks where only the EE position matters).
    """
    cfg: UniformPose3DCommandCfg  # type narrowing

    @property
    def command_dim(self) -> int:
        return 7

    def _resample(self, env_ids: List[int]) -> None:
        cfg: UniformPose3DCommandCfg = self.cfg  # type: ignore[assignment]
        for i in env_ids:
            rng = self._rngs[i]
            px = _uniform(rng, cfg.ranges.pos_x)
            py = _uniform(rng, cfg.ranges.pos_y)
            pz = _uniform(rng, cfg.ranges.pos_z)
            if cfg.position_only:
                qx, qy, qz, qw = 0.0, 0.0, 0.0, 1.0
            else:
                roll = _uniform(rng, cfg.ranges.roll)
                pitch = _uniform(rng, cfg.ranges.pitch)
                yaw = _uniform(rng, cfg.ranges.yaw)
                qx, qy, qz, qw = _quat_from_euler_xyz(roll, pitch, yaw)
            self._command[i] = [px, py, pz, qx, qy, qz, qw]


# ────────────────────────────────────────────────────────────────────────────
# Helpers (local; reuse utils.math if you prefer, this keeps mdp standalone)
# ────────────────────────────────────────────────────────────────────────────


def _uniform(rng: _Lcg, rng_tuple: tuple) -> float:
    lo, hi = rng_tuple
    return lo + (hi - lo) * rng.next_u01()


def _quat_from_euler_xyz(roll: float, pitch: float, yaw: float) -> tuple:
    """Same formula as isaaclab.utils.math.quat_from_euler_xyz, inlined
    so this module is self-contained."""
    hr, hp, hy = roll * 0.5, pitch * 0.5, yaw * 0.5
    cr, sr = math.cos(hr), math.sin(hr)
    cp, sp = math.cos(hp), math.sin(hp)
    cy, sy = math.cos(hy), math.sin(hy)
    return (
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    )
