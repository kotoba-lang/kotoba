"""isaaclab.envs.replay_buffer — off-policy RL transition storage.

Mirror of Isaac Lab's off-policy training scaffolding. Three buffer
variants matching common SAC / DQN / TD3 patterns:

  1. ReplayBuffer            — uniform FIFO ring (Lin 1992)
  2. PrioritizedReplayBuffer — Schaul et al. 2016 PER with proportional
                                priority + importance-sampling weights
                                via a fixed-size sum-tree
  3. NStepReplayBuffer       — wraps a base buffer, emitting n-step
                                transitions for return targets matching
                                rainbow-DQN / multi-step SAC variants

Transition format: dict with keys {"obs", "action", "reward", "next_obs",
"done"}. Each value is a list-of-per-env or per-batch payload (stdlib-
only — no torch / numpy). Callers convert to tensors on retrieval.

Pure stdlib (math + random via local LCG for cross-trainer determinism).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..algos.cem import _Lcg


# ────────────────────────────────────────────────────────────────────────────
# Transition dataclass
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class Transition:
    """Single SARSA transition. Optional info dict for extras (TD-error,
    behavior policy log_prob, etc.)."""
    obs: List[float] = field(default_factory=list)
    action: List[float] = field(default_factory=list)
    reward: float = 0.0
    next_obs: List[float] = field(default_factory=list)
    done: bool = False
    info: Dict[str, Any] = field(default_factory=dict)


# ────────────────────────────────────────────────────────────────────────────
# ReplayBuffer — FIFO ring
# ────────────────────────────────────────────────────────────────────────────


class ReplayBuffer:
    """Uniform FIFO ring buffer for off-policy RL.

    Capacity-bounded; old transitions evicted via FIFO. `sample(batch_size)`
    returns uniform random transitions (without replacement when possible,
    with replacement when batch_size > len(buffer)).

    Standard usage:

        buf = ReplayBuffer(capacity=10_000, seed=42)
        buf.add(Transition(obs=[1,2,3], action=[0.5], reward=1.0,
                            next_obs=[2,3,4], done=False))
        batch = buf.sample(64)
        # batch: dict with keys obs/action/reward/next_obs/done — each a
        # list of length batch_size (or list-of-lists for vector fields)
    """

    def __init__(self, capacity: int, seed: int = 0):
        if capacity <= 0:
            raise ValueError(f"capacity must be > 0; got {capacity}")
        self.capacity = capacity
        self._storage: List[Optional[Transition]] = [None] * capacity
        self._next_idx: int = 0
        self._size: int = 0
        self._rng = _Lcg(seed)

    # ── insertion ────────────────────────────────────────────────────────

    def add(self, transition: Transition) -> None:
        """Push a single transition; evict oldest if full (FIFO)."""
        self._storage[self._next_idx] = transition
        self._next_idx = (self._next_idx + 1) % self.capacity
        self._size = min(self._size + 1, self.capacity)

    def add_batch(self, transitions: List[Transition]) -> None:
        """Bulk add. Equivalent to repeated `add` calls."""
        for t in transitions:
            self.add(t)

    # ── sampling ─────────────────────────────────────────────────────────

    def sample(self, batch_size: int) -> Dict[str, List[Any]]:
        """Uniform random sample. Returns column-major dict — one list per
        field — for direct tensor stack downstream.

        Without-replacement when batch_size <= len; with-replacement
        otherwise (mirrors stable-baselines3 ReplayBuffer behavior).
        """
        if batch_size <= 0:
            raise ValueError(f"batch_size must be > 0; got {batch_size}")
        if self._size == 0:
            raise ValueError("cannot sample from empty buffer")
        n = self._size
        # Sample indices.
        if batch_size <= n:
            indices = self._sample_without_replacement(batch_size, n)
        else:
            indices = [
                int(self._rng.next_u01() * n) % n
                for _ in range(batch_size)
            ]
        return self._collect(indices)

    def _sample_without_replacement(self, k: int, n: int) -> List[int]:
        """Floyd's combination sampling (Knuth TAOCP vol 2 §3.4.2)."""
        s: List[int] = []
        seen = set()
        # Walk j = n-k..n-1; for each j, pick t in [0, j].
        for j in range(n - k, n):
            self._rng.next_u01()
            t = int(self._rng.state >> 33) % (j + 1)
            if t in seen:
                s.append(j)
                seen.add(j)
            else:
                s.append(t)
                seen.add(t)
        return s

    def _collect(self, indices: List[int]) -> Dict[str, List[Any]]:
        """Materialize transitions at indices into column-major dict."""
        out: Dict[str, List[Any]] = {
            "obs": [], "action": [], "reward": [],
            "next_obs": [], "done": [], "info": [],
        }
        for i in indices:
            t = self._storage[i]
            if t is None:
                continue
            out["obs"].append(t.obs)
            out["action"].append(t.action)
            out["reward"].append(t.reward)
            out["next_obs"].append(t.next_obs)
            out["done"].append(t.done)
            out["info"].append(t.info)
        return out

    # ── introspection ────────────────────────────────────────────────────

    def __len__(self) -> int:
        return self._size

    def is_full(self) -> bool:
        return self._size == self.capacity

    def clear(self) -> None:
        self._storage = [None] * self.capacity
        self._next_idx = 0
        self._size = 0


