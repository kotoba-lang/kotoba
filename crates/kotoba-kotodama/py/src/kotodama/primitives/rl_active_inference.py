"""Active Inference (Phase 1B) — discrete POMDP formulation (Friston 2017).

Runs in parallel with Phase 1 DPO (rl_preferences.py).  Reads from the same
vertex_rl_step table written by Phase 0 (rl_signal.py).

MATHEMATICAL FORMULATION
────────────────────────
Hidden states s ∈ {thriving=0, stable=1, at_risk=2, in_crisis=3}
Observations  o ∈ {0..49}  — flattened 2×5×5 grid:
    obs_index = floor_ok*25 + spirit_bin*5 + eta_bin
    floor_ok ∈ {0,1},  spirit_bin = int(reward_spirit*4.999) ∈ {0..4}
                        eta_bin   = int(reward_eta*4.999)    ∈ {0..4}

Matrices (all stored as JSON-encoded arrays in VARCHAR columns):
    A[o,s]   = P(o|s)          shape (50, 4)    likelihood
    B[s',s,a]= P(s'|s,a)       shape (4, 4, Na) transition per action
    C[o]     = log P̃(o)        shape (50,)      log-preference (Well-Becoming)
    D[s]     = P(s_0)          shape (4,)       initial state prior
    E[a]     = P(π)            shape (Na,)      action prior

Prior preferences C encode ADR-2604291800 Well-Becoming objective:
    C[floor=0, *, *] = -100.0          floor violation → strong aversion
    C[floor=1, s, e] = s * 0.5 + e * 0.3  spirit+eta linear value

Belief update (variational, 1-step):
    q(s) ∝ exp(A[o,:].log() + D.log())    (softmax of log-posterior)

Variational free energy:
    F = KL[q(s)||D] − E_q[log A[o,s]]
      = Σ_s q(s)(log q(s) − log D[s]) − Σ_s q(s) log A[o,s]

Expected Free Energy for policy selection:
    G(a) = − pragmatic(a) − epistemic(a)
    pragmatic(a) = Σ_s q(s) Σ_o B[·,s,a_idx] · A[o,·] · C[o]
    epistemic(a) = H[Σ_s q(s) A[:,s]] − Σ_s q(s) H[A[:,s]]   (info-gain)
    where H[p] = −Σ p log p

Policy posterior:
    π(a) = softmax(−γ · G(a))       γ = 16.0  (precision parameter)

Model learning (online Dirichlet):
    A_counts[o,s] += 1  when observation o occurred in state s
    B_counts[s',s,a] += 1  for each transition (s,a,s')
    A = normalize(A_counts + 1)  (add-one smoothing)
    B = normalize(B_counts + 1)

Pyzeebe task types registered via register():
    rl.aif.update_beliefs  — R/PT1H  belief update + EFE per new rl_step
    rl.aif.learn_model     — R/P1D   Dirichlet posterior update of A, B
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import datetime as _dt
import json
import logging
import math
from typing import Any


LOG = logging.getLogger("rl_active_inference")

# ─── constants ────────────────────────────────────────────────────────────────
_N_OBS = 50      # 2 × 5 × 5 flattened
_N_STATES = 4    # thriving, stable, at_risk, in_crisis
_GAMMA = 16.0    # precision (inverse temperature) for policy softmax
_EPS = 1e-12     # numerical floor


# ─── AIF math helpers ─────────────────────────────────────────────────────────

def _obs_index(floor_ok: bool, reward_spirit: float, reward_eta: float) -> int:
    """Map (floor_ok, spirit, eta) → flat observation index 0..49."""
    f = 1 if floor_ok else 0
    s = min(4, int(reward_spirit * 4.999)) if reward_spirit is not None else 0
    e = min(4, int(reward_eta   * 4.999)) if reward_eta   is not None else 0
    return f * 25 + s * 5 + e


def _build_C() -> list[float]:
    """Build prior-preference vector C (log P̃(o)) per ADR-2604291800."""
    C = [0.0] * _N_OBS
    for f in range(2):
        for s in range(5):
            for e in range(5):
                idx = f * 25 + s * 5 + e
                if f == 0:
                    C[idx] = -100.0
                else:
                    C[idx] = s * 0.5 + e * 0.3
    return C


def _softmax(xs: list[float]) -> list[float]:
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    s = sum(exps) + _EPS
    return [v / s for v in exps]


def _log_safe(x: float) -> float:
    return math.log(max(x, _EPS))


def _entropy(p: list[float]) -> float:
    return -sum(v * _log_safe(v) for v in p)


def _kl_divergence(q: list[float], p: list[float]) -> float:
    return sum(q[i] * (_log_safe(q[i]) - _log_safe(p[i])) for i in range(len(q)))


def _belief_update(
    A: list[list[float]],  # (n_obs, n_states)
    D: list[float],        # (n_states,)
    obs_idx: int,
) -> tuple[list[float], float]:
    """Return (q_s, free_energy)."""
    log_post = [_log_safe(A[obs_idx][s]) + _log_safe(D[s]) for s in range(_N_STATES)]
    q = _softmax(log_post)
    # F = KL[q||D] - E_q[log A[o,s]]
    kl = _kl_divergence(q, D)
    expected_log_lik = sum(q[s] * _log_safe(A[obs_idx][s]) for s in range(_N_STATES))
    free_energy = kl - expected_log_lik
    return q, free_energy


def _compute_efe(
    A: list[list[float]],  # (n_obs, n_states)
    B_a: list[list[float]],  # (n_states, n_states) — B[:,:,a_idx]
    C: list[float],          # (n_obs,)
    q: list[float],          # (n_states,)
) -> tuple[float, float, float]:
    """Return (efe_total, pragmatic, epistemic) for one action."""
    # Predictive state distribution: q̃[s'] = Σ_s B_a[s',s] * q[s]
    q_tilde = [
        sum(B_a[sp][s] * q[s] for s in range(_N_STATES))
        for sp in range(_N_STATES)
    ]
    # Predictive observation: p̃[o] = Σ_s A[o,s] * q̃[s]
    p_obs = [
        sum(A[o][s] * q_tilde[s] for s in range(_N_STATES))
        for o in range(_N_OBS)
    ]
    # Pragmatic value = E_q̃[C(o)] = Σ_o p̃[o] * C[o]
    pragmatic = sum(p_obs[o] * C[o] for o in range(_N_OBS))
    # Epistemic (info-gain) = H[p̃(o)] - E_q̃[H[A[:,s]]]
    h_pred = _entropy(p_obs)
    h_per_state = [_entropy([A[o][s] for o in range(_N_OBS)]) for s in range(_N_STATES)]
    expected_h = sum(q_tilde[s] * h_per_state[s] for s in range(_N_STATES))
    epistemic = h_pred - expected_h
    efe_total = -pragmatic - epistemic
    return efe_total, pragmatic, epistemic


def _init_A() -> list[list[float]]:
    """Uniform A matrix (n_obs × n_states)."""
    val = 1.0 / _N_OBS
    return [[val] * _N_STATES for _ in range(_N_OBS)]


def _init_B(n_actions: int) -> list[list[list[float]]]:
    """Identity-biased B matrix (n_states × n_states × n_actions)."""
    B = []
    for _sp in range(_N_STATES):
        row = []
        for s in range(_N_STATES):
            action_vec = []
            for _a in range(n_actions):
                # Weak self-transition prior (0.7 stay, 0.1 spread)
                action_vec.append(0.7 if s == _sp else 0.1 / (_N_STATES - 1))
            row.append(action_vec)
        B.append(row)
    return B


def _normalize_cols(mat: list[list[float]]) -> list[list[float]]:
    """Column-normalize a 2D matrix (in-place copy)."""
    n_rows = len(mat)
    n_cols = len(mat[0])
    result = [[0.0] * n_cols for _ in range(n_rows)]
    for c in range(n_cols):
        col_sum = sum(mat[r][c] for r in range(n_rows)) + _EPS
        for r in range(n_rows):
            result[r][c] = mat[r][c] / col_sum
    return result


def _normalize_B_cols(B: list[list[list[float]]]) -> list[list[list[float]]]:
    """Column-normalize B[sp][s][a] per (s,a) pair."""
    n_states = len(B)
    n_actions = len(B[0][0])
    result = [[[0.0] * n_actions for _ in range(n_states)] for _ in range(n_states)]
    for s in range(n_states):
        for a in range(n_actions):
            col_sum = sum(B[sp][s][a] for sp in range(n_states)) + _EPS
            for sp in range(n_states):
                result[sp][s][a] = B[sp][s][a] / col_sum
    return result


# ─── DB helpers ──────────────────────────────────────────────────────────────

def _now_ts() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def _slugify(nsid: str) -> str:
    return nsid.replace(".", "_").replace("/", "_")


def _model_vid(actor_did: str, action_nsid: str) -> str:
    return f"aif:model:{actor_did}:{_slugify(action_nsid)}"


def _cursor_vid(actor_did: str, action_nsid: str) -> str:
    return f"aif:cursor:{actor_did}:{_slugify(action_nsid)}"


def _get_or_create_model(
    cur: Any,
    actor_did: str,
    action_nsid: str,
    action_index: dict[str, int],
) -> dict:
    vid = _model_vid(actor_did, action_nsid)
    _res = client.q(
        'SELECT A_json, B_json, C_json, D_json, E_json, A_counts_json, B_counts_json, '
        'n_obs, n_states, n_actions, action_index_json, "version" '
        "FROM vertex_rl_aif_model WHERE vertex_id = %s LIMIT 1",
        (vid,),
    )
    row = (_res[0] if _res else None)
    if row:
        return {
            "vertex_id": vid,
            "A": json.loads(row[0]),
            "B": json.loads(row[1]),
            "C": json.loads(row[2]),
            "D": json.loads(row[3]),
            "E": json.loads(row[4]),
            "A_counts": json.loads(row[5]),
            "B_counts": json.loads(row[6]),
            "n_obs": row[7],
            "n_states": row[8],
            "n_actions": row[9],
            "action_index": json.loads(row[10]),
            "version": row[11],
        }
    # Create fresh model
    n_a = max(len(action_index), 1)
    A = _init_A()
    B = _init_B(n_a)
    C = _build_C()
    D = [1.0 / _N_STATES] * _N_STATES
    E = [1.0 / n_a] * n_a
    A_counts = [[1.0] * _N_STATES for _ in range(_N_OBS)]
    B_counts = [[[1.0] * n_a for _ in range(_N_STATES)] for _ in range(_N_STATES)]
    now = _now_ts()
    _res = client.q(
        'INSERT INTO vertex_rl_aif_model '
        '(vertex_id, actor_did, action_nsid, A_json, B_json, C_json, D_json, E_json, '
        ' A_counts_json, B_counts_json, n_obs, n_states, n_actions, action_index_json, '
        ' "version", updated_at, sensitivity_ord, owner_did, org_id, user_id, actor_id) '
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,1,%s,%s,%s,%s)",
        (
            vid, actor_did, action_nsid,
            json.dumps(A), json.dumps(B), json.dumps(C), json.dumps(D), json.dumps(E),
            json.dumps(A_counts), json.dumps(B_counts),
            _N_OBS, _N_STATES, n_a, json.dumps(action_index),
            now, actor_did, actor_did, actor_did, actor_did,
        ),
    )
    return {
        "vertex_id": vid, "A": A, "B": B, "C": C, "D": D, "E": E,
        "A_counts": A_counts, "B_counts": B_counts,
        "n_obs": _N_OBS, "n_states": _N_STATES, "n_actions": n_a,
        "action_index": action_index, "version": 1,
    }


def _get_cursor_ts(cur: Any, actor_did: str, action_nsid: str) -> str:
    vid = _cursor_vid(actor_did, action_nsid)
    _res = client.q(
        "SELECT last_step_ts FROM vertex_rl_aif_obs_cursor WHERE vertex_id = %s LIMIT 1",
        (vid,),
    )
    row = (_res[0] if _res else None)
    return row[0] if row else "1970-01-01 00:00:00"


def _save_cursor(cur: Any, actor_did: str, action_nsid: str, last_ts: str, count: int) -> None:
    vid = _cursor_vid(actor_did, action_nsid)
    now = _now_ts()
    _res = client.q(
        "SELECT 1 FROM vertex_rl_aif_obs_cursor WHERE vertex_id = %s LIMIT 1", (vid,)
    )
    exists = (_res[0] if _res else None)
    if exists:
        _res = client.q(
            "UPDATE vertex_rl_aif_obs_cursor "
            "SET last_step_ts=%s, steps_processed=steps_processed+%s, updated_at=%s "
            "WHERE vertex_id=%s",
            (last_ts, count, now, vid),
        )
    else:
        _res = client.q(
            "INSERT INTO vertex_rl_aif_obs_cursor "
            "(vertex_id, actor_did, action_nsid, last_step_ts, steps_processed, updated_at) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (vid, actor_did, action_nsid, last_ts, count, now),
        )


# ─── task: rl.aif.update_beliefs (R/PT1H) ────────────────────────────────────

def task_rl_aif_update_beliefs(
    *,
    batch_size: int = 50,
    max_actors: int = 20,
) -> dict:
    """Update AIF beliefs for each (actor_did, action_nsid) from new rl_step rows.

    Reads from vertex_rl_step (written by Phase 0 rl_signal.py).
    Writes vertex_rl_aif_belief + vertex_rl_aif_efe per step.
    Uses cursor per (actor_did, action_nsid) for incremental processing.
    """
    total_beliefs = 0
    total_efe = 0

    # 1. Discover active (actor_did, action_nsid) pairs
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT DISTINCT actor_did, action_nsid FROM vertex_rl_step "
            "WHERE actor_did IS NOT NULL ORDER BY actor_did LIMIT %d" % int(max_actors)
        )
        pairs = _res or []

    for actor_did, action_nsid in pairs:
        try:
            _process_actor_beliefs(actor_did, action_nsid, batch_size)
            total_beliefs += 1
        except Exception as exc:
            LOG.error("aif.update_beliefs actor=%s nsid=%s: %s", actor_did, action_nsid, exc)

    return {"ok": True, "actors_processed": len(pairs), "total_beliefs": total_beliefs}


def _process_actor_beliefs(actor_did: str, action_nsid: str, batch_size: int) -> int:
    """Process one (actor_did, action_nsid) pair; return number of steps written."""
    if True:
        client = get_kotoba_client()
        cursor_ts = _get_cursor_ts(cur, actor_did, action_nsid)

        # Build action index for this actor (all seen action_nsids → index)
        _res = client.q(
            "SELECT DISTINCT action_nsid FROM vertex_rl_step "
            "WHERE actor_did = %s LIMIT 64",
            (actor_did,),
        )
        all_nsids = sorted(r[0] for r in (_res or []))
        action_index = {n: i for i, n in enumerate(all_nsids)}

        model = _get_or_create_model(cur, actor_did, action_nsid, action_index)
        A = model["A"]
        B = model["B"]
        C = model["C"]
        D = model["D"]
        n_a = model["n_actions"]

        # Fetch new steps for this (actor_did, action_nsid)
        _res = client.q(
            "SELECT vertex_id, episode_id, created_at, reward_floor, reward_spirit, "
            "reward_eta, reward_scalar "
            "FROM vertex_rl_step "
            f"WHERE actor_did = %s AND action_nsid = %s AND created_at > %s "
            f"ORDER BY created_at ASC LIMIT {int(batch_size)}",
            (actor_did, action_nsid, cursor_ts),
        )
        steps = _res or []
        if not steps:
            return 0

        now = _now_ts()
        last_ts = cursor_ts
        written = 0

        for step_row in steps:
            (step_id, episode_id, created_at, reward_floor,
             reward_spirit, reward_eta, reward_scalar) = step_row

            floor_ok = bool(reward_floor) if reward_floor is not None else True
            spirit = float(reward_spirit) if reward_spirit is not None else 0.5
            eta = float(reward_eta) if reward_eta is not None else 0.5
            obs_idx = _obs_index(floor_ok, spirit, eta)

            # Belief update
            q, free_energy = _belief_update(A, D, obs_idx)

            belief_vid = f"aif:belief:{step_id}"
            _res = client.q(
                "INSERT INTO vertex_rl_aif_belief "
                "(vertex_id, episode_id, actor_did, step_id, belief_json, "
                " free_energy, updated_at, sensitivity_ord, owner_did, org_id, user_id, actor_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s,%s)",
                (
                    belief_vid, episode_id or "", actor_did, step_id,
                    json.dumps(q), free_energy, now,
                    actor_did, actor_did, actor_did, actor_did,
                ),
            )

            # EFE for each action
            all_efe: dict[str, float] = {}
            efe_rows = []
            for nsid, a_idx in action_index.items():
                # Extract B slice for action a_idx: B_a[sp][s] = B[sp][s][a_idx]
                B_a = [[B[sp][s][a_idx] for s in range(_N_STATES)] for sp in range(_N_STATES)]
                efe_total, pragmatic, epistemic = _compute_efe(A, B_a, C, q)
                # Policy probability (softmax over -gamma*G)
                all_efe[nsid] = efe_total
                efe_rows.append((nsid, a_idx, efe_total, pragmatic, epistemic))

            # Compute policy probs from all_efe
            g_vals = [r[2] for r in efe_rows]
            policy_probs = _softmax([-_GAMMA * g for g in g_vals])

            for (nsid, a_idx, efe_total, pragmatic, epistemic), prob in zip(efe_rows, policy_probs):
                efe_vid = f"aif:efe:{step_id}:{_slugify(nsid)}"
                _res = client.q(
                    "INSERT INTO vertex_rl_aif_efe "
                    "(vertex_id, episode_id, actor_did, step_id, action_nsid, "
                    " efe_total, pragmatic_value, epistemic_value, policy_prob, "
                    " all_efe_json, created_at, sensitivity_ord, "
                    " owner_did, org_id, user_id, actor_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s,%s)",
                    (
                        efe_vid, episode_id or "", actor_did, step_id, nsid,
                        efe_total, pragmatic, epistemic, prob,
                        json.dumps(all_efe), now,
                        actor_did, actor_did, actor_did, actor_did,
                    ),
                )

            last_ts = str(created_at)
            written += 1

        _save_cursor(cur, actor_did, action_nsid, last_ts, written)
        return written


# ─── task: rl.aif.learn_model (R/P1D) ────────────────────────────────────────

def task_rl_aif_learn_model(
    *,
    min_steps: int = 20,
    max_actors: int = 20,
) -> dict:
    """Online Dirichlet update of A_counts, B_counts from accumulated rl_step rows.

    Re-normalises A and B matrices after count update.
    Only runs for (actor_did, action_nsid) pairs with >= min_steps steps.
    """
    updated = 0

    if True:

        client = get_kotoba_client()
        _res = client.q(
            "SELECT DISTINCT actor_did, action_nsid FROM vertex_rl_step "
            "WHERE actor_did IS NOT NULL ORDER BY actor_did LIMIT %d" % int(max_actors)
        )
        pairs = _res or []

    for actor_did, action_nsid in pairs:
        try:
            ok = _learn_model_for_pair(actor_did, action_nsid, min_steps)
            if ok:
                updated += 1
        except Exception as exc:
            LOG.error("aif.learn_model actor=%s nsid=%s: %s", actor_did, action_nsid, exc)

    return {"ok": True, "models_updated": updated}


def _learn_model_for_pair(actor_did: str, action_nsid: str, min_steps: int) -> bool:
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT COUNT(*) FROM vertex_rl_step WHERE actor_did=%s AND action_nsid=%s",
            (actor_did, action_nsid),
        )
        row = (_res[0] if _res else None)
        count = int(row[0]) if row else 0
        if count < min_steps:
            return False

        vid = _model_vid(actor_did, action_nsid)
        _res = client.q(
            "SELECT A_counts_json, B_counts_json, n_states, n_actions, action_index_json "
            "FROM vertex_rl_aif_model WHERE vertex_id = %s LIMIT 1",
            (vid,),
        )
        mrow = (_res[0] if _res else None)
        if not mrow:
            return False

        A_counts = json.loads(mrow[0])
        B_counts = json.loads(mrow[1])
        n_states = int(mrow[2])
        n_actions = int(mrow[3])
        action_index: dict[str, int] = json.loads(mrow[4])

        # Fetch all steps for this (actor, action) to rebuild A counts (idempotent).
        _res = client.q(
            "SELECT vertex_id, reward_floor, reward_spirit, reward_eta "
            "FROM vertex_rl_step WHERE actor_did=%s AND action_nsid=%s "
            "ORDER BY created_at ASC",
            (actor_did, action_nsid),
        )
        steps = _res or []

        # Phase 3: fetch causal steps for this actor — steps attributed to a
        # specific dispatch — to learn B transitions from real action→outcome pairs.
        # Maps step_vid → dispatched_action_nsid.
        _res = client.q(
            "SELECT s.vertex_id, d.action_nsid "
            "FROM vertex_rl_step s "
            "JOIN vertex_rl_aif_dispatch_log d "
            "  ON s.triggered_by_dispatch = d.vertex_id "
            "WHERE s.actor_did = %s AND d.action_nsid IS NOT NULL",
            (actor_did,),
        )
        causal_dispatch_nsid: dict[str, str] = {
            r[0]: r[1] for r in (_res or [])
        }
        has_causal = bool(causal_dispatch_nsid)

        # Reset to add-one prior
        A_counts = [[1.0] * n_states for _ in range(_N_OBS)]
        B_counts = [[[1.0] * n_actions for _ in range(n_states)] for _ in range(n_states)]

        prev_state_idx: int | None = None
        prev_action_idx: int | None = None
        a_idx = action_index.get(action_nsid, 0)

        for step_row in steps:
            _step_id, reward_floor, reward_spirit, reward_eta = step_row
            floor_ok = bool(reward_floor) if reward_floor is not None else True
            spirit = float(reward_spirit) if reward_spirit is not None else 0.5
            eta = float(reward_eta) if reward_eta is not None else 0.5
            obs_idx = _obs_index(floor_ok, spirit, eta)

            # Approximate MAP state from spirit score
            spirit_bin = min(3, int(spirit * 3.999))
            # {0.75-1: thriving, 0.5-0.75: stable, 0.25-0.5: at_risk, <0.25: in_crisis}
            s_idx = 3 - spirit_bin  # invert (high spirit → low index = thriving)
            s_idx = max(0, min(3, s_idx))

            # A counts: every step updates the likelihood matrix.
            A_counts[obs_idx][s_idx] += 1.0

            # B counts: use the action that caused this transition.
            # Phase 3 (causal): if this step was attributed to a dispatch, use
            # the dispatched NSID for the action index — real causal signal.
            # Phase 2 fallback: if no causal data yet, use correlational a_idx.
            dispatched_nsid = causal_dispatch_nsid.get(_step_id)
            if dispatched_nsid is not None:
                b_action_idx = action_index.get(dispatched_nsid, a_idx)
            elif not has_causal:
                b_action_idx = a_idx  # correlational fallback until causal data arrives
            else:
                b_action_idx = None  # causal data exists; skip non-causal steps for B

            if prev_state_idx is not None and b_action_idx is not None:
                B_counts[s_idx][prev_state_idx][b_action_idx] += 1.0

            prev_state_idx = s_idx
            prev_action_idx = b_action_idx if b_action_idx is not None else a_idx

        # Recompute A, B from updated counts
        A = _normalize_cols(A_counts)
        B = _normalize_B_cols(B_counts)

        now = _now_ts()
        _res = client.q('SELECT "version" FROM vertex_rl_aif_model WHERE vertex_id=%s', (vid,))
        _vrow = (_res[0] if _res else None)
        new_version = (int(_vrow[0]) + 1) if _vrow else 2
        _res = client.q(
            'UPDATE vertex_rl_aif_model SET '
            'A_json=%s, B_json=%s, A_counts_json=%s, B_counts_json=%s, '
            '"version"=%s, updated_at=%s '
            "WHERE vertex_id=%s",
            (
                json.dumps(A), json.dumps(B),
                json.dumps(A_counts), json.dumps(B_counts),
                new_version, now, vid,
            ),
        )
        return True


# ─── task: rl.aif.attribute_outcomes (R/PT1H) ─────────────────────────────────

def _add_hours(ts: str, hours: float) -> str:
    """Add hours to a timestamp string (ISO or 'YYYY-MM-DD HH:MM:SS')."""
    import datetime as _dti
    try:
        dt = _dti.datetime.fromisoformat(ts.replace(" ", "T"))
    except ValueError:
        dt = _dti.datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")
    dt = dt + _dti.timedelta(hours=hours)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def task_rl_aif_attribute_outcomes(
    *,
    batch_size: int = 50,
    window_hours: float = 2.0,
) -> dict:
    """Link dispatched BPMN actions to subsequent rl_step observations.

    For each vertex_rl_aif_dispatch_log row where dispatch_ok=True and
    outcome_step_id IS NULL, find the earliest vertex_rl_step for the same
    actor_did within [dispatched_at, dispatched_at + window_hours] where
    triggered_by_dispatch IS NULL. Update both tables bidirectionally.
    """
    linked = 0
    skipped = 0

    if True:

        client = get_kotoba_client()
        _res = client.q(
            "SELECT vertex_id, actor_did, dispatched_at "
            "FROM vertex_rl_aif_dispatch_log "
            "WHERE dispatch_ok = TRUE AND outcome_step_id IS NULL "
            "ORDER BY dispatched_at ASC "
            "LIMIT %d" % int(batch_size)
        )
        dispatches = _res or []

    for dispatch_vid, actor_did, dispatched_at in dispatches:
        try:
            if True:
                client = get_kotoba_client()
                window_end = _add_hours(str(dispatched_at), window_hours)
                _res = client.q(
                    "SELECT vertex_id FROM vertex_rl_step "
                    "WHERE actor_did = %s "
                    "  AND triggered_by_dispatch IS NULL "
                    "  AND created_at > %s "
                    "  AND created_at < %s "
                    "ORDER BY created_at ASC LIMIT 1",
                    (actor_did, str(dispatched_at), window_end),
                )
                row = (_res[0] if _res else None)
                if not row:
                    skipped += 1
                    continue
                step_vid = row[0]

                _res = client.q(
                    "UPDATE vertex_rl_aif_dispatch_log "
                    "SET outcome_step_id = %s "
                    "WHERE vertex_id = %s AND outcome_step_id IS NULL",
                    (step_vid, dispatch_vid),
                )
                _res = client.q(
                    "UPDATE vertex_rl_step "
                    "SET triggered_by_dispatch = %s "
                    "WHERE vertex_id = %s AND triggered_by_dispatch IS NULL",
                    (dispatch_vid, step_vid),
                )
                linked += 1
                LOG.info(
                    "aif.attribute_outcomes dispatch=%s -> step=%s actor=%s",
                    dispatch_vid, step_vid, actor_did,
                )
        except Exception as exc:  # noqa: BLE001
            LOG.error("aif.attribute_outcomes dispatch=%s: %s", dispatch_vid, exc)

    return {"ok": True, "linked": linked, "skipped": skipped}


# ─── registration ─────────────────────────────────────────────────────────────

def register(worker: Any, *, timeout_ms: int = 300_000) -> None:
    def _update_beliefs(
        batch_size: int = 50,
        max_actors: int = 20,
    ) -> dict:
        return task_rl_aif_update_beliefs(
            batch_size=batch_size,
            max_actors=max_actors,
        )

    def _learn_model(
        min_steps: int = 20,
        max_actors: int = 20,
    ) -> dict:
        return task_rl_aif_learn_model(
            min_steps=min_steps,
            max_actors=max_actors,
        )

    worker.task(
        task_type="rl.aif.update_beliefs",
        single_value=False,
        timeout_ms=max(timeout_ms, 300_000),
    )(_update_beliefs)

    worker.task(
        task_type="rl.aif.learn_model",
        single_value=False,
        timeout_ms=max(timeout_ms, 300_000),
    )(_learn_model)

    def _attribute_outcomes(
        batch_size: int = 50,
        window_hours: float = 2.0,
    ) -> dict:
        return task_rl_aif_attribute_outcomes(
            batch_size=batch_size,
            window_hours=window_hours,
        )

    worker.task(
        task_type="rl.aif.attribute_outcomes",
        single_value=False,
        timeout_ms=max(timeout_ms, 300_000),
    )(_attribute_outcomes)
