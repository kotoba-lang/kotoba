"""Well-Becoming γ Restoring Force primitive — E (homeostasis term).

ADR-0098 Repo-as-Attractor:
  SBGE の γ-項: restoring_delta_i = -γ * (q_i - q_i^0)

  q_i^0 = baseline score (first observed score per agent, write-once).
  Each tick records deviation and restoring_delta to vertex_belief_restoring.
  mv_belief_restoring_summary tracks deviation_status for D-feed gate.

Pyzeebe task type: wellbecoming.restoring.capture
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client
from kotodama.primitives.pydantic_job import ZeebeJobInput
from kotodama.langserver_compat import LangServerJob as Job, LangServerWorker

LOG = logging.getLogger("wellbecoming.restoring")

# γ: 復元力の学習率。小さいほど保守的。
_GAMMA_LR: float = float(os.environ.get("WB_GAMMA_LR", "0.05"))

# 信念状態が少ないエージェントは除外
_MIN_SCORED_EVENTS: int = int(os.environ.get("WB_MIN_SCORED_EVENTS", "3"))


class _RestoringInput(ZeebeJobInput):
    gamma_lr: float = _GAMMA_LR
    min_scored_events: int = _MIN_scored_events


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _tick_ms() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)


def task_belief_restoring_capture(
    gamma_lr: float = _GAMMA_LR,
    min_scored_events: int = _MIN_SCORED_EVENTS,
) -> dict[str, Any]:
    """γ 復元力を計算して vertex_belief_restoring に記録する。

    restoring_delta_i = -γ * (q_i - q_i^0)

    q_i^0 = vertex_belief_baseline の q0 (初回観測スコア、write-once)。
    baseline が未存在のエージェントは今回のスコアで初期化する。

    Returns:
        agents_processed: 信念状態が既知のエージェント数
        rows_written:     upsert した行数
        max_abs_deviation: 最大 |deviation| (収束指標)
        mean_abs_deviation: 平均 |deviation|
        n_new_baselines: 今回新規に baseline を登録したエージェント数
    """
    # R0: Complex query using q() for multi-predicate WHERE and in-Python ORDER BY.
    # Assumes Datalog attributes are snake_case.
    query_edn = f"""
    [:find ?agent_did ?mean_score_total
     :where
     [?e :mv-attractor-stability-by-agent/agent_did ?agent_did]
     [?e :mv-attractor-stability-by-agent/mean_score_total ?mean_score_total]
     [?e :mv-attractor-stability-by-agent/scored_events ?scored_events]
     [(>= ?scored_events {int(min_scored_events)})]
    ]
    """
    raw_agents = get_kotoba_client().q(query_edn=query_edn)
    # Convert to list of dicts for consistency and sort by agent_did
    agents = sorted(
        [{"agent_did": r[0], "mean_score_total": r[1]} for r in raw_agents],
        key=lambda x: x["agent_did"],
    )

    if not agents:
        LOG.info("restoring_capture: no agents with sufficient scored events")
        return {
            "ok": True,
            "agents_processed": 0,
            "rows_written": 0,
            "max_abs_deviation": 0.0,
            "mean_abs_deviation": 0.0,
            "n_new_baselines": 0,
            "gamma_lr": gamma_lr,
        }

    agent_dids = [row[0] for row in agents]
    agent_map = {row[0]: float(row[1]) for row in agents}

    # 既存 baseline を一括取得
    # R0: Use q() for IN clause.
    # Assumes Datalog attributes are snake_case.
    query_edn = """
    [:find ?agent_did ?q0
     :in $ [?agent_did ...]
     :where
     [?e :vertex-belief-baseline/agent_did ?agent_did]
     [?e :vertex-belief-baseline/q0 ?q0]]
    """
    raw_baseline_rows = get_kotoba_client().q(
        query_edn=query_edn,
        args=[agent_dids],
    )
    baseline_rows = [{"agent_did": r[0], "q0": r[1]} for r in raw_baseline_rows]

    baseline_map = {row[0]: float(row[1]) for row in baseline_rows}

    tick_ms = _tick_ms()
    now_iso = _now_iso()

    # baseline 未存在のエージェントに初回スコアで INSERT
    new_baselines: list[tuple] = []
    for agent_did in agent_dids:
        if agent_did not in baseline_map:
            q0 = agent_map[agent_did]
            vertex_id = f"wb:baseline:{agent_did}"
            new_baselines.append((vertex_id, agent_did, q0, now_iso, now_iso))
            baseline_map[agent_did] = q0

    if new_baselines:
        kotoba_client = get_kotoba_client()
        for row_tuple in new_baselines:
            row_dict = {
                "vertex_id": row_tuple[0],
                "agent_did": row_tuple[1],
                "q0": row_tuple[2],
                "captured_at": row_tuple[3],
                "updated_at": row_tuple[4],
                "sensitivity_ord": 1,
                "org_id": "",
                "user_id": "",
                "actor_id": "sys.bpmn.wellbecoming",
            }
            kotoba_client.insert_row("vertex_belief_baseline", row_dict)

    # 各エージェントの restoring_delta を計算
    rows: list[tuple] = []
    for agent_did in agent_dids:
        q_i = agent_map[agent_did]
        q0 = baseline_map[agent_did]
        deviation = q_i - q0
        restoring_delta = -gamma_lr * deviation
        vertex_id = f"wb:restoring:{agent_did}:{tick_ms}"
        rows.append((
            vertex_id, agent_did,
            q_i, q0, deviation, restoring_delta, gamma_lr,
            now_iso, now_iso,
        ))

    if not rows:
        return {
            "ok": True,
            "agents_processed": len(agents),
            "rows_written": 0,
            "max_abs_deviation": 0.0,
            "mean_abs_deviation": 0.0,
            "n_new_baselines": len(new_baselines),
            "gamma_lr": gamma_lr,
        }

    # vertex_belief_restoring に upsert
    kotoba_client = get_kotoba_client()
    for row_tuple in rows:
        row_dict = {
            "vertex_id": row_tuple[0],
            "agent_did": row_tuple[1],
            "q_current": row_tuple[2],
            "q0": row_tuple[3],
            "deviation": row_tuple[4],
            "restoring_delta": row_tuple[5],
            "gamma_lr": row_tuple[6],
            "tick_at": row_tuple[7],
            "updated_at": row_tuple[8],
            "sensitivity_ord": 1,
            "org_id": "",
            "user_id": "",
            "actor_id": "sys.bpmn.wellbecoming",
        }
        kotoba_client.insert_row("vertex_belief_restoring", row_dict)

    abs_devs = [abs(r[4]) for r in rows]
    max_abs = max(abs_devs) if abs_devs else 0.0
    mean_abs = sum(abs_devs) / len(abs_devs) if abs_devs else 0.0

    LOG.info(
        "restoring_capture: agents=%d rows=%d new_baselines=%d "
        "max_abs_dev=%.4f mean_abs_dev=%.4f gamma=%.3f",
        len(agents),
        len(rows),
        len(new_baselines),
        max_abs,
        mean_abs,
        gamma_lr,
    )

    return {
        "ok": True,
        "agents_processed": len(agents),
        "rows_written": len(rows),
        "max_abs_deviation": max_abs,
        "mean_abs_deviation": mean_abs,
        "n_new_baselines": len(new_baselines),
        "gamma_lr": gamma_lr,
        "tick_ms": tick_ms,
    }


def register(worker: LangServerWorker, timeout_ms: int = 60_000) -> None:
    """Zeebe worker にタスクを登録する。"""

    @worker.task(
        task_type="wellbecoming.restoring.capture",
        timeout_ms=timeout_ms,
    )
    async def _capture(job: Job) -> dict[str, Any]:
        inp = _RestoringInput.from_job(job)
        return task_belief_restoring_capture(
            gamma_lr=inp.gamma_lr,
            min_scored_events=inp.min_scored_events,
        )