# ────────────────────────────────────────────────────────────────────────────
# Sum-tree (for PrioritizedReplayBuffer)
# ────────────────────────────────────────────────────────────────────────────


class _SumTree:
    """Binary heap where each internal node = sum of children. O(log N)
    update + prefix-sum query. Implements PER's proportional priority
    weighting (Schaul et al. 2016, §3.3)."""

    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError(f"capacity must be > 0; got {capacity}")
        self.capacity = capacity
        # Tree of size 2*capacity - 1 (binary heap; leaves at positions
        # [capacity-1, 2*capacity-2]).
        self._tree: List[float] = [0.0] * (2 * capacity - 1)

    def total(self) -> float:
        """Sum of all leaves (root)."""
        return self._tree[0]

    def update(self, leaf_idx: int, value: float) -> None:
        """Set leaf priority + propagate up."""
        tree_idx = leaf_idx + self.capacity - 1
        delta = value - self._tree[tree_idx]
        self._tree[tree_idx] = value
        # Bubble up.
        while tree_idx > 0:
            tree_idx = (tree_idx - 1) // 2
            self._tree[tree_idx] += delta

    def get(self, leaf_idx: int) -> float:
        return self._tree[leaf_idx + self.capacity - 1]

    def find(self, prefix_sum: float) -> Tuple[int, float]:
        """Return (leaf_idx, priority) where prefix_sum falls in the
        proportional weighting. O(log N) descent."""
        idx = 0
        while True:
            left = 2 * idx + 1
            right = left + 1
            if left >= len(self._tree):
                break
            if prefix_sum <= self._tree[left]:
                idx = left
            else:
                prefix_sum -= self._tree[left]
                idx = right
        leaf_idx = idx - (self.capacity - 1)
        return leaf_idx, self._tree[idx]


# ────────────────────────────────────────────────────────────────────────────
# PrioritizedReplayBuffer
# ────────────────────────────────────────────────────────────────────────────


