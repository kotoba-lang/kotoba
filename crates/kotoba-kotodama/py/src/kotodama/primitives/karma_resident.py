"""Karma resident organism agents — long-running LangGraph daemons.

The artificial organism ecosystem.

Each organism DID has a resident agent runtime that:
  1. Heartbeats (R/PT15M default) to update vertex_organism_runtime
  2. Scans its 1-hop neighborhood via Pregel BFS over edge_karma_dependency
  3. Evaluates new edges with the LangGraph state machine (karma_agent.py)
  4. Posts karma observations as new edges (Help / Witness direction)
  5. Persists thread state to vertex_organism_checkpoint per LangGraph
     checkpointer protocol (RisingWave-backed saver below)
  6. Reports cost / token / GPU usage so the cohort genesis primitive
     can rebalance resources

Substrate selection:
  - "k8s"      Vultr VKE pod in mitama-karma-pool (default, CPU-bound)
  - "runpod"   GPU pod for LLM-heavy reasoning (delegates to RunPod
                 serverless endpoint per ADR-2605010000)
  - "ethereum" stub for Phase K3 — on-chain ERC-4337 execution agent

Pyzeebe task types:
  karma.organism.spawn      INSERT vertex_organism_runtime, set status=alive
  karma.organism.tick       single tick (called by R/PT15M BPMN per organism)
  karma.organism.checkpoint persist LangGraph state to vertex_organism_checkpoint
  karma.organism.heartbeat  bulk-update heartbeat_at + tick_count
  karma.organism.harvest    cohort genesis trigger (R/PT24H autonomous)
  karma.organism.dissolveRuntime mark substrate as dissolved (defer to
                                  karma.organism.dissolve for the actual seal)
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import asyncio
import datetime as _dt
import hashlib
import json
import logging
import os
import time
import uuid
from typing import Any, Optional, TypedDict


LOG = logging.getLogger("karma.resident")

KARMA_DID = "did:web:karma.etzhayyim.com"

VALID_SUBSTRATES = ("k8s", "runpod", "ethereum")
VALID_STATUSES = ("alive", "paused", "dissolved", "fissioning")

DEFAULT_TICK_INTERVAL_SEC = 15 * 60
COHORT_GENESIS_K = int(os.environ.get("KARMA_COHORT_GENESIS_K", "50"))
COHORT_FISSION_THRESHOLD = float(os.environ.get("KARMA_COHORT_FISSION_THRESHOLD", "0.95"))


# ── Helpers ────────────────────────────────────────────────────────────


def _now_ms() -> int:
    return int(time.time() * 1000)


def _now_ts() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def _runtime_vertex_id(did: str) -> str:
    return f"organism-rt-{hashlib.sha256(did.encode()).hexdigest()[:32]}"


def _checkpoint_vertex_id(did: str, thread_id: str, checkpoint_id: str) -> str:
    return f"organism-ck-{hashlib.sha256(f'{did}|{thread_id}|{checkpoint_id}'.encode()).hexdigest()[:32]}"


def _cohort_vertex_id(cohort_id: str) -> str:
    return f"organism-cohort-{hashlib.sha256(cohort_id.encode()).hexdigest()[:32]}"


# ── Task: spawn organism runtime ────────────────────────────────────────


async def task_karma_organism_spawn(**kwargs: Any) -> dict[str, Any]:
    did = kwargs["did"]
    substrate = (kwargs.get("substrate") or "k8s").lower()
    if substrate not in VALID_SUBSTRATES:
        raise ValueError(f"karma.organism.spawn: invalid substrate {substrate}")

    pod_name = kwargs.get("podName") or ""
    runpod_endpoint_id = kwargs.get("runpodEndpointId") or ""
    runpod_pod_id = kwargs.get("runpodPodId") or ""
    eth_wallet_address = kwargs.get("ethWalletAddress") or ""
    eth_chain = kwargs.get("ethChain") or ""
    cpu_m = int(kwargs.get("cpuRequestM") or 100)
    mem_mi = int(kwargs.get("memoryRequestMi") or 256)
    gpu_count = int(kwargs.get("gpuCount") or 0)

    vertex_id = _runtime_vertex_id(did)
    today_iso = _dt.datetime.now(tz=_dt.UTC).date().isoformat()
    now_ts = _now_ts()
    now_ms = _now_ms()

    if True:

        client = get_kotoba_client()
        _res = client.q(
            "SELECT vertex_id, status FROM vertex_organism_runtime WHERE did = %s",
            (did,),
        )
        existing = (_res[0] if _res else None)
        if existing:
            _res = client.q(
                """
                UPDATE vertex_organism_runtime
                SET substrate = %s,
                    pod_name = %s,
                    runpod_endpoint_id = %s,
                    runpod_pod_id = %s,
                    eth_wallet_address = %s,
                    eth_chain = %s,
                    cpu_request_m = %s,
                    memory_request_mi = %s,
                    gpu_count = %s,
                    heartbeat_at = %s,
                    heartbeat_at_ms = %s,
                    status = 'alive',
                    last_error = NULL
                WHERE did = %s
                """,
                (
                    substrate, pod_name, runpod_endpoint_id, runpod_pod_id,
                    eth_wallet_address, eth_chain, cpu_m, mem_mi, gpu_count,
                    now_ts, now_ms, did,
                ),
            )
        else:
            _res = client.q(
                """
                INSERT INTO vertex_organism_runtime (
                    vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    did, substrate, pod_name,
                    runpod_endpoint_id, runpod_pod_id,
                    eth_wallet_address, eth_chain,
                    cpu_request_m, memory_request_mi, gpu_count,
                    heartbeat_at, heartbeat_at_ms,
                    tick_count, observation_count, cost_usd_to_date, llm_tokens_to_date,
                    status,
                    created_at, org_id, user_id, actor_id
                ) VALUES (
                    %s, NULL, %s, 1, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    0, 0, 0.0, 0,
                    'alive',
                    %s, %s, %s, %s
                )
                """,
                (
                    vertex_id, today_iso, did,
                    did, substrate, pod_name,
                    runpod_endpoint_id, runpod_pod_id,
                    eth_wallet_address, eth_chain,
                    cpu_m, mem_mi, gpu_count,
                    now_ts, now_ms,
                    now_ts, did, did, "karma.organism.spawn",
                ),
            )

    return {"did": did, "substrate": substrate, "status": "alive", "spawnedAt": now_ts}


# ── Task: organism tick (called by R/PT15M BPMN per resident) ──────────


async def task_karma_organism_tick_batch(**kwargs: Any) -> dict[str, Any]:
    """Bulk tick driver — called by organismResident.bpmn (R/PT15M).

    Selects up to `maxOrganisms` alive organisms ordered by oldest
    heartbeat, calls task_karma_organism_tick for each. Returns the
    aggregate ticked count + observation total.

    Sharded across the karma worker pool (replicas=2 default): each
    worker activates one batch job at a time, so multiple replicas
    process disjoint batches concurrently. Bounded fan-out keeps the
    Hyperdrive connection pool from being saturated.
    """
    max_organisms = int(kwargs.get("maxOrganisms") or 50)
    max_neighbors = int(kwargs.get("maxNeighborsPerOrganism") or 50)

    if True:

        client = get_kotoba_client()
        _res = client.q(
            f"""
            SELECT did, substrate
            FROM vertex_organism_runtime
            WHERE status = 'alive'
            ORDER BY COALESCE(heartbeat_at_ms, 0) ASC
            LIMIT {int(max_organisms)}
            """
        )
        rows = _res

    ticked = 0
    observations = 0
    failed = 0

    for did, substrate in rows:
        try:
            result = await task_karma_organism_tick(
                did=did,
                maxNeighbors=max_neighbors,
                substrate=substrate,
            )
            ticked += 1
            observations += int(result.get("observations", 0))
        except Exception as exc:  # noqa: BLE001
            LOG.warning("tickBatch did=%s err=%s", did, exc)
            failed += 1

    return {
        "ticked": ticked,
        "observations": observations,
        "failed": failed,
        "totalAlive": len(rows),
    }


async def task_karma_organism_tick(**kwargs: Any) -> dict[str, Any]:
    """Single tick of a resident organism agent.

    1. Pregel BFS over its 1-hop neighborhood (bounded)
    2. For each newly-discovered edge, dispatch karma.agent.evaluate
       (delegates to LangGraph state machine in karma_agent.py)
    3. Aggregate observations + emit one karma 'witness' edge per cycle
       (Vinculum axis, low tier — represents the resident's attention)
    4. Update heartbeat_at + tick_count + observation_count
    """
    did = kwargs["did"]
    max_neighbors = int(kwargs.get("maxNeighbors") or 50)
    emit_witness = bool(kwargs.get("emitWitness", True))

    now_ms = _now_ms()
    now_ts = _now_ts()
    observations = 0
    new_edges_seen: list[str] = []

    if True:

        client = get_kotoba_client()
        # Step 1: 1-hop neighbors not yet observed by this resident.
        _res = client.q(
            f"""
            SELECT edge_id, source_did_at_event, target_did_at_event,
                   axis, tier, direction, ts_ms
            FROM edge_karma_dependency
            WHERE (source_did_at_event = %s OR target_did_at_event = %s)
              AND source_did_at_event != target_did_at_event
              AND ts_ms >= COALESCE(
                    (SELECT heartbeat_at_ms FROM vertex_organism_runtime WHERE did = %s),
                    0
              )
            ORDER BY ts_ms DESC
            LIMIT {int(max_neighbors)}
            """,
            (did, did, did),
        )
        rows = _res
        observations = len(rows)
        new_edges_seen = [r[0] for r in rows]

        # Step 4: heartbeat update
        _res = client.q(
            """
            UPDATE vertex_organism_runtime
            SET heartbeat_at = %s,
                heartbeat_at_ms = %s,
                tick_count = COALESCE(tick_count, 0) + 1,
                observation_count = COALESCE(observation_count, 0) + %s
            WHERE did = %s
            """,
            (now_ts, now_ms, observations, did),
        )

    return {
        "did": did,
        "tickAt": now_ts,
        "observations": observations,
        "newEdgesSeen": new_edges_seen[:20],  # cap returned list
    }


# ── Task: organism checkpoint (LangGraph thread state save) ────────────


async def task_karma_organism_checkpoint(**kwargs: Any) -> dict[str, Any]:
    """Persist a LangGraph thread checkpoint. Called by langgraph
    checkpointer at superstep boundaries; thread state is opaque JSON
    (recovered via langgraph_resume primitive in Phase K3)."""
    did = kwargs["did"]
    thread_id = kwargs["threadId"]
    langgraph_node = kwargs.get("langgraphNode") or "unknown"
    state = kwargs.get("state") or {}
    parent_checkpoint_id = kwargs.get("parentCheckpointId")

    state_json = json.dumps(state, separators=(",", ":"))
    nonce = uuid.uuid4().hex
    checkpoint_id = hashlib.sha256(
        f"{did}|{thread_id}|{_now_ms()}|{nonce}".encode()
    ).hexdigest()[:32]

    vertex_id = _checkpoint_vertex_id(did, thread_id, checkpoint_id)
    today_iso = _dt.datetime.now(tz=_dt.UTC).date().isoformat()
    now_ts = _now_ts()
    now_ms = _now_ms()

    if True:

        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_organism_checkpoint (
                vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                did, thread_id, checkpoint_id, parent_checkpoint_id,
                langgraph_node, state_json, state_byte_size,
                saved_at, saved_at_ms,
                created_at, org_id, user_id, actor_id
            ) VALUES (
                %s, NULL, %s, 1, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s
            )
            """,
            (
                vertex_id, today_iso, did,
                did, thread_id, checkpoint_id, parent_checkpoint_id,
                langgraph_node, state_json, len(state_json),
                now_ts, now_ms,
                now_ts, did, did, "karma.organism.checkpoint",
            ),
        )

    return {"checkpointId": checkpoint_id, "savedAt": now_ts}


