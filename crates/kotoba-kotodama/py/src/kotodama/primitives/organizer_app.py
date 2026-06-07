"""Organizer appview XRPC primitives for BPMN/LangServer."""

from __future__ import annotations

import datetime as _dt
import decimal as _decimal
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from kotodama import llm
from kotodama.kotoba_datomic import get_kotoba_client


APP_DID = "did:web:organizer.etzhayyim.com"
APP_ID = "org4n1z3"
KIND_TABLES = {
    "item": "vertex_organizer_item",
    "classification": "vertex_organizer_classification",
    "tag": "vertex_organizer_tag",
    "collection": "vertex_organizer_collection",
    "collectionItem": "edge_organizer_collection_item",
    "organizeRule": "vertex_organizer_rule",
    "subscriptionItem": "vertex_organizer_subscription_item",
    "subscriptionAnalysis": "vertex_organizer_subscription_analysis",
    "itemDeletion": "vertex_organizer_item_deletion",
    "tagDeletion": "vertex_organizer_tag_deletion",
    "collectionItemDeletion": "vertex_organizer_collection_item_deletion",
    "organizeRuleDeletion": "vertex_organizer_rule_deletion",
    "subscriptionReviewJob": "vertex_organizer_subscription_review_job",
    "subscriptionItemUpdate": "vertex_organizer_subscription_item_update",
}
EDGE_TABLES = {
    "collectionItem": "edge_organizer_collection_item",
}


def _now() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _gid(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000):x}_{uuid.uuid4().hex[:6]}"


def _str(v: Any) -> str:
    return v if isinstance(v, str) else ""


def _num(v: Any, fallback: float = 0.0) -> float:
    try:
        n = float(v)
        return n if n == n and n not in (float("inf"), float("-inf")) else fallback
    except (TypeError, ValueError):
        return fallback


def _int(v: Any, fallback: int = 0) -> int:
    return int(_num(v, fallback))


def _jsonable(v: Any) -> Any:
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat()
    if isinstance(v, _decimal.Decimal):
        f = float(v)
        return int(f) if f.is_integer() else f
    return v


def _rows(cur: Any) -> list[dict[str, Any]]:
    cols = [d[0] for d in (cur.description or [])]
    out: list[dict[str, Any]] = []
    for row in cur.fetchall():
        raw = {cols[i]: _jsonable(row[i]) for i in range(len(cols))}
        value_json = raw.get("value_json")
        if isinstance(value_json, str) and value_json:
            try:
                value = json.loads(value_json)
                if isinstance(value, dict):
                    raw = {**value, **raw}
            except json.JSONDecodeError:
                pass
        out.append(raw)
    return out


def _rls(orgId: Any = "", userId: Any = "", actorId: Any = "") -> dict[str, str]:
    return {"orgId": _str(orgId) or "anon", "userId": _str(userId) or "anon", "actorId": _str(actorId) or APP_ID}


def _collection(name: str) -> str:
    return f"com.etzhayyim.apps.organizer.{name}"


def _record_key(name: str, record: dict[str, Any]) -> str:
    key = (
        record.get("itemId")
        or record.get("classificationId")
        or record.get("tagId")
        or record.get("collectionId")
        or record.get("ruleId")
        or record.get("subscriptionId")
        or record.get("analysisId")
        or record.get("jobId")
        or record.get("linkId")
    )
    return _str(key or _gid(name))[:128]


def _vertex_uri(name: str, rkey: str) -> str:
    return f"at://{APP_DID}/{_collection(name)}/{rkey}"


def _common_columns() -> list[str]:
    return [
        "vertex_id",
        "record_key",
        "label",
        "status",
        "value_json",
        "indexed_at",
        "created_at",
        "updated_at",
        "org_id",
        "user_id",
        "actor_id",
        "actor_did",
        "org_did",
        "owner_did",
        "sensitivity_ord",
    ]


def _label(record: dict[str, Any]) -> str:
    return _str(record.get("name") or record.get("filename") or record.get("serviceName") or record.get("condition"))


