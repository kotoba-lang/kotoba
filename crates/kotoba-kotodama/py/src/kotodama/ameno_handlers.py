"""Ameno LangServer handlers (ADR-2605111200).

Receives XRPC saveResult / listHistory forwarded from
ameno.etzhayyim.com CF Worker → bpmn-dispatcher → AgentGateway MCP →
ameno-langserver pod, and persists / queries vertex_ameno_inferenceresult
via the kotoba Datomic client.

Lexicons (SSoT):
  00-contracts/lexicons/com/etzhayyim/apps/ameno/saveResult.json
  00-contracts/lexicons/com/etzhayyim/apps/ameno/listHistory.json
  00-contracts/lexicons/com/etzhayyim/apps/ameno/inferenceResult.json
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Iterable

from kotodama.kotoba_datomic import get_kotoba_client

_TABLE = "vertex_ameno_inferenceresult"
_KNOWN_MODELS = {"gemma-4-e2b-it", "gemma-4-e4b-it", "baien-bitnet-2b"}

# Phase 5c — credits AF event recorded per browser inference. Flat 10 credits
# per saveResult plus 1 credit per 100 output tokens. Tunable via env at
# the langserver pod boundary so we don't have to redeploy app code to
# adjust the murakumo Tier 2 reward curve.
_CREDIT_EVENT_TYPE = "ameno_browser_inference"
_CREDIT_BASE = int(os.environ.get("AMENO_CREDIT_BASE", "10"))
_CREDIT_PER_100_TOKENS = int(os.environ.get("AMENO_CREDIT_PER_100_TOKENS", "1"))

# subscribeBriefs scope guard — only social collections allowed (Phase 4a).
_ALLOWED_BRIEF_COLLECTIONS = {"app.bsky.feed.post"}
_NATS_URL = os.environ.get("NATS_URL", "nats://nats.nats.svc.cluster.local:4222")
_NATS_SUBJECT_PREFIX = os.environ.get("PUBLISH_SUBJECT_PREFIX", "pds.repo.commit")
_LIST_COLS = (
    "result_id",
    "vertex_id",
    "model_id",
    "actor_did",
    "prompt",
    "output",
    "elapsed_ms",
    "tokens_per_sec",
    "created_at",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(raw: Any, default: str = "") -> str:
    return str(raw) if raw is not None else default


def _safe_int(raw: Any, default: int = 0) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _new_result_id() -> str:
    return f"infer-{int(time.time() * 1000):x}-{secrets.token_hex(4)}"


def _credit_amount(output_tokens: int) -> int:
    """Phase 5c — base + per-100-tokens reward. Tier 2 (browser) crowd-source."""
    return max(0, _CREDIT_BASE + (max(0, output_tokens) // 100) * _CREDIT_PER_100_TOKENS)


def _record_credit_event(
    client: Any,
    actor_did: str,
    org_did: str,
    result_id: str,
    output_tokens: int,
    created_at: str,
) -> None:
    """Append an AF event row crediting the actor for one browser inference.

    Best-effort — the saveResult INSERT has already committed by the time
    we're here; a credit-side failure should never roll back the inference
    persist. Caller wraps this in try/except.
    """
    amount = _credit_amount(output_tokens)
    if amount <= 0:
        return
    user_id = actor_did or "anon"
    ts_ms = int(time.time() * 1000)
    af_vertex_id = f"af://credits/{user_id}/{result_id}"
    row_dict = {
        "vertex_id": af_vertex_id,
        "user_id": user_id,
        "event_type": _CREDIT_EVENT_TYPE,
        "amount": amount,
        "ts_ms": ts_ms,
        "created_at": created_at,
        "actor_did": actor_did or "anon",
        "org_did": org_did or "anon",
    }
    client.insert_row("vertex_credits_af_event", row_dict)


def handle_save_result(payload: dict[str, Any]) -> dict[str, Any]:
    """com.etzhayyim.apps.ameno.saveResult — INSERT vertex_ameno_inferenceresult."""
    model_id = _safe_str(payload.get("modelId"))
    if not model_id:
        return {"status": "failed", "error": "modelId required"}
    if model_id not in _KNOWN_MODELS:
        return {"status": "failed", "error": f"unknown modelId: {model_id}"}
    prompt = _safe_str(payload.get("prompt"))
    output = _safe_str(payload.get("output"))
    if not prompt or not output:
        return {"status": "failed", "error": "prompt and output required"}

    result_id = _new_result_id()
    actor_did = _safe_str(payload.get("actorDid"))
    vertex_id = (
        f"at://{actor_did or 'did:web:ameno.etzhayyim.com'}"
        f"/com.etzhayyim.apps.ameno.inferenceResult/{result_id}"
    )
    created_at = _now_iso()
    lora_adapters_raw = payload.get("loraAdapters")
    lora_adapters_json = (
        json.dumps(list(lora_adapters_raw)) if isinstance(lora_adapters_raw, Iterable) and not isinstance(lora_adapters_raw, (str, bytes)) else ""
    )

    row_dict = dict(zip(columns, values))
    client = get_kotoba_client()

    org_did = _safe_str(payload.get("orgDid"), "anon")
    try:
        client.insert_row(_TABLE, row_dict)
        try:
            _record_credit_event(
                client,
                actor_did,
                org_did,
                result_id,
                _safe_int(payload.get("outputTokens")),
                created_at,
            )
        except Exception:  # noqa: BLE001
            # Phase 5c: credit event is best-effort. The inference is
            # already persisted by the line above; a metering failure
            # must not roll back the user-visible saveResult result.
            pass
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "error": str(exc)}

    return {
        "status": "persisted",
        "resultId": result_id,
        "uri": vertex_id,
    }


def _sse_event(event: str, data: dict[str, Any]) -> bytes:
    """Encode one SSE frame (event + data + blank line)."""
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n".encode()


def _extract_brief(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Pull the fields a browser subscriber needs for inference + provenance."""
    record = payload.get("record") if isinstance(payload.get("record"), dict) else {}
    text = ""
    if isinstance(record, dict):
        text = str(record.get("text") or "").strip()
    if not text:
        return None
    return {
        "uri": str(payload.get("uri") or ""),
        "authorDid": str(payload.get("did") or payload.get("authorDid") or ""),
        "collection": str(payload.get("collection") or "app.bsky.feed.post"),
        "text": text[:4000],
        "tsMs": int(payload.get("seq") or payload.get("tsMs") or int(time.time() * 1000)),
    }


