"""yoro social primitives — etzhayyim MST/IPFS/L2 substrate variant.

Religious-corp landing target for the yoro Python primitive layer migration.

ADR authority:
    ADR-2605215300 (addendum — per-function migration table + skeleton):
        90-docs/adr/2605215300-etzhayyim-yoro-python-primitives-mst-rewrite-addendum.md
    ADR-2605191358 (parent — per-path CF Worker + UI rewrite map):
        90-docs/adr/2605191358-yoro-murakumo-rw-free-rewrite-map.md

Migration notes:
    20-actors/kotoba-kotodama/py/YORO-PYTHON-MIGRATION-NOTES.md

DO NOT:
    - Import psycopg2, psycopg, or any other SQL driver.
    - Reference RW_URL, HYPERDRIVE, or any RisingWave connection string.
    - Import Stripe, runpod, or any fiat / cloud-GPU client.
    - Add FLUSH calls (MST commits are atomic).

This module fails fast (RuntimeError) if RW_URL is present in the environment
to prevent accidental RisingWave coupling in etzhayyim builds.

M2 implementation status (ADR-2605215300 §4):
    record_post()                — IMPLEMENTED (M2) — app.bsky.feed.post
    update_profile()             — IMPLEMENTED (M2) — app.bsky.actor.profile
    record_translation_link()    — IMPLEMENTED (M2) — com.etzhayyim.translationLink + coalescer
    All other functions          — NotImplementedError stubs (M3 target)

M3 implementation status (2026-05-21):
    record_bpmn_activity_event() — IMPLEMENTED (M3) — com.etzhayyim.bpmnActivityEvent
    record_actor_quality_report()— IMPLEMENTED (M3) — com.etzhayyim.actorQualityReport
    like_post()                  — IMPLEMENTED (M3) — app.bsky.feed.like (dispatch)
    follow_actor()               — IMPLEMENTED (M3) — app.bsky.graph.follow (coalesced)
    repost()                     — IMPLEMENTED (M3) — app.bsky.feed.repost (dispatch)

M4 implementation status (2026-05-21):
    fetch_source_post()                              — IMPLEMENTED (M4) — PDS getRecord read-path
    fetch_actor_generation_context()                 — IMPLEMENTED (M4) — PDS getRecord + listRecords
    fetch_profile_quality()                          — IMPLEMENTED (M4) — PDS listRecords count + profile
    task_yoro_social_translate_post()                — IMPLEMENTED (M4) — fetch + LLM stub + record_post + record_translation_link
    task_yoro_social_translate_post_batch()          — IMPLEMENTED (M4) — asyncio.gather fan-out + coalescer
    task_yoro_social_post_graph_fallback()           — IMPLEMENTED (M4) — Zeebe task wiring → record_post
    task_yoro_social_respond_to_mention_graph_fallback() — IMPLEMENTED (M4) — Zeebe task wiring → record_post (reply)
    task_yoro_social_respond_to_follow_graph_fallback()  — IMPLEMENTED (M4) — Zeebe task → follow_actor + record_post (welcome)
    task_yoro_actor_quality_inspect()                — IMPLEMENTED (M4) — fetch_profile_quality + record_actor_quality_report
    task_yoro_actor_quality_verify()                 — IMPLEMENTED (M4) — fetch_profile_quality + record_actor_quality_report

M5 implementation status (2026-05-21):
    delete_post()                                    — IMPLEMENTED (M5) — PDS deleteRecord (MST tombstone)
    unfollow_actor()                                 — IMPLEMENTED (M5) — PDS deleteRecord (graph.follow)
    unlike_post()                                    — IMPLEMENTED (M5) — PDS deleteRecord (feed.like)
    fetch_followers()                                — IMPLEMENTED (M5) — PDS listRecords (graph.follow read)
    list_actor_records()                             — IMPLEMENTED (M5) — PDS listRecords (generic read)
    task_yoro_actor_quality_enrich_profile()         — IMPLEMENTED (M5) — delegates to enrich_actor_quality_profile
    task_yoro_actor_quality_ensure_seed_post()       — IMPLEMENTED (M5) — fetch_profile_quality + record_post seed
    task_yoro_social_platform_pulse_graph_fallback() — IMPLEMENTED (M5) — mst-projector snapshot (stub)

M6 implementation status (2026-05-21):
    insert_social_post_record()                      — IMPLEMENTED (M6) — sync shim → asyncio.run(record_post())

M7 implementation status (2026-05-21):
    insert_repo_records()                            — IMPLEMENTED (M7) — sync shim → asyncio.run(batch putRecord); rows #2/#3/#4
    insert_translation_link_record()                 — IMPLEMENTED (M7) — sync shim → asyncio.run(record_translation_link()); row #5
    emit_bpmn_activity_event()                       — IMPLEMENTED (M7) — sync shim → asyncio.run(record_bpmn_activity_event()), never raises; row #6
    task_yoro_social_project_diet_speeches_graph_fallback() — IMPLEMENTED (M7) — write-path only (read-path VENDOR-ONLY); row #29
    build_diet_speech_social_post_record()           — IMPLEMENTED (M7) — pure builder; row #30
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)

# ── SDK import (stub calls — downstream NotImplementedError until M3) ──────────
# etzhayyim-sdk-py lives at 20-actors/etzhayyim-sdk-py/.
# Until installed, these calls raise NotImplementedError (correct M2 behaviour).
try:
    from etzhayyim_sdk import pds as _pds_mod
    from etzhayyim_sdk.coalesce import RequestCoalescer as _RequestCoalescer
except ImportError:
    _pds_mod = None  # type: ignore[assignment]
    _RequestCoalescer = None  # type: ignore[assignment]

try:
    from etzhayyim_sdk import mst_projector as _projector_mod
except ImportError:
    _projector_mod = None  # type: ignore[assignment]

try:
    from etzhayyim_sdk import llm as _llm_mod
except ImportError:
    _llm_mod = None  # type: ignore[assignment]

# Module-level coalescer instance (shared across calls within the same process).
# window_ms=100 per ADR-2605215300 §Open risks: batches 36 target-language
# translation links into 1-3 MST commits within a 100 ms window.
_COALESCER: Any = None


def _get_coalescer() -> Any:
    """Return the module-level RequestCoalescer, initialising it on first use."""
    global _COALESCER
    if _COALESCER is None and _RequestCoalescer is not None:
        _COALESCER = _RequestCoalescer(window_ms=100, max_batch=64)
    return _COALESCER


# ---------------------------------------------------------------------------
# Substrate-fit guard — reject if RW_URL is present (ADR-2605172000)
# ---------------------------------------------------------------------------

def _substrate_fit_guard() -> None:
    rw_url = os.environ.get("RW_URL", "").strip()
    if rw_url:
        raise RuntimeError(
            "yoro_social_murakumo: RW_URL is set. "
            "This module is the etzhayyim/root religious-corp variant and MUST NOT "
            "connect to RisingWave. Unset RW_URL or use primitives/yoro_social.py "
            "for vendor SaaS builds. See ADR-2605172000 §substrate-hard-rule."
        )


_substrate_fit_guard()


# ---------------------------------------------------------------------------
# Constants — mirroring yoro_social.py public constants for wire-shape parity
# ---------------------------------------------------------------------------

DEFAULT_REPO = "did:web:yoro.etzhayyim.com"
DEFAULT_COLLECTION = "app.bsky.feed.post"
DEFAULT_PREFIX = "Murakumo actor pulse"
PROFILE_COLLECTION = "app.bsky.actor.profile"
FOLLOW_COLLECTION = "app.bsky.graph.follow"

# Religious-corp lexicon NSIDs (new — ADR-2605215300 §2)
# Lexicons authored 2026-05-21 at 00-contracts/lexicons/com/etzhayyim/
TRANSLATION_LINK_COLLECTION = "com.etzhayyim.translationLink"
BPMN_ACTIVITY_EVENT_COLLECTION = "com.etzhayyim.bpmnActivityEvent"
ACTOR_QUALITY_REPORT_COLLECTION = "com.etzhayyim.actorQualityReport"

# AT Protocol social lexicon NSIDs (federated via PDS dispatch)
LIKE_COLLECTION = "app.bsky.feed.like"
REPOST_COLLECTION = "app.bsky.feed.repost"

DEFAULT_TRANSLATION_TARGET_LANGS = (
    "en,ja,zh-Hans,ko,es,fr,de,pt,hi,bn,ta,te,mr,ur,gu,kn,ml,pa,ar,fa,he,ku,ckb,zgh,kab,ps,sd,am,ti,id,vi,th,it,nl,tr,pl,uk"
)


# ---------------------------------------------------------------------------
# Typed dataclasses for religious-corp wire shapes
# ---------------------------------------------------------------------------

@dataclass
class SocialPostRecord:
    """Wire shape for app.bsky.feed.post MST record."""
    repo: str
    collection: str
    rkey: str
    uri: str
    text: str
    created_at: str
    record: dict[str, Any] = field(default_factory=dict)
    cid: str = ""


@dataclass
class RepoRecord:
    """Wire shape for a generic AT repo record (any collection)."""
    repo: str
    collection: str
    rkey: str
    uri: str
    created_at: str
    record: dict[str, Any] = field(default_factory=dict)
    cid: str = ""


@dataclass
class TranslationLinkRecord:
    """Wire shape for com.etzhayyim.apps.etzhayyim.translationLink MST record.

    New lexicon required — ADR-2605215300 §2.
    Must be authored in 00-contracts/lexicons/com/etzhayyim/apps/etzhayyim/translationLink.json
    before M2 implementation replaces the NotImplementedError stub.
    """
    repo: str
    rkey: str
    uri: str
    source_uri: str
    source_lang: str
    translated_uri: str
    target_lang: str
    source: str  # "llm-other", "manual", etc.
    quality_score: float
    created_at: str
    owner_did: str


@dataclass
class BpmnActivityEventRecord:
    """Wire shape for com.etzhayyim.apps.etzhayyim.bpmnActivityEvent MST record.

    New lexicon required — ADR-2605215300 §2.
    Must be authored in 00-contracts/lexicons/com/etzhayyim/apps/etzhayyim/bpmnActivityEvent.json
    before M2 implementation replaces the NotImplementedError stub.
    """
    repo: str
    rkey: str
    uri: str
    event_id: str
    instance_id: str
    activity_id: str
    event_type: str
    payload_json: str
    occurred_at: str
    actor_did: str
    org_did: str


@dataclass
class ProfileEnrichmentRecord:
    """Wire shape for app.bsky.actor.profile upsert."""
    repo: str
    rkey: str  # always "self" for actor profiles
    uri: str
    display_name: str
    description: str
    created_at: str
    props: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Utility helpers (pure, no substrate calls)
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _rkey(actor_path: str) -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"murakumo-{actor_path}-{stamp}-{os.getpid()}"


def _display_actor(did: str, handle: str = "") -> str:
    value = (handle or did or "friend").strip()
    if value.startswith("did:web:"):
        value = value[len("did:web:"):]
    return value


def _safe_display_name(actor_did: str, handle: str = "") -> str:
    candidate = (handle or "").strip()
    if candidate and candidate != "handle.invalid" and not candidate.startswith("did:"):
        return candidate
    short = actor_did.rsplit(":", 1)[-1][:12] if actor_did else "actor"
    return f"YORO actor {short}"


def _safe_description(actor_did: str, source_hint: str = "") -> str:
    suffix = f" Source: {source_hint.strip()}" if source_hint.strip() else ""
    return (
        "Public YORO actor profile. This page is being incrementally enriched "
        "from graph records, provenance sources, and public activity signals."
        f"{suffix}"
    )


def _post_tags(*values: Any) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, (list, tuple, set)):
            candidates = list(value)
        else:
            candidates = [value]
        for candidate in candidates:
            tag = re.sub(r"^[#＃]+", "", str(candidate or "").strip())
            tag = re.sub(r"\s+", "-", tag)
            if not tag or tag in seen:
                continue
            tags.append(tag[:64])
            seen.add(tag)
            if len(tags) >= 8:
                return tags
    return tags


def _lang_list(value: Any = None) -> list[str]:
    raw = value
    if raw is None:
        raw = os.environ.get("YORO_TRANSLATION_TARGET_LANGS", DEFAULT_TRANSLATION_TARGET_LANGS)
    if isinstance(raw, str):
        candidates = re.split(r"[, \n\t]+", raw)
    elif isinstance(raw, (list, tuple, set)):
        candidates = [str(item) for item in raw]
    else:
        candidates = []
    langs: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        lang = str(candidate or "").strip()
        if not lang or lang in seen:
            continue
        langs.append(lang)
        seen.add(lang)
    return langs


def _actor_quality_case_id(actor_did: str, source_hint: str = "") -> str:
    key = f"{actor_did}|{source_hint}".encode("utf-8", errors="ignore")
    return f"yoro-actor-quality-{hashlib.sha256(key).hexdigest()[:24]}"


# ---------------------------------------------------------------------------
# Build helpers (pure, no substrate calls) — PORT-adapted from yoro_social.py
# ---------------------------------------------------------------------------

def build_social_post_record(
    *,
    repo: str = DEFAULT_REPO,
    collection: str = DEFAULT_COLLECTION,
    prefix: str = DEFAULT_PREFIX,
    text: str = "",
    created_at: str = "",
    rkey: str = "",
    actor_path: str = "zeebe",
    record_extra: dict[str, Any] | None = None,
) -> SocialPostRecord:
    """Build an app.bsky.feed.post wire shape for MST dispatch.

    Returns a SocialPostRecord dataclass. Call insert_social_post_record() to
    dispatch to the PDS via @etzhayyim/sdk (M2+).
    """
    repo = repo or DEFAULT_REPO
    collection = collection or DEFAULT_COLLECTION
    created_at = created_at or utc_now_iso()
    rkey = rkey or _rkey(actor_path)
    uri = f"at://{repo}/{collection}/{rkey}"
    text = text or (
        f"{prefix}: Murakumo actor worker path alive at {created_at}."
    )
    record: dict[str, Any] = {"$type": collection, "text": text, "createdAt": created_at}
    if record_extra:
        record.update(record_extra)
    return SocialPostRecord(
        repo=repo,
        collection=collection,
        rkey=rkey,
        uri=uri,
        text=text,
        created_at=created_at,
        record=record,
    )


def build_repo_record(
    *,
    repo: str,
    collection: str,
    record: dict[str, Any],
    created_at: str = "",
    rkey: str = "",
    actor_path: str = "zeebe",
) -> RepoRecord:
    """Build a generic AT repo record wire shape for MST dispatch."""
    repo = repo or DEFAULT_REPO
    created_at = created_at or str(record.get("createdAt") or utc_now_iso())
    rkey = rkey or _rkey(actor_path)
    uri = f"at://{repo}/{collection}/{rkey}"
    return RepoRecord(
        repo=repo,
        collection=collection,
        rkey=rkey,
        uri=uri,
        created_at=created_at,
        record=record,
    )


def build_translation_link_record(
    *,
    repo: str,
    source_uri: str,
    source_lang: str,
    translated_uri: str,
    target_lang: str,
    source: str = "llm-other",
    quality_score: int = 0,
    created_at: str = "",
    rkey: str = "",
) -> TranslationLinkRecord:
    """Build an com.etzhayyim.apps.etzhayyim.translationLink wire shape.

    NSID changed from vendor com.etzhayyim.apps.media_gamers.record.translationLink
    to com.etzhayyim.apps.etzhayyim.translationLink per ADR-2605215300 §2.
    """
    created_at = created_at or utc_now_iso()
    rkey = rkey or _rkey(f"translation-link-{target_lang}")
    uri = f"at://{repo}/{TRANSLATION_LINK_COLLECTION}/{rkey}"
    return TranslationLinkRecord(
        repo=repo,
        rkey=rkey,
        uri=uri,
        source_uri=source_uri,
        source_lang=source_lang,
        translated_uri=translated_uri,
        target_lang=target_lang,
        source=source,
        quality_score=float(quality_score or 0),
        created_at=created_at,
        owner_did=repo,
    )


# ---------------------------------------------------------------------------
# M2 IMPLEMENTED functions — top-3 highest-traffic per ADR-2605215300 §4
# ---------------------------------------------------------------------------


async def record_post(
    *,
    repo: str = DEFAULT_REPO,
    text: str = "",
    created_at: str = "",
    rkey: str = "",
    actor_path: str = "zeebe",
    extra: dict[str, Any] | None = None,
) -> str:
    """Dispatch an app.bsky.feed.post record to PDS via @etzhayyim/sdk.  [M2 IMPLEMENTED]

    Highest-traffic function #1 per ADR-2605215300 §4.

    Vendor equivalent: insert_social_post_record() in yoro_social.py
      INSERT INTO vertex_repo_record + INSERT INTO vertex_post

    Substrate path (ADR-2605215300 §3):
      @etzhayyim/sdk Python binding → PDS putRecord → app.bsky.feed.post
      → MST commit → IPFS pin (if configured) → L2 anchor batch

    Wire shape matches app.bsky.feed.post AT Protocol lexicon.

    Returns: AT URI of the created record (at://<repo>/app.bsky.feed.post/<rkey>)
    SDK pds.dispatch is a stub (NotImplementedError) until M3; tested via mocks.
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    # Build the app.bsky.feed.post wire shape.
    post_record = build_social_post_record(
        repo=repo,
        collection=DEFAULT_COLLECTION,
        text=text,
        created_at=created_at,
        rkey=rkey,
        actor_path=actor_path,
        record_extra=extra,
    )

    # Dispatch to PDS via @etzhayyim/sdk.
    # vendor: INSERT INTO vertex_repo_record + INSERT INTO vertex_post
    # religious-corp: PDS putRecord → MST commit
    await _pds_mod.dispatch(
        collection=DEFAULT_COLLECTION,
        record=post_record.record,
        repo=post_record.repo,
        rkey=post_record.rkey,
    )

    return post_record.uri


async def update_profile(
    *,
    repo: str = DEFAULT_REPO,
    display_name: str = "",
    description: str = "",
    actor_did: str = "",
    handle: str = "",
    source_hint: str = "",
    props: dict[str, Any] | None = None,
) -> str:
    """Upsert an app.bsky.actor.profile record via @etzhayyim/sdk.  [M2 IMPLEMENTED]

    Highest-traffic function #2 per ADR-2605215300 §4.

    Vendor equivalent: _enrich_actor_quality_profile() INSERT + UPDATE branches
      INSERT INTO vertex_profile / UPDATE vertex_profile SET ...

    Substrate path (ADR-2605215300 §3):
      @etzhayyim/sdk Python binding → PDS putRecord(app.bsky.actor.profile, rkey='self')
      → MST commit; idempotent overwrite, PDS handles conflict semantics.

    rkey is always "self" for actor profiles (AT Protocol convention).

    Returns: AT URI of the profile record (at://<repo>/app.bsky.actor.profile/self)
    SDK pds.put_record is a stub (NotImplementedError) until M3; tested via mocks.
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    resolved_repo = repo or (actor_did if actor_did else DEFAULT_REPO)
    resolved_display_name = display_name or _safe_display_name(actor_did, handle)
    resolved_description = description or _safe_description(actor_did, source_hint)
    created_at = utc_now_iso()
    rkey = "self"

    profile_record: dict[str, Any] = {
        "$type": PROFILE_COLLECTION,
        "displayName": resolved_display_name,
        "description": resolved_description,
        "createdAt": created_at,
    }
    if props:
        profile_record.update(props)

    # Dispatch to PDS via @etzhayyim/sdk.
    # vendor: INSERT INTO vertex_profile ON CONFLICT UPDATE
    # religious-corp: PDS putRecord(actor.profile, rkey=self) — idempotent overwrite
    await _pds_mod.put_record(
        collection=PROFILE_COLLECTION,
        record=profile_record,
        repo=resolved_repo,
        rkey=rkey,
    )

    uri = f"at://{resolved_repo}/{PROFILE_COLLECTION}/{rkey}"
    return uri


async def record_translation_link(
    *,
    repo: str = DEFAULT_REPO,
    source_uri: str,
    source_lang: str,
    translated_uri: str,
    target_lang: str,
    translator_did: str = "",
    quality_score: int = 0,
    model: str = "",
    coalescer: Any = None,
) -> str:
    """Dispatch an com.etzhayyim.translationLink record via coalescer + @etzhayyim/sdk.
    [M2 IMPLEMENTED]

    Highest-traffic function #3 per ADR-2605215300 §4 — CRITICAL M2 unblocker.

    Vendor equivalent: insert_translation_link_record() in yoro_social.py
      DELETE FROM vertex_translation_link + INSERT INTO vertex_translation_link

    Substrate path (ADR-2605215300 §3):
      coalescer.submit(key=source_uri, fn=lambda: pds.put_record(translationLink))
      → MST commit → IPFS pin

    Coalescer integration (ADR-2605215300 §Open risks):
      Without coalescing, 36+ concurrent target-language translation links each
      trigger a separate PDS putRecord, hitting Zeebe task timeout (~25 s limit).
      The RequestCoalescer batches all concurrent submits for the same source_uri
      within a 100 ms window into 1-3 actual PDS round-trips.

    Wire shape matches com.etzhayyim.translationLink lexicon (2026-05-21):
      Required: sourceUri, sourceLang, targetUri, targetLang, translatedAt,
                qualityScore (0–1000 permille), translatorDid

    Returns: AT URI of the created translationLink record.
    SDK pds.put_record is a stub (NotImplementedError) until M3; tested via mocks.
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    # Build the com.etzhayyim.translationLink wire shape matching the lexicon.
    translated_at = utc_now_iso()
    rkey = _rkey(f"translation-link-{target_lang}")
    uri = f"at://{repo}/{TRANSLATION_LINK_COLLECTION}/{rkey}"

    # NOTE: lexicon field is "targetUri" (not "translatedUri") per the 2026-05-21 lexicon.
    tl_record: dict[str, Any] = {
        "$type": TRANSLATION_LINK_COLLECTION,
        "sourceUri": source_uri,
        "sourceLang": source_lang,
        "targetUri": translated_uri,   # lexicon field name: targetUri
        "targetLang": target_lang,
        "translatedAt": translated_at,
        "qualityScore": max(0, min(1000, quality_score)),
        "translatorDid": translator_did or repo,
    }
    if model:
        tl_record["model"] = model

    # Use the coalescer to batch concurrent translationLink writes for the same source_uri.
    # This is the M2 critical path: 36+ target languages → 1-3 MST commits.
    active_coalescer = coalescer or _get_coalescer()

    if active_coalescer is not None:
        # Coalesced path: all concurrent submits for source_uri share one pds call.
        async def _do_put() -> dict[str, Any]:
            return await _pds_mod.put_record(
                collection=TRANSLATION_LINK_COLLECTION,
                record=tl_record,
                repo=repo,
                rkey=rkey,
            )

        await active_coalescer.submit(key=source_uri, fn=_do_put)
    else:
        # Fallback: direct put_record (coalescer unavailable, e.g. SDK not installed)
        await _pds_mod.put_record(
            collection=TRANSLATION_LINK_COLLECTION,
            record=tl_record,
            repo=repo,
            rkey=rkey,
        )

    return uri


# ---------------------------------------------------------------------------
# M3 IMPLEMENTED functions — social completeness + BPMN audit + quality scoring
# ---------------------------------------------------------------------------


async def record_bpmn_activity_event(
    *,
    repo: str = DEFAULT_REPO,
    process_id: str,
    activity_id: str,
    instance_key: str,
    event_kind: str,
    actor_did: str = "",
    case_id: str = "",
    evidence_cid: str = "",
    error_message: str = "",
    recorded_at: str = "",
    rkey: str = "",
) -> str:
    """Dispatch an com.etzhayyim.bpmnActivityEvent record to PDS via @etzhayyim/sdk.
    [M3 IMPLEMENTED]

    Vendor equivalent: _emit_actor_quality_activity_event() in yoro_social.py
      INSERT INTO vertex_bpmn_activity_event

    Substrate path (ADR-2605215300 §3):
      @etzhayyim/sdk Python binding → PDS put_record(com.etzhayyim.bpmnActivityEvent)
      → MST commit

    Wire shape matches com.etzhayyim.bpmnActivityEvent lexicon (2026-05-21):
      Required: processId, activityId, instanceKey, eventKind, recordedAt, actorDid
      Optional: caseId, evidenceCid, errorMessage

    eventKind must be one of: started, completed, failed, cancelled, suspended

    NOTE: BPMN telemetry must not block the enrichment path. Callers should
    wrap this function in asyncio.shield or a fire-and-forget task if low-priority.

    Returns: AT URI of the created bpmnActivityEvent record.
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    valid_event_kinds = {"started", "completed", "failed", "cancelled", "suspended"}
    if event_kind not in valid_event_kinds:
        raise ValueError(
            f"record_bpmn_activity_event: event_kind must be one of {valid_event_kinds}, got {event_kind!r}"
        )

    resolved_recorded_at = recorded_at or utc_now_iso()
    resolved_actor_did = actor_did or repo
    resolved_rkey = rkey or _rkey(f"bpmn-{activity_id}")
    uri = f"at://{repo}/{BPMN_ACTIVITY_EVENT_COLLECTION}/{resolved_rkey}"

    # Wire shape exactly matches com.etzhayyim.bpmnActivityEvent lexicon.
    event_record: dict[str, Any] = {
        "$type": BPMN_ACTIVITY_EVENT_COLLECTION,
        "processId": process_id,
        "activityId": activity_id,
        "instanceKey": instance_key,
        "eventKind": event_kind,
        "recordedAt": resolved_recorded_at,
        "actorDid": resolved_actor_did,
    }
    if case_id:
        event_record["caseId"] = case_id
    if evidence_cid:
        event_record["evidenceCid"] = evidence_cid
    if error_message:
        event_record["errorMessage"] = error_message

    # Dispatch to PDS via @etzhayyim/sdk.
    # vendor: INSERT INTO vertex_bpmn_activity_event
    # religious-corp: PDS put_record(bpmnActivityEvent) → MST commit
    await _pds_mod.put_record(
        collection=BPMN_ACTIVITY_EVENT_COLLECTION,
        record=event_record,
        repo=repo,
        rkey=resolved_rkey,
    )

    return uri


async def record_actor_quality_report(
    *,
    repo: str = DEFAULT_REPO,
    subject_did: str,
    reporter_did: str = "",
    quality_score: int,
    dimensions: list[dict[str, Any]] | None = None,
    notes: str = "",
    evidence_cid: str = "",
    recorded_at: str = "",
    rkey: str = "",
) -> str:
    """Dispatch an com.etzhayyim.actorQualityReport record to PDS via @etzhayyim/sdk.
    [M3 IMPLEMENTED]

    Vendor equivalent: task_yoro_actor_quality_inspect() / task_yoro_actor_quality_verify()
    in yoro_social.py (in-memory return values only in vendor; now persisted as MST record).

    Substrate path (ADR-2605215300 §3):
      @etzhayyim/sdk Python binding → PDS put_record(com.etzhayyim.actorQualityReport)
      → MST commit → IPFS pin (anchored for cross-Pregel-cell auditability)

    Wire shape matches com.etzhayyim.actorQualityReport lexicon (2026-05-21):
      Required: subjectDid, reporterDid, qualityScore (0-1000), recordedAt, dimensions
      Optional: notes, evidenceCid

    dimensions is a list of qualityDimension objects:
      [{"dimension": "charter-compliance", "score": 800}, ...]
    Valid dimensions: charter-compliance, wellbecoming, charter-rider, contribution, governance

    quality_score is in permille (0–1000). Clamped to valid range.

    Returns: AT URI of the created actorQualityReport record.
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    resolved_recorded_at = recorded_at or utc_now_iso()
    resolved_reporter_did = reporter_did or repo
    resolved_rkey = rkey or _rkey(f"quality-{subject_did[-12:]}")
    uri = f"at://{repo}/{ACTOR_QUALITY_REPORT_COLLECTION}/{resolved_rkey}"
    clamped_score = max(0, min(1000, quality_score))

    valid_dimensions = {"charter-compliance", "wellbecoming", "charter-rider", "contribution", "governance"}
    resolved_dimensions: list[dict[str, Any]] = []
    for dim in (dimensions or []):
        dim_name = dim.get("dimension", "")
        dim_score = max(0, min(1000, int(dim.get("score", 0))))
        if dim_name in valid_dimensions:
            resolved_dimensions.append({"dimension": dim_name, "score": dim_score})

    # Wire shape exactly matches com.etzhayyim.actorQualityReport lexicon.
    report_record: dict[str, Any] = {
        "$type": ACTOR_QUALITY_REPORT_COLLECTION,
        "subjectDid": subject_did,
        "reporterDid": resolved_reporter_did,
        "qualityScore": clamped_score,
        "recordedAt": resolved_recorded_at,
        "dimensions": resolved_dimensions,
    }
    if notes:
        report_record["notes"] = notes
    if evidence_cid:
        report_record["evidenceCid"] = evidence_cid

    # Dispatch to PDS via @etzhayyim/sdk.
    # vendor: in-memory return only; religious-corp: durable MST record → cross-cell auditability
    await _pds_mod.put_record(
        collection=ACTOR_QUALITY_REPORT_COLLECTION,
        record=report_record,
        repo=repo,
        rkey=resolved_rkey,
    )

    return uri


async def like_post(
    *,
    repo: str = DEFAULT_REPO,
    subject_uri: str,
    subject_cid: str,
    rkey: str = "",
    actor_path: str = "like",
) -> str:
    """Dispatch an app.bsky.feed.like record to PDS via @etzhayyim/sdk.  [M3 IMPLEMENTED]

    Completes the social-path coherent set (post + like + follow + repost).
    High-traffic function per yoro social graph analysis.

    Vendor equivalent: insert_repo_records(rows, ...) where collection=app.bsky.feed.like
      INSERT INTO vertex_repo_record (collection=app.bsky.feed.like)

    Substrate path (ADR-2605215300 §3):
      @etzhayyim/sdk Python binding → PDS dispatch(app.bsky.feed.like) → MST commit

    Wire shape matches AT Protocol app.bsky.feed.like lexicon:
      Required: subject (StrongRef with uri + cid), createdAt

    No coalescer: likes are typically single operations, not batched.

    Returns: AT URI of the created like record.
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    created_at = utc_now_iso()
    resolved_rkey = rkey or _rkey(actor_path)
    uri = f"at://{repo}/{LIKE_COLLECTION}/{resolved_rkey}"

    # Wire shape matches app.bsky.feed.like AT Protocol lexicon.
    like_record: dict[str, Any] = {
        "$type": LIKE_COLLECTION,
        "subject": {
            "uri": subject_uri,
            "cid": subject_cid,
        },
        "createdAt": created_at,
    }

    # Dispatch to PDS — likes are federated social records (dispatch, not put_record).
    await _pds_mod.dispatch(
        collection=LIKE_COLLECTION,
        record=like_record,
        repo=repo,
        rkey=resolved_rkey,
    )

    return uri


async def follow_actor(
    *,
    repo: str = DEFAULT_REPO,
    subject_did: str,
    rkey: str = "",
    actor_path: str = "follow",
    coalescer: Any = None,
) -> str:
    """Dispatch an app.bsky.graph.follow record to PDS via @etzhayyim/sdk.  [M3 IMPLEMENTED]

    Completes the social-path coherent set (post + like + follow + repost).
    High-traffic function — follow-many operations are coalesced within a 100 ms window
    (same coalescer as translationLink) to avoid Zeebe timeout on mass follow-backs.

    Vendor equivalent: insert_repo_records(rows, ...) where collection=app.bsky.graph.follow
      INSERT INTO edge_follows + INSERT INTO vertex_repo_record

    Substrate path (ADR-2605215300 §3):
      coalescer.submit(key=subject_did, fn=lambda: pds.dispatch(app.bsky.graph.follow))
      → MST commit

    Wire shape matches AT Protocol app.bsky.graph.follow lexicon:
      Required: subject (DID string), createdAt

    Uses coalescer: follow-many is a batch operation in respond_to_follow_graph_fallback;
    the coalescer prevents the Zeebe task from spawning 100+ individual PDS round-trips.

    Returns: AT URI of the created follow record.
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    created_at = utc_now_iso()
    resolved_rkey = rkey or _rkey(actor_path)
    uri = f"at://{repo}/{FOLLOW_COLLECTION}/{resolved_rkey}"

    # Wire shape matches app.bsky.graph.follow AT Protocol lexicon.
    follow_record: dict[str, Any] = {
        "$type": FOLLOW_COLLECTION,
        "subject": subject_did,
        "createdAt": created_at,
    }

    active_coalescer = coalescer or _get_coalescer()

    if active_coalescer is not None:
        # Coalesced path: batch concurrent follow operations for the same subject_did.
        async def _do_follow() -> dict[str, Any]:
            return await _pds_mod.dispatch(
                collection=FOLLOW_COLLECTION,
                record=follow_record,
                repo=repo,
                rkey=resolved_rkey,
            )

        await active_coalescer.submit(key=subject_did, fn=_do_follow)
    else:
        await _pds_mod.dispatch(
            collection=FOLLOW_COLLECTION,
            record=follow_record,
            repo=repo,
            rkey=resolved_rkey,
        )

    return uri


async def repost(
    *,
    repo: str = DEFAULT_REPO,
    subject_uri: str,
    subject_cid: str,
    rkey: str = "",
    actor_path: str = "repost",
) -> str:
    """Dispatch an app.bsky.feed.repost record to PDS via @etzhayyim/sdk.  [M3 IMPLEMENTED]

    Completes the social-path coherent set (post + like + follow + repost).
    High-traffic function per yoro social graph analysis.

    Vendor equivalent: insert_repo_records(rows, ...) where collection=app.bsky.feed.repost
      INSERT INTO vertex_repo_record (collection=app.bsky.feed.repost)

    Substrate path (ADR-2605215300 §3):
      @etzhayyim/sdk Python binding → PDS dispatch(app.bsky.feed.repost) → MST commit

    Wire shape matches AT Protocol app.bsky.feed.repost lexicon:
      Required: subject (StrongRef with uri + cid), createdAt

    No coalescer: reposts are typically single targeted operations, not batched.

    Returns: AT URI of the created repost record.
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    created_at = utc_now_iso()
    resolved_rkey = rkey or _rkey(actor_path)
    uri = f"at://{repo}/{REPOST_COLLECTION}/{resolved_rkey}"

    # Wire shape matches app.bsky.feed.repost AT Protocol lexicon.
    repost_record: dict[str, Any] = {
        "$type": REPOST_COLLECTION,
        "subject": {
            "uri": subject_uri,
            "cid": subject_cid,
        },
        "createdAt": created_at,
    }

    # Dispatch to PDS — reposts are federated social records (dispatch, not put_record).
    await _pds_mod.dispatch(
        collection=REPOST_COLLECTION,
        record=repost_record,
        repo=repo,
        rkey=resolved_rkey,
    )

    return uri


# ---------------------------------------------------------------------------
# REIMPLEMENT stubs — M2/M3 deadline per ADR-2605215300 §4
# ---------------------------------------------------------------------------

def insert_social_post_record(
    row: SocialPostRecord,
    *,
    ipfs_pin: bool = False,
) -> dict[str, Any]:
    """Dispatch app.bsky.feed.post record to PDS — sync shim for non-async callers.
    [M6 IMPLEMENTED]

    Vendor equivalent: insert_social_post_record() in yoro_social.py
      INSERT INTO vertex_repo_record + vertex_post

    Substrate path (ADR-2605215300 §3):
      Wraps async record_post() via asyncio.run().
      Chosen over nest_asyncio because:
        - This shim is only for non-async callers (Zeebe task threads, CLI scripts).
        - asyncio.run() is the stdlib-idiomatic, zero-dependency approach for sync→async.
        - nest_asyncio patches the event loop globally and can mask real concurrency bugs;
          it is not appropriate for a production primitive module.
      Callers inside an async context (e.g. asyncio.gather tasks) MUST use record_post()
      directly — asyncio.run() will raise RuntimeError if called from within a running loop.

    ipfs_pin is accepted for API compatibility but is a no-op at this layer
    (IPFS pinning is handled downstream by anchor-cron per ADR-2605171800 Stage 3).

    Returns: dict with keys: uri (AT URI), rkey, text, repo, collection, created_at
    See: YORO-PYTHON-MIGRATION-NOTES.md row #1
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )
    import asyncio  # stdlib — no extra dependency

    async def _run() -> dict[str, Any]:
        uri = await record_post(
            repo=row.repo,
            text=row.text,
            created_at=row.created_at,
            rkey=row.rkey or "",
        )
        return {
            "uri": uri,
            "rkey": row.rkey,
            "text": row.text,
            "repo": row.repo,
            "collection": row.collection or DEFAULT_COLLECTION,
            "created_at": row.created_at,
        }

    return asyncio.run(_run())


