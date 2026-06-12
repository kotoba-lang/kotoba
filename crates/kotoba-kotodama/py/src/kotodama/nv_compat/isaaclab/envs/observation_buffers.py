"""isaaclab.envs.observation_buffers — N-step history + online normalization.

Mirror of Isaac Lab's observation preprocessing primitives. Three classes
used in every Isaac Lab training script that feeds into iter 32 PPO or
external RL libs (skrl / rsl_rl):

  1. ObservationHistoryBuffer — N-step observation stacking (POMDP →
     near-Markov via frame-stack). Replicates the first observation
     when not yet warm; resets fill the buffer with the reset obs.
  2. RunningMeanStd — Welford online mean/variance with batch merge.
     Used to normalize observations and value targets during training
     (the standard "obs - μ / σ" preprocessor).
  3. RewardScaling — discount-aware return scaler (rl_games convention).
     Tracks a running estimate of return magnitude; scales rewards by
     1 / σ_R so the policy gradient signal stays consistent across
     reward ranges.

Pure stdlib (math + list-of-floats).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional


# ────────────────────────────────────────────────────────────────────────────
# ObservationHistoryBuffer — N-step frame stack
# ────────────────────────────────────────────────────────────────────────────


class ObservationHistoryBuffer:
    """Per-env N-step observation stack.

    Internal state: per-env deque of length `history_length`. `append(obs)`
    pushes the newest obs and drops the oldest. `flat()` returns a single
    concatenated vector per env (oldest→newest).

    First-fill semantics: when `replicate_first=True` (default), the very
    first observation fills every slot in the buffer (so .flat() returns
    a full-length vector from step 0 — useful for downstream policies that
    can't handle ragged history). When False, slots before fill return 0
    (gym convention).

    Standard usage:

        buf = ObservationHistoryBuffer(num_envs=4, obs_dim=8, history_length=3)
        for step in range(...):
            obs_t = env.step(...)["observations"]
            buf.append(obs_t)
            policy_input = buf.flat()  # shape (4, 24)
        # On episode reset:
        buf.reset(env_ids=done_env_indices, fill_obs=obs_t)
    """

    def __init__(
        self,
        num_envs: int,
        obs_dim: int,
        history_length: int,
        replicate_first: bool = True,
    ):
        if num_envs <= 0 or obs_dim <= 0 or history_length <= 0:
            raise ValueError(
                f"num_envs / obs_dim / history_length must be > 0; "
                f"got {num_envs} / {obs_dim} / {history_length}"
            )
        self.num_envs = num_envs
        self.obs_dim = obs_dim
        self.history_length = history_length
        self.replicate_first = replicate_first
        # Per-env list of obs vectors (length history_length each).
        self._buf: List[List[List[float]]] = [
            [[0.0] * obs_dim for _ in range(history_length)]
            for _ in range(num_envs)
        ]
        self._is_warm: List[bool] = [False] * num_envs

    # ── append + flat ────────────────────────────────────────────────────

    def append(self, obs_per_env: List[List[float]]) -> None:
        """Push a new observation to every env's history.

        `obs_per_env[i]` is the length-obs_dim observation for env i.
        First call on a cold env replicates obs across the buffer when
        `replicate_first=True`.
        """
        if len(obs_per_env) != self.num_envs:
            raise ValueError(
                f"expected {self.num_envs} obs vectors; got {len(obs_per_env)}"
            )
        for i, obs in enumerate(obs_per_env):
            if len(obs) != self.obs_dim:
                raise ValueError(
                    f"env {i}: expected obs_dim={self.obs_dim}, got {len(obs)}"
                )
            if not self._is_warm[i] and self.replicate_first:
                # Fill every slot with this obs.
                self._buf[i] = [list(obs) for _ in range(self.history_length)]
                self._is_warm[i] = True
            else:
                # Shift left (drop oldest) + append newest.
                self._buf[i] = self._buf[i][1:] + [list(obs)]
                self._is_warm[i] = True

    def flat(self) -> List[List[float]]:
        """Returns the flattened (oldest→newest) buffer per env.

        Shape: `(num_envs, history_length * obs_dim)`.
        """
        out: List[List[float]] = []
        for env_buf in self._buf:
            flat: List[float] = []
            for obs in env_buf:
                flat.extend(obs)
            out.append(flat)
        return out

    def latest(self, env_idx: int) -> List[float]:
        """Most recently appended obs for env_idx (the newest frame)."""
        return list(self._buf[env_idx][-1])

    def reset(
        self,
        env_ids: Optional[List[int]] = None,
        fill_obs: Optional[List[List[float]]] = None,
    ) -> None:
        """Reset history for the named envs (or all envs when env_ids is None).

        When `fill_obs` is supplied, fills each reset env with its
        corresponding obs (replicated across history). Otherwise zero-fills
        and marks the env as cold (next `append` will replicate-on-first
        when `replicate_first=True`).
        """
        targets = env_ids if env_ids is not None else list(range(self.num_envs))
        for slot, env_idx in enumerate(targets):
            if fill_obs is not None:
                obs = fill_obs[slot] if env_ids is not None else fill_obs[env_idx]
                if len(obs) != self.obs_dim:
                    raise ValueError(
                        f"fill_obs[{slot}] has wrong dim; expected {self.obs_dim}"
                    )
                self._buf[env_idx] = [list(obs) for _ in range(self.history_length)]
                self._is_warm[env_idx] = True
            else:
                self._buf[env_idx] = [
                    [0.0] * self.obs_dim for _ in range(self.history_length)
                ]
                self._is_warm[env_idx] = False

    @property
    def flat_dim(self) -> int:
        return self.history_length * self.obs_dim

    def is_warm(self, env_idx: int) -> bool:
        return self._is_warm[env_idx]


# ────────────────────────────────────────────────────────────────────────────
# RunningMeanStd — Welford online algorithm
# ────────────────────────────────────────────────────────────────────────────


class RunningMeanStd:
    """Online mean/variance via Welford's algorithm with batch merge.

    Operates on D-dim vectors. After enough updates, `mean()` and `std()`
    track the population statistics so callers can `(x - mean) / std`
    normalize incoming observations / value targets.

    Standard usage:

        rms = RunningMeanStd(dim=obs_dim, epsilon=1e-4)
        for batch in rollouts:
            rms.update(batch)            # batch: List[List[float]]
        normalized = rms.normalize(obs)

    `epsilon` adds to variance before sqrt — avoids divide-by-zero in
    early training when variance is still 0.

    Merge formula (Chan et al. 2007, parallel-stream Welford):

        n = n_a + n_b
        δ = μ_b - μ_a
        μ = μ_a + δ * (n_b / n)
        M2 = M2_a + M2_b + δ² * (n_a * n_b / n)
        σ² = M2 / n
    """

    def __init__(self, dim: int, epsilon: float = 1e-4):
        if dim <= 0:
            raise ValueError(f"dim must be > 0; got {dim}")
        if epsilon <= 0:
            raise ValueError(f"epsilon must be > 0; got {epsilon}")
        self.dim = dim
        self.epsilon = epsilon
        self._mean: List[float] = [0.0] * dim
        self._m2: List[float] = [0.0] * dim  # sum of squared deltas
        self._count: int = 0

    def update(self, batch: List[List[float]]) -> None:
        """Update running stats with a batch of vectors.

        Each row must be length `dim`. Empty batch is a no-op.
        """
        if not batch:
            return
        n_b = len(batch)
        # Batch mean.
        batch_mean = [0.0] * self.dim
        for row in batch:
            if len(row) != self.dim:
                raise ValueError(
                    f"row length {len(row)} != dim {self.dim}"
                )
            for j in range(self.dim):
                batch_mean[j] += row[j]
        for j in range(self.dim):
            batch_mean[j] /= n_b
        # Batch M2 (sum of squared deviations).
        batch_m2 = [0.0] * self.dim
        for row in batch:
            for j in range(self.dim):
                d = row[j] - batch_mean[j]
                batch_m2[j] += d * d
        # Merge.
        if self._count == 0:
            self._mean = list(batch_mean)
            self._m2 = list(batch_m2)
            self._count = n_b
            return
        n_a = self._count
        n_total = n_a + n_b
        for j in range(self.dim):
            delta = batch_mean[j] - self._mean[j]
            self._mean[j] += delta * (n_b / n_total)
            self._m2[j] += batch_m2[j] + delta * delta * (n_a * n_b / n_total)
        self._count = n_total

    # ── statistics ───────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        return self._count

    def mean(self) -> List[float]:
        return list(self._mean)

    def var(self) -> List[float]:
        """Population variance (M2 / count). 0 when count == 0."""
        if self._count == 0:
            return [0.0] * self.dim
        return [m / self._count for m in self._m2]

    def std(self) -> List[float]:
        """sqrt(var + epsilon) — non-zero, safe for division."""
        return [math.sqrt(v + self.epsilon) for v in self.var()]

    # ── normalize / denormalize ──────────────────────────────────────────

    def normalize(self, x: List[List[float]]) -> List[List[float]]:
        """Apply (x - mean) / std element-wise. Batch shape preserved."""
        means = self._mean
        stds = self.std()
        return [
            [(row[j] - means[j]) / stds[j] for j in range(self.dim)]
            for row in x
        ]

    def denormalize(self, x: List[List[float]]) -> List[List[float]]:
        """Inverse — x * std + mean."""
        means = self._mean
        stds = self.std()
        return [
            [row[j] * stds[j] + means[j] for j in range(self.dim)]
            for row in x
        ]


# ────────────────────────────────────────────────────────────────────────────
# RewardScaling — discount-aware reward normalizer (rl_games convention)
# ────────────────────────────────────────────────────────────────────────────


class RewardScaling:
    """Discount-aware running-std reward scaler.

    Tracks a running estimate of the discounted-return magnitude σ_R and
    scales rewards by `1 / σ_R`. Reduces sensitivity to absolute reward
    scale (a network trained at reward magnitude 1 transfers cleanly to
    reward magnitude 100).

    Per-env state: running discounted return R_t = γ R_{t-1} + r_t.
    Statistics over R updated via RunningMeanStd (1-D).

    Standard usage:

        scaler = RewardScaling(num_envs=4, gamma=0.99)
        for batch_rewards in rollouts:
            scaled = scaler.scale(rewards, dones)
        # On episode reset, scaler.reset(env_ids) zeros R for done envs.
    """

    def __init__(self, num_envs: int, gamma: float = 0.99,
                 epsilon: float = 1e-4):
        if num_envs <= 0:
            raise ValueError(f"num_envs must be > 0; got {num_envs}")
        if not (0.0 < gamma <= 1.0):
            raise ValueError(f"gamma must be in (0, 1]; got {gamma}")
        self.num_envs = num_envs
        self.gamma = gamma
        self.epsilon = epsilon
        self._returns: List[float] = [0.0] * num_envs
        self._rms = RunningMeanStd(dim=1, epsilon=epsilon)

    def scale(self, rewards: List[float],
              dones: Optional[List[bool]] = None) -> List[float]:
        """Update running discounted returns + return scaled rewards.

        `rewards[i]` is env i's latest reward; `dones[i]` is True if env i
        terminated on this step (zeroes its discounted return).
        """
        if len(rewards) != self.num_envs:
            raise ValueError(
                f"expected {self.num_envs} rewards; got {len(rewards)}"
            )
        # Update discounted returns.
        for i in range(self.num_envs):
            done = dones[i] if dones is not None and i < len(dones) else False
            if done:
                self._returns[i] = 0.0
            self._returns[i] = self.gamma * self._returns[i] + rewards[i]
        # Update RMS over current discounted returns (1D).
        batch = [[r] for r in self._returns]
        self._rms.update(batch)
        # Scale.
        std = self._rms.std()[0]
        return [r / max(std, self.epsilon) for r in rewards]

    def reset(self, env_ids: Optional[List[int]] = None) -> None:
        """Zero the running discounted return for the named envs (or all)."""
        targets = env_ids if env_ids is not None else list(range(self.num_envs))
        for i in targets:
            self._returns[i] = 0.0

    @property
    def std(self) -> float:
        return self._rms.std()[0]