def _typed_values(name: str, record: dict[str, Any], rkey: str) -> dict[str, Any]:
    if name == "item":
        return {
            "item_id": _str(record.get("itemId") or rkey),
            "filename": _str(record.get("filename")),
            "content_type": _str(record.get("content_type") or record.get("contentType")),
            "size_bytes": _num(record.get("size")),
            "blake3": _str(record.get("blake3")),
            "blob_ref": _str(record.get("blob_ref") or record.get("blobRef")),
            "vault_did": _str(record.get("vault_did") or record.get("vaultDid")),
        }
    if name == "classification":
        return {
            "classification_id": _str(record.get("classificationId") or rkey),
            "item_id": _str(record.get("item_rkey") or record.get("itemId")),
            "category": _str(record.get("category")),
            "subcategory": _str(record.get("subcategory")),
            "model": _str(record.get("model")),
            "confidence": _num(record.get("confidence")),
        }
    if name == "tag":
        return {
            "tag_id": _str(record.get("tagId") or rkey),
            "item_id": _str(record.get("item_rkey") or record.get("itemId")),
            "name": _str(record.get("name")),
            "source": _str(record.get("source")),
        }
    if name == "collection":
        return {
            "collection_id": _str(record.get("collectionId") or rkey),
            "name": _str(record.get("name")),
            "description": _str(record.get("description")),
            "visibility": _str(record.get("visibility")),
        }
    if name == "organizeRule":
        return {
            "rule_id": _str(record.get("ruleId") or rkey),
            "condition": _str(record.get("condition")),
            "action": _str(record.get("action")),
            "priority": _num(record.get("priority")),
            "target_collection_id": _str(record.get("targetCollectionId")),
        }
    if name == "subscriptionItem":
        return {
            "subscription_id": _str(record.get("subscriptionId") or rkey),
            "sender": _str(record.get("sender")),
            "service_name": _str(record.get("serviceName")),
            "amount": _num(record.get("amount")),
            "currency": _str(record.get("currency")),
            "billing_cycle": _str(record.get("billingCycle")),
            "first_seen_at": _str(record.get("firstSeenAt")),
            "last_seen_at": _str(record.get("lastSeenAt")),
            "email_count": _int(record.get("emailCount")),
        }
    if name == "subscriptionAnalysis":
        return {
            "analysis_id": _str(record.get("analysisId") or rkey),
            "subscription_id": _str(record.get("subscriptionId")),
            "service_name": _str(record.get("serviceName")),
            "usage_score": _num(record.get("usageScore")),
            "cost_per_month": _num(record.get("costPerMonth")),
            "currency": _str(record.get("currency")),
            "recommendation": _str(record.get("recommendation")),
            "analyzed_at": _str(record.get("analyzedAt")),
        }
    return {}


def _edge_id(table: str, src: str, dst: str, relation: str) -> str:
    return f"{table}:{uuid.uuid5(uuid.NAMESPACE_URL, f'{src}|{dst}|{relation}')}"


def _write_edge(cur: Any, table: str, src: str, dst: str, relation: str, value: dict[str, Any], now: str) -> None:
    value_json = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    cur.execute(
        f"""
        INSERT INTO {table}
          (edge_id,src_vid,dst_vid,relation_kind,value_json,created_at,updated_at,owner_did,sensitivity_ord)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (edge_id) DO UPDATE SET
          value_json = EXCLUDED.value_json,
          updated_at = EXCLUDED.updated_at
        """,
        (_edge_id(table, src, dst, relation), src, dst, relation, value_json, now, now, APP_DID, 2),
    )