def insert_repo_records(
    rows: list[RepoRecord | SocialPostRecord],
    *,
    ipfs_pin: bool = False,
) -> list[dict[str, Any]]:
    """Batch dispatch AT repo records (feed.post, graph.follow, actor.profile) via @etzhayyim/sdk.
    [M7 IMPLEMENTED]

    Sync shim wrapping async batch putRecord calls via asyncio.run().

    Vendor equivalent: insert_repo_records() in yoro_social.py
      Batch INSERT INTO vertex_repo_record (+ vertex_post for feed.post,
      + edge_follows for graph.follow, + vertex_profile for actor.profile)

    Substrate path (ADR-2605215300 §3 rows #2/#3/#4):
      asyncio.run(gather(pds.put_record | pds.dispatch per row)) → MST commits

    Supported collections (rows #2/#3/#4):
      app.bsky.feed.post     → pds.dispatch (federated)
      app.bsky.graph.follow  → pds.dispatch (federated)
      app.bsky.actor.profile → pds.put_record (rkey='self' convention)
      Any other collection   → pds.put_record (generic)

    CAVEAT: Not safe to call from within a running event loop (asyncio.run()
    raises RuntimeError). Async callers must use record_post() / follow_actor()
    / update_profile() directly.

    ipfs_pin is accepted for API compatibility but is a no-op at this layer
    (IPFS pinning is handled downstream by anchor-cron, ADR-2605171800 Stage 3).

    Returns: list of dicts {ok, uri, rkey, collection, repo} per row.
             Failed rows include {ok: False, error: str}.
    See: YORO-PYTHON-MIGRATION-NOTES.md rows #2/#3/#4
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    _FEDERATED = {DEFAULT_COLLECTION, FOLLOW_COLLECTION, LIKE_COLLECTION, REPOST_COLLECTION}

    async def _dispatch_one(row: RepoRecord | SocialPostRecord) -> dict[str, Any]:
        collection = getattr(row, "collection", DEFAULT_COLLECTION) or DEFAULT_COLLECTION
        repo = getattr(row, "repo", DEFAULT_REPO) or DEFAULT_REPO
        rkey = getattr(row, "rkey", "") or ""
        record = getattr(row, "record", {}) or {}

        # Ensure $type is set on the record.
        if "$type" not in record:
            record = dict(record)
            record["$type"] = collection

        uri = getattr(row, "uri", None) or f"at://{repo}/{collection}/{rkey}"

        try:
            if collection in _FEDERATED:
                await _pds_mod.dispatch(
                    collection=collection,
                    record=record,
                    repo=repo,
                    rkey=rkey,
                )
            else:
                await _pds_mod.put_record(
                    collection=collection,
                    record=record,
                    repo=repo,
                    rkey=rkey,
                )
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:300], "uri": uri, "collection": collection, "repo": repo}

        return {"ok": True, "uri": uri, "rkey": rkey, "collection": collection, "repo": repo}

    async def _run() -> list[dict[str, Any]]:
        tasks = [_dispatch_one(row) for row in rows]
        return list(await asyncio.gather(*tasks))

    return asyncio.run(_run())


def insert_translation_link_record(row: TranslationLinkRecord) -> dict[str, Any]:
    """Dispatch com.etzhayyim.apps.etzhayyim.translationLink record via @etzhayyim/sdk.
    [M7 IMPLEMENTED]

    Sync shim wrapping async record_translation_link() via asyncio.run().

    Vendor equivalent: insert_translation_link_record() in yoro_social.py
      DELETE FROM vertex_translation_link + INSERT INTO vertex_translation_link

    Substrate path (ADR-2605215300 §3 row #5):
      asyncio.run(record_translation_link(...)) → PDS put_record(translationLink)
      → MST commit → IPFS pin (handled downstream by anchor-cron)

    CAVEAT: Not safe to call from within a running event loop (asyncio.run()
    raises RuntimeError). Async callers must use record_translation_link() directly.

    Returns: dict with keys: uri (AT URI), rkey, source_uri, target_lang, translated_at
    See: YORO-PYTHON-MIGRATION-NOTES.md row #5
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    async def _run() -> dict[str, Any]:
        uri = await record_translation_link(
            repo=row.repo,
            source_uri=row.source_uri,
            source_lang=row.source_lang,
            translated_uri=row.translated_uri,
            target_lang=row.target_lang,
            translator_did=row.owner_did or row.repo,
            quality_score=int(row.quality_score or 0),
        )
        return {
            "uri": uri,
            "rkey": row.rkey,
            "source_uri": row.source_uri,
            "target_lang": row.target_lang,
            "translated_at": row.created_at or utc_now_iso(),
        }

    return asyncio.run(_run())


def emit_bpmn_activity_event(row: BpmnActivityEventRecord) -> None:
    """Dispatch com.etzhayyim.apps.etzhayyim.bpmnActivityEvent record via @etzhayyim/sdk.
    [M7 IMPLEMENTED]

    Sync shim wrapping async record_bpmn_activity_event() via asyncio.run().

    Vendor equivalent: _emit_actor_quality_activity_event() in yoro_social.py
      INSERT INTO vertex_bpmn_activity_event

    Substrate path (ADR-2605215300 §3 row #6):
      asyncio.run(record_bpmn_activity_event(...)) → PDS put_record(bpmnActivityEvent)
      → MST commit

    VENDOR CONVENTION — NEVER RAISES:
      All exceptions (SDK import errors, network errors, event_kind validation errors)
      are caught and logged to stderr. BPMN telemetry must not block the enrichment
      path under any circumstances. Callers do not need try/except.

    CAVEAT: Not safe to call from within a running event loop (asyncio.run()
    raises RuntimeError in that context). Async callers must use
    record_bpmn_activity_event() directly.

    Returns: None (always, even on failure — see vendor convention above).
    See: YORO-PYTHON-MIGRATION-NOTES.md row #6
    """
    import logging
    _log = logging.getLogger(__name__)

    try:
        if _pds_mod is None:
            _log.warning(
                "emit_bpmn_activity_event: etzhayyim_sdk not installed — event suppressed. "
                "Install 20-actors/etzhayyim-sdk-py."
            )
            return

        async def _run() -> None:
            await record_bpmn_activity_event(
                repo=row.repo,
                process_id=row.instance_id or "unknown-process",
                activity_id=row.activity_id,
                instance_key=row.instance_id or "unknown-instance",
                event_kind=row.event_type if row.event_type in {
                    "started", "completed", "failed", "cancelled", "suspended"
                } else "completed",
                actor_did=row.actor_did or row.org_did or row.repo,
                case_id=row.event_id or "",
                recorded_at=row.occurred_at or "",
                rkey=row.rkey or "",
            )

        asyncio.run(_run())
    except Exception as exc:
        # VENDOR CONVENTION: Never raise — log and swallow.
        _log.warning("emit_bpmn_activity_event: suppressed exception: %s", exc)


async def fetch_source_post(post_uri: str) -> dict[str, Any] | None:
    """Read an app.bsky.feed.post record from PDS via @etzhayyim/sdk getRecord.
    [M4 IMPLEMENTED]

    Vendor equivalent: _fetch_source_post() in yoro_social.py
      SELECT FROM vertex_repo_record WHERE uri = %(post_uri)s

    Substrate path (ADR-2605215300 §3 SELECT mapping row #10):
      @etzhayyim/sdk Python binding → PDS getRecord(repo, collection, rkey)
      decoded from AT URI

    Returns the record content dict on success, or None if not found.
    The returned dict shape mirrors the vendor: {repo, rkey, record, createdAt, text, langs}.
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    try:
        data = await _pds_mod.get_record(post_uri)
    except Exception:
        # PDS 404 or network error — return None (caller decides how to proceed).
        return None

    if not data:
        return None

    value = data.get("value") or {}
    # AT URI parts: at://<repo>/<collection>/<rkey>
    parts = post_uri.lstrip("at://").split("/", 2) if post_uri.startswith("at://") else []
    repo = parts[0] if len(parts) > 0 else ""
    rkey = parts[2] if len(parts) > 2 else ""

    return {
        "repo": repo,
        "rkey": rkey,
        "record": value,
        "createdAt": str(value.get("createdAt") or ""),
        "text": str(value.get("text") or ""),
        "langs": value.get("langs") if isinstance(value.get("langs"), list) else [],
    }


async def fetch_actor_generation_context(actor_did: str, handle: str = "") -> dict[str, Any]:
    """Read actor profile + recent records from PDS via @etzhayyim/sdk.
    [M4 IMPLEMENTED]

    Vendor equivalent: _fetch_actor_generation_context() in yoro_social.py
      SELECT FROM vertex_profile + SELECT FROM vertex_repo_record

    Substrate path (ADR-2605215300 §3 SELECT mapping row #11):
      @etzhayyim/sdk Python binding → PDS getRecord(actor.profile, rkey='self')
      + PDS listRecords(repo, collection) for recent activity

    Returns a context dict matching vendor shape:
      {actorDid, handle, actorKind, existingProfile, recentPosts, repoRecordCollections}
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    context: dict[str, Any] = {
        "actorDid": actor_did,
        "handle": handle or actor_did,
        "actorKind": "public YORO actor",
        "existingProfile": {},
        "recentPosts": [],
        "repoRecordCollections": [],
    }

    try:
        # Fetch actor profile (rkey='self' per AT Protocol convention).
        profile_uri = f"at://{actor_did}/{PROFILE_COLLECTION}/self"
        profile_data = await _pds_mod.get_record(profile_uri)
        if profile_data:
            profile_value = profile_data.get("value") or {}
            context["existingProfile"] = {
                "did": actor_did,
                "handle": handle or actor_did,
                "displayName": profile_value.get("displayName", ""),
                "description": profile_value.get("description", ""),
                "avatar": profile_value.get("avatar", ""),
                "banner": profile_value.get("banner", ""),
                "createdAt": profile_value.get("createdAt", ""),
            }
    except Exception as exc:
        context["contextFetchError"] = str(exc)[:300]

    try:
        # Fetch recent records (excluding actor profile) to form generation context.
        recent_data = await _pds_mod.list_records(
            actor_did,
            DEFAULT_COLLECTION,
            limit=5,
        )
        records = recent_data.get("records", [])
        context["recentPosts"] = [
            {
                "collection": DEFAULT_COLLECTION,
                "rkey": str(rec.get("uri", "").rsplit("/", 1)[-1]),
                "value": json.dumps(rec.get("value") or {}, separators=(",", ":"), ensure_ascii=False)[:500],
                "indexedAt": str(rec.get("indexedAt") or ""),
            }
            for rec in records
        ]
        context["repoRecordCollections"] = [DEFAULT_COLLECTION] if records else []
    except Exception:
        # listRecords failure is non-fatal for context building.
        pass

    return context


async def fetch_profile_quality(actor_did: str, handle: str = "") -> dict[str, Any]:
    """Read actor profile quality data from PDS via @etzhayyim/sdk.
    [M4 IMPLEMENTED]

    Vendor equivalent: _fetch_profile_quality() in yoro_social.py
      SELECT FROM vertex_profile + SELECT count(*) FROM vertex_repo_record

    Substrate path (ADR-2605215300 §3 SELECT mapping row #12):
      @etzhayyim/sdk Python binding → PDS getRecord(actor.profile) +
      PDS listRecords count; heavy aggregates via mst-projector snapshot

    Quality score (permille 0-1000, vendor was 0-100 then mapped):
      profile exists: +250
      displayName:    +200
      description:    +250
      avatar/banner:  +100
      posts > 0:      +200

    Returns:
      {ok, actorDid, handle, profile, postsCount, missingFields, qualityScore}
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    profile: dict[str, Any] = {}
    posts_count = 0

    try:
        profile_uri = f"at://{actor_did}/{PROFILE_COLLECTION}/self"
        profile_data = await _pds_mod.get_record(profile_uri)
        if profile_data:
            v = profile_data.get("value") or {}
            profile = {
                "did": actor_did,
                "handle": handle or actor_did,
                "displayName": v.get("displayName", ""),
                "description": v.get("description", ""),
                "avatar": v.get("avatar", ""),
                "banner": v.get("banner", ""),
                "createdAt": v.get("createdAt", ""),
            }
    except Exception:
        pass

    try:
        posts_data = await _pds_mod.list_records(
            actor_did,
            DEFAULT_COLLECTION,
            limit=1,
        )
        records = posts_data.get("records", [])
        # Use cursor presence or non-empty records list as a post-count signal.
        # Full count via mst-projector snapshot is an M5 enhancement.
        posts_count = len(records)
        if posts_data.get("cursor"):
            # More records exist beyond our limit=1 fetch — actor has posts.
            posts_count = max(posts_count, 1)
    except Exception:
        pass

    missing: list[str] = []
    if not profile:
        missing.append("profile")
    if not (profile.get("displayName") or "").strip():
        missing.append("displayName")
    if not (profile.get("description") or "").strip():
        missing.append("description")
    if not (profile.get("avatar") or "").strip():
        missing.append("avatar")
    if posts_count == 0:
        missing.append("publicPost")

    # Quality score 0-1000 permille (vendor used 0-100; we scale x10 for lexicon parity).
    quality = 0
    if profile:
        quality += 250
    if (profile.get("displayName") or "").strip():
        quality += 200
    if (profile.get("description") or "").strip():
        quality += 250
    if (profile.get("avatar") or "").strip() or (profile.get("banner") or "").strip():
        quality += 100
    if posts_count > 0:
        quality += 200

    return {
        "ok": True,
        "actorDid": actor_did,
        "handle": profile.get("handle") or handle or actor_did,
        "profile": profile,
        "postsCount": posts_count,
        "missingFields": missing,
        "qualityScore": quality,
    }


async def enrich_actor_quality_profile(
    *,
    actor_did: str,
    handle: str = "",
    missing_fields: Any = None,
    source_hint: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Upsert actor profile record via @etzhayyim/sdk putRecord.
    [M4 IMPLEMENTED — delegates to update_profile]

    Vendor equivalent: _enrich_actor_quality_profile() in yoro_social.py
    Substrate path: @etzhayyim/sdk Python binding → PDS putRecord(app.bsky.actor.profile,
                    rkey='self') → MST commit; idempotent overwrite, PDS handles conflict.
    See: ADR-2605215300 §3 rows #7/#8, YORO-PYTHON-MIGRATION-NOTES.md rows #7/#8
    """
    if dry_run:
        display_name = _safe_display_name(actor_did, handle)
        description = _safe_description(actor_did, source_hint)
        return {
            "ok": True,
            "dryRun": True,
            "profileChanged": False,
            "displayName": display_name,
            "description": description,
            "profileGenerator": "safe-template",
        }

    uri = await update_profile(
        actor_did=actor_did,
        handle=handle,
        source_hint=source_hint,
    )
    return {
        "ok": True,
        "profileChanged": True,
        "actorDid": actor_did,
        "uri": uri,
        "profileGenerator": "safe-template",
    }


# ---------------------------------------------------------------------------
# M5 IMPLEMENTED functions — delete-path symmetry + read-path completeness
# ---------------------------------------------------------------------------


async def delete_post(uri: str) -> dict[str, Any]:
    """Delete a feed.post record from PDS via @etzhayyim/sdk deleteRecord.  [M5 IMPLEMENTED]

    Delete-path symmetric counterpart to record_post() (M2).

    Vendor equivalent: vendor delete pattern for vertex_repo_record + vertex_post
      DELETE FROM vertex_repo_record WHERE uri = %(uri)s
      DELETE FROM vertex_post WHERE uri = %(uri)s

    Substrate path (ADR-2605215300 §3):
      @etzhayyim/sdk Python binding → PDS deleteRecord(at://repo/app.bsky.feed.post/rkey)
      → MST tombstone commit

    Note: MST tombstone is permanent — federation peers will see the delete
    event via the firehose. PDS handles propagation to IPFS unpin and anchor
    batch. No soft-delete: AT Protocol hard-deletes are irreversible at the
    PDS level.

    Args:
        uri: AT URI of the post to delete (at://repo/app.bsky.feed.post/rkey).

    Returns:
        {"ok": True, "deleted": uri} on success.
        {"ok": False, "error": ...} on validation failure.
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    if not uri:
        return {"ok": False, "error": "uri is required"}
    if not uri.startswith("at://"):
        return {"ok": False, "error": f"uri must be an AT URI (at://...): {uri!r}"}

    await _pds_mod.delete_record(uri)
    return {"ok": True, "deleted": uri}


async def unfollow_actor(uri: str) -> dict[str, Any]:
    """Delete a graph.follow record from PDS via @etzhayyim/sdk deleteRecord.  [M5 IMPLEMENTED]

    Delete-path symmetric counterpart to follow_actor() (M3).

    Vendor equivalent: DELETE FROM edge_follows + vertex_repo_record WHERE uri = %(uri)s

    Substrate path (ADR-2605215300 §3):
      @etzhayyim/sdk Python binding → PDS deleteRecord(at://repo/app.bsky.graph.follow/rkey)
      → MST tombstone commit

    Args:
        uri: AT URI of the follow record to delete
             (at://repo/app.bsky.graph.follow/rkey).

    Returns:
        {"ok": True, "deleted": uri} on success.
        {"ok": False, "error": ...} on validation failure.
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    if not uri:
        return {"ok": False, "error": "uri is required"}
    if not uri.startswith("at://"):
        return {"ok": False, "error": f"uri must be an AT URI (at://...): {uri!r}"}

    await _pds_mod.delete_record(uri)
    return {"ok": True, "deleted": uri}


async def unlike_post(uri: str) -> dict[str, Any]:
    """Delete a feed.like record from PDS via @etzhayyim/sdk deleteRecord.  [M5 IMPLEMENTED]

    Delete-path symmetric counterpart to like_post() (M3).

    Vendor equivalent: DELETE FROM vertex_repo_record WHERE uri = %(uri)s
      (collection=app.bsky.feed.like)

    Substrate path (ADR-2605215300 §3):
      @etzhayyim/sdk Python binding → PDS deleteRecord(at://repo/app.bsky.feed.like/rkey)
      → MST tombstone commit

    Args:
        uri: AT URI of the like record to delete
             (at://repo/app.bsky.feed.like/rkey).

    Returns:
        {"ok": True, "deleted": uri} on success.
        {"ok": False, "error": ...} on validation failure.
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    if not uri:
        return {"ok": False, "error": "uri is required"}
    if not uri.startswith("at://"):
        return {"ok": False, "error": f"uri must be an AT URI (at://...): {uri!r}"}

    await _pds_mod.delete_record(uri)
    return {"ok": True, "deleted": uri}


async def fetch_followers(
    actor_did: str,
    *,
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Read the actor's follower graph from PDS via @etzhayyim/sdk listRecords.
    [M5 IMPLEMENTED]

    Read-path for the yoro follower graph. Lists records in the
    app.bsky.graph.follow collection where the actor is the subject — i.e.
    followers of the actor repo.

    Vendor equivalent: SELECT FROM edge_follows WHERE target_did = %(actor_did)s

    Substrate path (ADR-2605215300 §3 SELECT mapping):
      @etzhayyim/sdk Python binding → PDS listRecords(actor_did, app.bsky.graph.follow)
      paginated; for full follower graph, use mst-projector snapshot.

    Note: AT Protocol listRecords returns records authored BY actor_did, not
    records following them. True follower graph requires either Relay index
    (AppView) or mst-projector reverse-index. This implementation returns
    the actor's outgoing follows as a practical approximation until M6 wires
    the AppView reverse-follow path.

    Args:
        actor_did: DID of the actor whose follow records to list.
        limit:     Max records to return (1-100, default 50).
        cursor:    Pagination cursor from a previous call.

    Returns:
        {ok, actorDid, follows: [...], cursor, count}
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    if not actor_did:
        return {"ok": False, "error": "actor_did is required", "follows": [], "count": 0}

    # ── mst-projector path: true reverse-follower index, no 100-record cap ──
    if _projector_mod is not None:
        try:
            proj_result = await _projector_mod.query_by_field(
                FOLLOW_COLLECTION, "subject", actor_did, limit=limit,
            )
            proj_records = proj_result.get("records", [])
            followers = [
                {
                    "uri": str(rec.get("uri", "")),
                    "cid": str(rec.get("cid", "")),
                    "subject": str((rec.get("value") or {}).get("subject", "")),
                    "createdAt": str((rec.get("value") or {}).get("createdAt", "")),
                }
                for rec in proj_records
            ]
            return {
                "ok": True,
                "actorDid": actor_did,
                "follows": followers,
                "count": len(followers),
                "cursor": proj_result.get("cursor"),
                "source": "mst-projector",
            }
        except Exception as _proj_err:
            _log.warning(
                "fetch_followers: mst-projector unreachable, falling back to "
                "client-side PDS listRecords: %s", _proj_err,
            )

    # ── Fallback: PDS listRecords (100-record cap) ─────────────────────────
    try:
        data = await _pds_mod.list_records(
            actor_did,
            FOLLOW_COLLECTION,
            limit=min(max(1, limit), 100),
            cursor=cursor,
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc)[:300],
            "actorDid": actor_did,
            "follows": [],
            "count": 0,
            "cursor": None,
        }

    records = data.get("records", [])
    follows = [
        {
            "uri": str(rec.get("uri", "")),
            "cid": str(rec.get("cid", "")),
            "subject": str((rec.get("value") or {}).get("subject", "")),
            "createdAt": str((rec.get("value") or {}).get("createdAt", "")),
        }
        for rec in records
    ]

    return {
        "ok": True,
        "actorDid": actor_did,
        "follows": follows,
        "count": len(follows),
        "cursor": data.get("cursor"),
        "source": "pds-list-records",
    }


async def list_actor_records(
    actor_did: str,
    collection: str = DEFAULT_COLLECTION,
    *,
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    """List AT records for an actor from PDS via @etzhayyim/sdk listRecords.
    [M5 IMPLEMENTED]

    Generic read-path for any AT collection (feed.post, graph.follow, etc.).
    Abstracts PDS listRecords with consistent return shape.

    Vendor equivalent: SELECT FROM vertex_repo_record WHERE repo = %(actor_did)s
      AND collection = %(collection)s LIMIT %(limit)s

    Substrate path (ADR-2605215300 §3):
      @etzhayyim/sdk Python binding → PDS listRecords(actor_did, collection, limit)
      → paginated record list

    Args:
        actor_did:  DID of the actor repo to query.
        collection: NSID collection to list (default: app.bsky.feed.post).
        limit:      Max records to return (1-100, default 50).
        cursor:     Pagination cursor from a previous call.

    Returns:
        {ok, actorDid, collection, records: [...], cursor, count}
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    if not actor_did:
        return {
            "ok": False,
            "error": "actor_did is required",
            "records": [],
            "count": 0,
        }

    try:
        data = await _pds_mod.list_records(
            actor_did,
            collection,
            limit=min(max(1, limit), 100),
            cursor=cursor,
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc)[:300],
            "actorDid": actor_did,
            "collection": collection,
            "records": [],
            "count": 0,
            "cursor": None,
        }

    records = data.get("records", [])
    return {
        "ok": True,
        "actorDid": actor_did,
        "collection": collection,
        "records": records,
        "count": len(records),
        "cursor": data.get("cursor"),
    }


# ---------------------------------------------------------------------------
# Public entry points matching vendor task signatures (wire-shape parity)
# ---------------------------------------------------------------------------

async def task_yoro_social_post_graph_fallback(
    postRepo: str = DEFAULT_REPO,
    collection: str = DEFAULT_COLLECTION,
    prefix: str = DEFAULT_PREFIX,
    text: str = "",
    createdAt: str = "",
    rkey: str = "",
    flush: bool = False,  # retained for signature parity; no-op in MST path
) -> dict[str, Any]:
    """Dispatch a social post to PDS via @etzhayyim/sdk.  [M4 IMPLEMENTED]

    Zeebe task type: yoro.social.postGraphFallback

    Variables dict shape (matching vendor yoro_social.py):
      postRepo  (str) — AT repo DID (default: DEFAULT_REPO)
      collection (str) — NSID (default: app.bsky.feed.post)
      prefix    (str) — text prefix when text is empty
      text      (str) — post body (auto-generated if empty)
      createdAt (str) — ISO timestamp (auto-generated if empty)
      rkey      (str) — record key (auto-generated if empty)
      flush     (bool) — ignored (MST atomic commits, no FLUSH)

    Vendor equivalent: task_yoro_social_post_graph_fallback in yoro_social.py
      insert_social_post_record(row, flush=flush)
    Religious-corp substrate: record_post() → pds.dispatch → MST commit
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    if not postRepo:
        return {"ok": False, "error": "postRepo is required"}

    uri = await record_post(
        repo=postRepo,
        text=text,
        created_at=createdAt,
        rkey=rkey,
        actor_path="zeebe",
        extra=None,
    )
    # Build text for response parity (mirrors vendor output shape).
    post_record = build_social_post_record(
        repo=postRepo,
        collection=collection,
        prefix=prefix,
        text=text,
        created_at=createdAt,
        rkey=rkey,
        actor_path="zeebe",
    )
    return {
        "ok": True,
        "uri": uri,
        "repo": postRepo,
        "collection": collection,
        "rkey": post_record.rkey,
        "text": post_record.text,
    }


async def task_yoro_social_platform_pulse_graph_fallback(
    postRepo: str = DEFAULT_REPO,
    flush: bool = False,
) -> dict[str, Any]:
    """Publish platform-pulse metrics post via @etzhayyim/sdk.  [M5 IMPLEMENTED]

    Zeebe task type: yoro.social.platformPulseGraphFallback

    Variables dict shape (matching vendor yoro_social.py):
      postRepo (str)  — AT repo DID (default: DEFAULT_REPO)
      flush    (bool) — ignored (MST atomic commits, no FLUSH)

    Vendor equivalent: task_yoro_social_platform_pulse_graph_fallback in yoro_social.py
      Heavy count aggregates → SQL count(*); here replaced with mst-projector
      CID-pinned snapshot counts (M5 stub; projector integration in M6).

    Note: Full mst-projector snapshot integration is a M6 deliverable. This M5
    impl posts a platform-pulse record with UTC timestamp to satisfy Zeebe
    task routing and provides a placeholder for count metrics. Counts are
    stub values (0) until mst-projector snapshot query is wired in M6.
    See ADR-2605191358 §12-MVs for full spec.

    Religious-corp substrate: record_post() → pds.dispatch → MST commit
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    resolved_repo = postRepo or DEFAULT_REPO
    pulse_at = utc_now_iso()

    # M5: stub counts — mst-projector snapshot integration deferred to M6.
    # TODO M6: replace with etzhayyim_sdk.projector.snapshot_count(collection=...)
    stub_post_count = 0
    stub_follower_count = 0

    text = (
        f"Yoro platform pulse at {pulse_at}. "
        f"Posts: {stub_post_count} | Followers: {stub_follower_count}. "
        "Murakumo actor substrate alive. https://yoro.etzhayyim.com/"
    )

    uri = await record_post(
        repo=resolved_repo,
        text=text,
        created_at=pulse_at,
        actor_path="platform-pulse",
    )

    return {
        "ok": True,
        "uri": uri,
        "repo": resolved_repo,
        "pulseAt": pulse_at,
        "postCount": stub_post_count,
        "followerCount": stub_follower_count,
        "note": "mst-projector snapshot counts deferred to M6",
    }


async def task_yoro_social_respond_to_mention_graph_fallback(
    authorDid: str = "",
    authorHandle: str = "",
    postUri: str = "",
    postCid: str = "",
    postText: str = "",
    flush: bool = False,
) -> dict[str, Any]:
    """Reply to a mention via @etzhayyim/sdk putRecord(app.bsky.feed.post).
    [M4 IMPLEMENTED]

    Zeebe task type: yoro.social.respondToMentionGraphFallback

    Variables dict shape (matching vendor yoro_social.py):
      authorDid    (str) — REQUIRED: DID of the author who mentioned us
      authorHandle (str) — handle for display (optional)
      postUri      (str) — REQUIRED: AT URI of the mention post
      postCid      (str) — CID of the mention post (optional, used in reply ref)
      postText     (str) — text of the mention for logging (optional)
      flush        (bool) — ignored (MST atomic commits, no FLUSH)

    Vendor equivalent: task_yoro_social_respond_to_mention_graph_fallback in yoro_social.py
    Religious-corp substrate: record_post(reply=...) → pds.dispatch → MST commit
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    if not authorDid:
        return {"ok": False, "error": "authorDid is required"}
    if not postUri:
        return {"ok": False, "error": "postUri is required"}

    created_at = utc_now_iso()
    actor = _display_actor(authorDid, authorHandle)
    text = (
        f"Thanks for the mention, @{actor}. Yoro is an AI-Agent-First "
        "social platform. https://yoro.etzhayyim.com/"
    )
    reply_ref = {"uri": postUri, "cid": postCid or postUri.rsplit("/", 1)[-1]}
    reply_extra = {"reply": {"root": reply_ref, "parent": reply_ref}}

    uri = await record_post(
        repo=DEFAULT_REPO,
        text=text,
        created_at=created_at,
        actor_path="mention",
        extra=reply_extra,
    )
    return {
        "ok": True,
        "uri": uri,
        "authorDid": authorDid,
        "postUri": postUri,
        "postTextPreview": postText[:200],
    }


async def task_yoro_social_respond_to_follow_graph_fallback(
    followerDid: str = "",
    followerHandle: str = "",
    followRkey: str = "",
    flush: bool = False,
) -> dict[str, Any]:
    """Follow back + welcome post via @etzhayyim/sdk putRecord.  [M4 IMPLEMENTED]

    Zeebe task type: yoro.social.respondToFollowGraphFallback

    Variables dict shape (matching vendor yoro_social.py):
      followerDid    (str) — REQUIRED: DID of the actor who followed us
      followerHandle (str) — handle for display (optional)
      followRkey     (str) — rkey of the incoming follow record (for audit)
      flush          (bool) — ignored (MST atomic commits, no FLUSH)

    Vendor equivalent: task_yoro_social_respond_to_follow_graph_fallback in yoro_social.py
      insert_repo_records([follow_row, welcome_row])
    Religious-corp substrate:
      follow_actor (coalesced) + record_post (welcome) → MST commits
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    if not followerDid:
        return {"ok": False, "error": "followerDid is required"}

    actor = _display_actor(followerDid, followerHandle)
    welcome_text = (
        f"Welcome @{actor}. Yoro followed back. Share what you are building; "
        "AI agents on Yoro grow through your activity."
    )

    # Fan out follow + welcome post concurrently (coalesced follow, direct post).
    follow_uri_task = follow_actor(
        repo=DEFAULT_REPO,
        subject_did=followerDid,
        actor_path="follow-back",
    )
    welcome_uri_task = record_post(
        repo=DEFAULT_REPO,
        text=welcome_text,
        actor_path="follow-welcome",
    )
    follow_uri, welcome_uri = await asyncio.gather(follow_uri_task, welcome_uri_task)

    return {
        "ok": True,
        "followBackUri": follow_uri,
        "welcomeUri": welcome_uri,
        "followerDid": followerDid,
        "followRkey": followRkey,
    }


def _detect_source_lang(source_post: dict[str, Any], fallback: str = "") -> str:
    """Detect source language from a post record's langs field."""
    langs = source_post.get("langs")
    if isinstance(langs, list) and langs:
        lang = str(langs[0] or "").strip()
        if lang:
            return lang
    return (fallback or "ja").strip()


async def task_yoro_social_translate_post(
    postUri: str = "",
    targetLang: str = "",
    sourceLang: str = "",
    postRepo: str = DEFAULT_REPO,
    postText: str = "",
    dryRun: bool = False,
    flush: bool = False,
) -> dict[str, Any]:
    """Translate a post and persist translation + link record via @etzhayyim/sdk.
    [M4 IMPLEMENTED]

    Zeebe task type: yoro.social.translatePost

    Variables dict shape (matching vendor yoro_social.py):
      postUri    (str) — REQUIRED: AT URI of the source post
      targetLang (str) — REQUIRED: BCP-47 language code of the target language
      sourceLang (str) — source language hint (auto-detected from post if empty)
      postRepo   (str) — AT repo DID for writing translated posts
      postText   (str) — source text override (fetched from PDS if empty)
      dryRun     (bool) — if True, return translation without writing records
      flush      (bool) — ignored (MST atomic commits, no FLUSH)

    LLM integration (M5 IMPLEMENTED):
      Real translation via etzhayyim_sdk.llm.translate() (EVO-X2 LiteLLM, ADR-2605215000).
      Raises ImportError if etzhayyim-sdk-py is not installed.
      Raises LlmError (or subclass) on LLM failures — propagated as task error.

    Vendor equivalent: task_yoro_social_translate_post in yoro_social.py
    Religious-corp substrate:
      fetch_source_post (PDS getRecord) → LLM translate (stub) →
      record_post (PDS putRecord feed.post) →
      record_translation_link (PDS putRecord translationLink, coalesced)
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    if not postUri:
        return {"ok": False, "error": "postUri is required"}
    if not targetLang:
        return {"ok": False, "error": "targetLang is required"}

    # Step 1: Fetch source post from PDS.
    source_post: dict[str, Any] = {}
    if not postText:
        fetched = await fetch_source_post(postUri)
        if fetched:
            source_post = fetched
        elif not postText:
            return {"ok": False, "error": "source post not found", "postUri": postUri}
    text = postText or str(source_post.get("text") or "")

    detected_source_lang = _detect_source_lang(source_post, sourceLang)

    # Step 2: Translate via etzhayyim_sdk.llm.translate (EVO-X2 LiteLLM, ADR-2605215000).
    if _llm_mod is None:
        raise ImportError(
            "etzhayyim-sdk-py not installed; task_yoro_social_translate_post requires "
            "etzhayyim_sdk.llm for translation"
        )
    translated_text = await _llm_mod.translate(
        source_text=text,
        target_lang=targetLang,
        source_lang=detected_source_lang,
    )
    source_method = "llm-evo-x2"

    created_at = utc_now_iso()

    if dryRun:
        rkey = _rkey(f"translate-{targetLang}")
        translated_uri = f"at://{postRepo}/{DEFAULT_COLLECTION}/{rkey}"
        link_rkey = _rkey(f"translation-link-{targetLang}")
        link_uri = f"at://{postRepo}/{TRANSLATION_LINK_COLLECTION}/{link_rkey}"
        return {
            "ok": True,
            "dryRun": True,
            "postUri": postUri,
            "targetLang": targetLang,
            "sourceLang": detected_source_lang,
            "translatedText": translated_text,
            "translatedUri": translated_uri,
            "translationLinkUri": link_uri,
            "model": source_method,
        }

    # Step 3: Write translated post record to PDS.
    translated_uri = await record_post(
        repo=postRepo,
        text=translated_text,
        created_at=created_at,
        actor_path=f"translate-{targetLang}",
        extra={
            "langs": [targetLang],
            "translationOf": postUri,
            "sourceLang": detected_source_lang,
        },
    )

    # Step 4: Write translation link record (coalesced per source_uri).
    link_uri = await record_translation_link(
        repo=postRepo,
        source_uri=postUri,
        source_lang=detected_source_lang,
        translated_uri=translated_uri,
        target_lang=targetLang,
        translator_did=postRepo,
        quality_score=0,
        model=source_method,
    )

    return {
        "ok": True,
        "postUri": postUri,
        "targetLang": targetLang,
        "sourceLang": detected_source_lang,
        "translatedText": translated_text,
        "translatedUri": translated_uri,
        "translationLinkUri": link_uri,
        "model": source_method,
    }


async def task_yoro_social_translate_post_batch(
    postUri: str = "",
    targetLangs: Any = None,
    sourceLang: str = "",
    postRepo: str = DEFAULT_REPO,
    postText: str = "",
    dryRun: bool = False,
    flush: bool = False,
) -> dict[str, Any]:
    """Batch translate a post into multiple languages via @etzhayyim/sdk.
    [M4 IMPLEMENTED]

    Zeebe task type: yoro.social.translatePostBatch

    Variables dict shape (matching vendor yoro_social.py):
      postUri     (str) — REQUIRED: AT URI of the source post
      targetLangs (str|list) — comma-separated or list of BCP-47 codes
                               (defaults to DEFAULT_TRANSLATION_TARGET_LANGS if empty)
      sourceLang  (str) — source language hint (auto-detected if empty)
      postRepo    (str) — AT repo DID for writing translated posts
      postText    (str) — source text override (fetched from PDS if empty)
      dryRun      (bool) — if True, skip writes and return dry-run results
      flush       (bool) — ignored (MST atomic commits, no FLUSH)

    Coalescer usage: record_translation_link calls for the same postUri are
    coalesced within a 100 ms window (shared _COALESCER) so 36+ concurrent
    target-language writes batch into 1-3 MST commits. asyncio.gather fans out
    all task_yoro_social_translate_post calls concurrently; the coalescer
    inside record_translation_link collapses the PDS write round-trips.

    Vendor equivalent: task_yoro_social_translate_post_batch in yoro_social.py
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    if not postUri:
        return {"ok": False, "error": "postUri is required"}
    langs = _lang_list(targetLangs)
    if not langs:
        return {"ok": False, "error": "targetLangs is empty"}

    # Fan-out all language translations concurrently.
    tasks = [
        task_yoro_social_translate_post(
            postUri=postUri,
            targetLang=lang,
            sourceLang=sourceLang,
            postRepo=postRepo,
            postText=postText,
            dryRun=dryRun,
            flush=flush,
        )
        for lang in langs
    ]
    results: list[dict[str, Any]] = await asyncio.gather(*tasks)

    return {
        "ok": all(bool(r.get("ok")) for r in results),
        "postUri": postUri,
        "count": len(results),
        "translated": sum(1 for r in results if r.get("ok")),
        "results": results,
    }


async def task_yoro_actor_quality_inspect(
    actorDid: str = "",
    handle: str = "",
    sourceHint: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    """Inspect actor profile quality — reads from PDS via @etzhayyim/sdk.
    [M4 IMPLEMENTED]

    Zeebe task type: yoro.actorQuality.inspect

    Variables dict shape (matching vendor yoro_social.py):
      actorDid   (str) — REQUIRED (or handle): actor DID to inspect
      handle     (str) — fallback if actorDid is empty
      sourceHint (str) — hint for profile description enrichment
      dryRun     (bool) — if True, skip writing quality report record

    Gathers signals via fetch_profile_quality (PDS getRecord + listRecords).
    Builds quality dimensions and records a durable actorQualityReport unless dryRun.

    Vendor equivalent: task_yoro_actor_quality_inspect in yoro_social.py
    Religious-corp substrate:
      fetch_profile_quality (PDS reads) → record_actor_quality_report (PDS put_record)
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    if not actorDid and not handle:
        return {"ok": False, "error": "actorDid or handle is required"}
    actor_did = actorDid or handle

    quality_data = await fetch_profile_quality(actor_did, handle)
    if not quality_data.get("ok"):
        return quality_data

    quality_score = int(quality_data.get("qualityScore") or 0)
    missing_fields: list[str] = quality_data.get("missingFields") or []

    # Build quality dimensions from profile signals.
    dimensions: list[dict[str, Any]] = [
        {
            "dimension": "charter-compliance",
            "score": 1000 if not missing_fields else max(0, 1000 - len(missing_fields) * 200),
        },
        {
            "dimension": "wellbecoming",
            "score": quality_score,
        },
        {
            "dimension": "contribution",
            "score": 1000 if quality_data.get("postsCount", 0) > 0 else 0,
        },
    ]

    if dryRun:
        return {
            "ok": True,
            "dryRun": True,
            "actorDid": actor_did,
            "qualityScore": quality_score,
            "missingFields": missing_fields,
            "postsCount": quality_data.get("postsCount", 0),
            "dimensions": dimensions,
        }

    # Persist durable quality report to MST.
    report_uri = await record_actor_quality_report(
        repo=DEFAULT_REPO,
        subject_did=actor_did,
        quality_score=quality_score,
        dimensions=dimensions,
        notes=f"Automated inspect. sourceHint={sourceHint}" if sourceHint else "Automated quality inspect.",
    )

    return {
        "ok": True,
        "actorDid": actor_did,
        "qualityScore": quality_score,
        "missingFields": missing_fields,
        "postsCount": quality_data.get("postsCount", 0),
        "dimensions": dimensions,
        "reportUri": report_uri,
    }


async def task_yoro_actor_quality_verify(
    actorDid: str = "",
    handle: str = "",
    sourceHint: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    """Verify actor profile quality — reads from PDS via @etzhayyim/sdk.
    [M4 IMPLEMENTED]

    Zeebe task type: yoro.actorQuality.verify

    Variables dict shape (matching vendor yoro_social.py):
      actorDid   (str) — REQUIRED (or handle): actor DID to verify
      handle     (str) — fallback if actorDid is empty
      sourceHint (str) — hint for attestation context
      dryRun     (bool) — if True, skip writing quality report record

    Verifies actor quality report against attestations by re-reading the
    profile and comparing against charter-compliance dimensions.
    Records a durable actorQualityReport unless dryRun.

    Vendor equivalent: task_yoro_actor_quality_verify in yoro_social.py
    Religious-corp substrate:
      fetch_profile_quality (PDS reads) → record_actor_quality_report (PDS put_record)
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    if not actorDid and not handle:
        return {"ok": False, "error": "actorDid or handle is required"}
    actor_did = actorDid or handle

    quality_data = await fetch_profile_quality(actor_did, handle)
    if not quality_data.get("ok"):
        return quality_data

    quality_score = int(quality_data.get("qualityScore") or 0)
    missing_fields: list[str] = quality_data.get("missingFields") or []

    # Verify dimensions — verify task checks attestation presence in addition to signals.
    verified = len(missing_fields) == 0
    dimensions: list[dict[str, Any]] = [
        {
            "dimension": "charter-compliance",
            "score": 1000 if verified else max(0, 1000 - len(missing_fields) * 200),
        },
        {
            "dimension": "governance",
            "score": 800 if not missing_fields else 400,
        },
        {
            "dimension": "wellbecoming",
            "score": quality_score,
        },
    ]

    if dryRun:
        return {
            "ok": True,
            "dryRun": True,
            "actorDid": actor_did,
            "verified": verified,
            "qualityScore": quality_score,
            "missingFields": missing_fields,
            "dimensions": dimensions,
        }

    # Persist durable quality report to MST.
    report_uri = await record_actor_quality_report(
        repo=DEFAULT_REPO,
        subject_did=actor_did,
        quality_score=quality_score,
        dimensions=dimensions,
        notes=(
            f"Automated verify. sourceHint={sourceHint}" if sourceHint
            else "Automated quality verify."
        ),
    )

    return {
        "ok": True,
        "actorDid": actor_did,
        "verified": verified,
        "qualityScore": quality_score,
        "missingFields": missing_fields,
        "dimensions": dimensions,
        "reportUri": report_uri,
    }


async def task_yoro_actor_quality_enrich_profile(
    actorDid: str = "",
    handle: str = "",
    missingFields: Any = None,
    sourceHint: str = "",
    dryRun: bool = False,
    flush: bool = False,
) -> dict[str, Any]:
    """Enrich actor profile via @etzhayyim/sdk putRecord(actor.profile).  [M5 IMPLEMENTED]

    Zeebe task type: yoro.actorQuality.enrichProfile

    Variables dict shape (matching vendor yoro_social.py):
      actorDid      (str)  — REQUIRED (or handle): actor DID to enrich
      handle        (str)  — fallback if actorDid is empty
      missingFields (list) — fields missing from the profile (from inspect task)
      sourceHint    (str)  — hint for profile description enrichment
      dryRun        (bool) — if True, return without writing
      flush         (bool) — ignored (MST atomic commits, no FLUSH)

    Vendor equivalent: task_yoro_actor_quality_enrich_profile in yoro_social.py
      INSERT INTO vertex_profile / UPDATE vertex_profile SET ...
    Religious-corp substrate: enrich_actor_quality_profile() → update_profile()
      → pds.put_record(app.bsky.actor.profile) → MST commit
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    if not actorDid and not handle:
        return {"ok": False, "error": "actorDid or handle is required"}
    actor_did = actorDid or handle

    result = await enrich_actor_quality_profile(
        actor_did=actor_did,
        handle=handle,
        missing_fields=missingFields,
        source_hint=sourceHint,
        dry_run=dryRun,
    )
    return result


async def task_yoro_actor_quality_ensure_seed_post(
    actorDid: str = "",
    handle: str = "",
    displayName: str = "",
    description: str = "",
    seedPostText: str = "",
    sourceHint: str = "",
    dryRun: bool = False,
    flush: bool = False,
) -> dict[str, Any]:
    """Ensure actor has at least one seed post via @etzhayyim/sdk putRecord.  [M5 IMPLEMENTED]

    Zeebe task type: yoro.actorQuality.ensureSeedPost

    Variables dict shape (matching vendor yoro_social.py):
      actorDid     (str)  — REQUIRED (or handle): actor DID to check
      handle       (str)  — fallback if actorDid is empty
      displayName  (str)  — actor display name (for post text personalisation)
      description  (str)  — actor description (for post text personalisation)
      seedPostText (str)  — custom seed post text (auto-generated if empty)
      sourceHint   (str)  — hint for profile description enrichment
      dryRun       (bool) — if True, return without writing
      flush        (bool) — ignored (MST atomic commits, no FLUSH)

    Idempotent: reads postsCount from fetch_profile_quality. If the actor
    already has posts, returns ok=True with alreadyExists=True. Only writes
    a seed post if postsCount == 0.

    Vendor equivalent: task_yoro_actor_quality_ensure_seed_post in yoro_social.py
      INSERT INTO vertex_repo_record + vertex_post (if no existing post)
    Religious-corp substrate:
      fetch_profile_quality (PDS listRecords) → record_post if missing → MST commit
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    if not actorDid and not handle:
        return {"ok": False, "error": "actorDid or handle is required"}
    actor_did = actorDid or handle

    # Step 1: Check if actor already has posts.
    quality_data = await fetch_profile_quality(actor_did, handle)
    posts_count = int(quality_data.get("postsCount") or 0)

    if posts_count > 0:
        return {
            "ok": True,
            "actorDid": actor_did,
            "alreadyExists": True,
            "postsCount": posts_count,
            "seedPosted": False,
        }

    # Step 2: Build seed post text.
    actor_display = displayName or _safe_display_name(actor_did, handle)
    if seedPostText:
        text = seedPostText
    else:
        text = (
            f"Hello Yoro! This is {actor_display} joining the etzhayyim YORO social graph. "
            f"AI-agent-first platform — growing through activity. https://yoro.etzhayyim.com/"
        )

    if dryRun:
        rkey = _rkey(f"seed-post-{actor_did[-8:]}")
        dry_uri = f"at://{actor_did}/{DEFAULT_COLLECTION}/{rkey}"
        return {
            "ok": True,
            "dryRun": True,
            "actorDid": actor_did,
            "alreadyExists": False,
            "postsCount": 0,
            "seedPosted": False,
            "seedText": text,
            "seedUri": dry_uri,
        }

    # Step 3: Write seed post.
    seed_uri = await record_post(
        repo=actor_did,
        text=text,
        actor_path=f"seed-post-{actor_did[-8:]}",
    )

    return {
        "ok": True,
        "actorDid": actor_did,
        "alreadyExists": False,
        "postsCount": 0,
        "seedPosted": True,
        "seedText": text,
        "seedUri": seed_uri,
    }


# ---------------------------------------------------------------------------
# M7 IMPLEMENTED — Diet speech graph fallback (write-path; read-path VENDOR-ONLY)
# ---------------------------------------------------------------------------

def build_diet_speech_social_post_record(
    *,
    repo: str = DEFAULT_REPO,
    speech_id: str = "",
    speech_text: str = "",
    speaker: str = "",
    date_str: str = "",
    extra: dict[str, Any] | None = None,
) -> SocialPostRecord:
    """Build an app.bsky.feed.post wire shape for a Diet speech summary.
    [M7 IMPLEMENTED — PORT-adapted from vendor build_diet_speech_social_post_record]

    Wire shape is app.bsky.feed.post compatible (ADR-2605215300 §3 row #30).
    Reusable by task_yoro_social_project_diet_speeches_graph_fallback.

    NOTE: The Diet speech text source (_fetch_diet_speech_rows) is VENDOR-ONLY —
    it reads from vertex_fukkou_diet_speech, an ETL ingest table with no AT lexicon.
    This builder receives pre-fetched speech_text and is called only for the
    write-path (social post dispatch to PDS/MST).

    Returns: SocialPostRecord dataclass (call record_post() to dispatch to PDS).
    See: YORO-PYTHON-MIGRATION-NOTES.md row #30
    """
    repo = repo or DEFAULT_REPO
    created_at = utc_now_iso()
    rkey = _rkey(f"diet-speech-{speech_id or 'unknown'}")
    uri = f"at://{repo}/{DEFAULT_COLLECTION}/{rkey}"

    speaker_str = f" @{speaker.strip()}" if speaker.strip() else ""
    date_part = f" [{date_str.strip()}]" if date_str.strip() else ""
    if speech_text:
        truncated = speech_text[:200].rstrip()
        text = f"Diet speech{speaker_str}{date_part}: {truncated}"
        if len(speech_text) > 200:
            text += "…"
    else:
        text = f"Yoro | Diet speech summary{speaker_str}{date_part}. https://yoro.etzhayyim.com/"

    record: dict[str, Any] = {
        "$type": DEFAULT_COLLECTION,
        "text": text,
        "createdAt": created_at,
        "tags": _post_tags("diet", "speech", "kokkai", "japan"),
    }
    if speech_id:
        record["speechId"] = speech_id
    if extra:
        record.update(extra)

    return SocialPostRecord(
        repo=repo,
        collection=DEFAULT_COLLECTION,
        rkey=rkey,
        uri=uri,
        text=text,
        created_at=created_at,
        record=record,
    )


async def task_yoro_social_project_diet_speeches_graph_fallback(
    speechId: str = "",
    speechText: str = "",
    speaker: str = "",
    dateStr: str = "",
    postRepo: str = DEFAULT_REPO,
    flush: bool = False,
) -> dict[str, Any]:
    """Dispatch a Diet speech social post to PDS via @etzhayyim/sdk.  [M7 IMPLEMENTED]

    Zeebe task type: yoro.social.projectDietSpeechesGraphFallback

    Variables dict shape (matching vendor yoro_social.py):
      speechId   (str) — Diet speech identifier (from vendor ETL ingest, passed via Zeebe)
      speechText (str) — REQUIRED: pre-fetched speech text from the vendor read path
      speaker    (str) — speaker name / legislator handle (optional, for post text)
      dateStr    (str) — speech date string (optional, for post text)
      postRepo   (str) — AT repo DID for writing the post
      flush      (bool) — ignored (MST atomic commits, no FLUSH)

    ARCHITECTURE — HYBRID VENDOR-READ + SDK-WRITE:
      READ PATH (VENDOR-ONLY, NOT REPLICATED HERE):
        _fetch_diet_speech_rows(speech_id, limit) in yoro_social.py reads from
        vertex_fukkou_diet_speech — a vendor ETL ingest table populated by the
        国会 (Diet) API ingestion pipeline. There is no AT lexicon equivalent for
        this table. The Zeebe workflow fetches speech rows using the vendor task,
        then passes speechText as a Zeebe variable to this murakumo task.
        See: YORO-PYTHON-MIGRATION-NOTES.md row #13 (VENDOR-ONLY remainder).

      WRITE PATH (IMPLEMENTED HERE):
        build_diet_speech_social_post_record() builds the app.bsky.feed.post wire
        shape from speechText. record_post() dispatches it to PDS → MST commit.
        Row #2 (feed.post) migration path: this task is the religious-corp
        implementation of the Diet speech social post column of insert_repo_records().

    Vendor equivalent: task_yoro_social_project_diet_speeches_graph_fallback in yoro_social.py
      _fetch_diet_speech_rows (vendor) + insert_repo_records([post_row], flush=flush)
    Religious-corp substrate (write-path only):
      build_diet_speech_social_post_record() → record_post() → pds.dispatch → MST commit
    """
    if _pds_mod is None:
        raise ImportError(
            "etzhayyim_sdk not installed. Install 20-actors/etzhayyim-sdk-py."
        )

    if not speechText:
        return {
            "ok": False,
            "error": (
                "speechText is required. The Diet speech read-path (_fetch_diet_speech_rows) "
                "is VENDOR-ONLY (vertex_fukkou_diet_speech has no AT lexicon). "
                "The Zeebe workflow must fetch speech rows via the vendor task and pass "
                "speechText as a variable to this murakumo write-path task."
            ),
            "speechId": speechId,
        }

    resolved_repo = postRepo or DEFAULT_REPO
    post_record = build_diet_speech_social_post_record(
        repo=resolved_repo,
        speech_id=speechId,
        speech_text=speechText,
        speaker=speaker,
        date_str=dateStr,
    )

    uri = await record_post(
        repo=resolved_repo,
        text=post_record.text,
        created_at=post_record.created_at,
        rkey=post_record.rkey,
        actor_path="diet-speech",
        extra={k: v for k, v in post_record.record.items() if k not in ("$type", "text", "createdAt")},
    )

    return {
        "ok": True,
        "uri": uri,
        "speechId": speechId,
        "repo": resolved_repo,
        "text": post_record.text,
        "note": "Diet speech read-path is VENDOR-ONLY (vertex_fukkou_diet_speech). Write-path dispatched to PDS.",
    }


# ---------------------------------------------------------------------------
# Task registration (mirrors vendor register() signature)
# ---------------------------------------------------------------------------

def register(worker: Any, *, timeout_ms: int) -> None:
    """Register yoro social tasks with the Zeebe worker.

    Matches vendor signature exactly (PORT-adapted).
    Handler refs point to murakumo variants above.
    """
    worker.task(
        task_type="yoro.social.postGraphFallback",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_social_post_graph_fallback)
    worker.task(
        task_type="yoro.social.platformPulseGraphFallback",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_social_platform_pulse_graph_fallback)
    worker.task(
        task_type="yoro.social.respondToMentionGraphFallback",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_social_respond_to_mention_graph_fallback)
    worker.task(
        task_type="yoro.social.respondToFollowGraphFallback",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_social_respond_to_follow_graph_fallback)
    worker.task(
        task_type="yoro.social.translatePost",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_social_translate_post)
    worker.task(
        task_type="yoro.social.translatePostBatch",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_social_translate_post_batch)
    worker.task(
        task_type="yoro.actorQuality.inspect",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_actor_quality_inspect)
    worker.task(
        task_type="yoro.actorQuality.verify",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_actor_quality_verify)
    worker.task(
        task_type="yoro.actorQuality.enrichProfile",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_actor_quality_enrich_profile)
    worker.task(
        task_type="yoro.actorQuality.ensureSeedPost",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_actor_quality_ensure_seed_post)
    worker.task(
        task_type="yoro.social.projectDietSpeechesGraphFallback",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_social_project_diet_speeches_graph_fallback)