class PrioritizedReplayBuffer:
    """Proportional PER (Schaul et al. 2016).

    Priority: |TD-error| + ε raised to power α (controls how strongly
    priority influences sampling; α=0 → uniform). Importance-sampling
    weights: (N · P(i))^(-β), normalized by max weight for stability.

    Beta is typically annealed from β₀ (e.g. 0.4) to 1.0 over training
    via `update_beta(new_beta)`.

    Standard usage:

        per = PrioritizedReplayBuffer(capacity=10_000, alpha=0.6, beta=0.4)
        per.add(transition)
        batch = per.sample(64)
        # batch["weights"]: importance-sampling weights to multiply TD loss
        # batch["indices"]: leaf indices for the priority update
        per.update_priorities(batch["indices"], new_td_errors)
    """

    def __init__(
        self,
        capacity: int,
        alpha: float = 0.6,
        beta: float = 0.4,
        epsilon: float = 1e-6,
        seed: int = 0,
    ):
        if capacity <= 0:
            raise ValueError(f"capacity must be > 0; got {capacity}")
        if not (0.0 <= alpha <= 1.0):
            raise ValueError(f"alpha must be in [0, 1]; got {alpha}")
        if not (0.0 <= beta <= 1.0):
            raise ValueError(f"beta must be in [0, 1]; got {beta}")
        if epsilon <= 0.0:
            raise ValueError(f"epsilon must be > 0; got {epsilon}")
        self.capacity = capacity
        self.alpha = alpha
        self.beta = beta
        self.epsilon = epsilon
        self._storage: List[Optional[Transition]] = [None] * capacity
        self._tree = _SumTree(capacity)
        self._next_idx: int = 0
        self._size: int = 0
        self._max_priority: float = 1.0  # initial priority for new entries
        self._rng = _Lcg(seed)

    # ── insertion ────────────────────────────────────────────────────────

    def add(self, transition: Transition,
            priority: Optional[float] = None) -> None:
        """Add transition with given priority (defaults to max-priority-
        seen to encourage early sampling). Eviction is FIFO."""
        p = priority if priority is not None else self._max_priority
        p_alpha = (p + self.epsilon) ** self.alpha
        self._storage[self._next_idx] = transition
        self._tree.update(self._next_idx, p_alpha)
        self._next_idx = (self._next_idx + 1) % self.capacity
        self._size = min(self._size + 1, self.capacity)

    # ── sampling ─────────────────────────────────────────────────────────

    def sample(self, batch_size: int) -> Dict[str, List[Any]]:
        """Sample batch_size transitions weighted by priority. Returns
        the same fields as ReplayBuffer.sample + "weights" + "indices".
        """
        if batch_size <= 0:
            raise ValueError(f"batch_size must be > 0; got {batch_size}")
        if self._size == 0:
            raise ValueError("cannot sample from empty buffer")

        total = self._tree.total()
        # Stratified sampling: divide [0, total] into batch_size buckets,
        # pick one prefix in each bucket (Schaul et al. §A.1).
        segment = total / batch_size
        indices: List[int] = []
        priorities: List[float] = []
        for k in range(batch_size):
            self._rng.next_u01()
            u = self._rng.state >> 33
            r = (u / (1 << 31)) * segment + k * segment
            leaf_idx, p_alpha = self._tree.find(r)
            indices.append(leaf_idx)
            priorities.append(p_alpha)

        # Importance-sampling weights.
        n = self._size
        weights: List[float] = []
        max_w = 0.0
        for p_alpha in priorities:
            prob = p_alpha / max(total, self.epsilon)
            w = (n * prob) ** (-self.beta) if prob > 0 else 0.0
            weights.append(w)
            if w > max_w:
                max_w = w
        # Normalize by max weight.
        if max_w > 0:
            weights = [w / max_w for w in weights]

        # Collect transitions.
        out: Dict[str, List[Any]] = {
            "obs": [], "action": [], "reward": [],
            "next_obs": [], "done": [], "info": [],
            "weights": weights, "indices": indices,
        }
        for i in indices:
            t = self._storage[i]
            if t is None:
                continue
            out["obs"].append(t.obs)
            out["action"].append(t.action)
            out["reward"].append(t.reward)
            out["next_obs"].append(t.next_obs)
            out["done"].append(t.done)
            out["info"].append(t.info)
        return out

    def update_priorities(self, indices: List[int],
                          priorities: List[float]) -> None:
        """Update priorities for the given leaf indices. Call after computing
        new TD errors. Track max priority for future `add()` defaults.
        """
        if len(indices) != len(priorities):
            raise ValueError(
                f"indices ({len(indices)}) and priorities ({len(priorities)}) "
                f"must have same length"
            )
        for idx, p in zip(indices, priorities):
            if p < 0:
                raise ValueError(f"priority must be ≥ 0; got {p}")
            p_alpha = (p + self.epsilon) ** self.alpha
            self._tree.update(idx, p_alpha)
            if p > self._max_priority:
                self._max_priority = p

    def update_beta(self, new_beta: float) -> None:
        """Update β annealing schedule. Typical pattern: β₀=0.4 → 1.0
        over training; caller updates each iteration."""
        if not (0.0 <= new_beta <= 1.0):
            raise ValueError(f"beta must be in [0, 1]; got {new_beta}")
        self.beta = new_beta

    # ── introspection ────────────────────────────────────────────────────

    def __len__(self) -> int:
        return self._size

    def is_full(self) -> bool:
        return self._size == self.capacity


