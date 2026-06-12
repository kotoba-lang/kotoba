"""RL preference pair generation — Phase 1 DPO dataset construction.

ADR-2604291800 Well-Becoming Spirit objective function.

Phase 1: cross-actor DPO pair generation from vertex_rl_step.
         Pairs rows with the same action_nsid from different actor_did values
         where reward_scalar differs by >= delta_threshold.

Pyzeebe task type registered via register():
  rl.generate.preferences  — R/P1D BPMN timer, gated by min_steps count

Key constraints observed from data (2026-05-06):
  - Within (action_nsid, actor_did) groups, reward_scalar has zero variance
    at current data volume. Cross-actor pairing is the only viable path.
  - delta_threshold is a task parameter, not hard-coded.
  - Gate uses total step count (all actors) rather than per-actor counts.
"""

from __future__ import annotations

import datetime as _dt
from datetime import datetime, timezone
import logging
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("rl_preferences")

# Remove _now_ts function as datetime.now(timezone.utc).isoformat(timespec='seconds') will be used directly.

def _get_total_step_count() -> int:
    try:
        client = get_kotoba_client()
        count_float = client.aggregate_where("vertex_rl_step", "count", "*", "source", "server")
        return int(count_float)
    except Exception as e:
        LOG.warning("get_total_step_count failed: %s", e)
        return 0