def _write_related_edges(cur: Any, name: str, record: dict[str, Any], vertex_id: str, now: str) -> None:
    if name == "classification":
        item_id = _str(record.get("item_rkey") or record.get("itemId"))
        if item_id:
            _write_edge("edge_organizer_item_classification", _vertex_uri("item", item_id), vertex_id, "classified_as", record, now)
    elif name == "tag":
        item_id = _str(record.get("item_rkey") or record.get("itemId"))
        if item_id:
            _write_edge("edge_organizer_item_tag", _vertex_uri("item", item_id), vertex_id, "tagged_with", record, now)
    elif name == "organizeRule":
        collection_id = _str(record.get("targetCollectionId"))
        if collection_id:
            _write_edge(cur, "edge_organizer_rule_collection", vertex_id, _vertex_uri("collection", collection_id), "targets_collection", record, now)
    elif name == "subscriptionAnalysis":
        subscription_id = _str(record.get("subscriptionId"))
        if subscription_id:
            _write_edge(cur, "edge_organizer_subscription_analysis", vertex_id, _vertex_uri("subscriptionItem", subscription_id), "analyzes_subscription", record, now)
    elif name == "subscriptionReviewJob":
        subscription_id = _str(record.get("subscriptionId"))
        if subscription_id:
            _write_edge(cur, "edge_organizer_subscription_review_job", vertex_id, _vertex_uri("subscriptionItem", subscription_id), "reviews_subscription", record, now)


def _write_vertex(name: str, record: dict[str, Any]) -> dict[str, str]:
    table = KIND_TABLES.get(name)
    if table is None or table in EDGE_TABLES.values():
        raise ValueError(f"unsupported organizer vertex kind: {name}")
    now = _now()
    rkey = _record_key(name, record)
    vertex_id = _vertex_uri(name, rkey)
    value_json = json.dumps({"$type": _collection(name), **record}, ensure_ascii=False, separators=(",", ":"), default=str)
    typed = _typed_values(name, record, rkey)
    values = {
        "vertex_id": vertex_id,
        "record_key": rkey,
        "label": _label(record),
        "status": _str(record.get("status")),
        "value_json": value_json,
        "indexed_at": now,
        "created_at": _str(record.get("createdAt")) or now,
        "updated_at": _str(record.get("updatedAt")) or now,
        "org_id": _str(record.get("orgId")) or "anon",
        "user_id": _str(record.get("userId")) or "anon",
        "actor_id": _str(record.get("actorId")) or APP_ID,
        "actor_did": APP_DID,
        "org_did": _str(record.get("orgId")) or "anon",
        "owner_did": APP_DID,
        "sensitivity_ord": 2,
        **typed,
    }
    get_kotoba_client().insert_row(table, values)
    _write_related_edges(name, record, vertex_id, now)
    return {"uri": vertex_id, "rkey": rkey}


def _write_collection_item(record: dict[str, Any]) -> dict[str, str]:
    now = _now()
    rkey = _record_key("collectionItem", record)
    collection_id = _str(record.get("collectionId"))
    item_id = _str(record.get("itemId"))
    src = _vertex_uri("collection", collection_id)
    dst = _vertex_uri("item", item_id)
    _write_edge("edge_organizer_collection_item", src, dst, "contains_item", {"$type": _collection("collectionItem"), **record}, now)
    return {"uri": _edge_id("edge_organizer_collection_item", src, dst, "contains_item"), "rkey": rkey}


def _write(name: str, record: dict[str, Any]) -> dict[str, str]:
    if name == "collectionItem":
        return _write_collection_item(record)
    return _write_vertex(name, record)