# ── Task: organism resume from checkpoint ──────────────────────────────


async def task_karma_organism_resume(**kwargs: Any) -> dict[str, Any]:
    """Resume a resident organism from its latest LangGraph checkpoint.

    Reconstruction strategy:
      1. SELECT the latest vertex_organism_checkpoint by (did, thread_id)
         (or specific checkpoint_id if provided)
      2. Decode state_json
      3. Mark vertex_organism_runtime status='alive' (idempotent)

    Phase K3 stub for the actual LangGraph state replay: returns the
    decoded state + node so the caller (or a downstream task) can
    re-instantiate the StateGraph with checkpoint_id-rooted resume.
    The full langgraph.checkpoint protocol integration is K4.
    """
    did = kwargs["did"]
    thread_id = kwargs.get("threadId") or "main"
    checkpoint_id = kwargs.get("checkpointId") or ""
    force = bool(kwargs.get("force", False))

    if True:

        client = get_kotoba_client()
        # Verify organism exists
        _res = client.q(
            "SELECT status FROM vertex_organism_runtime WHERE did = %s",
            (did,),
        )
        row = (_res[0] if _res else None)
        if not row:
            return {
                "did": did, "threadId": thread_id,
                "resumedFromCheckpointId": "", "parentCheckpointId": "",
                "langgraphNode": "", "stateByteSize": 0, "savedAtMs": 0,
                "rejectedReason": "organism-dissolved",
            }
        status = row[0]
        if status == "dissolved" and not force:
            return {
                "did": did, "threadId": thread_id,
                "resumedFromCheckpointId": "", "parentCheckpointId": "",
                "langgraphNode": "", "stateByteSize": 0, "savedAtMs": 0,
                "rejectedReason": "organism-dissolved",
            }

        # Load checkpoint
        if checkpoint_id:
            _res = client.q(
                """
                SELECT checkpoint_id, parent_checkpoint_id, langgraph_node,
                       state_byte_size, saved_at_ms
                FROM vertex_organism_checkpoint
                WHERE did = %s AND thread_id = %s AND checkpoint_id = %s
                LIMIT 1
                """,
                (did, thread_id, checkpoint_id),
            )
        else:
            _res = client.q(
                """
                SELECT checkpoint_id, parent_checkpoint_id, langgraph_node,
                       state_byte_size, saved_at_ms
                FROM vertex_organism_checkpoint
                WHERE did = %s AND thread_id = %s
                ORDER BY saved_at_ms DESC
                LIMIT 1
                """,
                (did, thread_id),
            )
        ck_row = (_res[0] if _res else None)
        if not ck_row:
            return {
                "did": did, "threadId": thread_id,
                "resumedFromCheckpointId": "", "parentCheckpointId": "",
                "langgraphNode": "", "stateByteSize": 0, "savedAtMs": 0,
                "rejectedReason": "no-checkpoint",
            }

        resumed_id, parent_id, langgraph_node, state_size, saved_at_ms = ck_row

        # Idempotently mark runtime as alive (clear any prior dissolved flag).
        _res = client.q(
            """
            UPDATE vertex_organism_runtime
            SET status = 'alive',
                last_error = NULL,
                heartbeat_at = %s,
                heartbeat_at_ms = %s
            WHERE did = %s
            """,
            (_now_ts(), _now_ms(), did),
        )

    return {
        "did": did,
        "threadId": thread_id,
        "resumedFromCheckpointId": resumed_id,
        "parentCheckpointId": parent_id or "",
        "langgraphNode": langgraph_node,
        "stateByteSize": int(state_size or 0),
        "savedAtMs": int(saved_at_ms or 0),
    }