async def subscribe_briefs_sse(payload: dict[str, Any]) -> AsyncIterator[bytes]:
    """com.etzhayyim.apps.ameno.subscribeBriefs — yield SSE frames per NATS commit event.

    Subscribes to NATS subject `pds.repo.commit.<collection_underscored>` and
    yields one `event: brief` frame per matching record. Closes the stream after
    `maxEvents` events or `idleTimeoutSec` seconds of inactivity.
    """
    collection = str(payload.get("collection") or "app.bsky.feed.post")
    if collection not in _ALLOWED_BRIEF_COLLECTIONS:
        yield _sse_event("error", {"error": f"collection not allowed: {collection}"})
        yield _sse_event("done", {"reason": "collection-not-allowed"})
        return

    max_events = max(1, min(_safe_int(payload.get("maxEvents"), 100), 1000))
    idle_timeout = max(5.0, min(float(_safe_int(payload.get("idleTimeoutSec"), 60)), 600.0))
    subject = f"{_NATS_SUBJECT_PREFIX}.{collection.replace('.', '_')}"

    try:
        import nats as _nats  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        yield _sse_event("error", {"error": f"nats client unavailable: {exc}"})
        yield _sse_event("done", {"reason": "nats-import-failed"})
        return

    try:
        nc = await _nats.connect(_NATS_URL, connect_timeout=3, max_reconnect_attempts=2)
    except Exception as exc:  # noqa: BLE001
        yield _sse_event("error", {"error": f"nats connect failed: {exc}"})
        yield _sse_event("done", {"reason": "nats-connect-failed"})
        return

    queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=max_events * 2)

    async def _msg_handler(msg: Any) -> None:
        try:
            data = json.loads(msg.data.decode("utf-8"))
        except Exception:
            return
        brief = _extract_brief(data)
        if brief is None:
            return
        try:
            queue.put_nowait(_sse_event("brief", brief))
        except asyncio.QueueFull:
            pass

    sub = await nc.subscribe(subject, cb=_msg_handler)
    yield _sse_event("ready", {"subject": subject, "maxEvents": max_events})
    delivered = 0
    try:
        while delivered < max_events:
            try:
                frame = await asyncio.wait_for(queue.get(), timeout=idle_timeout)
            except asyncio.TimeoutError:
                yield _sse_event("done", {"reason": "idle-timeout", "delivered": delivered})
                return
            yield frame
            delivered += 1
        yield _sse_event("done", {"reason": "max-events", "delivered": delivered})
    finally:
        try:
            await sub.unsubscribe()
        except Exception:
            pass
        try:
            await nc.close()
        except Exception:
            pass


