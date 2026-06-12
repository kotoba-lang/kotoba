"""Sponsored-post ads handlers for BPMN + Zeebe."""

from __future__ import annotations

import json
import os
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

ACTOR = "did:web:ads.etzhayyim.com"
PDS_ORIGIN = os.environ.get("PDS_ORIGIN", "https://atproto.etzhayyim.com")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _campaign_id() -> str:
    return f"cmp_{int(time.time() * 1000):x}_{uuid.uuid4().hex[:8]}"


def _rkey(value: str) -> str:
    return "".join(c if c.isalnum() or c in "._~-" else "-" for c in value.lower())[:220] or uuid.uuid4().hex


def _campaign_did(campaign_id: str) -> str:
    return f"{ACTOR}:campaign:{campaign_id}"








def _http_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    token = (
        os.environ.get("PDS_SERVICE_AUTH_TOKEN")
        or os.environ.get("PDS_ADMIN_TOKEN")
        or os.environ.get("PDS_INTERNAL_TOKEN")
        or ""
    )
    headers = {"content-type": "application/json", "user-agent": "etzhayyim-ads-zeebe/1"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, method="POST", data=json.dumps(payload).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        return {"error": f"pds_{e.code}", "body": raw[:500]}
    except Exception as e:
        return {"error": "pds_unreachable", "message": str(e)}


def _create_identity(campaign_id: str, name: str, description: str) -> dict[str, Any]:
    return _http_json(
        f"{PDS_ORIGIN}/xrpc/com.atproto.identity.create",
        {"handle": f"campaign:{campaign_id}", "displayName": name, "description": description},
    )


def _create_social_post(record: dict[str, Any], repo: str = ACTOR) -> dict[str, Any]:
    from kotodama.primitives.yoro_social import build_repo_record, insert_social_post_record
    row = build_repo_record(repo=repo, collection="app.bsky.feed.post", record=record)
    try:
        return insert_social_post_record(row, flush=False)
    except Exception as e:
        return {"error": "c_path_failed", "message": str(e)}


def create_campaign(name: str = "", description: str = "", advertiser: str = "", budgetJpy: Any = 0, **_: Any) -> dict[str, Any]:
    if not name:
        return {"error": "name is required"}
    campaign_id = _campaign_id()
    did = _campaign_did(campaign_id)
    created_at = now_iso()
    identity = _create_identity(campaign_id, name, description or "")
    record = {
        "$type": "com.etzhayyim.apps.ads.campaign",
        "campaignId": campaign_id,
        "did": did,
        "name": name,
        "description": description or "",
        "advertiser": advertiser or "",
        "budgetJpy": _int(budgetJpy),
        "active": True,
        "createdAt": created_at,
    }
    kotoba_client = get_kotoba_client()
    row_dict = {
        "vertex_id": f"at://{ACTOR}/com.etzhayyim.apps.ads.campaign/{_rkey(campaign_id)}",
        "owner_did": ACTOR,
        "rkey": campaign_id,
        "repo": ACTOR,
        "collection": "com.etzhayyim.apps.ads.campaign",
        "campaign_id": campaign_id,
        "did": did,
        "name": name,
        "description": description or "",
        "advertiser": advertiser or "",
        "budget_jpy": _int(budgetJpy),
        "active": True,
        "created_at": created_at,
        "org_id": "anon",
        "user_id": "anon",
        "actor_id": ACTOR,
        "actor_did": ACTOR,
        "org_did": "anon",
    }
    kotoba_client.insert_row("vertex_ads_campaign", row_dict)
    return {"campaignId": campaign_id, "did": did, "createdAt": created_at, **({"identityWarning": identity} if identity.get("error") else {})}


def post_sponsored(campaignId: str = "", text: str = "", embedUri: str = "", embedTitle: str = "", embedDesc: str = "", embedThumb: str = "", langs: list[str] | None = None, **_: Any) -> dict[str, Any]:
    if not campaignId or not text:
        return {"error": "campaignId and text are required"}
    did = _campaign_did(campaignId)
    created_at = now_iso()
    post: dict[str, Any] = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": created_at,
        "labels": {"$type": "com.atproto.label.defs#selfLabels", "values": [{"val": "!ad"}]},
    }
    if embedUri:
        external = {"uri": embedUri, "title": embedTitle or "", "description": embedDesc or ""}
        if embedThumb:
            external["thumb"] = embedThumb
        post["embed"] = {"$type": "app.bsky.embed.external", "external": external}
    if langs:
        post["langs"] = langs
    posted = _create_social_post(post, did)
    uri = _str(posted.get("uri"))
    cid = _str(posted.get("cid"))
    kotoba_client = get_kotoba_client()
    row_dict = {
        "vertex_id": f"at://{ACTOR}/com.etzhayyim.apps.ads.sponsoredPost/{_rkey(campaignId + '-' + created_at)}",
        "owner_did": ACTOR,
        "rkey": _rkey(campaignId + "-" + created_at),
        "repo": ACTOR,
        "collection": "com.etzhayyim.apps.ads.sponsoredPost",
        "campaign_id": campaignId,
        "post_uri": uri,
        "cid": cid,
        "text": text,
        "created_at": created_at,
        "org_id": "anon",
        "user_id": "anon",
        "actor_id": ACTOR,
        "actor_did": ACTOR,
        "org_did": "anon",
    }
    kotoba_client.insert_row("vertex_ads_sponsored_post", row_dict)
    if posted.get("error"):
        return {"uri": "", "cid": "", "createdAt": created_at, "error": posted.get("error"), "body": posted.get("body")}
    return {"uri": uri, "cid": cid, "createdAt": created_at}


def list_campaigns(limit: Any = 50, **_: Any) -> dict[str, Any]:
    n = max(1, min(_int(limit, 50), 100))
    kotoba_client = get_kotoba_client()
    # R0: Fetch all campaign records matching the collection and apply ORDER BY and LIMIT in Python.
    all_campaigns = kotoba_client.select_where(
        "vertex_ads_campaign",
        "collection",  # All entries in vertex_ads_campaign should have this collection
        "com.etzhayyim.apps.ads.campaign",
        columns=[
            "campaign_id",
            "did",
            "name",
            "description",
            "advertiser",
            "budget_jpy",
            "active",
            "created_at",
        ],
        limit=2000  # Max limit to fetch for in-memory sorting/slicing
    )
    # Apply Python sorting and slicing
    sorted_campaigns = sorted(all_campaigns, key=lambda x: x.get("created_at", ""), reverse=True)
    rows = sorted_campaigns[:n]
    return {
        "campaigns": [
            {
                "campaignId": row.get("campaign_id"),
                "did": row.get("did"),
                "name": row.get("name"),
                "description": row.get("description") or "",
                "advertiser": row.get("advertiser") or "",
                "budgetJpy": _int(row.get("budget_jpy")),
                "active": bool(row.get("active")),
                "createdAt": row.get("created_at"),
            }
            for row in rows
        ]
    }
