"""otakiage.etzhayyim.com LangServer primitives — Reuse & Ritual Platform Phase 1.

ADR-2605081700 + ADR-0036 (Worker-direct Hyperdrive) + ADR-0056 (BPMN-as-actor)
+ ADR-2604282300 (T2 = kotodama + Zeebe, no CF Worker).

Task families:
  otakiage.item.submit              XRPC submitItem      (handler)
  otakiage.reuse.requestSubmit      XRPC requestReuse    (handler)
  otakiage.reuse.findCandidates     R/PT1H reuseMatch
  otakiage.reuse.expireOpen         R/PT24H reuseExpire
  otakiage.handover.confirm         XRPC confirmHandover (handler)
  otakiage.ritual.request           XRPC requestRitual   (handler)
  otakiage.ritual.issueCertificate  XRPC issueCertificate (handler)
  otakiage.matsuri.scheduleSubmit   XRPC scheduleMatsuri (handler)
  otakiage.matsuri.seedNextMonth    cron 月初 matsuriSchedule
  otakiage.social.composeAnnounce   socialAnnounce BPMN inner step

Schema (migration 20260508120000):
  vertex_otakiage_{item, reuse_request, handover, ritual, matsuri, certificate}
  edge_otakiage_{item_owner, item_handover, item_ritual, ritual_certificate}
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import hashlib
import json
import os
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any


# ── Constants ──────────────────────────────────────────────────────────

# Category mode classification (ADR-2605081700 §8 lifecycle).
# Furniture / appliances stay in reuse_only mode — they don't flow into ritual.
CATEGORY_MODE: dict[str, str] = {
    "ehon": "reuse_then_ritual",
    "jidousho": "reuse_then_ritual",
    "nuigurumi": "reuse_then_ritual",
    "ningyo": "reuse_then_ritual",
    "omocha": "reuse_then_ritual",
    "kagu": "reuse_only",
    "kaden": "reuse_only",
}

PATH_DID_ROOT = "did:web:otakiage.etzhayyim.com"
PATH_DID_REUSE = "did:web:otakiage.etzhayyim.com:reuse"
PATH_DID_RITUAL = "did:web:otakiage.etzhayyim.com:ritual"
PATH_DID_MATSURI = "did:web:otakiage.etzhayyim.com:matsuri"

REUSE_TTL_DAYS = 30


# ── Helpers ────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _content_addressed_rkey(*parts: str) -> str:
    """Stable content-addressed rkey (ADR-0041)."""
    h = hashlib.sha256("|".join(p or "" for p in parts).encode("utf-8")).hexdigest()
    return h[:24]


def _h3_truncate_to_res(cell: str | None, target_res: int) -> str | None:
    """Best-effort truncation of an H3 cell ID to a coarser resolution.

    Phase 1 is a degenerate truncation: we keep the first N hex chars of the
    cell ID. For real geo math this is wrong, but for PII redaction in T1
    social derive (where we round res-5 to res-3) it's a deterministic 1:1
    mapping and an analyst can recover the upstream cell. Phase 2 should
    replace this with the real h3 library (`h3-py`) when available in the pod.
    """
    if not cell:
        return None
    if target_res >= 5:
        return cell
    # H3 res-5 cell IDs are 15 hex chars; we trim to res-3 ~ 13 chars heuristic.
    keep = max(8, 15 - max(0, 5 - target_res))
    return cell[:keep]


def _category_to_mode(category: str, hint: str | None = None) -> str:
    if hint in {"reuse_then_ritual", "reuse_only"}:
        return hint
    return CATEGORY_MODE.get(category, "reuse_then_ritual")


# ── XRPC handlers ──────────────────────────────────────────────────────


async def task_otakiage_item_submit(  # noqa: PLR0913 — XRPC arity
    ownerDid: str = "",
    category: str = "",
    title: str = "",
    storyText: str = "",
    photoBlobKeys: list | None = None,
    h3Cell: str = "",
    lat: float | None = None,
    lng: float | None = None,
    weightKgClass: str = "light",
    modeHint: str = "",
    **_: Any,
) -> dict[str, Any]:
    """com.etzhayyim.apps.otakiage.submitItem — register a new item, auto reuse_open."""
    if not ownerDid or not category or not title:
        return {"ok": False, "state": "submitted", "error": "ownerDid/category/title required"}
    mode = _category_to_mode(category, modeHint or None)
    rkey = _content_addressed_rkey(ownerDid, category, title, str(time.time_ns()))
    item_uri = f"at://{ownerDid}/com.etzhayyim.apps.otakiage.item/{rkey}"
    photos_json = json.dumps(list(photoBlobKeys or []))
    state = "reuse_open"  # auto-transition: submitted → reuse_open
    now = _now_iso()
    today = _today().isoformat()
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_otakiage_item (
              vertex_id, owner_did, item_id, category, title, story_text, photo_blob_keys,
              h3_cell, h3_res, lat, lng, weight_kg_class, mode, state, donor_did,
              created_at, created_date, sensitivity_ord, org_id, user_id, actor_id
            ) VALUES (
              %s, %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s, %s, %s
            )
            """,
            (
                item_uri, ownerDid, rkey, category, title, storyText or None, photos_json,
                h3Cell or None, 5 if h3Cell else None, lat, lng, weightKgClass, mode, state, ownerDid,
                now, today, 0, ownerDid, ownerDid, "otakiage.item.submit",
            ),
        )
        # owner edge
        owner_edge_id = f"otakiage:{rkey}:owner"
        _res = client.q(
            """
            INSERT INTO edge_otakiage_item_owner (
              edge_id, owner_did, src_vid, dst_vid, role,
              created_at, created_date, sensitivity_ord, org_id, user_id, actor_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner_edge_id, ownerDid, item_uri, ownerDid, "owns",
                now, today, 0, ownerDid, ownerDid, "otakiage.item.submit",
            ),
        )
    return {"ok": True, "itemUri": item_uri, "state": state, "mode": mode, "h3Cell": h3Cell or None}


async def task_otakiage_reuse_request_submit(  # noqa: PLR0913
    itemUri: str = "",
    requesterDid: str = "",
    message: str = "",
    h3Cell: str = "",
    lat: float | None = None,
    lng: float | None = None,
    preferredHandoverDate: str = "",
    **_: Any,
) -> dict[str, Any]:
    """com.etzhayyim.apps.otakiage.requestReuse."""
    if not itemUri or not requesterDid:
        return {"ok": False, "error": "itemUri/requesterDid required"}
    rkey = _content_addressed_rkey(itemUri, requesterDid, str(time.time_ns()))
    request_uri = f"at://{requesterDid}/com.etzhayyim.apps.otakiage.reuseRequest/{rkey}"
    now = _now_iso()
    today = _today().isoformat()
    # Phase 1: distance approximation = 0 if both cells set, else NULL.
    distance_km: float | None = 0.0 if h3Cell else None
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_otakiage_reuse_request (
              vertex_id, owner_did, request_id, item_uri, requester_did, message,
              h3_cell, lat, lng, distance_km, preferred_handover_date, state,
              created_at, created_date, sensitivity_ord, org_id, user_id, actor_id
            ) VALUES (
              %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s, %s, %s
            )
            """,
            (
                request_uri, requesterDid, rkey, itemUri, requesterDid, message or None,
                h3Cell or None, lat, lng, distance_km,
                preferredHandoverDate or None, "pending",
                now, today, 0, requesterDid, requesterDid, "otakiage.reuse.requestSubmit",
            ),
        )
    return {"ok": True, "reuseRequestUri": request_uri, "distanceKm": distance_km, "withinAdjacentCells": True}