def task_rl_generate_preferences(
    min_steps: int = 50,
    delta_threshold: float = 0.05,
    batch_limit: int = 500,
) -> dict[str, Any]:
    """Cross-actor DPO preference pair generation from vertex_rl_step.

    BPMN: rl/rlGeneratePreferences.bpmn → Task_Generate (rl.generate.preferences, R/P1D)

    Strategy: for each action_nsid, find all (actor_a, actor_b) pairs where
      reward_scalar(actor_a) - reward_scalar(actor_b) >= delta_threshold.
    The higher-reward actor's step is 'chosen', the lower is 'rejected'.

    FEEL gate in BPMN: =totalSteps >= min_steps
    totalSteps is written to process variables by a preceding query step.

    # Conventions:
    # - kotoba-datomic-q-idiom: Datalog query with explicit graph and custom Python sorting.
    # - flush: bool = False: never FLUSH in kotodama
    """
    total_steps = _get_total_step_count()
    if total_steps < int(min_steps):
        LOG.info(
            "rl.generate.preferences: skipped — total_steps=%d < min_steps=%d",
            total_steps, min_steps,
        )
        return {
            "generated": 0,
            "skipped": 0,
            "total_steps": total_steps,
            "gate_passed": False,
        }

    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    generated = 0
    skipped = 0
    threshold = float(delta_threshold)

    # Load all server-sourced steps (bounded: only server rows, no cross-source noise).
    # With current data volume (22–100 rows) a full load is safe.
    # At >10K rows switch to cursor-based per-action_nsid pagination.
    try:
        client = get_kotoba_client()
        # R0: Multi-predicate/ORDER BY/LIMIT not directly supported by select_where shim.
        #    Using raw q() for full SQL compatibility.
        rows_tuples = client.q(
            f"""[:find ?vertex_id ?action_nsid ?actor_did ?reward_scalar
                   ?reward_floor ?reward_spirit ?reward_eta ?sensitivity_ord
                   ?owner_did ?org_id ?user_id ?actor_id
                :where
                  [?e :vertex_rl_step/vertex_id ?vertex_id]
                  [?e :vertex_rl_step/source "server"]
                  [?e :vertex_rl_step/reward_scalar ?reward_scalar]
                  [?e :vertex_rl_step/action_nsid ?action_nsid]
                  [?e :vertex_rl_step/actor_did ?actor_did]
                  (or
                    [?e :vertex_rl_step/reward_floor ?reward_floor]
                    (not [?e :vertex_rl_step/reward_floor _]))
                  (or
                    [?e :vertex_rl_step/reward_spirit ?reward_spirit]
                    (not [?e :vertex_rl_step/reward_spirit _]))
                  (or
                    [?e :vertex_rl_step/reward_eta ?reward_eta]
                    (not [?e :vertex_rl_step/reward_eta _]))
                  (or
                    [?e :vertex_rl_step/sensitivity_ord ?sensitivity_ord]
                    (not [?e :vertex_rl_step/sensitivity_ord _]))
                  (or
                    [?e :vertex_rl_step/owner_did ?owner_did]
                    (not [?e :vertex_rl_step/owner_did _]))
                  (or
                    [?e :vertex_rl_step/org_id ?org_id]
                    (not [?e :vertex_rl_step/org_id _]))
                  (or
                    [?e :vertex_rl_step/user_id ?user_id]
                    (not [?e :vertex_rl_step/user_id _]))
                  (or
                    [?e :vertex_rl_step/actor_id ?actor_id]
                    (not [?e :vertex_rl_step/actor_id _]))
                :limit {int(batch_limit)}
                :order-by desc ?action_nsid desc ?reward_scalar]""",
            graph="kotodama" # Explicitly specify graph for consistency
        )
        # Convert list of lists from q() to list of dicts for consistency with select_where
        # and re-sort in Python as Datalog :order-by might not be exact for multiple keys
        # or handle nulls the same way SQL does.
        rows = [
            {
                "vertex_id": row[0],
                "action_nsid": row[1],
                "actor_did": row[2],
                "reward_scalar": row[3],
                "reward_floor": row[4],
                "reward_spirit": row[5],
                "reward_eta": row[6],
                "sensitivity_ord": row[7],
                "owner_did": row[8],
                "org_id": row[9],
                "user_id": row[10],
                "actor_id": row[11],
            }
            for row in rows_tuples
        ]
        rows.sort(key=lambda x: (x["action_nsid"], -float(x["reward_scalar"] or 0.0)))
    except Exception as e:
        LOG.warning("rl.generate.preferences: query failed: %s", e)
        return {"generated": 0, "skipped": 0, "total_steps": total_steps, "error": str(e)}

    # Group by action_nsid
    from collections import defaultdict
    by_action: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        action_nsid = str(row["action_nsid"] or "")
        by_action[action_nsid].append(row)

    for action_nsid, steps in by_action.items():
        # Generate all cross-actor pairs where reward delta >= threshold.
        # steps is already sorted DESC by reward_scalar (from SQL ORDER BY).
        for i, chosen_row in enumerate(steps):
            for rejected_row in steps[i + 1 :]:
                chosen_scalar = float(chosen_row["reward_scalar"] or 0.0)
                rejected_scalar = float(rejected_row["reward_scalar"] or 0.0)
                reward_delta = chosen_scalar - rejected_scalar

                if reward_delta < threshold:
                    # Since sorted DESC, remaining will also be < threshold
                    break

                chosen_actor = str(chosen_row["actor_did"] or "")
                rejected_actor = str(rejected_row["actor_did"] or "")

                # Skip same-actor pairs (within-actor variance = zero, no signal)
                if chosen_actor == rejected_actor:
                    continue

                chosen_step_id = str(chosen_row["vertex_id"])
                rejected_step_id = str(rejected_row["vertex_id"])

                # Stable pair_id: sorted step IDs so (A,B) == (B,A)
                pair_key = ":".join(sorted([chosen_step_id, rejected_step_id]))
                pair_id = f"rl:pair:{pair_key}"

                try:
                    client = get_kotoba_client()
                    row_dict = {
                        "vertex_id": pair_id,
                        "action_nsid": action_nsid,
                        "chosen_step_id": chosen_step_id,
                        "rejected_step_id": rejected_step_id,
                        "chosen_actor_did": chosen_actor,
                        "rejected_actor_did": rejected_actor,
                        "chosen_reward": chosen_scalar,
                        "rejected_reward": rejected_scalar,
                        "reward_delta": round(reward_delta, 4),
                        "pairing_strategy": "cross_actor_reward_delta",
                        "sensitivity_ord": int(chosen_row["sensitivity_ord"] or 1),
                        "owner_did": str(chosen_row["owner_did"] or ""),
                        "org_id": str(chosen_row["org_id"] or ""),
                        "user_id": str(chosen_row["user_id"] or ""),
                        "actor_id": str(chosen_row["actor_id"] or "rl.generate"),
                        "created_at": datetime.now(timezone.utc).isoformat(timespec='seconds'), # ISO format for timestamp
                    }
                    client.insert_row("vertex_rl_preference_pair", row_dict)
                    generated += 1
                except Exception as e:
                    # Duplicate vertex_id for upsert means already generated; skip silently
                    LOG.debug("insert pair skipped for %s: %s", pair_id, e)
                    skipped += 1

    LOG.info(
        "rl.generate.preferences: generated=%d skipped=%d total_steps=%d",
        generated, skipped, total_steps,
    )
    return {
        "generated": generated,
        "skipped": skipped,
        "total_steps": total_steps,
        "gate_passed": True,
    }


def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="rl.generate.preferences",
        single_value=False,
        timeout_ms=max(timeout_ms, 300_000),
    )(task_rl_generate_preferences)
