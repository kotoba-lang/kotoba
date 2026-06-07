"""Oshikatsu creator subscription XRPC primitives for BPMN/LangServer."""

from __future__ import annotations

import datetime as _dt
import decimal as _decimal
import json
import time
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


APP_DID = "did:web:oshikatsu.etzhayyim.com"
APP_ID = "dyd3lr50"
TIER_RANK = {"free": 0, "supporter": 1, "premium": 2, "vip": 3}
DEFAULT_TIERS = [
    {"name": "free", "priceCredits": 0, "label": "Free", "description": "Public content only"},
    {"name": "supporter", "priceCredits": 500, "label": "Supporter", "description": "Exclusive posts and early access"},
    {"name": "premium", "priceCredits": 2000, "label": "Premium", "description": "All content, DM access, behind-the-scenes"},
    {"name": "vip", "priceCredits": 5000, "label": "VIP", "description": "Everything + 1-on-1 sessions, custom content requests"},
]


def _now() -> _dt.datetime:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0)


def _id(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000):x}_{uuid.uuid4().hex[:8]}"


def _str(v: Any) -> str:
    return v if isinstance(v, str) else ""


def _num(v: Any, fallback: float = 0.0) -> float:
    try:
        n = float(v)
        return n if n == n and n not in (float("inf"), float("-inf")) else fallback
    except (TypeError, ValueError):
        return fallback


def _jsonable(v: Any) -> Any:
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat()
    if isinstance(v, _decimal.Decimal):
        f = float(v)
        return int(f) if f.is_integer() else f
    return v


def _vertex_id(kind: str, key: str) -> str:
    return f"at://{APP_DID}/com.etzhayyim.apps.oshikatsu.{kind}/{key}"


def _edge_id(kind: str, src: str, dst: str) -> str:
    return f"at://{APP_DID}/com.etzhayyim.apps.oshikatsu.edge/{kind}:{src}:{dst}"[:512]