async def task_otakiage_reuse_find_candidates(maxItems: int = 100, **_: Any) -> dict[str, Any]:
    """R/PT1H BPMN — count reuse_open items per H3 cell (push-notify is Phase 2)."""
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"SELECT h3_cell, category, weight_kg_class, COUNT(*) AS c "
            f"FROM vertex_otakiage_item "
            f"WHERE state = 'reuse_open' AND h3_cell IS NOT NULL "
            f"GROUP BY h3_cell, category, weight_kg_class "
            f"LIMIT {int(maxItems)}"
        )
        rows = _res or []
    cells = {r[0] for r in rows if r and r[0]}
    return {"candidateCount": len(rows), "cellsScanned": len(cells)}


async def task_otakiage_reuse_expire_open(  # noqa: PLR0913
    ttlDays: int = REUSE_TTL_DAYS, maxItems: int = 500, **_: Any,
) -> dict[str, Any]:
    """R/PT24H BPMN — sweep reuse_open older than TTL.

    Category-aware transition (ADR-2605081700 §8):
      - reuse_then_ritual mode → ritual_pending
      - reuse_only mode (kagu/kaden) → reuse_expired (留まる)
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=int(ttlDays))).strftime("%Y-%m-%dT%H:%M:%SZ")
    moved_ritual = 0
    stayed_expired = 0
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"SELECT vertex_id, mode FROM vertex_otakiage_item "
            f"WHERE state = 'reuse_open' AND created_at < %s "
            f"LIMIT {int(maxItems)}",
            (cutoff,),
        )
        candidates = _res or []
        for vertex_id, mode in candidates:
            new_state = "ritual_pending" if mode == "reuse_then_ritual" else "reuse_expired"
            _res = client.q(
                "UPDATE vertex_otakiage_item SET state = %s WHERE vertex_id = %s",
                (new_state, vertex_id),
            )
            if new_state == "ritual_pending":
                moved_ritual += 1
            else:
                stayed_expired += 1
    return {"expiredCount": len(candidates), "movedToRitualPending": moved_ritual, "stayedReuseExpired": stayed_expired}


async def task_otakiage_handover_confirm(  # noqa: PLR0913
    itemUri: str = "",
    reuseRequestUri: str = "",
    donorDid: str = "",
    recipientDid: str = "",
    handoverPhotoBlobKey: str = "",
    gratitudeText: str = "",
    skipSocialAnnounce: bool = False,
    **_: Any,
) -> dict[str, Any]:
    """com.etzhayyim.apps.otakiage.confirmHandover — terminal: state → handed_over."""
    if not itemUri or not donorDid or not recipientDid:
        return {"ok": False, "error": "itemUri/donorDid/recipientDid required"}
    rkey = _content_addressed_rkey(itemUri, recipientDid, str(time.time_ns()))
    handover_uri = f"at://{donorDid}/com.etzhayyim.apps.otakiage.handover/{rkey}"
    now = _now_iso()
    today = _today().isoformat()
    cancelled = 0
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_otakiage_handover (
              vertex_id, owner_did, handover_id, item_uri, reuse_request_uri,
              donor_did, recipient_did, handover_at, handover_photo_blob_key, gratitude_text,
              created_at, created_date, sensitivity_ord, org_id, user_id, actor_id
            ) VALUES (
              %s, %s, %s, %s, %s,
              %s, %s, %s, %s, %s,
              %s, %s, %s, %s, %s, %s
            )
            """,
            (
                handover_uri, donorDid, rkey, itemUri, reuseRequestUri or None,
                donorDid, recipientDid, now, handoverPhotoBlobKey or None, gratitudeText or None,
                now, today, 0, donorDid, donorDid, "otakiage.handover.confirm",
            ),
        )
        _res = client.q(
            "UPDATE vertex_otakiage_item SET state = 'handed_over' WHERE vertex_id = %s",
            (itemUri,),
        )
        # Cancel sibling pending reuse_requests
        _res = client.q(
            "UPDATE vertex_otakiage_reuse_request SET state = 'cancelled' "
            "WHERE item_uri = %s AND state = 'pending' "
            "AND vertex_id <> %s",
            (itemUri, reuseRequestUri or ""),
        )
        # Edge: item → handover
        edge_id = f"otakiage:{rkey}:handover"
        _res = client.q(
            """
            INSERT INTO edge_otakiage_item_handover (
              edge_id, owner_did, src_vid, dst_vid, role,
              created_at, created_date, sensitivity_ord, org_id, user_id, actor_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                edge_id, donorDid, itemUri, handover_uri, "handed-over-via",
                now, today, 0, donorDid, donorDid, "otakiage.handover.confirm",
            ),
        )
    return {
        "ok": True,
        "handoverUri": handover_uri,
        "itemState": "handed_over",
        "cancelledReuseRequests": cancelled,
        "socialAnnounceQueued": not skipSocialAnnounce,
    }


async def task_otakiage_ritual_request(
    itemUri: str = "",
    matsuriUri: str = "",
    donorMessage: str = "",
    skipReuse: bool = False,
    **_: Any,
) -> dict[str, Any]:
    """com.etzhayyim.apps.otakiage.requestRitual — state → ritual_pending.

    Rejected for kagu/kaden (mode=reuse_only).
    """
    if not itemUri:
        return {"ok": False, "error": "itemUri required"}
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT mode, category, state FROM vertex_otakiage_item WHERE vertex_id = %s",
            (itemUri,),
        )
        row = (_res[0] if _res else None)
        if not row:
            return {"ok": False, "error": "item not found"}
        mode, category, state = row
        if mode == "reuse_only":
            return {"ok": False, "rejectedReason": f"category {category} is reuse_only and cannot be ritualized"}
        if state in {"handed_over", "ritualized"}:
            return {"ok": False, "rejectedReason": f"item already terminal state={state}"}

        # Auto-assign matsuri if none provided: pick the next upcoming matsuri whose
        # category_scope JSON array contains this category.
        if not matsuriUri:
            _res = client.q(
                "SELECT vertex_id, scheduled_date, category_scope "
                "FROM vertex_otakiage_matsuri "
                "WHERE state IN ('open', 'preparing') AND scheduled_date >= CURRENT_DATE "
                "ORDER BY scheduled_date ASC LIMIT 50"
            )
            for v_id, sched_date, scope_json in _res or []:
                try:
                    scope = json.loads(scope_json or "[]")
                except Exception:
                    scope = []
                if category in scope:
                    matsuriUri = v_id  # noqa: N806 — XRPC param name
                    break

        _res = client.q(
            "UPDATE vertex_otakiage_item SET state = 'ritual_pending', story_text = COALESCE(story_text, '') || %s "
            "WHERE vertex_id = %s",
            (f"\n\n[ritual donor message]\n{donorMessage}" if donorMessage else "", itemUri),
        )
        scheduled = None
        if matsuriUri:
            _res = client.q(
                "SELECT scheduled_date FROM vertex_otakiage_matsuri WHERE vertex_id = %s",
                (matsuriUri,),
            )
            r = (_res[0] if _res else None)
            scheduled = r[0].isoformat() if r and r[0] else None
    _ = skipReuse  # currently unused; reserved for explicit skip path
    return {"ok": True, "itemState": "ritual_pending", "matsuriUri": matsuriUri or "", "scheduledDate": scheduled}


async def task_otakiage_ritual_issue_certificate(
    matsuriUri: str = "",
    ceremonyDate: str = "",
    ceremonyPhotoBlobKey: str = "",
    displayText: str = "",
    **_: Any,
) -> dict[str, Any]:
    """com.etzhayyim.apps.otakiage.issueCertificate — terminal: ritual_pending items → ritualized."""
    if not matsuriUri:
        return {"ok": False, "error": "matsuriUri required"}
    now = _now_iso()
    today = _today().isoformat()
    ceremony_at = ceremonyDate or now

    if True:

        client = get_kotoba_client()
        _res = client.q(
            "SELECT name, category_scope FROM vertex_otakiage_matsuri WHERE vertex_id = %s",
            (matsuriUri,),
        )
        m = (_res[0] if _res else None)
        if not m:
            return {"ok": False, "error": "matsuri not found"}
        matsuri_name, scope_json = m
        try:
            scope = json.loads(scope_json or "[]")
        except Exception:
            scope = []

        # Pull all ritual_pending items whose category is in scope.
        _res = client.q(
            """
            SELECT vertex_id, donor_did, category FROM vertex_otakiage_item
            WHERE state = 'ritual_pending'
            """
        )
        candidates = [(v, d, c) for v, d, c in (_res or []) if (not scope) or c in scope]

        item_uris = [v for v, _, _ in candidates]
        donor_dids = list({d for _, d, _ in candidates})
        breakdown: dict[str, int] = {}
        for _, _, c in candidates:
            breakdown[c] = breakdown.get(c, 0) + 1

        # Build ritual + certificate URIs
        ritual_rkey = _content_addressed_rkey(matsuriUri, ceremony_at, "ritual")
        cert_rkey = _content_addressed_rkey(matsuriUri, ceremony_at, "certificate")
        ritual_uri = f"at://{PATH_DID_RITUAL}/com.etzhayyim.apps.otakiage.ritual/{ritual_rkey}"
        cert_uri = f"at://{PATH_DID_RITUAL}/com.etzhayyim.apps.otakiage.certificate/{cert_rkey}"

        # Compose certificate JSON (Phase 1 = AT Record JSON only, Phase 2 = ERC725 anchor)
        if not displayText:
            parts = [f"{n} 体" if c in {"nuigurumi", "ningyo"} else f"{n} 点" for c, n in breakdown.items()]
            displayText = f"{matsuri_name} にて {', '.join(parts) or '物品'} を謹んでお焚き上げいたしました"
        cert_json = {
            "$type": "com.etzhayyim.apps.otakiage.certificate",
            "ritualUri": ritual_uri,
            "itemUris": item_uris,
            "donorDids": donor_dids,
            "issuedAt": now,
            "issuer": {
                "name": "etzhayyim",
                "kind": "religious-corporation",
                "did": PATH_DID_RITUAL,
            },
            "displayText": displayText,
            "categoryBreakdown": breakdown,
            "matsuriUri": matsuriUri,
            "photoBlobKey": ceremonyPhotoBlobKey or None,
            "version": "1.0",
        }

        # INSERT ritual
        _res = client.q(
            """
            INSERT INTO vertex_otakiage_ritual (
              vertex_id, owner_did, ritual_id, matsuri_uri, item_uris, item_count,
              ceremony_date, ceremony_photo_blob_key, certificate_uri, state,
              created_at, created_date, sensitivity_ord, org_id, user_id, actor_id
            ) VALUES (
              %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s,
              %s, %s, %s, %s, %s, %s
            )
            """,
            (
                ritual_uri, PATH_DID_RITUAL, ritual_rkey, matsuriUri, json.dumps(item_uris), len(item_uris),
                ceremony_at, ceremonyPhotoBlobKey or None, cert_uri, "completed",
                now, today, 0, PATH_DID_RITUAL, PATH_DID_RITUAL, "otakiage.ritual.issueCertificate",
            ),
        )
        # INSERT certificate
        _res = client.q(
            """
            INSERT INTO vertex_otakiage_certificate (
              vertex_id, owner_did, certificate_id, ritual_uri, matsuri_uri, item_uris, item_count,
              donor_dids, issued_at, issuer_did, issuer_name, display_text, category_breakdown,
              photo_blob_key, certificate_json, anchor_token_id, version,
              created_at, created_date, sensitivity_ord, org_id, user_id, actor_id
            ) VALUES (
              %s, %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s,
              %s, %s, %s, %s, %s, %s
            )
            """,
            (
                cert_uri, PATH_DID_RITUAL, cert_rkey, ritual_uri, matsuriUri, json.dumps(item_uris), len(item_uris),
                json.dumps(donor_dids), now, PATH_DID_RITUAL, "etzhayyim", displayText, json.dumps(breakdown),
                ceremonyPhotoBlobKey or None, json.dumps(cert_json, ensure_ascii=False), None, "1.0",
                now, today, 0, PATH_DID_RITUAL, PATH_DID_RITUAL, "otakiage.ritual.issueCertificate",
            ),
        )
        # Mark all items ritualized + edges
        for v, _, _ in candidates:
            _res = client.q(
                "UPDATE vertex_otakiage_item SET state = 'ritualized' WHERE vertex_id = %s",
                (v,),
            )
            edge_id = f"otakiage:{ritual_rkey}:{_content_addressed_rkey(v, 'ritual')[:12]}"
            _res = client.q(
                """
                INSERT INTO edge_otakiage_item_ritual (
                  edge_id, owner_did, src_vid, dst_vid, role,
                  created_at, created_date, sensitivity_ord, org_id, user_id, actor_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    edge_id, PATH_DID_RITUAL, v, ritual_uri, "ritualized-via",
                    now, today, 0, PATH_DID_RITUAL, PATH_DID_RITUAL, "otakiage.ritual.issueCertificate",
                ),
            )
        cert_edge_id = f"otakiage:{ritual_rkey}:cert"
        _res = client.q(
            """
            INSERT INTO edge_otakiage_ritual_certificate (
              edge_id, owner_did, src_vid, dst_vid, role,
              created_at, created_date, sensitivity_ord, org_id, user_id, actor_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                cert_edge_id, PATH_DID_RITUAL, ritual_uri, cert_uri, "certified-by",
                now, today, 0, PATH_DID_RITUAL, PATH_DID_RITUAL, "otakiage.ritual.issueCertificate",
            ),
        )

    # Phase 2b1: auto-queue the freshly-issued certificate for ERC725
    # anchoring. Failure is non-fatal — the sweep BPMN can still pick the
    # certificate up later via direct anchorCertificate XRPC.
    try:
        await task_otakiage_certificate_anchor(
            certificateUri=cert_uri,
            chain=os.environ.get("OTAKIAGE_DEFAULT_ANCHOR_CHAIN", _DEFAULT_ANCHOR_CHAIN),
            force=False,
        )
    except Exception:
        # Don't block ritual completion on anchor queue failure.
        pass

    return {
        "ok": True,
        "certificateUri": cert_uri,
        "ritualUri": ritual_uri,
        "itemCount": len(item_uris),
        "categoryBreakdown": json.dumps(breakdown),
        "anchorTokenId": "",
    }


async def task_otakiage_matsuri_schedule_submit(  # noqa: PLR0913
    name: str = "",
    scheduledDate: str = "",
    categoryScope: list | None = None,
    capacity: int = 0,
    locationH3: str = "",
    description: str = "",
    **_: Any,
) -> dict[str, Any]:
    """com.etzhayyim.apps.otakiage.scheduleMatsuri."""
    if not name or not scheduledDate or not categoryScope:
        return {"ok": False, "error": "name/scheduledDate/categoryScope required"}
    rkey = _content_addressed_rkey(name, scheduledDate, str(uuid.uuid4()))
    matsuri_uri = f"at://{PATH_DID_MATSURI}/com.etzhayyim.apps.otakiage.matsuri/matsuri-{rkey}"
    now = _now_iso()
    today = _today().isoformat()
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_otakiage_matsuri (
              vertex_id, owner_did, matsuri_id, name, category_scope, scheduled_date,
              capacity, registered_count, location_h3, description, state,
              created_at, created_date, sensitivity_ord, org_id, user_id, actor_id
            ) VALUES (
              %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s, %s,
              %s, %s, %s, %s, %s, %s
            )
            """,
            (
                matsuri_uri, PATH_DID_MATSURI, rkey, name, json.dumps(list(categoryScope)),
                scheduledDate, int(capacity), 0, locationH3 or None, description or None, "open",
                now, today, 0, PATH_DID_MATSURI, PATH_DID_MATSURI, "otakiage.matsuri.scheduleSubmit",
            ),
        )
    return {"ok": True, "matsuriUri": matsuri_uri}