_ADAPTER_COLS = (
    "adapter_id",
    "did",
    "domain",
    "status",
    "base_model",
    "weight_b2_uri",
    "weight_byte_size",
    "weight_sha256",
    "adapter_rank",
    "adapter_alpha",
    "adapter_format",
    "display_name_yomi",
    "created_at",
)


def handle_list_actor_adapters(payload: dict[str, Any]) -> dict[str, Any]:
    """com.etzhayyim.apps.ameno.listActorAdapters — SELECT vertex_lora_adapter."""
    actor_did = _safe_str(payload.get("actorDid"))
    if not actor_did:
        return {"items": [], "total": 0, "error": "actorDid required"}
    domain = _safe_str(payload.get("domain"))
    limit = max(1, min(_safe_int(payload.get("limit"), 20), 100))

    client = get_kotoba_client()
    items: list[dict[str, Any]] = []
    total = 0
    try:
        # R0: Multi-predicate filter and ORDER BY are applied in Python.
        # Fetch all active adapters for the actor_did up to a reasonable limit.
        raw_results = client.select_where(
            "vertex_lora_adapter", "did", actor_did, columns=_ADAPTER_COLS, limit=2000
        )

        filtered_results = []
        for r in raw_results:
            if r.get("status") == "active":
                if domain and r.get("domain") != domain:
                    continue
                filtered_results.append(r)

        total = len(filtered_results)

        # Sort by created_at in descending order
        filtered_results.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # Apply limit
        limited_results = filtered_results[:limit]

        for r in limited_results:
            # adapter_alpha is DOUBLE PRECISION on RW but the lexicon
            # constrains output to integer (×1000) per AT Protocol rules.
            alpha_raw = r.get("adapter_alpha")
            alpha_val = float(alpha_raw) if alpha_raw is not None else 0.0
            items.append(
                {
                    "adapterId": r.get("adapter_id") or "",
                    "actorDid": r.get("did") or "",
                    "domain": r.get("domain") or "",
                    "status": r.get("status") or "",
                    "baseModel": r.get("base_model") or "",
                    "weightB2Uri": r.get("weight_b2_uri") or "",
                    "weightByteSize": int(r.get("weight_byte_size") or 0),
                    "weightSha256": r.get("weight_sha256") or "",
                    "adapterRank": int(r.get("adapter_rank") or 0),
                    "adapterAlpha": int(round(alpha_val * 1000)),
                    "adapterFormat": r.get("adapter_format") or "",
                    "displayNameYomi": r.get("display_name_yomi") or "",
                    "createdAt": r.get("created_at") or "",
                }
            )
    except Exception:  # noqa: BLE001
        return {"items": [], "total": 0}

    return {"items": items, "total": total}


