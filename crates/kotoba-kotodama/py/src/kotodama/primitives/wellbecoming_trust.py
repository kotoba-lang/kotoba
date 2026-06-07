"""Well-Becoming Trust Weight primitives — W_ij dynamic update + Bounded Confidence.

ADR-0098 Repo-as-Attractor:
  SBGE の W_ij（主体間信頼重み）を mv_attractor_stability_by_agent から計算し
  edge_trust_weight テーブルに upsert する。

  Bounded Confidence (Hegselmann-Krause):
    W_ij = exp(-k * D(q_i, q_j))  if D < bc_epsilon
           0                        if D >= bc_epsilon
    D(q_i, q_j) = |mean_score_total_i - mean_score_total_j|

Pyzeebe task type: wellbecoming.trust.updateWeights
"""

from __future__ import annotations

import datetime as _dt
import logging
import math
import os
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.primitives.pydantic_job import ZeebeJobInput
from kotodama.langserver_compat import LangServerJob as Job, LangServerWorker

LOG = logging.getLogger("wellbecoming.trust")

# Bounded Confidence 閾値 ε（この距離以上 → W_ij = 0）
_BC_EPSILON: float = float(os.environ.get("WB_BC_EPSILON", "0.3"))

# W_ij = exp(-k * distance) の steepness。k が大きいほど距離に敏感
_WEIGHT_K: float = float(os.environ.get("WB_WEIGHT_K", "5.0"))

# scored_events が少ない agent は信念推定が不安定 → 対象外
_MIN_SCORED_EVENTS: int = int(os.environ.get("WB_MIN_SCORED_EVENTS", "3"))


class _TrustWeightInput(ZeebeJobInput):
    bc_epsilon: float = _BC_EPSILON
    weight_k: float = _WEIGHT_K
    min_scored_events: int = _MIN_SCORED_EVENTS


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _compute_weight(distance: float, bc_epsilon: float, k: float) -> tuple[float, bool]:
    """距離から W_ij と blocked フラグを計算する。"""
    if distance >= bc_epsilon:
        return 0.0, True
    return math.exp(-k * distance), False


def task_trust_weight_update(
    bc_epsilon: float = _BC_EPSILON,
    weight_k: float = _WEIGHT_K,
    min_scored_events: int = _MIN_SCORED_EVENTS,
) -> dict[str, Any]:
    """mv_attractor_stability_by_agent から W_ij を計算して edge_trust_weight に upsert する。

    Returns:
        pairs_evaluated: 評価したエージェントペア数
        pairs_blocked:   Bounded Confidence で遮断されたペア数（W_ij = 0）
        pairs_updated:   upsert した行数
        agents_found:    信念状態が既知のエージェント数
    """
    client = get_kotoba_client()
    # R0: Fetch all agents from mv_attractor_stability_by_agent and filter/order in Python
    # due to complex WHERE (range, IS NOT NULL) and ORDER BY clauses not directly
    # supported by select_where.
    all_agents_raw = client.select_where(
        "mv_attractor_stability_by_agent",
        None,  # No specific column for equality filter
        None,  # No specific value for equality filter
        columns=["agent_did", "mean_score_total", "entropy_spread", "attractor_status", "scored_events"],
        limit=2000 # as per instruction for fetching a broader set
    )
    # Apply filtering and ordering in Python
    agents = [
        agent for agent in all_agents_raw
        if agent.get("scored_events", 0) >= min_scored_events and agent.get("mean_score_total") is not None
    ]
    agents.sort(key=lambda x: x["agent_did"])

    if len(agents) < 2:
        LOG.info("trust_weight_update: not enough agents with scored events (%d)", len(agents))
        return {
            "ok": True,
            "agents_found": len(agents),
            "pairs_evaluated": 0,
            "pairs_blocked": 0,
            "pairs_updated": 0,
            "bc_epsilon": bc_epsilon,
        }

    # エージェント情報を dict に変換
    agent_map = {
        row["agent_did"]: {
            "mean_score": row["mean_score_total"],
            "entropy_spread": row["entropy_spread"],
            "attractor_status": row["attractor_status"],
            "scored_events": row["scored_events"],
        }
        for row in agents
    }
    agent_dids = list(agent_map.keys())

    now_iso = _now_iso()
    upserts: list[tuple] = []
    pairs_blocked = 0

    # 全ペア（i, j）の W_ij を計算（自己参照は除外）
    for i_did in agent_dids:
        for j_did in agent_dids:
            if i_did == j_did:
                continue
            score_i = agent_map[i_did]["mean_score"]
            score_j = agent_map[j_did]["mean_score"]
            distance = abs(score_i - score_j)
            weight, blocked = _compute_weight(distance, bc_epsilon, weight_k)
            edge_id = f"{i_did}→{j_did}"
            upserts.append((edge_id, i_did, j_did, weight, distance, bc_epsilon, blocked, now_iso))
            if blocked:
                pairs_blocked += 1

    if not upserts:
        return {
            "ok": True,
            "agents_found": len(agents),
            "pairs_evaluated": 0,
            "pairs_blocked": 0,
            "pairs_updated": 0,
            "bc_epsilon": bc_epsilon,
        }

    client = get_kotoba_client()
    pairs_updated = 0
    # edge_trust_weight に upsert (kotoba Datom log handles upsert logic internally)
    for row_tuple in upserts:
        row_dict = {
            "edge_id": row_tuple[0],
            "src_did": row_tuple[1],
            "dst_did": row_tuple[2],
            "weight": row_tuple[3],
            "distance": row_tuple[4],
            "bc_epsilon": row_tuple[5],
            "blocked": row_tuple[6],
            "updated_at": _dt.datetime.now(tz=_dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z"), # Use Python datetime
        }
        client.insert_row("edge_trust_weight", row_dict)
        pairs_updated += 1

    blocked_pairs = [
        f"{u[1].split(':')[-1]}→{u[2].split(':')[-1]}"
        for u in upserts if u[6]  # blocked=True
    ]

    LOG.info(
        "trust_weight_update: agents=%d pairs=%d blocked=%d epsilon=%.2f",
        len(agents),
        len(upserts),
        pairs_blocked,
        bc_epsilon,
    )

    return {
        "ok": True,
        "agents_found": len(agents),
        "pairs_evaluated": len(upserts),
        "pairs_blocked": pairs_blocked,
        "pairs_updated": pairs_updated,  # Updated to use the counter
        "bc_epsilon": bc_epsilon,
        "weight_k": weight_k,
        "blocked_pairs": blocked_pairs[:10],  # log 用（最大 10 件）
    }


def register(worker: LangServerWorker, timeout_ms: int = 60_000) -> None:
    """Zeebe worker にタスクを登録する。"""

    @worker.task(
        task_type="wellbecoming.trust.updateWeights",
        timeout_ms=timeout_ms,
    )
    async def _update(job: Job) -> dict[str, Any]:
        inp = _TrustWeightInput.from_job(job)
        return task_trust_weight_update(
            bc_epsilon=inp.bc_epsilon,
            weight_k=inp.weight_k,
            min_scored_events=inp.min_scored_events,
        )