async def task_otakiage_matsuri_seed_next_month(**_: Any) -> dict[str, Any]:
    """cron 月初 — seed next-month matsuri events from annual calendar template.

    Annual template (by month):
      April:    人形供養祭 (春) + 絵本供養祭
      August:   おもちゃ供養祭
      November: 人形供養祭 (秋)
    """
    now = datetime.now(timezone.utc).date()
    # Compute the first day of next month
    if now.month == 12:
        next_month = date(now.year + 1, 1, 1)
    else:
        next_month = date(now.year, now.month + 1, 1)
    yyyymm = next_month.strftime("%Y%m")
    seeded = 0
    skipped = 0
    template: list[tuple[str, list[str], int]] = []  # (slug, categoryScope, day_of_month)
    if next_month.month == 4:
        template = [
            ("haru-ningyo", ["ningyo", "nuigurumi"], 15),
            ("ehon", ["ehon", "jidousho"], 20),
        ]
    elif next_month.month == 8:
        template = [("omocha", ["omocha"], 8)]
    elif next_month.month == 11:
        template = [("aki-ningyo", ["ningyo", "nuigurumi"], 15)]

    if not template:
        return {"seededCount": 0, "skippedCount": 0}

    now_iso = _now_iso()
    today = _today().isoformat()
    if True:
        client = get_kotoba_client()
        for slug, scope, dom in template:
            sched_date = date(next_month.year, next_month.month, dom).isoformat()
            vertex_id = f"at://{PATH_DID_MATSURI}/com.etzhayyim.apps.otakiage.matsuri/matsuri-{slug}-{yyyymm}"
            matsuri_id = f"matsuri-{slug}-{yyyymm}"
            _res = client.q(
                "SELECT 1 FROM vertex_otakiage_matsuri WHERE vertex_id = %s LIMIT 1",
                (vertex_id,),
            )
            if (_res[0] if _res else None):
                skipped += 1
                continue
            display_name = {
                "haru-ningyo": f"春の人形供養祭 {next_month.year}",
                "aki-ningyo": f"秋の人形供養祭 {next_month.year}",
                "ehon": f"絵本供養祭 {next_month.year}",
                "omocha": f"おもちゃ供養祭 {next_month.year}",
            }.get(slug, f"{slug} {next_month.year}")
            description = f"{display_name} — etzhayyim 主催の digital ritual。Phase 1 は永続証跡 (AT Record JSON) を発行。"
            _res = client.q(
                """
                INSERT INTO vertex_otakiage_matsuri (
                  vertex_id, owner_did, matsuri_id, name, category_scope, scheduled_date,
                  capacity, registered_count, location_h3, description, state,
                  created_at, created_date, sensitivity_ord, org_id, user_id, actor_id
                ) VALUES (
                  %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    vertex_id, PATH_DID_MATSURI, matsuri_id, display_name, json.dumps(scope),
                    sched_date, 0, 0, None, description, "open",
                    now_iso, today, 0, PATH_DID_MATSURI, PATH_DID_MATSURI, "otakiage.matsuri.seedNextMonth",
                ),
            )
            seeded += 1
    return {"seededCount": seeded, "skippedCount": skipped}


# ── Phase 2b1 — ERC725 certificate anchor ────────────────────────────


# Default anchor target. Phase 2b1 has no real on-chain submission so
# the contract address is a placeholder; Phase 2b2 will inject the real
# deployed contract address via env var ANCHOR_CONTRACT_BASE.
_DEFAULT_ANCHOR_CHAIN = "base"
_PLACEHOLDER_CONTRACT = {
    "base":         "0x0000000000000000000000000000000000000000",
    "base-sepolia": "0x0000000000000000000000000000000000000000",
    "polygon":      "0x0000000000000000000000000000000000000000",
    "polygon-amoy": "0x0000000000000000000000000000000000000000",
}


def _resolve_anchor_contract(chain: str) -> str:
    """Phase 2b1: return env override if present, else placeholder."""
    env_key = "ANCHOR_CONTRACT_" + chain.upper().replace("-", "_")
    return os.environ.get(env_key) or _PLACEHOLDER_CONTRACT.get(chain) or _PLACEHOLDER_CONTRACT["base"]


async def task_otakiage_certificate_anchor(  # noqa: PLR0913
    certificateUri: str = "",
    chain: str = "",
    force: bool = False,
    **_: Any,
) -> dict[str, Any]:
    """com.etzhayyim.apps.otakiage.anchorCertificate — Phase 2b1 = queue only.

    1. Validate certificate exists.
    2. Compute content_hash = sha256(certificate_json) — stable token URI base.
    3. Set anchor_status = 'queued', anchor_chain, anchor_contract,
       content_hash. Phase 2b2 sweep will progress queued → submitted →
       anchored via real on-chain calls.
    4. force=true allows retry of failed certificates.
    """
    if not certificateUri:
        return {"ok": False, "anchorStatus": "pending", "error": "certificateUri required"}
    target_chain = (chain or _DEFAULT_ANCHOR_CHAIN).lower()
    if target_chain not in {"base", "base-sepolia", "polygon", "polygon-amoy"}:
        return {"ok": False, "anchorStatus": "pending", "error": f"unsupported chain {target_chain}"}
    contract = _resolve_anchor_contract(target_chain)
    now = _now_iso()

    if True:

        client = get_kotoba_client()
        _res = client.q(
            "SELECT certificate_json, anchor_status FROM vertex_otakiage_certificate "
            "WHERE vertex_id = %s",
            (certificateUri,),
        )
        row = (_res[0] if _res else None)
        if not row:
            return {"ok": False, "anchorStatus": "pending", "error": "certificate not found"}
        cert_json, current_status = row
        # Normalize: anchored or submitted should be left alone unless force=true.
        if current_status in {"submitted", "anchored"} and not force:
            return {
                "ok": True,
                "certificateUri": certificateUri,
                "anchorStatus": current_status,
                "chain": target_chain,
                "contentHash": "",
                "error": f"already {current_status}; pass force=true to re-anchor",
            }

        content_hash = hashlib.sha256(
            (cert_json or "").encode("utf-8") if isinstance(cert_json, str) else b""
        ).hexdigest()

        _res = client.q(
            "UPDATE vertex_otakiage_certificate "
            "SET anchor_status = 'queued', anchor_chain = %s, anchor_contract = %s, "
            "    content_hash = %s, failure_reason = NULL, anchored_at = NULL "
            "WHERE vertex_id = %s",
            (target_chain, contract, content_hash, certificateUri),
        )

    return {
        "ok": True,
        "certificateUri": certificateUri,
        "anchorStatus": "queued",
        "chain": target_chain,
        "contentHash": content_hash,
        "anchorTokenId": "",
        "txHash": "",
        "blockNumber": 0,
        "anchoredAt": now,
        "failureReason": "",
    }


async def task_otakiage_certificate_anchor_sweep(maxItems: int = 20, **_: Any) -> dict[str, Any]:
    """R/PT1H sweep — progress queued certificates through the anchor lifecycle.

    Phase 2b1 (this version):
      queued → submitted   (stub: assign deterministic token_id from content_hash)
      submitted → anchored (stub finalize: set anchored_at = now, no real tx_hash)

    Phase 2b2 (future):
      queued → submitted: ethers/viem `anchor.mint(tokenId, contentHash, donorDids)`
                          → keep returned tx_hash + block_number
      submitted → anchored: poll receipt with confirmations >= 3

    The sweep is idempotent and bounded by maxItems to keep gas cost (when
    Phase 2b2 wires real chain calls) predictable per fire.
    """
    processed = 0
    submitted = 0
    anchored = 0
    failed = 0
    now = _now_iso()

    if True:

        client = get_kotoba_client()
        # Phase: queued → submitted (stub)
        _res = client.q(
            f"SELECT vertex_id, content_hash FROM vertex_otakiage_certificate "
            f"WHERE anchor_status = 'queued' "
            f"LIMIT {int(maxItems)}"
        )
        queued_rows = list(_res or [])
        for v_id, ch in queued_rows:
            processed += 1
            if not ch:
                _res = client.q(
                    "UPDATE vertex_otakiage_certificate "
                    "SET anchor_status = 'failed', failure_reason = %s "
                    "WHERE vertex_id = %s",
                    ("missing content_hash", v_id),
                )
                failed += 1
                continue
            # Deterministic token_id from content_hash (16 hex chars = 64-bit).
            token_id = "0x" + ch[:16]
            _res = client.q(
                "UPDATE vertex_otakiage_certificate "
                "SET anchor_status = 'submitted', anchor_token_id = %s "
                "WHERE vertex_id = %s",
                (token_id, v_id),
            )
            submitted += 1

        # Phase: submitted → anchored (stub finalize). Phase 2b2 will only
        # advance on real receipt confirmations.
        _res = client.q(
            f"SELECT vertex_id, anchor_token_id FROM vertex_otakiage_certificate "
            f"WHERE anchor_status = 'submitted' "
            f"LIMIT {int(maxItems)}"
        )
        submitted_rows = list(_res or [])
        for v_id, token_id in submitted_rows:
            processed += 1
            stub_tx = "stub:" + (token_id or "")[:18]
            _res = client.q(
                "UPDATE vertex_otakiage_certificate "
                "SET anchor_status = 'anchored', anchored_at = %s, anchor_tx_hash = %s, "
                "    anchor_block_number = NULL "
                "WHERE vertex_id = %s",
                (now, stub_tx, v_id),
            )
            anchored += 1

    return {
        "processed": processed,
        "submitted": submitted,
        "anchored": anchored,
        "failed": failed,
    }


# ── Phase 2 — Conversational LangGraph agent ─────────────────────────


async def task_otakiage_agent_chat(  # noqa: PLR0913
    message: str = "",
    callerDid: str = "",
    threadId: str = "",
    intentHint: str = "",
    h3Cell: str = "",
    maxTurns: int = 10,
    **_: Any,
) -> dict[str, Any]:
    """com.etzhayyim.apps.otakiage.agentChat — invoke LangGraph (otakiage.agent.chat.v1).

    See `kotodama/agents/otakiage_agent.py` for the graph definition.
    Multi-turn conversation: load_history → parse_intent → branch
    (extract_details / search_candidates / resolve_matsuri / fetch_info /
    compose_reply) → compose_reply → persist_turn.
    """
    if not message or not callerDid:
        return {"ok": False, "error": "message/callerDid required"}
    # Lazy import: keeps the otakiage primitive module importable for
    # workers that haven't installed langgraph yet (e.g. shared zeebe-worker).
    try:
        from kotodama.agents.otakiage_agent import otakiage_chat_graph
    except Exception as e:
        return {"ok": False, "error": f"langgraph not available: {e}"}

    final = await otakiage_chat_graph.ainvoke({
        "userMessage": message,
        "callerDid": callerDid,
        "threadId": threadId or "",
        "intentHint": intentHint or "",
        "h3Cell": h3Cell or "",
        "maxTurns": int(maxTurns or 10),
    })
    out = dict(final)
    return {
        "ok": not bool(out.get("error")),
        "threadId": out.get("threadId") or "",
        "reply": out.get("reply") or "",
        "intent": out.get("intent") or "unknown",
        "actions": out.get("actions") or [],
        "draftItem": out.get("draftItem") or {},
        "candidates": out.get("candidates") or [],
        "llmCalls": int(out.get("llmCalls") or 0),
        "error": out.get("error") or "",
    }


async def task_otakiage_social_compose_announce(  # noqa: PLR0913
    eventKind: str = "",
    refUri: str = "",
    authorDid: str = "",
    summary: str = "",
    **_: Any,
) -> dict[str, Any]:
    """socialAnnounce inner step — compose post text + redact PII, return for pds.dispatch."""
    h3_res3 = _h3_truncate_to_res(None, 3)  # Phase 1: caller-provided H3 already redacted upstream
    if eventKind == "handover":
        text = f"♻️ 物が新しいお家へと渡りました。{summary or '想いと共にありがとうの気持ちが循環しました'} #otakiage"
    elif eventKind == "ritual":
        text = f"✨ お焚き上げを謹んで執り行いました。{summary or '物への感謝と共にお別れいたしました'} #otakiage"
    else:
        text = summary or "otakiage 更新"
    # Truncate to AT Protocol post text limit (300 graphemes ~ 1000 bytes)
    if len(text) > 280:
        text = text[:277] + "..."
    return {"postText": text, "h3Res3": h3_res3 or ""}


# ── Worker registration ────────────────────────────────────────────────


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    """Register all otakiage task types onto the LangServer worker.

    Static manifest (BPMN worker-task coverage linter discovery):

      task_type="otakiage.item.submit"
      task_type="otakiage.reuse.requestSubmit"
      task_type="otakiage.reuse.findCandidates"
      task_type="otakiage.reuse.expireOpen"
      task_type="otakiage.handover.confirm"
      task_type="otakiage.ritual.request"
      task_type="otakiage.ritual.issueCertificate"
      task_type="otakiage.matsuri.scheduleSubmit"
      task_type="otakiage.matsuri.seedNextMonth"
      task_type="otakiage.social.composeAnnounce"
      task_type="otakiage.agent.chat"
      task_type="otakiage.certificate.anchor"
      task_type="otakiage.certificate.anchorSweep"
    """
    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False, timeout_ms=ms or timeout_ms)(fn)

    # Eager import so the LangGraph graph_id "otakiage.agent.chat.v1" is
    # registered in langgraph_registry before any job arrives. Tolerate
    # ImportError so workers without langgraph (legacy environments)
    # still register the non-LLM primitives.
    try:
        from kotodama.agents import otakiage_agent as _otakiage_agent
        _ = _otakiage_agent  # used for side-effect registration
    except Exception:
        pass

    t("otakiage.item.submit",                task_otakiage_item_submit)
    t("otakiage.reuse.requestSubmit",        task_otakiage_reuse_request_submit)
    t("otakiage.reuse.findCandidates",       task_otakiage_reuse_find_candidates)
    t("otakiage.reuse.expireOpen",           task_otakiage_reuse_expire_open,           ms=300_000)
    t("otakiage.handover.confirm",           task_otakiage_handover_confirm)
    t("otakiage.ritual.request",             task_otakiage_ritual_request)
    t("otakiage.ritual.issueCertificate",    task_otakiage_ritual_issue_certificate,    ms=120_000)
    t("otakiage.matsuri.scheduleSubmit",     task_otakiage_matsuri_schedule_submit)
    t("otakiage.matsuri.seedNextMonth",      task_otakiage_matsuri_seed_next_month)
    t("otakiage.social.composeAnnounce",     task_otakiage_social_compose_announce)
    # Phase 2 — LangGraph conversational agent (ADR-2605072000).
    # 90s ceiling because 3 LLM call chain (parse_intent + extract_details +
    # compose_reply) can stack 60s+ on RunPod cold-start.
    t("otakiage.agent.chat",                 task_otakiage_agent_chat,                  ms=90_000)
    # Phase 2b1 — ERC725 certificate anchoring (ADR-0074, etzhayyim
    # blockchain 登記). State tracking only in 2b1; 2b2 wires real
    # ethers/viem on-chain calls.
    t("otakiage.certificate.anchor",         task_otakiage_certificate_anchor)
    t("otakiage.certificate.anchorSweep",    task_otakiage_certificate_anchor_sweep,    ms=600_000)


# Avoid unused import linter complaint (os imported for env access in subclass extensions)
_ = os