# ── Task: cohort genesis (R/PT24H autonomous self-growth) ───────────────


async def task_karma_organism_harvest(**kwargs: Any) -> dict[str, Any]:
    """Self-growth driver. Decides whether to spawn a new cohort based
    on ecosystem conditions:

      - active organism count
      - edge density (edges per organism)
      - cohort fission posterior (per ADR-0026)

    Triggers: cohort.genesis when k≥COHORT_GENESIS_K observations
              cluster; cohort.fission when posterior > 0.95.
    """
    now_ms = _now_ms()

    if True:

        client = get_kotoba_client()
        _res = client.q("SELECT count(*) FROM vertex_organism_runtime WHERE status = 'alive'")
        alive_count = int((_res[0] if _res else None)[0])

        _res = client.q("SELECT count(*) FROM edge_karma_dependency")
        edge_count = int((_res[0] if _res else None)[0])

        _res = client.q(
            """
            SELECT count(*) FROM vertex_organism_cohort
            WHERE status = 'active'
            """
        )
        active_cohorts = int((_res[0] if _res else None)[0])

        density = edge_count / max(alive_count, 1)

        # Decision rule (heuristic Phase K2):
        #   spawn cohort if alive_count >= K AND no active cohort exists
        #   for this generation, OR density > 100 (ecosystem maturing).
        should_spawn = (alive_count >= COHORT_GENESIS_K and active_cohorts < 1) or density > 100.0

        spawned_cohort_id = ""
        if should_spawn:
            cohort_id = f"cohort-{hashlib.sha256(f'gen-{now_ms}'.encode()).hexdigest()[:24]}"
            cohort_did = f"did:web:karma.etzhayyim.com:cohort:{cohort_id[:16]}"
            generation = active_cohorts + 1
            vertex_id = _cohort_vertex_id(cohort_id)
            today_iso = _dt.datetime.now(tz=_dt.UTC).date().isoformat()
            now_ts = _now_ts()

            _res = client.q(
                """
                INSERT INTO vertex_organism_cohort (
                    vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    cohort_id, cohort_did, generation, parent_cohort_id,
                    member_did_csv, member_count, genesis_trigger,
                    fitness_score, posterior,
                    genesis_at, genesis_at_ms, status,
                    created_at, org_id, user_id, actor_id
                ) VALUES (
                    %s, NULL, %s, 1, %s,
                    %s, %s, %s, NULL,
                    NULL, 0, 'autonomous-harvest',
                    NULL, NULL,
                    %s, %s, 'active',
                    %s, %s, %s, %s
                )
                """,
                (
                    vertex_id, today_iso, cohort_did,
                    cohort_id, cohort_did, generation,
                    now_ts, now_ms,
                    now_ts, cohort_did, cohort_did, "karma.organism.harvest",
                ),
            )
            spawned_cohort_id = cohort_id

    return {
        "aliveOrganisms": alive_count,
        "edgeCount": edge_count,
        "edgeDensity": density,
        "activeCohorts": active_cohorts,
        "shouldSpawn": should_spawn,
        "spawnedCohortId": spawned_cohort_id,
    }


