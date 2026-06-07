"""Well-Becoming ξ Stochastic Noise Injection — F (OU noise term).

ADR-0098 Repo-as-Attractor:
  SBGE の ξ-項: ξ_i(t+dt) = ξ_i(t)*exp(-θ*dt) + σ*sqrt(1-exp(-2θ*dt))*N(0,1)

  Ornstein-Uhlenbeck process — colored noise preventing attractor trapping.
  Each tick updates the current OU state per agent (delete+insert, one row).
  mv_belief_noise_summary tracks mean/max amplitude for monitoring.

Pyzeebe task type: wellbecoming.noise.inject
"""

from __future__ import annotations

import datetime as _dt
import logging
import math
import os
import random
from typing import Any
from datetime import datetime, timezone # Added for kotoba client

from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.primitives.pydantic_job import ZeebeJobInput
from kotodama.langserver_compat import LangServerJob as Job, LangServerWorker

LOG = logging.getLogger("wellbecoming.noise")

# OU process default parameters
_SIGMA: float = float(os.environ.get("WB_NOISE_SIGMA", "0.01"))
_OU_THETA: float = float(os.environ.get("WB_NOISE_OU_THETA", "0.1"))
_DT_SEC: float = float(os.environ.get("WB_NOISE_DT_SEC", "3600.0"))  # 1h tick
_MIN_SCORED_EVENTS: int = int(os.environ.get("WB_MIN_SCORED_EVENTS", "3"))


class _NoiseInput(ZeebeJobInput):
    sigma: float = _SIGMA
    ou_theta: float = _OU_THETA
    dt_sec: float = _DT_SEC
    min_scored_events: int = _MIN_SCORED_EVENTS


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _tick_ms() -> int:
    return int(_dt.datetime.now(tz=_dt.UTC).timestamp() * 1000)


def task_belief_noise_inject(
    sigma: float = _SIGMA,
    ou_theta: float = _OU_THETA,
    dt_sec: float = _DT_SEC,
    min_scored_events: int = _MIN_SCORED_EVENTS,
) -> dict[str, Any]:
    """OU ノイズプロセスを更新して vertex_belief_noise に記録する。

    ξ_i(t+dt) = ξ_i(t)*exp(-θ*dt) + σ*sqrt(1-exp(-2θ*dt))*N(0,1)

    各エージェントの現在 OU 状態を delete+insert で更新 (1 エージェント 1 行)。
    安定した vertex_id = 'wb:noise:{agent_did}' を使用 (時刻を含まない)。

    Returns:
        agents_processed: 信念状態が既知のエージェント数
        rows_written:     更新した行数
        mean_abs_xi:      平均 |ξ| (ノイズ振幅の監視指標)
        max_abs_xi:       最大 |ξ|
    """
    client = get_kotoba_client()
    # R0: Multi-predicate SELECT with ORDER BY, using q() for Datomic.
    # Datomic query for mv_attractor_stability_by_agent where scored_events >= min_scored_events and mean_score_total is not nil.
    query_agents = """
    [:find ?agent_did
     :in $ ?min_scored_events_val
     :where
       [?e :mv_attractor_stability_by_agent/agent_did ?agent_did]
       [?e :mv_attractor_stability_by_agent/scored_events ?scored_events]
       [(>= ?scored_events ?min_scored_events_val)]
       [?e :mv_attractor_stability_by_agent/mean_score_total ?mean_score_total]
       [(not= ?mean_score_total nil)]]
    """
    results_agents = client.q(query_agents, (int(min_scored_events),))
    agents = sorted([row[0] for row in results_agents]) # Order by agent_did in Python

    if not agents:
        LOG.info("noise_inject: no agents with sufficient scored events")
        return {
            "ok": True,
            "agents_processed": 0,
            "rows_written": 0,
            "mean_abs_xi": 0.0,
            "max_abs_xi": 0.0,
        }

    did_list = ",".join(f"'{d}'" for d in agents)

    # 既存 OU 状態を取得
    # R0: SELECT ... WHERE IN (...), using q() for Datomic
    query_existing = """
    [:find ?agent_did ?xi_value
     :in $ [?agent_did_in ...]
     :where
       [?e :vertex_belief_noise/agent_did ?agent_did]
       [(contains? ?agent_did_in ?agent_did)]
       [?e :vertex_belief_noise/xi_value ?xi_value]]
    """
    results_existing = client.q(query_existing, (agents,))
    existing = {row[0]: float(row[1]) for row in results_existing}

    tick_ms = _tick_ms()
    now_iso = _now_iso()

    # OU 更新係数
    exp_decay = math.exp(-ou_theta * dt_sec)
    noise_std = sigma * math.sqrt(max(0.0, 1.0 - exp_decay ** 2))

    rows: list[dict[str, Any]] = []
    for agent_did in agents:
        xi_prev = existing.get(agent_did, 0.0)
        xi_new = xi_prev * exp_decay + noise_std * random.gauss(0.0, 1.0)
        vertex_id = f"wb:noise:{agent_did}"
        rows.append({
            "vertex_id": vertex_id,
            "agent_did": agent_did,
            "tick_ms": tick_ms,
            "xi_value": xi_new,
            "sigma": sigma,
            "ou_theta": ou_theta,
            "created_at": _dt.datetime.now(tz=_dt.UTC), # Use datetime object
            "sensitivity_ord": 1,
            "org_id": "",
            "user_id": "",
            "actor_id": "sys.bpmn.wellbecoming",
        })

    # Idempotent upsert (kotoba Datom log handles upsert via insert_row)
    client = get_kotoba_client()
    for row_dict in rows:
        client.insert_row("vertex_belief_noise", row_dict)

    abs_xis = [abs(r["xi_value"]) for r in rows]
    mean_abs = sum(abs_xis) / len(abs_xis) if abs_xis else 0.0
    max_abs = max(abs_xis) if abs_xis else 0.0

    LOG.info(
        "noise_inject: agents=%d rows=%d mean_abs_xi=%.5f max_abs_xi=%.5f sigma=%.4f theta=%.3f",
        len(agents),
        len(rows),
        mean_abs,
        max_abs,
        sigma,
        ou_theta,
    )

    return {
        "ok": True,
        "agents_processed": len(agents),
        "rows_written": len(rows),
        "mean_abs_xi": mean_abs,
        "max_abs_xi": max_abs,
        "tick_ms": tick_ms,
    }


def register(worker: LangServerWorker, timeout_ms: int = 60_000) -> None:
    """Zeebe worker にタスクを登録する。"""

    @worker.task(
        task_type="wellbecoming.noise.inject",
        timeout_ms=timeout_ms,
    )
    async def _inject(job: Job) -> dict[str, Any]:
        inp = _NoiseInput.from_job(job)
        return task_belief_noise_inject(
            sigma=inp.sigma,
            ou_theta=inp.ou_theta,
            dt_sec=inp.dt_sec,
            min_scored_events=inp.min_scored_events,
        )
