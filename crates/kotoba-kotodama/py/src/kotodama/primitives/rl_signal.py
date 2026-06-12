"""RL signal collection — Phase 0 trajectory accretion.

ADR-2604291800 Well-Becoming Spirit objective function.

Phase 0: collect vertex_wellbecoming_event rows into vertex_rl_step.
         No training. Signal accretion only.

Pyzeebe task type registered via register():
  rl.collect.trajectories  — R/PT1H cursor scan of wellbecoming events → rl_step

Reward decomposition from wellbecoming_event:
  reward_floor   = NOT floor_violated                    (ADR-2604291800 Invariant 1)
  reward_spirit  = score_spirit                          (0.0–1.0)
  reward_eta     = (separation_delta + 1.0) / 2.0       (Shannon η proxy, mapped 0–1)
  reward_scalar  = score_total                           (composite U_total)
"""

from __future__ import annotations


from datetime import datetime, timezone
import logging
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


def _attribute_dispatch(actor_did: str, step_vid: str, step_ts: str) -> None:
    """Link the most recent unattributed dispatch for actor_did to this step.

    Looks for a successful dispatch within the last _ATTRIBUTION_WINDOW_MIN minutes
    that has not yet been attributed to any step.  When found, writes
    triggered_by_dispatch on the step and outcome_step_id on the dispatch log row.
    Both writes are best-effort; attribution failure never blocks step collection.
    """
    try:
        window_start = (
            datetime.fromisoformat(step_ts.replace(" ", "T"))
            - datetime.timedelta(minutes=_ATTRIBUTION_WINDOW_MIN)
        ).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return

    try:
        kotoba_client = get_kotoba_client()
        # R0: Datalog query to find dispatches for attribution, ordered in Python.
        # Find vertex_id and dispatched_at for dispatches that are:
        # 1. for the given actor_did
        # 2. dispatch_ok is true
        # 3. outcome_step_id is NULL (not yet attributed)
        # 4. dispatched_at is after window_start
        query_edn = f"""
        [:find ?vid ?dispatched_at
         :where
           [?e :vertex_rl_aif_dispatch_log/actor_did "{actor_did}"]
           [?e :vertex_rl_aif_dispatch_log/dispatch_ok true]
           (not [?e :vertex_rl_aif_dispatch_log/outcome_step_id])
           [?e :vertex_rl_aif_dispatch_log/dispatched_at ?dispatched_at]
           [(.compareTo ?dispatched_at "{window_start}") 1]
           [?e :vertex_rl_aif_dispatch_log/vertex_id ?vid]]
        """
        rows = kotoba_client.q(query_edn)
        if not rows:
            return

        # Sort in Python by 'dispatched_at' descending and take the first one (most recent)
        rows.sort(key=lambda x: x[1], reverse=True)
        dispatch_vid = rows[0][0]

        # Update vertex_rl_step: set triggered_by_dispatch
        kotoba_client.insert_row(
            "vertex_rl_step",
            {"vertex_id": step_vid, "triggered_by_dispatch": dispatch_vid},
        )
        # Update vertex_rl_aif_dispatch_log: set outcome_step_id
        kotoba_client.insert_row(
            "vertex_rl_aif_dispatch_log",
            {"vertex_id": dispatch_vid, "outcome_step_id": step_vid},
        )
        LOG.debug("attributed dispatch=%s → step=%s", dispatch_vid, step_vid)
    except Exception as exc:  # noqa: BLE001
        LOG.warning("attribution failed step=%s: %s", step_vid, exc)


def _sep_to_eta(sep_delta: float | None) -> float | None:
    """Map separation_delta [-1.0, 1.0] → reward_eta [0.0, 1.0]."""
    if sep_delta is None:
        return None
    clamped = max(-1.0, min(1.0, float(sep_delta)))
    return round((clamped + 1.0) / 2.0, 4)


def _get_cursor_ts() -> str:
    """Read last processed created_at from vertex_rl_collect_cursor."""
    try:
        kotoba_client = get_kotoba_client()
        row = kotoba_client.select_first_where(
            "vertex_rl_collect_cursor",
            "vertex_id",
            _CURSOR_ID,
            columns=["last_event_ts"]
        )
        if row and row["last_event_ts"]:
            return str(row["last_event_ts"])
    except Exception as e:
        LOG.warning("get_cursor_ts failed: %s", e)
    return "2024-01-01 00:00:00"


def _update_cursor(last_ts: str, batch_count: int, total: int) -> None:
    now = datetime.now(timezone.utc)
    try:
        kotoba_client = get_kotoba_client()
        kotoba_client.insert_row(
            "vertex_rl_collect_cursor",
            {
                "vertex_id": _CURSOR_ID,
                "last_event_ts": last_ts,
                "last_step_count": batch_count,
                "total_collected": total,
                "updated_at": now.isoformat(),
            },
        )
    except Exception as e:
        LOG.warning("update_cursor failed: %s", e)


