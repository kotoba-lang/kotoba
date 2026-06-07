"""Bluesky public AppView ingest for Zeebe.

Moves the former ``kotoba-kotodama-bsky1ngs`` Cloudflare Worker business logic into
the shared Python Zeebe worker. The edge Worker now only proxies manual XRPC
requests to the BPMN dispatcher; timer refreshes run from BPMN.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger(__name__)

ACTOR_DID = "did:web:bluesky.etzhayyim.com"
DEFAULT_APPVIEW = "https://public.api.bsky.app"
DEFAULT_NANOID = "bsky1ngs"
BLOCKING_LABELS = {
    "!no-unauthenticated",
    "!no-search",
    "!hide",
    "!takedown",
    "no-unauthenticated",
}
FORBIDDEN_COLLECTIONS = {
    "chat.bsky.convo.message",
    "chat.bsky.actor.declaration",
    "app.bsky.graph.block",
    "app.bsky.graph.listitem",
    "app.bsky.graph.listblock",
}


@dataclass(frozen=True)
class OptOutVerdict:
    allow: bool
    reason: str = ""
    hit_label: str = ""


class ForbiddenCollectionError(ValueError):
    pass


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _http_json(url: str, timeout: int = 20) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _appview_url(base_url: str, path: str, params: dict[str, str]) -> str:
    base = (base_url or DEFAULT_APPVIEW).rstrip("/")
    query = urllib.parse.urlencode(params)
    return f"{base}{path}?{query}"


def get_profile(actor: str, appview: str = DEFAULT_APPVIEW) -> dict[str, Any]:
    return _http_json(_appview_url(appview, "/xrpc/app.bsky.actor.getProfile", {"actor": actor}))


def get_author_feed(actor: str, appview: str = DEFAULT_APPVIEW, limit: int = 25) -> dict[str, Any]:
    return _http_json(
        _appview_url(
            appview,
            "/xrpc/app.bsky.feed.getAuthorFeed",
            {"actor": actor, "limit": str(limit), "filter": "posts_no_replies"},
        )
    )


def evaluate_profile_opt_out(profile: dict[str, Any]) -> OptOutVerdict:
    for label in profile.get("labels") or []:
        if label.get("neg"):
            continue
        val = str(label.get("val") or "")
        if val in BLOCKING_LABELS:
            if "no-unauthenticated" in val:
                reason = "no-unauthenticated"
            elif "no-search" in val:
                reason = "no-search"
            elif val == "!takedown":
                reason = "takedown"
            else:
                reason = "labeler-verdict"
            return OptOutVerdict(False, reason, val)
    return OptOutVerdict(True)


def evaluate_post_opt_out(labels: Any) -> OptOutVerdict:
    for label in labels or []:
        val = str(label.get("val") or "")
        if val in BLOCKING_LABELS:
            return OptOutVerdict(False, "labeler-verdict", val)
    return OptOutVerdict(True)


def _parse_rkey(uri: str) -> str:
    return (uri or "").split("/")[-1]


def _extract_cid_from_uri(uri: str | None) -> str | None:
    if not uri:
        return None
    return uri.rstrip("/").split("/")[-1] or None


def map_profile(profile: dict[str, Any], opt_out_signal: str, indexed_at: str) -> dict[str, Any]:
    labels = [str(l.get("val")) for l in (profile.get("labels") or []) if l.get("val")]
    return {
        "source_did": str(profile.get("did") or ""),
        "handle": str(profile.get("handle") or ""),
        "display_name": profile.get("displayName"),
        "description": profile.get("description"),
        "avatar_cid": _extract_cid_from_uri(profile.get("avatar")),
        "banner_cid": _extract_cid_from_uri(profile.get("banner")),
        "labels": ",".join(labels) if labels else None,
        "opt_out_signal": opt_out_signal,
        "indexed_at": indexed_at,
    }


def map_post(post: dict[str, Any], indexed_at: str) -> dict[str, Any]:
    record = post.get("record") or {}
    collection = str(record.get("$type") or "")
    if collection in FORBIDDEN_COLLECTIONS or collection != "app.bsky.feed.post":
        raise ForbiddenCollectionError(f"Forbidden collection: {collection}")

    embed = post.get("embed") or {}
    etype = str(embed.get("$type") or "")
    embed_kind = "none"
    media_cids: list[str] = []
    alt_text = None
    external_uri = None

    if "images" in etype:
        embed_kind = "images"
        alts: list[str] = []
        for img in embed.get("images") or []:
            cid = _extract_cid_from_uri(img.get("fullsize"))
            if cid:
                media_cids.append(cid)
            if img.get("alt"):
                alts.append(str(img.get("alt")))
        alt_text = "\n\n".join(alts) if alts else None
    elif "video" in etype:
        embed_kind = "video"
        video = embed.get("video") or {}
        alt_text = video.get("alt")
        cid = _extract_cid_from_uri(video.get("thumbnail"))
        if cid:
            media_cids.append(cid)
    elif "external" in etype:
        embed_kind = "external"
        external_uri = (embed.get("external") or {}).get("uri")
    elif "recordWithMedia" in etype:
        embed_kind = "recordWithMedia"
    elif "record" in etype:
        embed_kind = "record"

    labels = [str(l.get("val")) for l in (post.get("labels") or []) if l.get("val")]
    reply = record.get("reply") or {}
    author = post.get("author") or {}
    langs = record.get("langs") or []
    return {
        "source_did": str(author.get("did") or ""),
        "source_rkey": _parse_rkey(str(post.get("uri") or "")),
        "source_uri": str(post.get("uri") or ""),
        "source_cid": str(post.get("cid") or ""),
        "handle": str(author.get("handle") or ""),
        "text": str(record.get("text") or ""),
        "lang": str(langs[0]) if langs else None,
        "created_at": str(record.get("createdAt") or indexed_at),
        "indexed_at": indexed_at,
        "reply_root_uri": (reply.get("root") or {}).get("uri"),
        "reply_parent_uri": (reply.get("parent") or {}).get("uri"),
        "embed_kind": embed_kind,
        "embed_media_cids": ",".join(media_cids) if media_cids else None,
        "embed_alt_text": alt_text,
        "embed_external_uri": external_uri,
        "labels": ",".join(labels) if labels else None,
    }





def write_profile(rec: dict[str, Any], nanoid: str, indexed_at: str) -> int:
    rkey = rec["source_did"].replace(":", "-")
    vertex_id = f"at://{ACTOR_DID}/com.etzhayyim.apps.bluesky.profile/{rkey}"
    client = get_kotoba_client()
    row_dict = {
        "vertex_id": vertex_id,
        "rkey": rkey,
        "repo": ACTOR_DID,
        "owner_did": ACTOR_DID,
        "source_did": rec["source_did"],
        "handle": rec["handle"],
        "display_name": rec["displayName"],
        "description": rec["description"],
        "avatar_cid": rec["avatar_cid"],
        "banner_cid": rec["banner_cid"],
        "labels": rec["labels"],
        "opt_out_signal": rec["opt_out_signal"],
        "indexed_at": indexed_at,
        "created_date": indexed_at[:10],
        "sensitivity_ord": 200,
        "actor_id": f"t1:bluesky:{nanoid}",
    }
    client.insert_row("vertex_bluesky_profile", row_dict)
    return 1


def write_post(rec: dict[str, Any], nanoid: str, indexed_at: str) -> int:
    rkey = f"{rec['source_did'].replace(':', '-')}-{rec['source_rkey']}"
    vertex_id = f"at://{ACTOR_DID}/com.etzhayyim.apps.bluesky.post/{rkey}"
    client = get_kotoba_client()
    row_dict = {
        "vertex_id": vertex_id,
        "rkey": rkey,
        "repo": ACTOR_DID,
        "owner_did": ACTOR_DID,
        "source_did": rec["source_did"],
        "source_rkey": rec["source_rkey"],
        "source_uri": rec["source_uri"],
        "source_cid": rec["source_cid"],
        "handle": rec["handle"],
        "text": rec["text"],
        "lang": rec["lang"],
        "created_at": rec["created_at"],
        "indexed_at": indexed_at,
        "reply_root_uri": rec["reply_root_uri"],
        "reply_parent_uri": rec["reply_parent_uri"],
        "embed_kind": rec["embed_kind"],
        "embed_media_cids": rec["embed_media_cids"],
        "embed_alt_text": rec["embed_alt_text"],
        "embed_external_uri": rec["embed_external_uri"],
        "labels": rec["labels"],
        "created_date": indexed_at[:10],
        "sensitivity_ord": 200,
        "actor_id": f"t1:bluesky:{nanoid}",
    }
    client.insert_row("vertex_bluesky_post", row_dict)
    return 1


def write_opt_out(did: str, handle: str | None, reason: str, hit_label: str, nanoid: str, indexed_at: str) -> int:
    rkey = did.replace(":", "-")
    vertex_id = f"at://{ACTOR_DID}/com.etzhayyim.apps.bluesky.optOut/{rkey}"
    note = f"hit label: {hit_label}" if hit_label else None
    client = get_kotoba_client()
    row_dict = {
        "vertex_id": vertex_id,
        "rkey": rkey,
        "repo": ACTOR_DID,
        "owner_did": ACTOR_DID,
        "source_did": did,
        "handle": handle,
        "reason": reason,
        "note": note,
        "detected_at": indexed_at,
        "created_date": indexed_at[:10],
        "sensitivity_ord": 200,
        "actor_id": f"t1:bluesky:{nanoid}",
    }
    client.insert_row("vertex_bluesky_opt_out", row_dict)
    return 1


def cascade_tombstones(source_did: str, fresh_rkeys: set[str], nanoid: str, indexed_at: str) -> dict[str, Any]:
    if not fresh_rkeys:
        return {"purged": 0, "existingCount": 0, "toPurgeList": []}
    client = get_kotoba_client()
    existing_raw = client.select_where(
        "vertex_bluesky_post", "source_did", source_did,
        columns=["source_rkey", "created_at"], limit=25
    )
    # R0: Order by created_at DESC in Python, as kotoba_datomic.select_where does not support ORDER BY.
    existing = sorted(existing_raw, key=lambda x: x["created_at"], reverse=True)

    to_purge = [row["source_rkey"] for row in existing if row["source_rkey"] not in fresh_rkeys]
    for rkey in to_purge:
        vertex_id = f"at://{ACTOR_DID}/com.etzhayyim.apps.bluesky.post/{source_did.replace(':', '-')}-{rkey}"
        # R0: Deleting entity via Datalog transaction, assuming `q` can handle transaction data for retracting an entity by a unique attribute.
        client.q(f'[[:db.fn/retractEntity [:vertex-bluesky-post/vertex-id "{vertex_id}"]]]')
        tomb_rkey = f"{source_did.replace(':', '-')}-{rkey}-{int(time.time() * 1000)}"
        tomb_vid = f"at://{ACTOR_DID}/com.etzhayyim.apps.bluesky.tombstone/{tomb_rkey}"
        tomb_row_dict = {
            "vertex_id": tomb_vid,
            "rkey": tomb_rkey,
            "repo": ACTOR_DID,
            "owner_did": ACTOR_DID,
            "source_did": source_did,
            "source_rkey": rkey,
            "source_collection": "app.bsky.feed.post",
            "event_kind": "delete",
            "detected_at": indexed_at,
            "cascade_completed_at": indexed_at,
            "created_date": indexed_at[:10],
            "sensitivity_ord": 200,
            "actor_id": f"t1:bluesky:{nanoid}",
        }
        client.insert_row("vertex_bluesky_tombstone", tomb_row_dict)
    return {"purged": len(to_purge), "existingCount": len(existing), "toPurgeList": to_purge}


def ingest_actor(actor: str, appview: str = DEFAULT_APPVIEW, nanoid: str = DEFAULT_NANOID) -> dict[str, Any]:
    if not actor:
        return {"ok": False, "error": "actor required"}
    indexed_at = now_iso()
    try:
        profile = get_profile(actor, appview)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "actor": actor, "error": f"getProfile failed: {e}"}

    verdict = evaluate_profile_opt_out(profile)
    if not verdict.allow:
        write_opt_out(
            str(profile.get("did") or actor),
            profile.get("handle"),
            verdict.reason or "labeler-verdict",
            verdict.hit_label,
            nanoid,
            indexed_at,
        )
        return {
            "ok": True,
            "actor": profile.get("did"),
            "optOut": True,
            "reason": verdict.reason,
            "label": verdict.hit_label,
        }

    write_profile(map_profile(profile, "none", indexed_at), nanoid, indexed_at)

    try:
        feed = get_author_feed(actor, appview, 25)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "actor": profile.get("did"), "error": f"getAuthorFeed failed: {e}"}

    ingested = 0
    skipped_opt_out = 0
    skipped_forbidden = 0
    fresh_rkeys: set[str] = set()

    for item in feed.get("feed") or []:
        post = item.get("post") or {}
        post_author = post.get("author") or {}
        p_verdict = evaluate_post_opt_out(post.get("labels"))
        if not p_verdict.allow:
            skipped_opt_out += 1
            continue
        try:
            rec = map_post(post, indexed_at)
            ingested += write_post(rec, nanoid, indexed_at)
            if post_author.get("did") == profile.get("did"):
                fresh_rkeys.add(rec["source_rkey"])
        except ForbiddenCollectionError:
            skipped_forbidden += 1

    tombstone = cascade_tombstones(str(profile.get("did") or actor), fresh_rkeys, nanoid, indexed_at)
    return {
        "ok": True,
        "actor": profile.get("did"),
        "handle": profile.get("handle"),
        "ingested": ingested,
        "tombstoned": tombstone["purged"],
        "skippedOptOut": skipped_opt_out,
        "skippedForbidden": skipped_forbidden,
    }


def stale_actor_dids(batch_size: int) -> list[str]:
    client = get_kotoba_client()
    # R0: Complex query using Datalog escape hatch `q()`. Aggregation, ordering, and limiting done in Python.
    datalog_query = """
    [:find ?source-did ?indexed-at
     :where [?e :vertex-bluesky-post/source-did ?source-did]
            [?e :vertex-bluesky-post/indexed-at ?indexed-at]
            (not [?opt-out-e :vertex-bluesky-opt-out/source-did ?source-did])]
    """
    results_raw = client.q(datalog_query)

    # Group by source_did and find max indexed_at
    actor_last_indexed: dict[str, str] = {}
    for row in results_raw:
        source_did = row[0]
        indexed_at = row[1]
        if source_did not in actor_last_indexed or indexed_at > actor_last_indexed[source_did]:
            actor_last_indexed[source_did] = indexed_at

    # Sort by last_indexed ASC and limit
    sorted_actors = sorted(actor_last_indexed.items(), key=lambda item: item[1])

    return [did for did, _ in sorted_actors[:batch_size]]


def refresh_stalest(
    batch_size: int = 10,
    appview: str = DEFAULT_APPVIEW,
    nanoid: str = DEFAULT_NANOID,
) -> dict[str, Any]:
    actors = stale_actor_dids(max(1, int(batch_size or 10)))
    results: list[dict[str, Any]] = []
    errors = 0
    ingested = 0
    tombstoned = 0
    for actor in actors:
        result = ingest_actor(actor, appview=appview, nanoid=nanoid)
        results.append(result)
        if not result.get("ok"):
            errors += 1
        ingested += int(result.get("ingested") or 0)
        tombstoned += int(result.get("tombstoned") or 0)
    return {
        "ok": errors == 0,
        "actorsRead": len(actors),
        "ingested": ingested,
        "tombstoned": tombstoned,
        "errorCount": errors,
        "results": results[:20],
    }