# ── Task: cohort fission (ADR-0026 posterior > 0.95) ────────────────────


async def task_karma_cohort_fission(**kwargs: Any) -> dict[str, Any]:
    """Split an active cohort into N children. Per ADR-0026, fission
    fires when posterior > 0.95. Each child inherits a share of the
    parent's member_did_csv and fitness, increments generation, and
    points back via parent_cohort_id.
    """
    cohort_id = kwargs["cohortId"]
    split_into = max(2, min(8, int(kwargs.get("splitInto") or 2)))
    trigger = kwargs.get("trigger") or "manual"
    force = bool(kwargs.get("force", False))

    now_ts = _now_ts()
    now_ms = _now_ms()
    today_iso = _dt.datetime.now(tz=_dt.UTC).date().isoformat()

    if True:

        client = get_kotoba_client()
        _res = client.q(
            """
            SELECT cohort_did, generation, member_did_csv, fitness_score, posterior, status
            FROM vertex_organism_cohort
            WHERE cohort_id = %s
            LIMIT 1
            """,
            (cohort_id,),
        )
        row = (_res[0] if _res else None)
        if not row:
            return {
                "parentCohortId": cohort_id, "childCohortIds": [], "childCohortDids": [],
                "membersPerChild": [], "fissionedAt": "",
                "rejectedReason": "cohort-not-active",
            }
        parent_did, generation, member_csv, fitness, posterior, status = row
        if status != "active":
            return {
                "parentCohortId": cohort_id, "childCohortIds": [], "childCohortDids": [],
                "membersPerChild": [], "fissionedAt": "",
                "rejectedReason": "parent-fissioned" if status == "fissioned" else "cohort-not-active",
            }
        if not force and (posterior is None or float(posterior) < COHORT_FISSION_THRESHOLD):
            return {
                "parentCohortId": cohort_id, "childCohortIds": [], "childCohortDids": [],
                "membersPerChild": [], "fissionedAt": "",
                "rejectedReason": "posterior-below-threshold",
            }

        members = [m for m in (member_csv or "").split(",") if m]
        if len(members) < split_into:
            return {
                "parentCohortId": cohort_id, "childCohortIds": [], "childCohortDids": [],
                "membersPerChild": [], "fissionedAt": "",
                "rejectedReason": "insufficient-members",
            }

        # Even split. Remainder goes to first children.
        base = len(members) // split_into
        remainder = len(members) % split_into
        partitions: list[list[str]] = []
        idx = 0
        for i in range(split_into):
            take = base + (1 if i < remainder else 0)
            partitions.append(members[idx:idx + take])
            idx += take

        child_fitness = float(fitness or 0.0) / split_into

        child_ids: list[str] = []
        child_dids: list[str] = []
        for i, part in enumerate(partitions):
            ch_id = f"cohort-{hashlib.sha256(f'{cohort_id}|child{i}|{now_ms}'.encode()).hexdigest()[:24]}"
            ch_did = f"did:web:karma.etzhayyim.com:cohort:{ch_id[:16]}"
            ch_vertex = _cohort_vertex_id(ch_id)
            _res = client.q(
                """
                INSERT INTO vertex_organism_cohort (
                    vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    cohort_id, cohort_did, generation, parent_cohort_id,
                    member_did_csv, member_count, genesis_trigger,
                    fitness_score, posterior,
                    genesis_at, genesis_at_ms, status,
                    created_at, org_id, user_id, actor_id
                ) VALUES (
                    %s, NULL, %s, 1, %s,
                    %s, %s, %s, %s,
                    %s, %s, 'fission',
                    %s, NULL,
                    %s, %s, 'active',
                    %s, %s, %s, %s
                )
                """,
                (
                    ch_vertex, today_iso, ch_did,
                    ch_id, ch_did, int(generation or 0) + 1, cohort_id,
                    ",".join(part), len(part),
                    child_fitness,
                    now_ts, now_ms,
                    now_ts, ch_did, ch_did, "karma.cohort.fission",
                ),
            )
            child_ids.append(ch_id)
            child_dids.append(ch_did)

        _res = client.q(
            """
            UPDATE vertex_organism_cohort
            SET status = 'fissioned',
                fission_at = %s
            WHERE cohort_id = %s
            """,
            (now_ts, cohort_id),
        )

    return {
        "parentCohortId": cohort_id,
        "childCohortIds": child_ids,
        "childCohortDids": child_dids,
        "membersPerChild": [len(p) for p in partitions],
        "fissionedAt": now_ts,
    }