# ────────────────────────────────────────────────────────────────────────────
# NStepReplayBuffer — wraps base buffer with n-step transition emission
# ────────────────────────────────────────────────────────────────────────────


class NStepReplayBuffer:
    """Wraps a base ReplayBuffer to emit n-step transitions for return
    targets (rainbow-DQN / multi-step SAC).

    Holds a sliding window of `n_step` transitions per env. When the
    window fills, emits a "merged" transition:

        merged.obs       = window[0].obs
        merged.action    = window[0].action
        merged.reward    = Σ_{k=0..n-1} γ^k * r_k    (truncated on done)
        merged.next_obs  = window[n-1].next_obs       (or window[k].next_obs
                            for the first done in window)
        merged.done      = any(window[k].done)

    Episode boundaries trigger early emission. Used by Isaac Lab's multi-
    step DQN reference + Apex distributed training pattern.

    Standard usage:

        base = ReplayBuffer(capacity=100_000)
        n_step_buf = NStepReplayBuffer(base, n_step=3, gamma=0.99, num_envs=4)
        for t in range(T):
            n_step_buf.add_step(env_idx, transition_t)
        # Sample as if it were the base buffer:
        batch = base.sample(64)
    """

    def __init__(
        self,
        base_buffer: Any,  # ReplayBuffer or PrioritizedReplayBuffer
        n_step: int,
        gamma: float,
        num_envs: int = 1,
    ):
        if n_step <= 0:
            raise ValueError(f"n_step must be > 0; got {n_step}")
        if not (0.0 < gamma <= 1.0):
            raise ValueError(f"gamma must be in (0, 1]; got {gamma}")
        if num_envs <= 0:
            raise ValueError(f"num_envs must be > 0; got {num_envs}")
        self.base = base_buffer
        self.n_step = n_step
        self.gamma = gamma
        self.num_envs = num_envs
        # Per-env sliding window.
        self._windows: List[List[Transition]] = [[] for _ in range(num_envs)]

    def add_step(self, env_idx: int, transition: Transition) -> None:
        """Push a transition for env_idx; emit n-step merged when window
        is full OR when transition.done is True (terminal forces flush)."""
        if not (0 <= env_idx < self.num_envs):
            raise IndexError(f"env_idx={env_idx} out of [0, {self.num_envs})")
        window = self._windows[env_idx]
        window.append(transition)
        if transition.done:
            # Episode boundary: flush all pending steps from the front.
            while window:
                merged = self._merge_window(window)
                self.base.add(merged)
                window.pop(0)
        elif len(window) >= self.n_step:
            # Window full: emit merged n-step transition, drop oldest.
            merged = self._merge_window(window[: self.n_step])
            self.base.add(merged)
            window.pop(0)

    def _merge_window(self, window: List[Transition]) -> Transition:
        """Compute the n-step merged transition from window[0..k]."""
        first = window[0]
        merged_reward = 0.0
        merged_next_obs = first.next_obs
        merged_done = False
        for k, t in enumerate(window):
            merged_reward += (self.gamma ** k) * t.reward
            merged_next_obs = t.next_obs
            if t.done:
                merged_done = True
                break
        return Transition(
            obs=first.obs,
            action=first.action,
            reward=merged_reward,
            next_obs=merged_next_obs,
            done=merged_done,
            info=dict(first.info),
        )

    def reset_env(self, env_ids: Optional[List[int]] = None) -> None:
        """Drop any pending window state for the named envs (or all).

        Pending transitions are emitted via flush (so we don't lose data
        — matches stable-baselines3 N-step behavior on episode end).
        """
        targets = env_ids if env_ids is not None else list(range(self.num_envs))
        for env_idx in targets:
            window = self._windows[env_idx]
            while window:
                merged = self._merge_window(window)
                self.base.add(merged)
                window.pop(0)

    def pending_steps(self, env_idx: int) -> int:
        """Length of the current sliding window for env_idx."""
        return len(self._windows[env_idx])

    def __len__(self) -> int:
        return len(self.base)
