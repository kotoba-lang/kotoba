"""RL Policy Dispatch (Phase 2) — policy-guided BPMN action selection.

Reads π(a) = softmax(−γ·G(a)) from vertex_rl_aif_efe (written by
rl_active_inference.py) and dispatches the sampled action via the
bpmn-dispatcher ClusterIP (x-internal-trust, ADR-2604282300).

ε-greedy exploration:
    With probability ε   → uniform-random action (exploration)
    With probability 1-ε → weighted sample from policy_prob (exploitation)

Pyzeebe task registered via register():
    rl.policy.dispatch — R/PT1H  loop over actors; sample + dispatch + log
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import random
import urllib.error
import urllib.request
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("rl_policy")

_BPMN_DISPATCHER_URL = os.environ.get(
    "BPMN_DISPATCHER_INTERNAL_URL",
    "http://bpmn-dispatcher.mitama-udf.svc.cluster.local:8080",
).rstrip("/")
_BPMN_DISPATCHER_SECRET = os.environ.get("BPMN_DISPATCHER_INTERNAL_SECRET", "").strip()


# ─── helpers ──────────────────────────────────────────────────────────────────

def _weighted_sample(actions: list[str], probs: list[float]) -> str:
    total = sum(probs)
    if total <= 0:
        return random.choice(actions)
    r = random.random() * total
    cumulative = 0.0
    for action, p in zip(actions, probs):
        cumulative += p
        if r <= cumulative:
            return action
    return actions[-1]


def _fetch_latest_efe(actor_did: str) -> list[tuple[str, float, float]]:
    """Return [(action_nsid, policy_prob, efe_total)] for actor's latest step."""
    client = get_kotoba_client()
    row = client.select_first_where(
        "vertex_rl_aif_efe",
        "actor_did",
        actor_did,
        columns=["step_id"],
    )
    if not row:
        return []
    latest_step = row["step_id"]

    rows_data = client.select_where(
        "vertex_rl_aif_efe",
        "actor_did",
        actor_did,
        columns=["action_nsid", "policy_prob", "efe_total", "step_id"],
    )
    # R0: In-Python filter for step_id due to multiple WHERE clauses.
    # select_where only supports single equality predicate.
    filtered_rows = [
        r for r in rows_data if r.get("step_id") == latest_step
    ]
    return [
        (r["action_nsid"], float(r["policy_prob"]), float(r["efe_total"]))
        for r in filtered_rows
    ]


def _sample(actor_did: str, epsilon: float) -> tuple[str | None, float | None, bool]:
    """ε-greedy sample. Returns (action_nsid, efe_total, was_exploration)."""
    rows = _fetch_latest_efe(actor_did)
    if not rows:
        return None, None, False

    actions = [r[0] for r in rows]
    probs   = [r[1] for r in rows]
    efes    = [r[2] for r in rows]

    explore = random.random() < epsilon
    if explore:
        idx = random.randrange(len(actions))
        return actions[idx], efes[idx], True

    sampled = _weighted_sample(actions, probs)
    idx = actions.index(sampled)
    return sampled, efes[idx], False


def _resolve_dispatch_nsid(actor_did: str, action_nsid: str) -> str | None:
    """Return the full XRPC NSID to dispatch for (actor, action).

    If action_nsid is already a full NSID (contains '.'), use it directly.
    Otherwise look up vertex_bpmn_lexicon_binding for a binding whose
    bpmn_process_id contains the action_nsid slug.  Falls back to the
    actor's first available binding, or None if no binding exists.
    """
    if "." in action_nsid and action_nsid.startswith("com.etzhayyim."):
        return action_nsid
    try:
        client = get_kotoba_client()
        slug = action_nsid.replace("_", "").replace("-", "").lower()
        all_bindings = client.select_where(
            "vertex_bpmn_lexicon_binding",
            "actor_did",
            actor_did,
            columns=["nsid", "bpmn_process_id"],
        )

        # R0: In-Python filtering and ordering due to complex SQL WHERE/ORDER BY.
        # The original query's logic (CASE WHEN LIKE) is replicated here.
        def sort_key(binding):
            bpmn_process_id = binding.get("bpmn_process_id", "")
            processed_bpmn_id = bpmn_process_id.replace("_", "").replace("-", "").lower()
            # Check if processed_bpmn_id contains the slug
            like_match = slug in processed_bpmn_id
            return (0 if like_match else 1, binding.get("nsid", ""))

        all_bindings.sort(key=sort_key)

        if all_bindings:
            return all_bindings[0]["nsid"]
        return None
    except Exception as exc:  # noqa: BLE001
        LOG.warning("resolve_nsid actor=%s action=%s: %s", actor_did, action_nsid, exc)
        return None


