"""Well-Becoming Φ Influence Propagation primitive — D-obs (observation-only).

ADR-0098 Repo-as-Attractor:
  SBGE の λ-項: influence_delta_i = λ * Σ_j W_ij * (q_j - q_i)

  D-obs: influence_delta を記録するのみ。q_i 自体は更新しない（ループ非閉合）。
  D-feed（閉ループ）は mv_belief_convergence で収束を確認後に実装する。

  Φ(q_j, q_i) = q_j - q_i  (最単純な線形影響関数)
  W_ij は edge_trust_weight から取得（Bounded Confidence 済）。
  q_i は mv_attractor_stability_by_agent の mean_score_total。

Pyzeebe task type: wellbecoming.influence.propagate
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.primitives.pydantic_job import ZeebeJobInput
from kotodama.langserver_compat import LangServerJob as Job, LangServerWorker

LOG = logging.getLogger("wellbecoming.influence")

# λ: 影響の学習率。小さいほど保守的。
_LAMBDA_LR: float = float(os.environ.get("WB_LAMBDA_LR", "0.1"))

# 信念状態が少ないエージェントは除外
_MIN_SCORED_EVENTS: int = int(os.environ.get("WB_MIN_SCORED_EVENTS", "3"))


class _InfluenceInput(ZeebeJobInput):
    lambda_lr: float = _LAMBDA_LR
    min_scored_events: int = _MIN_SCORED_EVENTS


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _tick_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def task_belief_influence_propagate(
    lambda_lr: float = _LAMBDA_LR,
    min_scored_events: int = _MIN_SCORED_EVENTS,
) -> dict[str, Any]:
    """Φ 影響伝播を計算して vertex_belief_influence に記録する（D-obs）。

    influence_delta_i = λ * Σ_j W_ij * (q_j - q_i)

    W_ij = 0 → blocked (Bounded Confidence 外) → スキップ。

    Returns:
        agents_processed: 信念状態が既知のエージェント数
        rows_written:     upsert した行数
        max_abs_influence: 最大 |influence_delta| (収束指標)
        mean_abs_influence: 平均 |influence_delta|
    """
    client = get_kotoba_client()
    query_edn = f"""
        [:find ?agent_did ?mean_score_total
         :where
         [?e :mv_attractor_stability_by_agent/agent_did ?agent_did]
         [?e :mv_attractor_stability_by_agent/mean_score_total ?mean_score_total]
         [?e :mv_attractor_stability_by_agent/scored_events ?scored_events]
         [(>= ?scored_events {int(min_scored_events)})]
         [(not= ?mean_score_total nil)]
        ]
    """
    agents_data = client.q(query_edn)
    agents = []
    for row in agents_data:
        agents.append([row[0], row[1]])

    # R0: Replicating ORDER BY agent_did in Python
    agents.sort(key=lambda x: x[0])

    if not agents:
        LOG.info("influence_propagate: no agents with sufficient scored events")
        return {
            "ok": True,
            "agents_processed": 0,
            "rows_written": 0,
            "max_abs_influence": 0.0,
            "mean_abs_influence": 0.0,
            "lambda_lr": lambda_lr,
        }

    agent_map = {row[0]: float(row[1]) for row in agents}
    agent_dids = list(agent_map.keys())

    # edge_trust_weight から全 W_ij を取得（blocked=false のみ）
    client = get_kotoba_client()
    query_edn_trust = f"""
        [:find ?src_did ?dst_did ?weight
         :where
         [?e :edge_trust_weight/src_did ?src_did]
         [?e :edge_trust_weight/dst_did ?dst_did]
         [?e :edge_trust_weight/weight ?weight]
         [?e :edge_trust_weight/blocked false]
         [(> ?weight 0.0)]
         [(contains? #{{ { " ".join('"{}"'.format(d) for d in agent_dids) } }} ?src_did)]
        ]
    """
    trust_rows_data = client.q(query_edn_trust)
    trust_rows = []
    for row in trust_rows_data:
        trust_rows.append([row[0], row[1], row[2]])

    if not trust_rows:
        LOG.info("influence_propagate: no non-blocked trust weights yet (W_ij = 0 for all pairs)")
        return {
            "ok": True,
            "agents_processed": len(agents),
            "rows_written": 0,
            "max_abs_influence": 0.0,
            "mean_abs_influence": 0.0,
            "lambda_lr": lambda_lr,
        }

    # W_ij を dict に変換: w_map[(i,j)] = weight
    w_map: dict[tuple[str, str], float] = {
        (row[0], row[1]): float(row[2]) for row in trust_rows
    }

    tick_ms = _tick_ms()
    now_iso = _now_iso()

    # 各エージェント i の influence_delta を計算
    rows: list[tuple] = []
    for i_did in agent_dids:
        q_i = agent_map[i_did]
        delta = 0.0
        n_influencing = 0
        for j_did in agent_dids:
            if i_did == j_did:
                continue
            w_ij = w_map.get((i_did, j_did), 0.0)
            if w_ij <= 0.0:
                continue
            q_j = agent_map.get(j_did)
            if q_j is None:
                continue
            delta += w_ij * (q_j - q_i)
            n_influencing += 1
        delta *= lambda_lr
        vertex_id = f"{i_did}:{tick_ms}"
        rows.append((vertex_id, i_did, delta, n_influencing, lambda_lr, now_iso, now_iso))

    if not rows:
        return {
            "ok": True,
            "agents_processed": len(agents),
            "rows_written": 0,
            "max_abs_influence": 0.0,
            "mean_abs_influence": 0.0,
            "lambda_lr": lambda_lr,
        }

    client = get_kotoba_client()
    for row_tuple in rows:
        row_dict = {
            "vertex_id": row_tuple[0],
            "agent_did": row_tuple[1],
            "influence_delta": row_tuple[2],
            "n_influencing": row_tuple[3],
            "lambda_lr": row_tuple[4],
            "tick_at": row_tuple[5],
            "updated_at": row_tuple[6],
        }
        client.insert_row("vertex_belief_influence", row_dict)

    abs_deltas = [abs(r[2]) for r in rows]
    max_abs = max(abs_deltas) if abs_deltas else 0.0
    mean_abs = sum(abs_deltas) / len(abs_deltas) if abs_deltas else 0.0

    LOG.info(
        "influence_propagate: agents=%d rows=%d max_abs=%.4f mean_abs=%.4f lambda=%.3f",
        len(agents),
        len(rows),
        max_abs,
        mean_abs,
        lambda_lr,
    )

    return {
        "ok": True,
        "agents_processed": len(agents),
        "rows_written": len(rows),
        "max_abs_influence": max_abs,
        "mean_abs_influence": mean_abs,
        "lambda_lr": lambda_lr,
        "tick_ms": tick_ms,
    }


def register(worker: LangServerWorker, timeout_ms: int = 60_000) -> None:
    """Zeebe worker にタスクを登録する。"""

    @worker.task(
        task_type="wellbecoming.influence.propagate",
        timeout_ms=timeout_ms,
    )
    async def _propagate(job: Job) -> dict[str, Any]:
        inp = _InfluenceInput.from_job(job)
        return task_belief_influence_propagate(
            lambda_lr=inp.lambda_lr,
            min_scored_events=inp.min_scored_events,
        )