async def task_karma_cohort_fission_scan(**kwargs: Any) -> dict[str, Any]:
    """R/PT12H sweep — detect cohorts with posterior > 0.95 and
    fission them autonomously. Idempotent."""
    fissioned = 0
    children_spawned = 0
    eligible_skipped = 0

    if True:

        client = get_kotoba_client()
        _res = client.q(
            f"""
            SELECT cohort_id
            FROM vertex_organism_cohort
            WHERE status = 'active'
              AND posterior IS NOT NULL
              AND posterior > {COHORT_FISSION_THRESHOLD}
            ORDER BY posterior DESC
            LIMIT 50
            """
        )
        eligible = [r[0] for r in _res]

    for cohort_id in eligible:
        try:
            result = await task_karma_cohort_fission(cohortId=cohort_id, splitInto=2)
            if result.get("childCohortIds"):
                fissioned += 1
                children_spawned += len(result["childCohortIds"])
            else:
                eligible_skipped += 1
        except Exception as exc:  # noqa: BLE001
            LOG.warning("cohort.fissionScan cohort=%s err=%s", cohort_id, exc)
            eligible_skipped += 1

    return {
        "fissioned": fissioned,
        "childrenSpawned": children_spawned,
        "eligibleSkipped": eligible_skipped,
    }


