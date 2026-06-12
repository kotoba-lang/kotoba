"""Cross-Entropy Method (CEM) — population-based evolutionary trainer.

Algorithm (Rubinstein 1997, applied to RL by Mannor et al.):
  1. Init Gaussian distribution N(μ, σ²) over policy parameter vector.
  2. For each generation:
     a. Sample `pop_size` candidates from current distribution.
     b. Evaluate each via rollout(s) on env; fitness = mean episode reward.
     c. Select top `elite_frac · pop_size` candidates by fitness.
     d. Re-fit μ ← mean(elites), σ ← std(elites) + noise_floor.
  3. Track best candidate + per-generation fitness curve.

Linear policy: obs (n_obs,) → action (n_act,):
    action = tanh(W @ obs + b) * action_scale
  where W is (n_act × n_obs) and b is (n_act,). Total params = n_act * (n_obs + 1).

Pure stdlib (math + random via local LCG). No numpy/torch. Suitable for
low-DOF control tasks (Cartpole, mountain car, simple manipulation).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ── Sampler matching nv_compat / kami_shugyo LCG constants ─────────────────

class _Lcg:
    def __init__(self, seed: int):
        self.state = (seed * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF

    def next_u01(self) -> float:
        self.state = (self.state * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return ((self.state >> 33) & 0x7FFFFFFF) / float(1 << 31)

    def next_normal(self, mean: float = 0.0, std: float = 1.0) -> float:
        # Box–Muller transform.
        u1 = max(self.next_u01(), 1e-12)
        u2 = self.next_u01()
        z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
        return mean + std * z


# ── Linear policy ─────────────────────────────────────────────────────────

@dataclass
class LinearPolicy:
    """Linear obs→action policy with tanh squashing.

    params layout: first n_act * n_obs entries = W (row-major), then n_act
    entries = bias. Total length = n_act * (n_obs + 1).
    """
    n_obs: int
    n_act: int
    action_scale: float = 100.0
    params: list = field(default_factory=list)

    def __post_init__(self):
        if not self.params:
            self.params = [0.0] * (self.n_act * (self.n_obs + 1))
        assert len(self.params) == self.n_act * (self.n_obs + 1)

    def act(self, obs: list) -> list:
        """obs → action (length n_act)."""
        assert len(obs) == self.n_obs
        out = []
        for a in range(self.n_act):
            w_start = a * self.n_obs
            wsum = 0.0
            for o in range(self.n_obs):
                wsum += self.params[w_start + o] * obs[o]
            bias = self.params[self.n_act * self.n_obs + a]
            z = wsum + bias
            # tanh squash + scale
            out.append(math.tanh(z) * self.action_scale)
        return out

    @staticmethod
    def num_params(n_obs: int, n_act: int) -> int:
        return n_act * (n_obs + 1)


# ── CEM config + result ───────────────────────────────────────────────────

@dataclass
class CEMConfig:
    pop_size: int = 32
    elite_frac: float = 0.25
    init_std: float = 1.0
    noise_floor: float = 0.05
    n_generations: int = 20
    n_episodes_per_eval: int = 1
    max_steps_per_episode: int = 200
    seed: int = 0


@dataclass
class CEMResult:
    best_params: list
    best_fitness: float
    mean_fitness_curve: list
    elite_fitness_curve: list
    n_generations: int


# ── CEM trainer ───────────────────────────────────────────────────────────

class CEMTrainer:
    """Cross-Entropy Method trainer.

    `env_factory(seed)` must return a fresh env instance (subclass with
    .reset(seed=...) returning obs, .step(action) returning a 4-tuple
    obs / reward / terminated / truncated). For VectorizedCartpoleEnv,
    wrap each rollout to use one of the parallel envs.
    """

    def __init__(self, cfg: CEMConfig, n_obs: int, n_act: int,
                 action_scale: float = 100.0):
        self.cfg = cfg
        self.n_obs = n_obs
        self.n_act = n_act
        self.action_scale = action_scale
        self.n_params = LinearPolicy.num_params(n_obs, n_act)
        self.rng = _Lcg(cfg.seed)
        # Gaussian distribution over params: mean (n_params), std (n_params).
        self.mean = [0.0] * self.n_params
        self.std = [cfg.init_std] * self.n_params

    def sample_candidate(self) -> LinearPolicy:
        """Draw one candidate policy from the current Gaussian."""
        params = [self.rng.next_normal(self.mean[i], self.std[i]) for i in range(self.n_params)]
        return LinearPolicy(n_obs=self.n_obs, n_act=self.n_act,
                            action_scale=self.action_scale, params=params)

    def evaluate(self, policy: LinearPolicy, env_factory: Callable[[int], Any],
                 base_seed: int) -> float:
        """Mean episode reward across n_episodes_per_eval rollouts."""
        total = 0.0
        for ep in range(self.cfg.n_episodes_per_eval):
            env = env_factory(base_seed + ep)
            obs, _ = env.reset(seed=base_seed + ep)
            ep_reward = 0.0
            for _ in range(self.cfg.max_steps_per_episode):
                action = policy.act(list(obs))
                obs, reward, terminated, truncated, _ = env.step(action)
                ep_reward += reward
                if terminated or truncated:
                    break
            total += ep_reward
        return total / self.cfg.n_episodes_per_eval

    def fit_generation(self, env_factory: Callable[[int], Any], gen_idx: int) -> tuple:
        """One generation. Returns (best_params_in_gen, best_fitness, mean_fit, elite_mean_fit)."""
        candidates = [self.sample_candidate() for _ in range(self.cfg.pop_size)]
        fitnesses = []
        base = self.cfg.seed * 1000 + gen_idx * self.cfg.pop_size
        for k, cand in enumerate(candidates):
            f = self.evaluate(cand, env_factory, base + k)
            fitnesses.append(f)
        # Select elite.
        pairs = sorted(zip(fitnesses, range(len(candidates))), key=lambda x: -x[0])
        n_elite = max(1, int(self.cfg.elite_frac * self.cfg.pop_size))
        elite_idxs = [p[1] for p in pairs[:n_elite]]
        elite_params = [candidates[i].params for i in elite_idxs]
        elite_fits = [pairs[k][0] for k in range(n_elite)]
        # Refit distribution.
        for j in range(self.n_params):
            vals = [ep[j] for ep in elite_params]
            mean_j = sum(vals) / len(vals)
            var_j = sum((v - mean_j) ** 2 for v in vals) / max(1, len(vals) - 1)
            self.mean[j] = mean_j
            self.std[j] = math.sqrt(var_j) + self.cfg.noise_floor
        best_in_gen = pairs[0]
        return (candidates[best_in_gen[1]].params, best_in_gen[0],
                sum(fitnesses) / len(fitnesses),
                sum(elite_fits) / len(elite_fits))

    def train(self, env_factory: Callable[[int], Any]) -> CEMResult:
        """Run cfg.n_generations and return CEMResult."""
        best_params = list(self.mean)
        best_fitness = -float("inf")
        mean_curve = []
        elite_curve = []
        for g in range(self.cfg.n_generations):
            params, fit, mean_fit, elite_fit = self.fit_generation(env_factory, g)
            mean_curve.append(mean_fit)
            elite_curve.append(elite_fit)
            if fit > best_fitness:
                best_fitness = fit
                best_params = list(params)
        return CEMResult(
            best_params=best_params,
            best_fitness=best_fitness,
            mean_fitness_curve=mean_curve,
            elite_fitness_curve=elite_curve,
            n_generations=self.cfg.n_generations,
        )
