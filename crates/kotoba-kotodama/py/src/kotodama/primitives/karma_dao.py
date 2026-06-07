"""Karma 覚者 DAO arbitration primitives.

Triggered by `karma.evaluate` (recommendation = 'escalate-dao') OR by
caller with elevated standing (positive multi-generational karma streak).

Voting model:
  - voters discovered by Pregel cohort intersection (find_voters)
  - 2/3 supermajority of non-abstain votes → immediate finalize
  - sweeper finalizes by plurality after window closes
  - tied plurality → 'dismiss' (default conservative outcome)

Pyzeebe task types:
  karma.dao.findVoters       Pregel-style voter discovery
  karma.dao.openArbitration  INSERT vertex_karma_arbitration
  karma.dao.castVote         INSERT vertex_karma_vote + tally
  karma.dao.finalize         UPDATE vertex_karma_arbitration on supermajority
  karma.dao.sweepExpired     R/PT15M sweeper for expired windows
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("karma.dao")

KARMA_DID = "did:web:karma.etzhayyim.com"

VOTE_POSITIONS = ("admit", "floor", "dismiss", "abstain")
SUPERMAJORITY_PCT = 2.0 / 3.0


# ── Helpers ────────────────────────────────────────────────────────────


def _now_ms() -> int:
    return int(time.time() * 1000)


def _now_ts() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def _now_iso() -> str:
    return (
        _dt.datetime.now(tz=_dt.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _content_addressed_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return f"{prefix}-{digest[:24]}"


# ── Task: find voters (Pregel-style cohort intersection) ───────────────


async def task_karma_dao_find_voters(**kwargs: Any) -> dict[str, Any]:
    """Discover eligible 覚者 voters via 2-hop graph traversal from
    edge endpoints, excluding the source/target/opener themselves.

    Phase K1 heuristic: voter eligibility = "appears as source on at
    least one help-direction edge with vul ≥ 1.0 in the past 1y AND has
    zero floor violations in the past 5y" (positive multi-generational
    karma streak proxy). The full 覚者 status check is Phase K2.
    """
    edge_id = kwargs.get("edgeId")
    candidate = kwargs.get("candidate") or {}
    opened_by = kwargs.get("openedBy") or ""
    min_voters = int(kwargs.get("minVoters") or 5)

    seeds: set[str] = set()
    if edge_id:
        row = get_kotoba_client().select_first_where(
            "edge_karma_dependency",
            "edge_id",
            edge_id,
            columns=["source_did_at_event", "target_did_at_event"]
        )
        if row:
            if row["source_did_at_event"]:
                seeds.add(row["source_did_at_event"])
            if row["target_did_at_event"]:
                seeds.add(row["target_did_at_event"])
    else:
        if candidate.get("sourceDid"):
            seeds.add(candidate["sourceDid"])
        if candidate.get("targetDid"):
            seeds.add(candidate["targetDid"])

    excluded = set(seeds) | {opened_by}
    if not seeds:
        return {"voters": [], "voterCount": 0}

    one_year_ago = _now_ms() - 365 * 24 * 60 * 60 * 1000
    five_years_ago = _now_ms() - 5 * 365 * 24 * 60 * 60 * 1000

    # R0: Complex SELECT DISTINCT with CASE WHEN and multiple WHERE conditions.
    # Fetching data via multiple selects and processing in Python.
    seed_list = list(seeds)
    neighbors = set()

    for seed_did in seed_list:
        # Edges where seed_did is the source
        source_edges = get_kotoba_client().select_where(
            "edge_karma_dependency",
            "source_did_at_event",
            seed_did,
            columns=["target_did_at_event"]
        )
        for edge in source_edges:
            if edge["target_did_at_event"]:
                neighbors.add(edge["target_did_at_event"])

        # Edges where seed_did is the target
        target_edges = get_kotoba_client().select_where(
            "edge_karma_dependency",
            "target_did_at_event",
            seed_did,
            columns=["source_did_at_event"]
        )
        for edge in target_edges:
            if edge["source_did_at_event"]:
                neighbors.add(edge["source_did_at_event"])

    neighbors = {r for r in neighbors if r} # Ensure no empty strings or None

    # Filter: positive karma streak + no recent floor violation.
    candidates: list[str] = []
    for did in neighbors:
        if did in excluded:
            continue

        # Has at least one help-direction edge in past 1y?
        # R0: Multiple predicates for count, filtering in Python.
        help_edges = get_kotoba_client().select_where(
            "edge_karma_dependency",
            "source_did_at_event",
            did,
            columns=["direction", "ts_ms"]
        )
        found_help_edge = False
        for edge in help_edges:
            if edge["direction"] == "help" and edge["ts_ms"] >= one_year_ago:
                found_help_edge = True
                break
        if not found_help_edge:
            continue

        # Zero floor violations in past 5y?
        # R0: Multiple predicates for count, filtering in Python.
        floor_violations = get_kotoba_client().select_where(
            "edge_karma_dependency",
            "source_did_at_event",
            did,
            columns=["tier", "direction", "ts_ms"]
        )
        found_floor_violation = False
        for edge in floor_violations:
            if edge["tier"] == "floor" and edge["direction"] == "harm" and edge["ts_ms"] >= five_years_ago:
                found_floor_violation = True
                break
        if found_floor_violation:
            continue

        candidates.append(did)
        if len(candidates) >= min_voters * 4:  # enough headroom
            break

    return {"voters": candidates, "voterCount": len(candidates)}


# ── Task: open arbitration ─────────────────────────────────────────────


async def task_karma_dao_open_arbitration(**kwargs: Any) -> dict[str, Any]:
    edge_id = kwargs.get("edgeId") or ""
    candidate = kwargs.get("candidate")
    opened_by = kwargs["openedBy"]
    rationale = kwargs.get("rationale") or ""
    voting_days = int(kwargs.get("votingDays") or 7)
    min_voters = int(kwargs.get("minVoters") or 5)
    voters = kwargs.get("voters") or []
    if not isinstance(voters, list):
        voters = []

    nonce = uuid.uuid4().hex
    arbitration_id = _content_addressed_id(
        "arb", edge_id or "candidate", opened_by, str(_now_ms()), nonce
    )
    vertex_id = f"arbitration-{arbitration_id}"

    opened_at = _now_ts()
    opened_at_ms = _now_ms()
    closes_at_ms = opened_at_ms + voting_days * 24 * 60 * 60 * 1000
    today_iso = _dt.datetime.now(tz=_dt.UTC).date().isoformat()

    candidate_json = json.dumps(candidate, separators=(",", ":")) if candidate else None
    invited_csv = ",".join(voters)

    row_dict = {
        "vertex_id": vertex_id,
        "created_date": today_iso,
        "sensitivity_ord": 1,
        "owner_did": opened_by,
        "arbitration_id": arbitration_id,
        "edge_id": edge_id or None,
        "candidate_json": candidate_json,
        "opened_by_did": opened_by,
        "opened_at": opened_at,
        "opened_at_ms": opened_at_ms,
        "closes_at_ms": closes_at_ms,
        "voting_days": voting_days,
        "min_voters": min_voters,
        "invited_voters_csv": invited_csv,
        "rationale": rationale,
        "status": "open",
        "created_at": opened_at,
        "org_id": opened_by,
        "user_id": opened_by,
        "actor_id": "karma.dao.openArbitration",
    }
    get_kotoba_client().insert_row("vertex_karma_arbitration", row_dict)

    return {"arbitrationId": arbitration_id, "closesAtMs": closes_at_ms}


# ── Task: cast vote ────────────────────────────────────────────────────


def _tally_for(arbitration_id: str) -> dict[str, int]:
    counts = {p: 0 for p in VOTE_POSITIONS}
    # R0: Group by is not supported by select_where, aggregating in Python.
    votes = get_kotoba_client().select_where(
        "vertex_karma_vote", "arbitration_id", arbitration_id, columns=["vote_position"]
    )
    for vote in votes:
        pos = vote["vote_position"]
        if pos in counts:
            counts[pos] += 1
    counts["total"] = sum(counts[p] for p in VOTE_POSITIONS)
    return counts


def _supermajority_outcome(tally: dict[str, int]) -> tuple[bool, str, float]:
    """Return (reached, position, supermajority_pct).

    Supermajority = position has ≥ 2/3 of non-abstain votes
    AND non-abstain total >= 3 (minimum substantive participation).
    """
    non_abstain = tally["total"] - tally.get("abstain", 0)
    if non_abstain < 3:
        return False, "", 0.0
    best_pos = ""
    best_count = 0
    for pos in ("admit", "floor", "dismiss"):
        c = tally.get(pos, 0)
        if c > best_count:
            best_count = c
            best_pos = pos
    pct = best_count / non_abstain if non_abstain > 0 else 0.0
    return pct >= SUPERMAJORITY_PCT, best_pos, pct


async def task_karma_dao_cast_vote(**kwargs: Any) -> dict[str, Any]:
    arbitration_id = kwargs["arbitrationId"]
    voter_did = kwargs["voterDid"]
    position = (kwargs["position"] or "").lower()
    signature = kwargs["signature"]
    signature_alg = kwargs.get("signatureAlg") or "es256"
    rationale_cid = kwargs.get("rationaleCid")

    if position not in VOTE_POSITIONS:
        raise ValueError(f"karma.dao.castVote: invalid position {position}")

    now_ms = _now_ms()

    # Verify arbitration is open + voter is invited + window not closed.
    row = get_kotoba_client().select_first_where(
        "vertex_karma_arbitration",
        "arbitration_id",
        arbitration_id,
        columns=["status", "closes_at_ms", "invited_voters_csv"]
    )
    if not row:
        raise ValueError(f"arbitration {arbitration_id} not found")
    status = row["status"]
    closes_at_ms = row["closes_at_ms"]
    invited_csv = row["invited_voters_csv"]
    if status != "open":
        raise ValueError(f"arbitration not open (status={status})")
    if int(closes_at_ms) <= now_ms:
        raise ValueError("voting window closed")
    invited = set((invited_csv or "").split(","))
    if voter_did not in invited:
        raise ValueError("voter not in invited set")

    # No double-vote check.
    # R0: Multiple predicates for existence check, filtering in Python.
    existing_votes = get_kotoba_client().select_where(
        "vertex_karma_vote",
        "arbitration_id",
        arbitration_id,
        columns=["voter_did"]
    )
    for vote in existing_votes:
        if vote["voter_did"] == voter_did:
            raise ValueError("voter already cast")

    vote_id = _content_addressed_id(
        "vote", arbitration_id, voter_did, position, str(now_ms)
    )
    vertex_id = f"vote-{vote_id}"
    today_iso = _dt.datetime.now(tz=_dt.UTC).date().isoformat()

    vote_row = {
        "vertex_id": vertex_id,
        "created_date": today_iso,
        "sensitivity_ord": 1,
        "owner_did": voter_did,
        "vote_id": vote_id,
        "arbitration_id": arbitration_id,
        "voter_did": voter_did,
        "vote_position": position,
        "signature": signature,
        "signature_alg": signature_alg,
        "rationale_cid": rationale_cid,
        "ts_ms": now_ms,
        "created_at": _now_ts(),
        "org_id": voter_did,
        "user_id": voter_did,
        "actor_id": "karma.dao.castVote",
    }
    get_kotoba_client().insert_row("vertex_karma_vote", vote_row)

    tally = _tally_for(arbitration_id)
    reached, majority_pos, pct = _supermajority_outcome(tally)

    return {
        "voteId": vote_id,
        "tally": tally,
        "quorumReached": reached,
        "majorityPosition": majority_pos,
        "supermajorityPct": pct,
    }


# ── Task: finalize ─────────────────────────────────────────────────────


async def task_karma_dao_finalize(**kwargs: Any) -> dict[str, Any]:
    arbitration_id = kwargs["arbitrationId"]
    majority_position = kwargs.get("majorityPosition") or "dismiss"
    supermajority_pct = float(kwargs.get("supermajorityPct") or 0.0)
    finalized_at = _now_ts()

    # Fetch the existing arbitration row to update it.
    # R0: Update operation converted to fetch, modify, and insert (upsert) pattern.
    arbitration_row = get_kotoba_client().select_first_where(
        "vertex_karma_arbitration",
        "arbitration_id",
        arbitration_id
    )

    if arbitration_row:
        arbitration_row["status"] = "closed"
        arbitration_row["closed_at"] = finalized_at
        arbitration_row["finalized_position"] = majority_position
        arbitration_row["finalized_at"] = finalized_at
        arbitration_row["finalized_supermajority_pct"] = supermajority_pct

        get_kotoba_client().insert_row("vertex_karma_arbitration", arbitration_row)
    else:
        # Handle case where arbitration_id is not found, although in a finalize scenario it should exist.
        LOG.warning(f"Arbitration {arbitration_id} not found for finalization.")


    return {"finalizedAt": finalized_at}


# ── Task: sweep expired (timer-driven) ──────────────────────────────────


async def task_karma_dao_sweep_expired(**kwargs: Any) -> dict[str, Any]:
    """R/PT15M sweeper. Finalize arbitrations whose window has closed
    by plurality (tied → 'dismiss')."""
    now_ms = _now_ms()
    finalized = 0
    still_open = 0
    finalized_at = _now_ts()

    # R0: Multiple WHERE conditions, ORDER BY, and LIMIT. Filtering, sorting, and limiting in Python.
    all_open_arbitrations = get_kotoba_client().select_where(
        "vertex_karma_arbitration",
        "status",
        "open",
        columns=["arbitration_id", "closes_at_ms"]
    )
    # Filter by closes_at_ms
    expired_arbitrations = [
        arb for arb in all_open_arbitrations if arb["closes_at_ms"] <= now_ms
    ]
    # Sort by closes_at_ms ASC
    expired_arbitrations.sort(key=lambda arb: arb["closes_at_ms"])
    # Limit to 200
    expired_ids = [arb["arbitration_id"] for arb in expired_arbitrations[:200]]

    for arb_id in expired_ids:
        tally = _tally_for(arb_id)
        non_abstain = tally["total"] - tally.get("abstain", 0)

        # Plurality among admit/floor/dismiss.
        best_pos = "dismiss"
        best_count = -1
        tied = False
        for pos in ("admit", "floor", "dismiss"):
            c = tally.get(pos, 0)
            if c > best_count:
                best_pos = pos
                best_count = c
                tied = False
            elif c == best_count:
                tied = True

        # Tied → conservative dismiss.
        if tied:
            best_pos = "dismiss"

        pct = best_count / non_abstain if non_abstain > 0 else 0.0

        # R0: Update operation converted to fetch, modify, and insert (upsert) pattern.
        arbitration_row_to_update = get_kotoba_client().select_first_where(
            "vertex_karma_arbitration",
            "arbitration_id",
            arb_id
        )

        if arbitration_row_to_update and arbitration_row_to_update["status"] == "open":
            arbitration_row_to_update["status"] = "closed"
            arbitration_row_to_update["closed_at"] = finalized_at
            arbitration_row_to_update["finalized_position"] = best_pos
            arbitration_row_to_update["finalized_at"] = finalized_at
            arbitration_row_to_update["finalized_supermajority_pct"] = pct
            get_kotoba_client().insert_row("vertex_karma_arbitration", arbitration_row_to_update)
            finalized += 1

    # R0: Counting with a single predicate, using select_where and len in Python.
    all_open = get_kotoba_client().select_where(
        "vertex_karma_arbitration",
        "status",
        "open",
        columns=["arbitration_id"] # Fetching minimal columns for count
    )
    still_open = len(all_open)

    return {"finalized": finalized, "stillOpen": still_open}


# ── Worker registration ─────────────────────────────────────────────────


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    """Wire all karma DAO task types onto the shared LangServer worker.

      task_type="karma.dao.findVoters"
      task_type="karma.dao.openArbitration"
      task_type="karma.dao.castVote"
      task_type="karma.dao.finalize"
      task_type="karma.dao.sweepExpired"
    """
    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False, timeout_ms=ms or timeout_ms)(fn)

    t("karma.dao.findVoters",      task_karma_dao_find_voters,      ms=60_000)
    t("karma.dao.openArbitration", task_karma_dao_open_arbitration, ms=30_000)
    t("karma.dao.castVote",        task_karma_dao_cast_vote,        ms=30_000)
    t("karma.dao.finalize",        task_karma_dao_finalize,         ms=30_000)
    t("karma.dao.sweepExpired",    task_karma_dao_sweep_expired,    ms=60_000)


__all__ = [
    "register",
    "task_karma_dao_find_voters",
    "task_karma_dao_open_arbitration",
    "task_karma_dao_cast_vote",
    "task_karma_dao_finalize",
    "task_karma_dao_sweep_expired",
]