def _dispatch(action_nsid: str, actor_did: str) -> tuple[bool, str]:
    """POST to bpmn-dispatcher /xrpc/{resolved_nsid}. Returns (ok, error_msg)."""
    resolved = _resolve_dispatch_nsid(actor_did, action_nsid)
    if not resolved:
        return False, f"no binding for actor={actor_did} action={action_nsid}"
    url = f"{_BPMN_DISPATCHER_URL}/xrpc/{resolved}"
    payload = json.dumps({"actorDid": actor_did}).encode()
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept":       "application/json",
    }
    if _BPMN_DISPATCHER_SECRET:
        headers["x-internal-trust"] = _BPMN_DISPATCHER_SECRET
    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            ok = resp.status < 400
            return ok, ""
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.reason}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _log_dispatch(
    actor_did: str,
    action_nsid: str,
    dispatched_at: str,
    free_energy: float | None,
    epsilon: float,
    was_exploration: bool,
    dispatch_ok: bool,
    dispatch_error: str,
) -> None:
    vid = f"aif:dispatch:{actor_did}:{dispatched_at}"
    client = get_kotoba_client()
    row_dict = {
        "vertex_id": vid,
        "actor_did": actor_did,
        "action_nsid": action_nsid,
        "dispatched_at": dispatched_at,
        "free_energy_at_dispatch": free_energy,
        "epsilon": epsilon,
        "was_exploration": was_exploration,
        "dispatch_ok": dispatch_ok,
        "dispatch_error": dispatch_error or "",
        "sensitivity_ord": 1,
        "owner_did": actor_did,
        "org_id": actor_did,
        "user_id": actor_did,
        "actor_id": actor_did,
    }
    client.insert_row("vertex_rl_aif_dispatch_log", row_dict)


# ─── task: rl.policy.dispatch (R/PT1H) ───────────────────────────────────────

def task_rl_policy_dispatch(
    *,
    batch_size: int = 10,
    epsilon: float = 0.2,
) -> dict:
    """Sample AIF policy and dispatch BPMN for each actor with live EFE data.

    Runs ε-greedy: explores with prob ε (uniform), exploits with prob 1-ε
    (weighted sample from policy_prob). Dispatches via bpmn-dispatcher
    ClusterIP and writes vertex_rl_aif_dispatch_log for every attempt.
    """
    client = get_kotoba_client()
    # R0: Fetch records to get distinct actor_did, then filter/sort in Python.
    # select_rows has a default limit, but we'll request more to ensure enough for distinct + batch_size.
    all_efe_records = client.select_rows(
        "vertex_rl_aif_efe",
        columns=["actor_did"],
        limit=max(100, int(batch_size * 2)) # Fetch enough to cover unique actor_dids up to batch_size
    )
    # Extract actor_dids, get distinct values, sort, and limit.
    unique_actor_dids = sorted(list(set(r["actor_did"] for r in all_efe_records if "actor_did" in r)))
    actors = unique_actor_dids[:int(batch_size)]

    dispatched = 0
    errors = 0

    for actor_did in actors:
        try:
            action_nsid, free_energy, was_exploration = _sample(actor_did, epsilon)
            if not action_nsid:
                continue

            dispatched_at = _dt.datetime.now(_dt.timezone.utc).isoformat()
            ok, err = _dispatch(action_nsid, actor_did)

            try:
                _log_dispatch(
                    actor_did, action_nsid, dispatched_at,
                    free_energy, epsilon, was_exploration, ok, err,
                )
            except Exception as log_exc:  # noqa: BLE001
                LOG.warning("dispatch_log insert failed: %s", log_exc)

            if ok:
                dispatched += 1
                LOG.info(
                    "policy_dispatch actor=%s action=%s explore=%s ok=True",
                    actor_did, action_nsid, was_exploration,
                )
            else:
                errors += 1
                LOG.warning(
                    "policy_dispatch actor=%s action=%s err=%s",
                    actor_did, action_nsid, err,
                )
        except Exception as exc:  # noqa: BLE001
            LOG.error("policy_dispatch actor=%s: %s", actor_did, exc)
            errors += 1

    return {
        "ok": True,
        "actors_checked": len(actors),
        "dispatched": dispatched,
        "errors": errors,
    }


# ─── registration ─────────────────────────────────────────────────────────────

def register(worker: Any, *, timeout_ms: int = 300_000) -> None:
    def _dispatch_task(batch_size: int = 10, epsilon: float = 0.2) -> dict:
        return task_rl_policy_dispatch(batch_size=batch_size, epsilon=epsilon)

    worker.task(
        task_type="rl.policy.dispatch",
        single_value=False,
        timeout_ms=max(timeout_ms, 300_000),
    )(_dispatch_task)