def task_rl_collect_trajectories(batch_size: int = 200) -> dict[str, Any]:
    """Cursor-based scan of vertex_wellbecoming_event → vertex_rl_step.

    BPMN: rl/rlCollectTrajectories.bpmn → Task_Collect (rl.collect.trajectories, R/PT1H)

    Conventions:
    - rw-psycopg3-no-param-limit: LIMIT is inlined as int literal
    - rw-large-table-no-is-null-scan: cursor-based, not IS NULL scan
    - flush: bool = False: never FLUSH in kotodama
    """
    cursor_ts = _get_cursor_ts()
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    collected = 0
    skipped = 0
    max_ts = cursor_ts

    try:
        kotoba_client = get_kotoba_client()
        # R0: Datalog query for initial SELECT. Sorting and limiting done in Python.
        query_edn = f"""
        [:find ?vid ?case_id ?agent_did ?activity ?score_spirit ?score_total ?sep_delta ?floor_violated ?model ?created_at
         :where
           [?e :vertex_wellbecoming_event/created_at ?created_at]
           [(.compareTo ?created_at "{cursor_ts}") 1]
           [?e :vertex_wellbecoming_event/vertex_id ?vid]
           [?e :vertex_wellbecoming_event/case_id ?case_id]
           [?e :vertex_wellbecoming_event/agent_did ?agent_did]
           [?e :vertex_wellbecoming_event/activity ?activity]
           [?e :vertex_wellbecoming_event/score_spirit ?score_spirit]
           [?e :vertex_wellbecoming_event/score_total ?score_total]
           [?e :vertex_wellbecoming_event/separation_delta ?sep_delta]
           [?e :vertex_wellbecoming_event/floor_violated ?floor_violated]
           [?e :vertex_wellbecoming_event/model ?model]]
        """
        raw_rows = kotoba_client.q(query_edn)

        # Sort by created_at ASC and then limit in Python
        # The created_at will be the 10th element in each inner list (index 9)
        raw_rows.sort(key=lambda x: x[9])
        rows = raw_rows[:batch_size]

        # Map to dicts for easier processing
        column_names = [
            "vertex_id", "case_id", "agent_did", "activity",
            "score_spirit", "score_total", "separation_delta",
            "floor_violated", "model", "created_at"
        ]
        processed_rows = []
        for row_data in rows:
            processed_rows.append(dict(zip(column_names, row_data)))
        rows = processed_rows

    except Exception as e:
        LOG.warning("collect query failed: %s", e)
        return {"collected": 0, "skipped": 0, "cursor_ts": cursor_ts, "error": str(e)}

    for row in rows:
        (event_id, case_id, agent_did, activity,
         score_spirit, score_total, sep_delta,
         floor_violated, model, created_at) = (
            row["vertex_id"], row["case_id"], row["agent_did"], row["activity"],
            row["score_spirit"], row["score_total"], row["separation_delta"],
            row["floor_violated"], row["model"], row["created_at"]
        )

        step_id = f"rl:step:{event_id}"
        reward_floor = not bool(floor_violated)
        reward_eta = _sep_to_eta(sep_delta)
        reward_scalar = float(score_total or 0.0)
        created_str = str(created_at) if created_at else now

        try:
            kotoba_client.insert_row(
                "vertex_rl_step",
                {
                    "vertex_id": step_id,
                    "episode_id": str(case_id or ""),
                    "action_nsid": str(activity or "wellbecoming.agent.loop"),
                    "reward_floor": reward_floor,
                    "reward_spirit": float(score_spirit) if score_spirit is not None else None,
                    "reward_eta": reward_eta,
                    "reward_scalar": reward_scalar,
                    "source": "server",
                    "source_event_id": str(event_id),
                    "actor_did": str(agent_did or ""),
                    "model": str(model or ""),
                    "sensitivity_ord": 1,
                    "owner_did": str(agent_did or ""),
                    "org_id": str(agent_did or ""),
                    "user_id": str(agent_did or ""),
                    "actor_id": "rl.collect",
                    "created_at": created_str,
                },
            )
            collected += 1
            if created_str > max_ts:
                max_ts = created_str
            # Phase 3: attribute a recent dispatch to this step (best-effort).
            if agent_did:
                _attribute_dispatch(str(agent_did), step_id, created_str)
        except Exception as e:
            LOG.warning("insert rl_step failed for %s: %s", event_id, e)
            skipped += 1

    # Update cursor to the latest processed timestamp
    if collected > 0:
        try:
            # Get total count for logging
            prev_row = kotoba_client.select_first_where(
                "vertex_rl_collect_cursor",
                "vertex_id",
                _CURSOR_ID,
                columns=["total_collected"]
            )
            prev_total = int(prev_row["total_collected"] or 0) if prev_row and "total_collected" in prev_row else 0
        except Exception:
            prev_total = 0
        _update_cursor(max_ts, collected, prev_total + collected)

    LOG.info(
        "rl.collect.trajectories: collected=%d skipped=%d cursor_was=%s cursor_now=%s",
        collected, skipped, cursor_ts[:19], max_ts[:19],
    )
    return {
        "collected": collected,
        "skipped": skipped,
        "cursor_ts": max_ts,
        "has_more": len(rows) == batch_size,
    }


def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="rl.collect.trajectories",
        single_value=False,
        timeout_ms=max(timeout_ms, 120_000),
    )(task_rl_collect_trajectories)