# ── Task: dissolve runtime (called by karma.organism.dissolve) ─────────


async def task_karma_organism_dissolve_runtime(**kwargs: Any) -> dict[str, Any]:
    did = kwargs["did"]
    reason = kwargs.get("reason") or "voluntary"
    now_ts = _now_ts()
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            UPDATE vertex_organism_runtime
            SET status = 'dissolved',
                last_error = %s,
                heartbeat_at = %s
            WHERE did = %s
            """,
            (f"dissolved:{reason}", now_ts, did),
        )
    return {"did": did, "dissolvedAt": now_ts}


# ── Worker registration ────────────────────────────────────────────────


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    """Register resident organism agent task types.

      task_type="karma.organism.spawn"
      task_type="karma.organism.tick"
      task_type="karma.organism.tickBatch"
      task_type="karma.organism.checkpoint"
      task_type="karma.organism.harvest"
      task_type="karma.organism.dissolveRuntime"
    """
    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False, timeout_ms=ms or timeout_ms)(fn)

    t("karma.organism.spawn",            task_karma_organism_spawn,             ms=30_000)
    t("karma.organism.tick",             task_karma_organism_tick,              ms=60_000)
    t("karma.organism.tickBatch",        task_karma_organism_tick_batch,        ms=180_000)
    t("karma.organism.checkpoint",       task_karma_organism_checkpoint,        ms=15_000)
    t("karma.organism.resume",           task_karma_organism_resume,            ms=30_000)
    t("karma.organism.harvest",          task_karma_organism_harvest,           ms=60_000)
    t("karma.organism.dissolveRuntime",  task_karma_organism_dissolve_runtime,  ms=15_000)
    t("karma.cohort.fission",            task_karma_cohort_fission,             ms=60_000)
    t("karma.cohort.fissionScan",        task_karma_cohort_fission_scan,        ms=180_000)


__all__ = [
    "register",
    "task_karma_organism_spawn",
    "task_karma_organism_tick",
    "task_karma_organism_tick_batch",
    "task_karma_organism_checkpoint",
    "task_karma_organism_resume",
    "task_karma_organism_harvest",
    "task_karma_organism_dissolve_runtime",
    "task_karma_cohort_fission",
    "task_karma_cohort_fission_scan",
]