def handle_list_my_credits(payload: dict[str, Any]) -> dict[str, Any]:
    """com.etzhayyim.apps.ameno.listMyCredits — SELECT mv_ameno_credits_balance for one user."""
    actor_did = _safe_str(payload.get("actorDid"))
    if not actor_did:
        return {"actorDid": "", "balance": 0, "eventCount": 0}
    client = get_kotoba_client()
    try:
        row = client.select_first_where(
            "mv_ameno_credits_balance",
            "user_id",
            actor_did,
            columns=[
                "balance",
                "event_count",
                "last_event_ts_ms",
                "last_event_created_at",
            ],
        )
    except Exception:  # noqa: BLE001
        return {"actorDid": actor_did, "balance": 0, "eventCount": 0}
    if not row:
        return {"actorDid": actor_did, "balance": 0, "eventCount": 0}
    return {
        "actorDid": actor_did,
        "balance": int(row.get("balance") or 0),
        "eventCount": int(row.get("event_count") or 0),
        "lastEventTsMs": int(row.get("last_event_ts_ms") or 0),
        "lastEventCreatedAt": row.get("last_event_created_at") or "",
    }


def handle_list_history(payload: dict[str, Any]) -> dict[str, Any]:
    """com.etzhayyim.apps.ameno.listHistory — SELECT from vertex_ameno_inferenceresult."""
    actor_did = _safe_str(payload.get("actorDid"))
    model_id = _safe_str(payload.get("modelId"))
    limit_raw = _safe_int(payload.get("limit"), 20)
    limit = max(1, min(limit_raw, 100))
    offset = max(0, _safe_int(payload.get("offset"), 0))

    client = get_kotoba_client()
    items: list[dict[str, Any]] = []
    all_results: list[dict[str, Any]] = []
    try:
        # R0: Multi-predicate filter, ORDER BY, LIMIT, and OFFSET are applied in Python.
        if actor_did:
            all_results = client.select_where(_TABLE, "actor_did", actor_did, columns=_LIST_COLS, limit=2000)
        elif model_id:
            all_results = client.select_where(_TABLE, "model_id", model_id, columns=_LIST_COLS, limit=2000)
        else:
            # Full table scan via Datalog if no specific filter is provided.
            # Assuming _TABLE "vertex_ameno_inferenceresult" maps to ":vertex/type "ameno-inferenceresult""
            # and columns map to Datomic attributes.
            cols_for_pull = [f":{c.replace('_', '-')}" for c in _LIST_COLS]
            datalog_query = f"""
            [:find (pull ?e [{", ".join(cols_for_pull)}])
             :where
               [?e :vertex/type "ameno-inferenceresult"]]
            """
            raw_q_results = client.q(datalog_query, graph='kotoba-kotodama')
            all_results = [r[0] for r in raw_q_results]

        # Apply secondary filter if primary was broader
        if actor_did and model_id:
            all_results = [r for r in all_results if r.get("model_id") == model_id]
        elif actor_did and not model_id: # primary filter was actor_did, no secondary filter
            pass
        elif model_id and not actor_did: # primary filter was model_id, no secondary filter
            pass
        # else (no filters for select_where, used q()), already broad

        total = len(all_results)

        # Sort by created_at in descending order
        all_results.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # Apply offset and limit
        limited_results = all_results[offset : offset + limit]

        for r in limited_results:
            items.append(
                {
                    "resultId": r.get("result_id") or "",
                    "uri": r.get("vertex_id") or "",
                    "modelId": r.get("model_id") or "",
                    "actorDid": r.get("actor_did") or "",
                    "prompt": r.get("prompt") or "",
                    "output": r.get("output") or "",
                    "elapsedMs": int(r.get("elapsed_ms") or 0),
                    "tokensPerSec": int(r.get("tokens_per_sec") or 0),
                    "createdAt": r.get("created_at") or "",
                }
            )
    except Exception:  # noqa: BLE001
        return {"items": [], "total": 0, "offset": offset, "limit": limit}

    return {"items": items, "total": total, "offset": offset, "limit": limit}