def _list(name: str, match: dict[str, Any] | None = None, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    table = KIND_TABLES.get(name)
    if table is None or table in EDGE_TABLES.values():
        raise ValueError(f"unsupported organizer list kind: {name}")
    # R0: select_where does not support ORDER BY, LIMIT, OFFSET directly.
    # Fetch all records and apply sorting/pagination in Python.
    rows: list[dict[str, Any]] = get_kotoba_client().select_where(table, "org_id", _str((match or {}).get("orgId") or "anon"), limit=2000)
    # Apply additional filtering for other match parameters
    match = {k: v for k, v in (match or {}).items() if v not in ("", None)}
    if match:
        rows = [r for r in rows if all(str(r.get(k) or "") == str(v) for k, v in match.items())]

    # Apply sorting, limit, and offset in Python
    rows.sort(key=lambda x: x.get("indexed_at") or "", reverse=True) # Sort by indexed_at DESC
    return rows[offset:offset + limit]


def _clamp(limit: Any = 50, offset: Any = 0) -> tuple[int, int]:
    return max(0, _int(offset, 0)), max(1, min(_int(limit, 50), 100))


def _fnv1a(s: str) -> str:
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return f"{h:x}"


def _ext(mime: str) -> str:
    return {
        "image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp",
        "application/pdf": "pdf", "text/plain": "txt", "text/csv": "csv", "application/json": "json",
        "application/zip": "zip", "video/mp4": "mp4", "audio/mpeg": "mp3",
    }.get(mime, "bin")


def _guess_category(ct: str) -> str:
    if ct.startswith("image/"):
        return "image"
    if ct.startswith("video/"):
        return "video"
    if ct.startswith("audio/"):
        return "audio"
    if ct.startswith("text/") or "pdf" in ct:
        return "document"
    if "zip" in ct or "tar" in ct or "gzip" in ct:
        return "archive"
    if "json" in ct or "xml" in ct or "csv" in ct:
        return "data"
    if "presentation" in ct or "pptx" in ct:
        return "presentation"
    if "spreadsheet" in ct or "xlsx" in ct:
        return "spreadsheet"
    return "other"


def _classify(filename: str, content_type: str) -> dict[str, Any]:
    system = (
        "You classify files. Return one JSON object with category, subcategory, "
        "labels array, and confidence number. No prose."
    )
    try:
        result = llm.call_tier_json("classifier", system=system, user=f"Filename: {filename}\nContent-Type: {content_type}", max_tokens=250, temperature=0.1)
        data = result.get("data") if result.get("ok") else {}
        labels = data.get("labels") if isinstance(data, dict) else []
        return {
            "category": _str(data.get("category")) or _guess_category(content_type),
            "subcategory": _str(data.get("subcategory")) or "unknown",
            "labels": [str(x) for x in labels[:5]] if isinstance(labels, list) else [],
            "confidence": max(0.0, min(1.0, _num(data.get("confidence"), 0.5))),
        }
    except Exception:
        return {"category": _guess_category(content_type), "subcategory": "unknown", "labels": [], "confidence": 0.1}


def task_organizer_register_item(filename: str = "", blake3: str = "", contentType: str = "", size: Any = 0, blobRef: str = "", vaultDid: str = "", orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    if not filename:
        return {"error": "filename required"}
    if not blake3:
        return {"error": "blake3 required"}
    vault_did = vaultDid or f"did:web:organizer.etzhayyim.com:vault:{userId or 'anon'}"
    ct = contentType or "application/octet-stream"
    item_id = _gid("item")
    key = f"blobs/{_fnv1a(vault_did)}/{blake3}.{_ext(ct)}"
    record = {"itemId": item_id, "filename": filename, "content_type": ct, "size": _num(size), "blake3": blake3, "blob_ref": blobRef or key, "vault_did": vault_did, "status": "pending_classification", "createdAt": _now(), "updatedAt": _now(), **_rls(orgId, userId)}
    _write("item", record)
    return {"status": "ok", "itemId": item_id, "blake3": blake3, "blob_key": key}


def task_organizer_reclassify(itemId: str = "", filename: str = "", contentType: str = "", orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    if not itemId:
        return {"error": "itemId required"}
    classification = _classify(filename or itemId, contentType or "application/octet-stream")
    classification_id = _gid("cls")
    _write("classification", {"classificationId": classification_id, "item_rkey": itemId, "model": "qwen3-30b", "createdAt": _now(), **classification, **_rls(orgId, userId)})
    for label in classification["labels"]:
        _write("tag", {"tagId": _gid("tag"), "item_rkey": itemId, "name": label, "source": "ai", "createdAt": _now(), **_rls(orgId, userId)})
    return {"status": "ok", "classificationId": classification_id, **classification}


def task_organizer_delete_item(itemId: str = "", orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    if not itemId:
        return {"error": "itemId required"}
    _write("itemDeletion", {"itemId": itemId, "deletedAt": _now(), **_rls(orgId, userId)})
    return {"status": "ok", "itemId": itemId, "action": "deleted"}


def task_organizer_add_tag(itemId: str = "", name: str = "", orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    if not itemId or not name:
        return {"error": "itemId and tag name required"}
    tag_id = _gid("tag")
    _write("tag", {"tagId": tag_id, "item_rkey": itemId, "name": name, "source": "manual", "createdAt": _now(), **_rls(orgId, userId)})
    return {"status": "ok", "tagId": tag_id, "itemId": itemId, "name": name}


def task_organizer_remove_tag(tagId: str = "", orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    if not tagId:
        return {"error": "tagId required"}
    _write("tagDeletion", {"tagId": tagId, "deletedAt": _now(), **_rls(orgId, userId)})
    return {"status": "ok", "tagId": tagId, "action": "removed"}


def task_organizer_create_collection(name: str = "", description: str = "", visibility: str = "private", autoRules: Any = None, orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    if not name:
        return {"error": "name required"}
    if visibility not in ("private", "internal", "public"):
        return {"error": "visibility must be private, internal, or public"}
    collection_id = _gid("col")
    _write("collection", {"collectionId": collection_id, "name": name, "description": description, "visibility": visibility, "auto_rules": json.dumps(autoRules if isinstance(autoRules, list) else []), "status": "active", "createdAt": _now(), "updatedAt": _now(), **_rls(orgId, userId)})
    return {"status": "ok", "collectionId": collection_id, "name": name, "visibility": visibility}


def task_organizer_add_to_collection(collectionId: str = "", itemId: str = "", orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    if not collectionId or not itemId:
        return {"error": "collectionId and itemId required"}
    link_id = _gid("cil")
    _write("collectionItem", {"linkId": link_id, "collectionId": collectionId, "itemId": itemId, "addedAt": _now(), **_rls(orgId, userId)})
    return {"status": "ok", "linkId": link_id, "collectionId": collectionId, "itemId": itemId}


def task_organizer_remove_from_collection(linkId: str = "", orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    if not linkId:
        return {"error": "linkId required"}
    _write("collectionItemDeletion", {"linkId": linkId, "removedAt": _now(), **_rls(orgId, userId)})
    return {"status": "ok", "linkId": linkId, "action": "removed"}


def task_organizer_create_rule(condition: str = "", action: str = "", priority: Any = 0, targetCollectionId: str = "", orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    if not condition or not action:
        return {"error": "condition and action required"}
    rule_id = _gid("rule")
    _write("organizeRule", {"ruleId": rule_id, "condition": condition, "action": action, "priority": _num(priority), "targetCollectionId": targetCollectionId, "status": "active", "createdAt": _now(), **_rls(orgId, userId)})
    return {"status": "ok", "ruleId": rule_id}


def task_organizer_delete_rule(ruleId: str = "", orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    if not ruleId:
        return {"error": "ruleId required"}
    _write("organizeRuleDeletion", {"ruleId": ruleId, "deletedAt": _now(), **_rls(orgId, userId)})
    return {"status": "ok", "ruleId": ruleId, "action": "deleted"}


def task_organizer_search_items(query: str = "", orgId: str = "", limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    off, lim = _clamp(limit, offset)
    rows = _list("item", {"orgId": orgId} if orgId else {}, limit=500)
    q = query.lower()
    if q:
        rows = [r for r in rows if q in str(r.get("filename", "")).lower() or q in str(r.get("content_type", "")).lower()]
    return {"items": rows[off:off + lim], "total": len(rows), "offset": off, "limit": lim, "query": query}


def task_organizer_list_items(orgId: str = "", status: str = "", vaultDid: str = "", limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    off, lim = _clamp(limit, offset)
    match = {"orgId": orgId, "status": status, "vault_did": vaultDid}
    rows = _list("item", match, limit=500)
    return {"items": rows[off:off + lim], "total": len(rows), "offset": off, "limit": lim}


def task_organizer_list_collections(orgId: str = "", limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    off, lim = _clamp(limit, offset)
    rows = _list("collection", {"orgId": orgId} if orgId else {}, limit=500)
    return {"collections": rows[off:off + lim], "total": len(rows), "offset": off, "limit": lim}


def task_organizer_get_vault_stats(orgId: str = "anon", vaultDid: str = "", **_: Any) -> dict[str, Any]:
    items = _list("item", {"orgId": orgId} if orgId else {}, limit=500)
    if vaultDid:
        items = [r for r in items if r.get("vault_did") == vaultDid]
    collections = _list("collection", {"orgId": orgId} if orgId else {}, limit=500)
    return {"orgId": orgId or "anon", "vaultDid": vaultDid or "all", "itemCount": len(items), "classifiedCount": len([r for r in items if r.get("status") == "classified"]), "totalBytes": sum(_num(r.get("size")) for r in items), "collectionCount": len(collections)}


def task_organizer_suggest_rules(orgId: str = "", limit: Any = 5, **_: Any) -> dict[str, Any]:
    rows = _list("classification", {"orgId": orgId} if orgId else {}, limit=500)
    counts: dict[str, int] = {}
    for row in rows:
        cat = _str(row.get("category"))
        if cat:
            counts[cat] = counts.get(cat, 0) + 1
    suggestions = [{"category": c, "itemCount": n, "suggestedCondition": f'category == "{c}"', "suggestedAction": "add_to_collection"} for c, n in sorted(counts.items(), key=lambda x: -x[1])[: max(1, _int(limit, 5))]]
    return {"suggestions": suggestions, "total": len(suggestions)}


def _extract_subscription(subject: str, bodyText: str, sender: str) -> dict[str, Any]:
    system = "Detect subscription billing emails. Return JSON: isSubscription boolean, serviceName string, amount number, currency string, billingCycle monthly|yearly|weekly|unknown."
    try:
        result = llm.call_tier_json("classifier", system=system, user=f"Subject: {subject[:200]}\nFrom: {sender[:100]}\nBody:\n{bodyText[:2000]}", max_tokens=250, temperature=0.1)
        data = result.get("data") if result.get("ok") else {}
        cycle = _str(data.get("billingCycle")) if isinstance(data, dict) else ""
        return {"isSubscription": data.get("isSubscription") is True if isinstance(data, dict) else False, "serviceName": _str(data.get("serviceName")) if isinstance(data, dict) else "", "amount": _num(data.get("amount") if isinstance(data, dict) else 0), "currency": _str(data.get("currency")) or "JPY" if isinstance(data, dict) else "JPY", "billingCycle": cycle if cycle in ("monthly", "yearly", "weekly", "unknown") else "unknown"}
    except Exception:
        return {"isSubscription": False, "serviceName": "", "amount": 0, "currency": "JPY", "billingCycle": "unknown"}


def task_organizer_detect_subscription(subject: str = "", bodyText: str = "", sender: str = "", orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    if not subject:
        return {"error": "subject required"}
    ext = _extract_subscription(subject, bodyText, sender)
    if not ext["isSubscription"] or not ext["serviceName"]:
        return {"status": "not_subscription", **ext}
    subscription_id = _gid("org_sub")
    _write("subscriptionItem", {"subscriptionId": subscription_id, "sender": sender, "serviceName": ext["serviceName"], "amount": ext["amount"], "currency": ext["currency"], "billingCycle": ext["billingCycle"], "firstSeenAt": _now(), "lastSeenAt": _now(), "emailCount": 1, "status": "active", "createdAt": _now(), **_rls(orgId, userId)})
    return {"status": "ok", "subscriptionId": subscription_id, **ext}


def task_organizer_analyze_subscriptions(orgId: str = "", **_: Any) -> dict[str, Any]:
    subs = _list("subscriptionItem", {"orgId": orgId} if orgId else {}, limit=500)
    analyses = []
    total = 0.0
    for sub in subs:
        amount = _num(sub.get("amount"))
        cycle = _str(sub.get("billingCycle"))
        cost = amount / 12 if cycle == "yearly" else amount * 4.33 if cycle == "weekly" else amount
        total += cost
        recommendation = "review" if cost > 500 else "keep"
        analysis = {"analysisId": _gid("org_ana"), "subscriptionId": _str(sub.get("subscriptionId")), "serviceName": _str(sub.get("serviceName")), "usageScore": 50, "costPerMonth": round(cost), "currency": _str(sub.get("currency")) or "JPY", "recommendation": recommendation, "reason": "cost threshold review" if recommendation == "review" else "tracked subscription", "analyzedAt": _now(), **_rls(orgId, _str(sub.get("userId")))}
        _write("subscriptionAnalysis", analysis)
        analyses.append(analysis)
    return {"status": "ok", "analyses": analyses, "totalMonthly": round(total), "actionableCount": len([a for a in analyses if a["recommendation"] != "keep"])}


def task_organizer_get_recommendations(orgId: str = "", filter: str = "all", limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    off, lim = _clamp(limit, offset)
    rows = _list("subscriptionAnalysis", {"orgId": orgId} if orgId else {}, limit=500)
    if filter in ("review", "cancel", "keep"):
        rows = [r for r in rows if r.get("recommendation") == filter]
    return {"recommendations": rows[off:off + lim], "total": len(rows), "offset": off, "limit": lim, "filter": filter}


def task_organizer_request_cancellation(subscriptionId: str = "", orgId: str = "", userId: str = "", **_: Any) -> dict[str, Any]:
    if not subscriptionId:
        return {"error": "subscriptionId required"}
    job_id = _gid("org_rvw")
    _write("subscriptionReviewJob", {"jobId": job_id, "subscriptionId": subscriptionId, "status": "actioned", "userDecision": "cancel", "createdAt": _now(), **_rls(orgId, userId)})
    _write("subscriptionItemUpdate", {"subscriptionId": subscriptionId, "status": "cancellation_requested", "updatedAt": _now(), **_rls(orgId, userId)})
    return {"status": "ok", "jobId": job_id, "subscriptionId": subscriptionId}


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    tasks = {
        "xrpc.com.etzhayyim.apps.organizer.addTag": task_organizer_add_tag,
        "xrpc.com.etzhayyim.apps.organizer.addToCollection": task_organizer_add_to_collection,
        "xrpc.com.etzhayyim.apps.organizer.analyzeSubscriptions": task_organizer_analyze_subscriptions,
        "xrpc.com.etzhayyim.apps.organizer.createCollection": task_organizer_create_collection,
        "xrpc.com.etzhayyim.apps.organizer.createRule": task_organizer_create_rule,
        "xrpc.com.etzhayyim.apps.organizer.deleteItem": task_organizer_delete_item,
        "xrpc.com.etzhayyim.apps.organizer.deleteRule": task_organizer_delete_rule,
        "xrpc.com.etzhayyim.apps.organizer.detectSubscription": task_organizer_detect_subscription,
        "xrpc.com.etzhayyim.apps.organizer.getRecommendations": task_organizer_get_recommendations,
        "xrpc.com.etzhayyim.apps.organizer.getVaultStats": task_organizer_get_vault_stats,
        "xrpc.com.etzhayyim.apps.organizer.listCollections": task_organizer_list_collections,
        "xrpc.com.etzhayyim.apps.organizer.listItems": task_organizer_list_items,
        "xrpc.com.etzhayyim.apps.organizer.reclassify": task_organizer_reclassify,
        "xrpc.com.etzhayyim.apps.organizer.registerItem": task_organizer_register_item,
        "xrpc.com.etzhayyim.apps.organizer.removeFromCollection": task_organizer_remove_from_collection,
        "xrpc.com.etzhayyim.apps.organizer.removeTag": task_organizer_remove_tag,
        "xrpc.com.etzhayyim.apps.organizer.requestCancellation": task_organizer_request_cancellation,
        "xrpc.com.etzhayyim.apps.organizer.searchItems": task_organizer_search_items,
        "xrpc.com.etzhayyim.apps.organizer.suggestRules": task_organizer_suggest_rules,
    }
    for task_type, handler in tasks.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(handler)

