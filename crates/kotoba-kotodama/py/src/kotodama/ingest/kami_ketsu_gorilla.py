"""Goriketsu Dash handlers for BPMN + Zeebe."""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from datetime import datetime, timezone
from kotodama.kotoba_datomic import get_kotoba_client

OWNER_DID = "did:web:k3t5g0r1.etzhayyim.com"





def _num(value: Any, default: float = 0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if out >= 0 else default


def _int(value: Any, default: int = 0) -> int:
    return int(_num(value, default))


def _caller(kwargs: dict[str, Any]) -> str:
    for key in ("playerDid", "callerDid", "did", "actorDid"):
        value = kwargs.get(key)
        if isinstance(value, str) and value:
            return value
    caller = kwargs.get("caller")
    if isinstance(caller, dict) and isinstance(caller.get("did"), str):
        return caller["did"]
    return "anon"


def submit_score(**kwargs: Any) -> dict[str, Any]:
    score_id = f"score-{uuid4().hex[:12]}"
    score = _int(kwargs.get("score"))
    slaps = _int(kwargs.get("slaps"))
    bananas = _int(kwargs.get("bananas"))
    run_sec = _num(kwargs.get("runSec"))
    player = _caller(kwargs)
    client = get_kotoba_client()
    created_at = datetime.now(timezone.utc).isoformat()
    row_dict = {
        "vertex_id": f"at://{OWNER_DID}/com.etzhayyim.apps.kami.ketsu_gorilla.score/{score_id}",
        "owner_did": OWNER_DID,
        "player_did": player,
        "score": score,
        "slaps": slaps,
        "bananas": bananas,
        "run_sec": run_sec,
        "created_at": created_at,
    }
    client.insert_row("vertex_atrecord_kami_ketsu_gorilla_score", row_dict)
    return {"ok": True, "scoreId": score_id}


def get_leaderboard(limit: Any = 20, offset: Any = 0, **_: Any) -> dict[str, Any]:
    client = get_kotoba_client()
    lim = max(1, min(_int(limit, 20), 100))
    off = max(0, _int(offset, 0))

    # R0: Multi-predicate ORDER BY and LIMIT/OFFSET. Fetching all scores and filtering/sorting in Python.
    # Since select_where can only filter on one column, and we want to order by multiple,
    # we fetch all records and apply logic in Python.
    # Note: In a real-world scenario with very large tables, this would be inefficient.
    # A Datalog query with q() would be more appropriate if the schema allows complex queries.
    all_scores = client.select_where(
        "vertex_atrecord_kami_ketsu_gorilla_score",
        "owner_did",
        OWNER_DID,
        columns=[
            "vertex_id",
            "player_did",
            "score",
            "slaps",
            "bananas",
            "run_sec",
            "created_at",
        ],
        limit=2000 # Apply a reasonable limit to avoid fetching too many records
    )

    # Sort in Python: ORDER BY score DESC, bananas DESC, run_sec ASC, created_at ASC
    sorted_scores = sorted(
        all_scores,
        key=lambda s: (
            -s.get("score", 0),  # score DESC
            -s.get("bananas", 0),  # bananas DESC
            s.get("run_sec", 0.0),  # run_sec ASC
            s.get("created_at", ""),  # created_at ASC
        ),
    )

    # Apply limit and offset
    rows = []
    for i in range(off, min(off + lim, len(sorted_scores))):
        score_data = sorted_scores[i]
        rows.append({
            "scoreId": score_data.get("vertex_id"),
            "playerDid": score_data.get("player_did"),
            "score": score_data.get("score"),
            "slaps": score_data.get("slaps"),
            "bananas": score_data.get("bananas"),
            "runSec": score_data.get("run_sec"),
            "createdAt": score_data.get("created_at"),
        })

    return {"entries": rows, "limit": lim, "offset": off}
