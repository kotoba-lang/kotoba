"""Proximal Policy Optimization (PPO) — stdlib-only RL trainer.

The canonical Isaac Lab RL algorithm. Sibling of `cem.py` — where CEM is
population-based and gradient-free (works on opaque envs), PPO is a
policy-gradient method requiring a differentiable policy + value network.

Implementation: PPO-Clip (Schulman et al. 2017) with:
  - Diagonal Gaussian policy (`GaussianPolicy`) — 2-layer MLP for the mean,
    per-dim state-independent learnable log_std
  - Value function (`ValueFunction`) — separate 2-layer MLP, scalar output
  - GAE-λ advantage estimation (Schulman et al. 2015)
  - Clipped surrogate loss + value clipping + entropy bonus
  - Adam optimizer (m + v per parameter, bias correction)
  - Manual forward/backward MLP (no autograd) — list-of-floats ops
  - Pure stdlib (math + the local `_Lcg`), zero numpy/torch dependency

Suitable for low-DOF control tasks (Cartpole 4-obs × 1-act, DoublePendulum
4-obs × 2-act). For higher-DOF tasks the list-of-floats inner loops dominate
runtime; in that regime users should drop into PyTorch / skrl externally
(both wire to the same `DirectRLEnv` / `ManagerBasedRLEnv` contract).

Standard usage:

    env = CartpoleDirectEnv(CartpoleDirectEnvCfg(num_envs=1, urdf_text=URDF))
    trainer = PPOTrainer(env, PPOConfig(n_iterations=50))
    result = trainer.train()
    # result.fitness_curve, result.best_policy, result.best_value_fn
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Tuple

from .cem import _Lcg  # reuse the shared LCG for cross-trainer determinism


# ────────────────────────────────────────────────────────────────────────────
# Tiny manual-backprop MLP
# ────────────────────────────────────────────────────────────────────────────


class MLP:
    """Two-layer MLP. forward(x) → (y, cache). backward(dy, cache) → grads.

    Hidden nonlinearity = tanh, output = linear. Adam optimizer state lives
    on the MLP instance (per-parameter m + v moments).
    """

    def __init__(self, n_in: int, n_hidden: int, n_out: int, rng: _Lcg):
        # Xavier-ish init: std = sqrt(1/fan_in).
        s1 = math.sqrt(1.0 / max(1, n_in))
        s2 = math.sqrt(1.0 / max(1, n_hidden))
        self.W1: List[List[float]] = [
            [rng.next_normal(0.0, s1) for _ in range(n_in)]
            for _ in range(n_hidden)
        ]
        self.b1: List[float] = [0.0] * n_hidden
        self.W2: List[List[float]] = [
            [rng.next_normal(0.0, s2) for _ in range(n_hidden)]
            for _ in range(n_out)
        ]
        self.b2: List[float] = [0.0] * n_out
        # Adam state.
        self._mW1 = [[0.0] * n_in for _ in range(n_hidden)]
        self._mb1 = [0.0] * n_hidden
        self._mW2 = [[0.0] * n_hidden for _ in range(n_out)]
        self._mb2 = [0.0] * n_out
        self._vW1 = [[0.0] * n_in for _ in range(n_hidden)]
        self._vb1 = [0.0] * n_hidden
        self._vW2 = [[0.0] * n_hidden for _ in range(n_out)]
        self._vb2 = [0.0] * n_out
        self._adam_t = 0

    def forward(self, x: List[float]) -> Tuple[List[float], dict]:
        n_in = len(x)
        n_hidden = len(self.b1)
        n_out = len(self.b2)
        h_pre = [0.0] * n_hidden
        for i in range(n_hidden):
            w_row = self.W1[i]
            acc = self.b1[i]
            for j in range(n_in):
                acc += w_row[j] * x[j]
            h_pre[i] = acc
        h = [math.tanh(z) for z in h_pre]
        y = [0.0] * n_out
        for i in range(n_out):
            w_row = self.W2[i]
            acc = self.b2[i]
            for j in range(n_hidden):
                acc += w_row[j] * h[j]
            y[i] = acc
        return y, {"x": x, "h": h}

    def backward(self, dy: List[float], cache: dict) -> dict:
        x: List[float] = cache["x"]
        h: List[float] = cache["h"]
        n_in = len(x)
        n_hidden = len(h)
        n_out = len(dy)
        # dW2, db2.
        dW2 = [[dy[i] * h[j] for j in range(n_hidden)] for i in range(n_out)]
        db2 = list(dy)
        # dh = W2^T @ dy.
        dh = [0.0] * n_hidden
        for j in range(n_hidden):
            acc = 0.0
            for i in range(n_out):
                acc += self.W2[i][j] * dy[i]
            dh[j] = acc
        # dh_pre = dh * (1 - tanh^2).
        dh_pre = [dh[j] * (1.0 - h[j] * h[j]) for j in range(n_hidden)]
        # dW1, db1.
        dW1 = [[dh_pre[i] * x[j] for j in range(n_in)] for i in range(n_hidden)]
        db1 = list(dh_pre)
        return {"W1": dW1, "b1": db1, "W2": dW2, "b2": db2}

    def adam_step(
        self,
        grads: dict,
        lr: float = 3e-4,
        beta1: float = 0.9,
        beta2: float = 0.999,
        eps: float = 1e-8,
        max_grad_norm: Optional[float] = 0.5,
    ) -> None:
        """Apply Adam update with optional global gradient clipping."""
        # Optional global gradient norm clip.
        if max_grad_norm is not None:
            sq = 0.0
            for row in grads["W1"]:
                for g in row:
                    sq += g * g
            for g in grads["b1"]:
                sq += g * g
            for row in grads["W2"]:
                for g in row:
                    sq += g * g
            for g in grads["b2"]:
                sq += g * g
            gn = math.sqrt(sq)
            if gn > max_grad_norm and gn > 0:
                scale = max_grad_norm / gn
                for row in grads["W1"]:
                    for k in range(len(row)):
                        row[k] *= scale
                for k in range(len(grads["b1"])):
                    grads["b1"][k] *= scale
                for row in grads["W2"]:
                    for k in range(len(row)):
                        row[k] *= scale
                for k in range(len(grads["b2"])):
                    grads["b2"][k] *= scale

        self._adam_t += 1
        bc1 = 1.0 - beta1 ** self._adam_t
        bc2 = 1.0 - beta2 ** self._adam_t

        def step_2d(param, grad, m, v):
            for i in range(len(param)):
                row = param[i]
                grow = grad[i]
                mrow = m[i]
                vrow = v[i]
                for j in range(len(row)):
                    g = grow[j]
                    mrow[j] = beta1 * mrow[j] + (1.0 - beta1) * g
                    vrow[j] = beta2 * vrow[j] + (1.0 - beta2) * g * g
                    m_hat = mrow[j] / bc1
                    v_hat = vrow[j] / bc2
                    row[j] -= lr * m_hat / (math.sqrt(v_hat) + eps)

        def step_1d(param, grad, m, v):
            for i in range(len(param)):
                g = grad[i]
                m[i] = beta1 * m[i] + (1.0 - beta1) * g
                v[i] = beta2 * v[i] + (1.0 - beta2) * g * g
                m_hat = m[i] / bc1
                v_hat = v[i] / bc2
                param[i] -= lr * m_hat / (math.sqrt(v_hat) + eps)

        step_2d(self.W1, grads["W1"], self._mW1, self._vW1)
        step_1d(self.b1, grads["b1"], self._mb1, self._vb1)
        step_2d(self.W2, grads["W2"], self._mW2, self._vW2)
        step_1d(self.b2, grads["b2"], self._mb2, self._vb2)


# ────────────────────────────────────────────────────────────────────────────
# Diagonal Gaussian policy + Value function
# ────────────────────────────────────────────────────────────────────────────


class GaussianPolicy:
    """Diagonal Gaussian: mean from MLP, per-dim state-independent log_std."""

    def __init__(self, n_obs: int, n_act: int, hidden: int = 32,
                 init_log_std: float = 0.0, rng: Optional[_Lcg] = None):
        self.n_obs = n_obs
        self.n_act = n_act
        self.mlp = MLP(n_obs, hidden, n_act, rng or _Lcg(0))
        self.log_std: List[float] = [init_log_std] * n_act
        self._log_std_m: List[float] = [0.0] * n_act
        self._log_std_v: List[float] = [0.0] * n_act
        self._log_std_t: int = 0

    def forward(self, obs: List[float]) -> Tuple[List[float], dict]:
        return self.mlp.forward(obs)

    def sample(self, obs: List[float], rng: _Lcg) -> Tuple[List[float], float, List[float], dict]:
        """Sample a action ~ N(mean(obs), exp(log_std)^2)."""
        mean, cache = self.forward(obs)
        action = [
            mean[i] + math.exp(self.log_std[i]) * rng.next_normal()
            for i in range(self.n_act)
        ]
        log_prob = self._log_prob(action, mean, self.log_std)
        return action, log_prob, mean, cache

    def _log_prob(self, action: List[float], mean: List[float],
                  log_std: List[float]) -> float:
        n = len(action)
        ll = -0.5 * n * math.log(2.0 * math.pi)
        for i in range(n):
            ll -= log_std[i]
            d = (action[i] - mean[i]) / math.exp(log_std[i])
            ll -= 0.5 * d * d
        return ll

    def log_prob(self, obs: List[float], action: List[float]) -> Tuple[float, List[float], dict]:
        """Recompute log_prob for an old (obs, action). Returns (lp, mean, cache)."""
        mean, cache = self.forward(obs)
        return self._log_prob(action, mean, self.log_std), mean, cache

    def entropy(self) -> float:
        """Diagonal Gaussian entropy = sum over dims of 0.5*(log(2πe)) + log_std."""
        return sum(0.5 * (math.log(2.0 * math.pi) + 1.0) + ls for ls in self.log_std)

    def grad_mean_logstd(self, action: List[float], mean: List[float]) -> Tuple[List[float], List[float]]:
        """∂log_prob / ∂mean and ∂log_prob / ∂log_std at given (action, mean)."""
        n = len(action)
        d_mean = [0.0] * n
        d_logstd = [0.0] * n
        for i in range(n):
            std = math.exp(self.log_std[i])
            d = (action[i] - mean[i]) / std
            d_mean[i] = d / std
            d_logstd[i] = -1.0 + d * d
        return d_mean, d_logstd

    def update_log_std(self, grad: List[float], lr: float = 3e-4,
                       beta1: float = 0.9, beta2: float = 0.999, eps: float = 1e-8) -> None:
        """Adam step on the log_std parameter."""
        self._log_std_t += 1
        bc1 = 1.0 - beta1 ** self._log_std_t
        bc2 = 1.0 - beta2 ** self._log_std_t
        for i in range(len(self.log_std)):
            g = grad[i]
            self._log_std_m[i] = beta1 * self._log_std_m[i] + (1.0 - beta1) * g
            self._log_std_v[i] = beta2 * self._log_std_v[i] + (1.0 - beta2) * g * g
            m_hat = self._log_std_m[i] / bc1
            v_hat = self._log_std_v[i] / bc2
            self.log_std[i] -= lr * m_hat / (math.sqrt(v_hat) + eps)


class ValueFunction:
    """state → scalar V(s). 2-layer MLP wrapper."""

    def __init__(self, n_obs: int, hidden: int = 32, rng: Optional[_Lcg] = None):
        self.mlp = MLP(n_obs, hidden, 1, rng or _Lcg(1))

    def forward(self, obs: List[float]) -> Tuple[float, dict]:
        y, cache = self.mlp.forward(obs)
        return y[0], cache

    def grad_update(self, dV: float, cache: dict, lr: float = 3e-4) -> None:
        grads = self.mlp.backward([dV], cache)
        self.mlp.adam_step(grads, lr=lr)


# ────────────────────────────────────────────────────────────────────────────
# PPO trainer
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class PPOConfig:
    n_iterations: int = 30
    rollout_steps: int = 256
    n_epochs: int = 4
    minibatch_size: int = 64
    gamma: float = 0.99
    lam: float = 0.95
    clip_ratio: float = 0.2
    policy_lr: float = 3e-4
    value_lr: float = 1e-3
    entropy_coef: float = 0.0
    value_coef: float = 0.5
    max_episode_steps: int = 200
    hidden_size: int = 32
    action_scale: float = 10.0   # raw network output → env action scale
    seed: int = 0
    log_every: int = 1


@dataclass
class PPOResult:
    fitness_curve: List[float]
    policy: Any
    value_fn: Any
    best_fitness: float
    iterations: int


class PPOTrainer:
    """PPO trainer wired against a `DirectRLEnv`-style env (step/reset).

    Env contract: obs is `{"policy": [floats]}` (Isaac Lab DirectRLEnv default).
    For single-env training the obs vector is taken as the first num_observations
    floats. Multi-env collection follows the same pattern over env index 0.
    """

    def __init__(self, env: Any, cfg: PPOConfig):
        self.env = env
        self.cfg = cfg
        self.rng = _Lcg(cfg.seed)
        n_obs = int(getattr(env.cfg, "num_observations", 4))
        n_act = int(getattr(env.cfg, "num_actions", 1))
        self.n_obs = n_obs
        self.n_act = n_act
        self.policy = GaussianPolicy(n_obs, n_act, hidden=cfg.hidden_size,
                                     init_log_std=0.0, rng=_Lcg(cfg.seed + 100))
        self.value_fn = ValueFunction(n_obs, hidden=cfg.hidden_size,
                                      rng=_Lcg(cfg.seed + 200))

    # ── env wiring ────────────────────────────────────────────────────────

    def _obs_first(self, obs_dict: dict) -> List[float]:
        """Pull env 0 obs vector from {"policy": [obs0, obs1, …]} flat layout."""
        flat = obs_dict.get("policy", [])
        return list(flat[: self.n_obs])

    def _step_env(self, action_raw: List[float]) -> Tuple[List[float], float, bool]:
        """Single env-0 step. Returns (next_obs, reward, done)."""
        scaled = [a * self.cfg.action_scale for a in action_raw]
        # DirectRLEnv expects list of per-env action vectors.
        out = self.env.step([scaled])
        obs, reward, terminated, truncated, _info = out
        done = bool((terminated[0] if terminated else False) or
                    (truncated[0] if truncated else False))
        return self._obs_first(obs), float(reward[0]) if reward else 0.0, done

    def _reset_env(self, seed: Optional[int] = None) -> List[float]:
        obs, _ = self.env.reset(seed=seed)
        return self._obs_first(obs)

    # ── rollout collection ────────────────────────────────────────────────

    def collect_rollout(self) -> dict:
        """Collect a fixed-length rollout. Returns a dict of lists indexed by step."""
        T = self.cfg.rollout_steps
        obs_buf: List[List[float]] = []
        act_buf: List[List[float]] = []
        logp_buf: List[float] = []
        val_buf: List[float] = []
        rew_buf: List[float] = []
        done_buf: List[bool] = []
        ep_returns: List[float] = []
        ep_length = 0
        ep_return = 0.0

        obs = self._reset_env(seed=self.cfg.seed + self.rng.state % 1_000_000)
        for _ in range(T):
            action, log_prob, _mean, _ = self.policy.sample(obs, self.rng)
            value, _ = self.value_fn.forward(obs)
            next_obs, reward, done = self._step_env(action)

            obs_buf.append(obs)
            act_buf.append(action)
            logp_buf.append(log_prob)
            val_buf.append(value)
            rew_buf.append(reward)
            done_buf.append(done)

            ep_return += reward
            ep_length += 1
            obs = next_obs
            if done or ep_length >= self.cfg.max_episode_steps:
                ep_returns.append(ep_return)
                ep_return = 0.0
                ep_length = 0
                obs = self._reset_env()

        # Bootstrap value for final obs (used by GAE).
        last_value, _ = self.value_fn.forward(obs)
        return {
            "obs": obs_buf, "act": act_buf, "logp": logp_buf, "val": val_buf,
            "rew": rew_buf, "done": done_buf, "last_value": last_value,
            "ep_returns": ep_returns,
        }

    @staticmethod
    def compute_gae(rew: List[float], val: List[float], done: List[bool],
                    last_value: float, gamma: float, lam: float) -> Tuple[List[float], List[float]]:
        """Generalized Advantage Estimation. Returns (advantages, returns)."""
        T = len(rew)
        adv = [0.0] * T
        gae = 0.0
        for t in reversed(range(T)):
            next_v = last_value if t == T - 1 else val[t + 1]
            non_terminal = 0.0 if done[t] else 1.0
            delta = rew[t] + gamma * next_v * non_terminal - val[t]
            gae = delta + gamma * lam * non_terminal * gae
            adv[t] = gae
        ret = [adv[t] + val[t] for t in range(T)]
        # Normalize advantages.
        m = sum(adv) / T
        var = sum((a - m) ** 2 for a in adv) / T
        sd = math.sqrt(var) + 1e-8
        adv = [(a - m) / sd for a in adv]
        return adv, ret

    # ── PPO update ────────────────────────────────────────────────────────

    def update(self, rollout: dict) -> dict:
        obs_buf = rollout["obs"]
        act_buf = rollout["act"]
        old_logp = rollout["logp"]
        adv, ret = self.compute_gae(
            rollout["rew"], rollout["val"], rollout["done"],
            rollout["last_value"], self.cfg.gamma, self.cfg.lam,
        )
        T = len(obs_buf)
        bs = min(self.cfg.minibatch_size, T)
        cum_pol_loss = 0.0
        cum_val_loss = 0.0
        cum_kl = 0.0
        update_count = 0
        for _ in range(self.cfg.n_epochs):
            # Permute indices via LCG.
            indices = list(range(T))
            for i in range(T - 1, 0, -1):
                # LCG-driven Fisher-Yates shuffle (deterministic given seed).
                self.rng.next_u01()
                j = int(self.rng.state >> 33) % (i + 1)
                indices[i], indices[j] = indices[j], indices[i]
            for start in range(0, T, bs):
                batch = indices[start:start + bs]
                # Accumulate gradients across the minibatch.
                acc_W1 = [[0.0] * self.n_obs for _ in range(self.cfg.hidden_size)]
                acc_b1 = [0.0] * self.cfg.hidden_size
                acc_W2 = [[0.0] * self.cfg.hidden_size for _ in range(self.n_act)]
                acc_b2 = [0.0] * self.n_act
                acc_log_std = [0.0] * self.n_act
                vacc_W1 = [[0.0] * self.n_obs for _ in range(self.cfg.hidden_size)]
                vacc_b1 = [0.0] * self.cfg.hidden_size
                vacc_W2 = [[0.0] * self.cfg.hidden_size for _ in range(1)]
                vacc_b2 = [0.0] * 1
                for idx in batch:
                    obs = obs_buf[idx]
                    action = act_buf[idx]
                    old_lp = old_logp[idx]
                    a = adv[idx]
                    r_target = ret[idx]

                    # Policy forward.
                    new_lp, mean, pcache = self.policy.log_prob(obs, action)
                    ratio = math.exp(min(50.0, max(-50.0, new_lp - old_lp)))
                    # Clipped objective.
                    surr1 = ratio * a
                    eps_clip = self.cfg.clip_ratio
                    clipped_ratio = max(1.0 - eps_clip, min(1.0 + eps_clip, ratio))
                    surr2 = clipped_ratio * a
                    # Policy loss = -min(surr1, surr2).
                    # d_loss/d_ratio: if min is surr1 → -a; else if clip is binding → 0.
                    use_clipped = (surr2 < surr1)
                    pol_loss = -min(surr1, surr2)
                    cum_pol_loss += pol_loss
                    # d ratio / d new_lp = ratio.
                    if not use_clipped:
                        # Active term is surr1 = ratio * a. d/d_new_lp = ratio * a.
                        # d_loss/d_new_lp = -ratio * a.
                        d_logp_pol = -ratio * a
                    else:
                        # Clipped branch — gradient is 0 unless within clip.
                        if 1.0 - eps_clip < ratio < 1.0 + eps_clip:
                            d_logp_pol = -ratio * a
                        else:
                            d_logp_pol = 0.0
                    # Entropy bonus (state-independent → only affects log_std).
                    d_logp_ent = self.cfg.entropy_coef

                    # Backprop d_logp through mean + log_std.
                    d_mean, d_logstd = self.policy.grad_mean_logstd(action, mean)
                    # d_logp_pol * d_log_prob/d_mean → MLP backward gradient
                    dy_mean = [d_logp_pol * dm for dm in d_mean]
                    grads = self.policy.mlp.backward(dy_mean, pcache)
                    # Accumulate.
                    for i in range(self.cfg.hidden_size):
                        for j in range(self.n_obs):
                            acc_W1[i][j] += grads["W1"][i][j]
                        acc_b1[i] += grads["b1"][i]
                    for i in range(self.n_act):
                        for j in range(self.cfg.hidden_size):
                            acc_W2[i][j] += grads["W2"][i][j]
                        acc_b2[i] += grads["b2"][i]
                    for i in range(self.n_act):
                        acc_log_std[i] += d_logp_pol * d_logstd[i] - d_logp_ent

                    # Value forward + loss.
                    v_pred, vcache = self.value_fn.forward(obs)
                    v_err = v_pred - r_target
                    val_loss = 0.5 * v_err * v_err
                    cum_val_loss += val_loss
                    dV = self.cfg.value_coef * v_err
                    vgrads = self.value_fn.mlp.backward([dV], vcache)
                    for i in range(self.cfg.hidden_size):
                        for j in range(self.n_obs):
                            vacc_W1[i][j] += vgrads["W1"][i][j]
                        vacc_b1[i] += vgrads["b1"][i]
                    for j in range(self.cfg.hidden_size):
                        vacc_W2[0][j] += vgrads["W2"][0][j]
                    vacc_b2[0] += vgrads["b2"][0]

                    cum_kl += old_lp - new_lp
                    update_count += 1

                # Average gradients across the minibatch.
                inv = 1.0 / max(1, len(batch))
                for i in range(self.cfg.hidden_size):
                    for j in range(self.n_obs):
                        acc_W1[i][j] *= inv
                        vacc_W1[i][j] *= inv
                    acc_b1[i] *= inv
                    vacc_b1[i] *= inv
                for i in range(self.n_act):
                    for j in range(self.cfg.hidden_size):
                        acc_W2[i][j] *= inv
                    acc_b2[i] *= inv
                for j in range(self.cfg.hidden_size):
                    vacc_W2[0][j] *= inv
                vacc_b2[0] *= inv
                for i in range(self.n_act):
                    acc_log_std[i] *= inv

                # Apply Adam steps.
                self.policy.mlp.adam_step(
                    {"W1": acc_W1, "b1": acc_b1, "W2": acc_W2, "b2": acc_b2},
                    lr=self.cfg.policy_lr,
                )
                self.policy.update_log_std(acc_log_std, lr=self.cfg.policy_lr)
                self.value_fn.mlp.adam_step(
                    {"W1": vacc_W1, "b1": vacc_b1, "W2": vacc_W2, "b2": vacc_b2},
                    lr=self.cfg.value_lr,
                )

        return {
            "policy_loss": cum_pol_loss / max(1, update_count),
            "value_loss": cum_val_loss / max(1, update_count),
            "approx_kl": cum_kl / max(1, update_count),
            "log_std_mean": sum(self.policy.log_std) / len(self.policy.log_std),
        }

    # ── main loop ─────────────────────────────────────────────────────────

    def train(self, on_iter: Optional[Callable[[int, dict], None]] = None) -> PPOResult:
        fitness_curve: List[float] = []
        best_fit = -math.inf
        for it in range(self.cfg.n_iterations):
            rollout = self.collect_rollout()
            stats = self.update(rollout)
            mean_ret = (
                sum(rollout["ep_returns"]) / len(rollout["ep_returns"])
                if rollout["ep_returns"] else 0.0
            )
            fitness_curve.append(mean_ret)
            best_fit = max(best_fit, mean_ret)
            if on_iter is not None:
                on_iter(it, {**stats, "mean_return": mean_ret,
                             "n_episodes": len(rollout["ep_returns"])})
        return PPOResult(
            fitness_curve=fitness_curve, policy=self.policy,
            value_fn=self.value_fn, best_fitness=best_fit,
            iterations=self.cfg.n_iterations,
        )