def _rows(input_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in input_rows:
        raw = {k: _jsonable(v) for k, v in row.items()}
        for key in ("tiers", "media_urls"):
            if isinstance(raw.get(key), str) and raw[key].startswith("["):
                try:
                    raw[key] = json.loads(raw[key])
                except json.JSONDecodeError:
                    pass
        aliases = {
            "vertex_id": "vertexId",
            "creator_did": "creatorDid",
            "display_name": "displayName",
            "subscriber_count": "subscriberCount",
            "total_earned_credits": "totalEarnedCredits",
            "tier_id": "tierId",
            "price_credits": "priceCredits",
            "subscriber_did": "subscriberDid",
            "started_at": "startedAt",
            "expires_at": "expiresAt",
            "auto_renew": "autoRenew",
            "cancelled_at": "cancelledAt",
            "content_type": "contentType",
            "min_tier": "minTier",
            "media_urls": "mediaUrls",
            "preview_text": "previewText",
            "like_count": "likeCount",
            "comment_count": "commentCount",
            "tip_total_credits": "tipTotalCredits",
            "published_at": "publishedAt",
            "from_did": "fromDid",
            "created_at": "createdAt",
            "updated_at": "updatedAt",
        }
        for src, dst in aliases.items():
            if src in raw and dst not in raw:
                raw[dst] = raw[src]
        out.append(raw)
    return out


def _write(kind: str, rec: dict[str, Any]) -> dict[str, Any]:
    record = {**rec, "orgId": rec.get("orgId") or "anon", "actorId": rec.get("actorId") or APP_ID}
    if kind == "creatorProfile":
        vid = _vertex_id("creatorProfile", _str(record["id"]))
        row_dict = {
            "vertex_id": vid,
            "id": record["id"],
            "creator_did": record["creatorDid"],
            "display_name": record["displayName"],
            "bio": record.get("bio", ""),
            "tiers": json.dumps(record.get("tiers") or [], ensure_ascii=False),
            "subscriber_count": int(_num(record.get("subscriberCount"))),
            "total_earned_credits": _num(record.get("totalEarnedCredits")),
            "status": record.get("status", "active"),
            "created_at": record.get("createdAt") or _now(),
            "org_id": record["orgId"],
            "user_id": record.get("userId") or record["creatorDid"],
            "actor_id": record["actorId"],
            "sensitivity_ord": 2,
            "owner_did": APP_DID,
        }
        get_kotoba_client().insert_row("vertex_oshikatsu_creator_profile", row_dict)
        return {"uri": vid}
    if kind == "subscriptionTier":
        vid = _vertex_id("subscriptionTier", _str(record["tierId"]))
        row_dict = {
            "vertex_id": vid,
            "tier_id": record["tierId"],
            "rank": int(_num(record.get("rank"))),
            "name": record.get("name", ""),
            "label": record.get("label", ""),
            "price_credits": _num(record.get("priceCredits")),
            "description": record.get("description", ""),
            "creator_did": record.get("creatorDid", ""),
            "updated_at": record.get("updatedAt") or _now(),
            "org_id": record["orgId"],
            "user_id": record.get("userId") or record.get("creatorDid", ""),
            "actor_id": record["actorId"],
            "sensitivity_ord": 2,
            "owner_did": APP_DID,
        }
        get_kotoba_client().insert_row("vertex_oshikatsu_subscription_tier", row_dict)
        creator = _find("creatorProfile", "creatorDid", _str(record.get("creatorDid")))
        if creator:
            edge_id = _edge_id("creatorTier", _str(creator.get("vertexId")), vid)
            row_dict = {
                "edge_id": edge_id,
                "src_vid": creator.get("vertexId"),
                "dst_vid": vid,
                "creator_did": record.get("creatorDid"),
                "tier_id": record["tierId"],
                "relation": "HAS_TIER",
                "created_at": _now(),
                "owner_did": APP_DID,
                "sensitivity_ord": 2,
            }
            get_kotoba_client().insert_row("edge_oshikatsu_creator_tier", row_dict)
        return {"uri": vid}
    if kind == "subscription":
        vid = _vertex_id("subscription", _str(record["id"]))
        row_dict = {
            "vertex_id": vid,
            "id": record["id"],
            "subscriber_did": record["subscriberDid"],
            "creator_did": record["creatorDid"],
            "tier": record.get("tier", ""),
            "price_credits": _num(record.get("priceCredits")),
            "status": record.get("status", "active"),
            "started_at": record.get("startedAt") or _now(),
            "expires_at": record.get("expiresAt", ""),
            "auto_renew": bool(record.get("autoRenew", True)),
            "created_at": record.get("createdAt") or _now(),
            "org_id": record["orgId"],
            "user_id": record.get("userId") or record["subscriberDid"],
            "actor_id": record["actorId"],
            "sensitivity_ord": 2,
            "owner_did": APP_DID,
        }
        get_kotoba_client().insert_row("vertex_oshikatsu_subscription", row_dict)
        edge_id = _edge_id("subscription", record["subscriberDid"], record["creatorDid"])
        row_dict = {
            "edge_id": edge_id,
            "src_vid": record["subscriberDid"],
            "dst_vid": record["creatorDid"],
            "subscriber_did": record["subscriberDid"],
            "creator_did": record["creatorDid"],
            "subscription_id": record["id"],
            "tier": record.get("tier", ""),
            "relation": "SUBSCRIBES_TO",
            "created_at": record.get("createdAt") or _now(),
            "owner_did": APP_DID,
            "sensitivity_ord": 2,
        }
        get_kotoba_client().insert_row("edge_oshikatsu_subscription", row_dict)
        return {"uri": vid}
    if kind == "subscriptionCancel":
        vid = _vertex_id("subscriptionCancel", _str(record["id"]))
        row_dict = {
            "vertex_id": vid,
            "id": record["id"],
            "subscriber_did": record["subscriberDid"],
            "creator_did": record["creatorDid"],
            "cancelled_at": record.get("cancelledAt") or _now(),
            "org_id": record["orgId"],
            "user_id": record.get("userId") or record["subscriberDid"],
            "actor_id": record["actorId"],
            "sensitivity_ord": 2,
            "owner_did": APP_DID,
        }
        get_kotoba_client().insert_row("vertex_oshikatsu_subscription_cancel", row_dict)
        return {"uri": vid}
    if kind == "exclusiveContent":
        vid = _vertex_id("exclusiveContent", _str(record["id"]))
        row_dict = {
            "vertex_id": vid,
            "id": record["id"],
            "creator_did": record["creatorDid"],
            "title": record["title"],
            "body": record.get("body", ""),
            "content_type": record.get("contentType", "post"),
            "min_tier": record.get("minTier", "supporter"),
            "media_urls": json.dumps(record.get("mediaUrls") or [], ensure_ascii=False),
            "preview_text": record.get("previewText", ""),
            "like_count": int(_num(record.get("likeCount"))),
            "comment_count": int(_num(record.get("commentCount"))),
            "tip_total_credits": _num(record.get("tipTotalCredits")),
            "status": record.get("status", "published"),
            "published_at": record.get("publishedAt") or _now(),
            "created_at": record.get("createdAt") or _now(),
            "org_id": record["orgId"],
            "user_id": record.get("userId") or record["creatorDid"],
            "actor_id": record["actorId"],
            "sensitivity_ord": 2,
            "owner_did": APP_DID,
        }
        get_kotoba_client().insert_row("vertex_oshikatsu_exclusive_content", row_dict)
        edge_id = _edge_id("contentBy", record["creatorDid"], record["id"])
        row_dict = {
            "edge_id": edge_id,
            "src_vid": record["creatorDid"],
            "dst_vid": vid,
            "creator_did": record["creatorDid"],
            "content_id": record["id"],
            "relation": "PUBLISHED",
            "created_at": record.get("createdAt") or _now(),
            "owner_did": APP_DID,
            "sensitivity_ord": 2,
        }
        get_kotoba_client().insert_row("edge_oshikatsu_content_by_creator", row_dict)
        return {"uri": vid}
    if kind == "tip":
        vid = _vertex_id("tip", _str(record["id"]))
        row_dict = {
            "vertex_id": vid,
            "id": record["id"],
            "from_did": record["fromDid"],
            "creator_did": record["creatorDid"],
            "content_id": record.get("contentId", ""),
            "amount": _num(record.get("amount")),
            "message": record.get("message", ""),
            "created_at": record.get("createdAt") or _now(),
            "org_id": record["orgId"],
            "user_id": record.get("userId") or record["fromDid"],
            "actor_id": record["actorId"],
            "sensitivity_ord": 2,
            "owner_did": APP_DID,
        }
        get_kotoba_client().insert_row("vertex_oshikatsu_tip", row_dict)
        edge_id = _edge_id("tipTo", record["fromDid"], record["id"])
        row_dict = {
            "edge_id": edge_id,
            "src_vid": record["fromDid"],
            "dst_vid": record["creatorDid"],
            "from_did": record["fromDid"],
            "creator_did": record["creatorDid"],
            "tip_id": record["id"],
            "amount": _num(record.get("amount")),
            "relation": "TIPPED",
            "created_at": record.get("createdAt") or _now(),
            "owner_did": APP_DID,
            "sensitivity_ord": 2,
        }
        get_kotoba_client().insert_row("edge_oshikatsu_tip_to_creator", row_dict)
        if record.get("contentId"):
            edge_id = _edge_id("tipFor", record["id"], record["contentId"])
            row_dict = {
                "edge_id": edge_id,
                "src_vid": vid,
                "dst_vid": _vertex_id("exclusiveContent", _str(record["contentId"])),
                "tip_id": record["id"],
                "content_id": record["contentId"],
                "relation": "TIPS_CONTENT",
                "created_at": record.get("createdAt") or _now(),
                "owner_did": APP_DID,
                "sensitivity_ord": 2,
            }
            get_kotoba_client().insert_row("edge_oshikatsu_tip_for_content", row_dict)
        return {"uri": vid}
    raise ValueError(f"unknown oshikatsu kind: {kind}")


def _list(kind: str, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    # R0: Fetching a broader set with select_where and applying ordering/pagination in Python
    tables = {
        "creatorProfile": ("vertex_oshikatsu_creator_profile", "created_at"),
        "subscriptionTier": ("vertex_oshikatsu_subscription_tier", "updated_at"),
        "subscription": ("vertex_oshikatsu_subscription", "created_at"),
        "subscriptionCancel": ("vertex_oshikatsu_subscription_cancel", "cancelled_at"),
        "exclusiveContent": ("vertex_oshikatsu_exclusive_content", "created_at"),
        "tip": ("vertex_oshikatsu_tip", "created_at"),
    }
    table, order_col = tables[kind]

    rows = get_kotoba_client().select_where(table, "owner_did", APP_DID, limit=2000)

    # Apply Python-based ordering
    rows.sort(key=lambda r: r.get(order_col, _now()), reverse=True)

    # Apply Python-based limit and offset
    off = max(0, offset)
    lim = max(1, min(limit, 500))

    return _rows(rows[off:off + lim])


def _find(kind: str, key: str, value: str) -> dict[str, Any] | None:
    for row in _list(kind, limit=500):
        if str(row.get(key) or "") == value:
            return row
    return None


def _tiers(raw: Any, creator_did: str = "") -> list[dict[str, Any]]:
    arr = raw if isinstance(raw, list) else DEFAULT_TIERS
    out = []
    for i, t in enumerate(arr):
        t = t if isinstance(t, dict) else {}
        out.append({
            "tierId": _str(t.get("tierId")) or _id("tier"),
            "rank": i,
            "name": _str(t.get("name")),
            "label": _str(t.get("label")) or _str(t.get("name")),
            "priceCredits": _num(t.get("priceCredits")),
            "description": _str(t.get("description")),
            "creatorDid": creator_did,
            "updatedAt": _now(),
        })
    return out


def task_oshikatsu_create_creator_profile(creatorDid: str = "", displayName: str = "", bio: str = "", tiers: Any = None, **_: Any) -> dict[str, Any]:
    if not creatorDid or not displayName:
        return {"error": "creatorDid and displayName required"}
    creator_id = _id("creator")
    tier_rows = _tiers(tiers, creatorDid)
    record = {"id": creator_id, "creatorDid": creatorDid, "displayName": displayName, "bio": bio, "tiers": tier_rows, "subscriberCount": 0, "totalEarnedCredits": 0, "status": "active", "createdAt": _now(), "userId": creatorDid}
    _write("creatorProfile", record)
    for tier in tier_rows:
        _write("subscriptionTier", {**tier, "userId": creatorDid})
    return {"id": creator_id, "creatorDid": creatorDid, "tiers": tier_rows, "status": "created"}


def task_oshikatsu_get_creator_profile(creatorDid: str = "", **_: Any) -> dict[str, Any]:
    if not creatorDid:
        return {"error": "creatorDid required"}
    profile = _find("creatorProfile", "creatorDid", creatorDid)
    if not profile:
        return {"error": "creator not found"}
    tiers = [t for t in _list("subscriptionTier", limit=500) if t.get("creatorDid") == creatorDid]
    return {**profile, "tiers": sorted(tiers, key=lambda r: int(_num(r.get("rank"), 0)))}


def task_oshikatsu_list_creators(limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    rows = [r for r in _list("creatorProfile", limit=int(_num(limit, 50)), offset=int(_num(offset, 0))) if r.get("status") == "active"]
    return {"items": rows, "offset": int(_num(offset, 0)), "limit": int(_num(limit, 50))}


def task_oshikatsu_update_tiers(creatorDid: str = "", tiers: Any = None, **_: Any) -> dict[str, Any]:
    if not creatorDid or not isinstance(tiers, list):
        return {"error": "creatorDid and tiers[] required"}
    rows = _tiers(tiers, creatorDid)
    for tier in rows:
        _write("subscriptionTier", {**tier, "userId": creatorDid})
    return {"creatorDid": creatorDid, "tiers": rows, "status": "updated"}


def task_oshikatsu_subscribe(subscriberDid: str = "", creatorDid: str = "", tier: str = "supporter", **_: Any) -> dict[str, Any]:
    if not subscriberDid or not creatorDid:
        return {"error": "subscriberDid and creatorDid required"}
    existing = [s for s in _list("subscription", limit=500) if s.get("subscriberDid") == subscriberDid and s.get("creatorDid") == creatorDid and s.get("status") == "active"]
    if existing:
        return {"error": "alreadySubscribed", "currentTier": existing[0].get("tier")}
    tier_rows = [t for t in _list("subscriptionTier", limit=500) if t.get("creatorDid") == creatorDid and t.get("name") == tier]
    price = _num(tier_rows[0].get("priceCredits")) if tier_rows else 0
    sub_id = _id("sub")
    expires = (_dt.datetime.now(tz=_dt.UTC) + _dt.timedelta(days=30)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    _write("subscription", {"id": sub_id, "subscriberDid": subscriberDid, "creatorDid": creatorDid, "tier": tier, "priceCredits": price, "status": "active", "startedAt": _now(), "expiresAt": expires, "autoRenew": True, "createdAt": _now(), "userId": subscriberDid})
    return {"id": sub_id, "tier": tier, "priceCredits": price, "expiresAt": expires, "status": "active"}


def task_oshikatsu_unsubscribe(subscriberDid: str = "", creatorDid: str = "", **_: Any) -> dict[str, Any]:
    if not subscriberDid or not creatorDid:
        return {"error": "subscriberDid and creatorDid required"}
    cancel_id = _id("unsub")
    _write("subscriptionCancel", {"id": cancel_id, "subscriberDid": subscriberDid, "creatorDid": creatorDid, "cancelledAt": _now(), "userId": subscriberDid})
    return {"status": "cancelled", "subscriberDid": subscriberDid, "creatorDid": creatorDid}


def task_oshikatsu_list_subscriptions(subscriberDid: str = "", creatorDid: str = "", limit: Any = 50, offset: Any = 0, **_: Any) -> dict[str, Any]:
    if not subscriberDid and not creatorDid:
        return {"error": "subscriberDid or creatorDid required"}
    rows = _list("subscription", limit=500)
    if subscriberDid:
        rows = [r for r in rows if r.get("subscriberDid") == subscriberDid]
    if creatorDid:
        rows = [r for r in rows if r.get("creatorDid") == creatorDid]
    off = int(_num(offset, 0))
    lim = int(_num(limit, 50))
    return {"items": rows[off:off + lim], "offset": off, "limit": lim}


def _has_access(subscriber_did: str, creator_did: str, required_tier: str) -> dict[str, Any]:
    if required_tier == "free":
        return {"hasAccess": True, "tier": "free"}
    subs = [s for s in _list("subscription", limit=500) if s.get("subscriberDid") == subscriber_did and s.get("creatorDid") == creator_did and s.get("status") == "active"]
    if not subs:
        return {"hasAccess": False, "reason": "notSubscribed"}
    sub = subs[0]
    if TIER_RANK.get(str(sub.get("tier")), 0) < TIER_RANK.get(required_tier, 0):
        return {"hasAccess": False, "reason": "tierInsufficient", "currentTier": sub.get("tier"), "requiredTier": required_tier}
    return {"hasAccess": True, "tier": sub.get("tier"), "expiresAt": sub.get("expiresAt")}


def task_oshikatsu_check_access(subscriberDid: str = "", creatorDid: str = "", requiredTier: str = "free", **_: Any) -> dict[str, Any]:
    if not subscriberDid or not creatorDid:
        return {"error": "subscriberDid and creatorDid required"}
    return _has_access(subscriberDid, creatorDid, requiredTier or "free")


def task_oshikatsu_publish_content(creatorDid: str = "", title: str = "", body: str = "", contentType: str = "post", minTier: str = "supporter", mediaUrls: Any = None, previewText: str = "", **_: Any) -> dict[str, Any]:
    if not creatorDid or not title:
        return {"error": "creatorDid and title required"}
    content_id = _id("content")
    _write("exclusiveContent", {"id": content_id, "creatorDid": creatorDid, "title": title, "body": body, "contentType": contentType or "post", "minTier": minTier or "supporter", "mediaUrls": mediaUrls if isinstance(mediaUrls, list) else [], "previewText": previewText, "likeCount": 0, "commentCount": 0, "tipTotalCredits": 0, "status": "published", "publishedAt": _now(), "createdAt": _now(), "userId": creatorDid})
    return {"id": content_id, "title": title, "minTier": minTier or "supporter", "status": "published"}


def task_oshikatsu_get_content(contentId: str = "", viewerDid: str = "", **_: Any) -> dict[str, Any]:
    if not contentId:
        return {"error": "contentId required"}
    content = _find("exclusiveContent", "id", contentId)
    if not content:
        return {"error": "content not found"}
    min_tier = _str(content.get("minTier")) or "free"
    if min_tier == "free" or viewerDid == content.get("creatorDid"):
        return content
    if not viewerDid:
        return {**content, "body": "", "mediaUrls": [], "locked": True, "reason": "loginRequired"}
    access = _has_access(viewerDid, _str(content.get("creatorDid")), min_tier)
    if not access.get("hasAccess"):
        return {**content, "body": "", "mediaUrls": [], "locked": True, **access}
    return content


def task_oshikatsu_list_content(creatorDid: str = "", viewerDid: str = "", limit: Any = 20, offset: Any = 0, **_: Any) -> dict[str, Any]:
    if not creatorDid:
        return {"error": "creatorDid required"}
    rows = [r for r in _list("exclusiveContent", limit=500) if r.get("creatorDid") == creatorDid]
    out = []
    for c in rows:
        if viewerDid == creatorDid or _has_access(viewerDid, creatorDid, _str(c.get("minTier")) or "free").get("hasAccess"):
            out.append(c)
        else:
            out.append({**c, "body": "", "mediaUrls": [], "locked": True})
    off = int(_num(offset, 0))
    lim = int(_num(limit, 20))
    return {"items": out[off:off + lim], "offset": off, "limit": lim}


def task_oshikatsu_tip(fromDid: str = "", creatorDid: str = "", amount: Any = 0, contentId: str = "", message: str = "", **_: Any) -> dict[str, Any]:
    amt = _num(amount)
    if not fromDid or not creatorDid or amt <= 0:
        return {"error": "fromDid, creatorDid, and positive amount required"}
    tip_id = _id("tip")
    _write("tip", {"id": tip_id, "fromDid": fromDid, "creatorDid": creatorDid, "contentId": contentId, "amount": amt, "message": message, "createdAt": _now(), "userId": fromDid})
    return {"id": tip_id, "amount": amt, "status": "completed"}


def task_oshikatsu_creator_stats(creatorDid: str = "", **_: Any) -> dict[str, Any]:
    if not creatorDid:
        return {"error": "creatorDid required"}
    subs = [s for s in _list("subscription", limit=500) if s.get("creatorDid") == creatorDid and s.get("status") == "active"]
    contents = [c for c in _list("exclusiveContent", limit=500) if c.get("creatorDid") == creatorDid]
    tips = [t for t in _list("tip", limit=500) if t.get("creatorDid") == creatorDid]
    return {"creatorDid": creatorDid, "activeSubscribers": len(subs), "publishedContent": len(contents), "totalTipsCredits": sum(_num(t.get("amount")) for t in tips)}


def task_oshikatsu_search(q: str = "", limit: Any = 20, **_: Any) -> dict[str, Any]:
    term = q.lower()
    if not term:
        return {"items": []}
    rows = [r for r in _list("creatorProfile", limit=500) if term in _str(r.get("displayName")).lower() or term in _str(r.get("bio")).lower()]
    return {"items": rows[: int(_num(limit, 20))]}


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    tasks = {
        "xrpc.com.etzhayyim.apps.oshikatsu.checkAccess": task_oshikatsu_check_access,
        "xrpc.com.etzhayyim.apps.oshikatsu.createCreatorProfile": task_oshikatsu_create_creator_profile,
        "xrpc.com.etzhayyim.apps.oshikatsu.creatorStats": task_oshikatsu_creator_stats,
        "xrpc.com.etzhayyim.apps.oshikatsu.getContent": task_oshikatsu_get_content,
        "xrpc.com.etzhayyim.apps.oshikatsu.getCreatorProfile": task_oshikatsu_get_creator_profile,
        "xrpc.com.etzhayyim.apps.oshikatsu.listContent": task_oshikatsu_list_content,
        "xrpc.com.etzhayyim.apps.oshikatsu.listCreators": task_oshikatsu_list_creators,
        "xrpc.com.etzhayyim.apps.oshikatsu.listSubscriptions": task_oshikatsu_list_subscriptions,
        "xrpc.com.etzhayyim.apps.oshikatsu.publishContent": task_oshikatsu_publish_content,
        "xrpc.com.etzhayyim.apps.oshikatsu.search": task_oshikatsu_search,
        "xrpc.com.etzhayyim.apps.oshikatsu.subscribe": task_oshikatsu_subscribe,
        "xrpc.com.etzhayyim.apps.oshikatsu.tip": task_oshikatsu_tip,
        "xrpc.com.etzhayyim.apps.oshikatsu.unsubscribe": task_oshikatsu_unsubscribe,
        "xrpc.com.etzhayyim.apps.oshikatsu.updateTiers": task_oshikatsu_update_tiers,
    }
    for task_type, handler in tasks.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(handler)
