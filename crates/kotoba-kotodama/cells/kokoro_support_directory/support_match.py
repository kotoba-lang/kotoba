"""Pure mental-health SUPPORT-LINE DIRECTORY-QUERY core for ``kokoro`` (心).

Per ADR-2605263700 (kokoro — community/spiritual/relational mental-health
SUPPORT routing, **NOT clinical psychiatry / NOT licensed psychology /
NOT diagnosis or treatment**) and the worldwide seed directory shipped at
``20-actors/kokoro/registry/support-lines.seed.json``.

CONSTITUTIONAL CEILING (CRITICAL — IMMUTABLE):
  * **Renders no clinical opinion** — kokoro "renders no clinical opinion; it
    only routes" (seed note). This module ROUTES a member to an OFFICIAL crisis
    hotline / emergency number / support line. ``renders_clinical_opinion`` /
    ``rendersClinicalOpinion`` is ALWAYS ``False`` with no code path to flip it.
  * **Not a diagnosis, not a treatment** — ``is_diagnosis`` and ``is_treatment``
    are ALWAYS ``False``. Surfacing a line is NOT an assessment of the member's
    state, and NOT a course of treatment.
  * **Not itself a crisis responder** — for immediate life-threatening danger
    the directory routes to the OFFICIAL emergency number; kokoro is not 110 /
    119 / 911 / a clinical service and does not stand in for one.
  * **No ranking beyond the registry's own ``confidence`` then ``title``** —
    no inference, no relevance scoring (Charter §1.13 Wellbecoming; ADR-2605215000
    Murakumo-only forbids commercial mental-health AI). Emergency-triage ordering
    is the CALLER / cell's concern, never invented by this pure query.
  * **No surveillance, no PII persistence** beyond the jurisdiction string; pure
    stdlib, no network. Unknown jurisdiction → ``[]`` (never a guessed match).

R0/R1 BOUNDARY (CRITICAL): this pure core is importable independently of the
deployable Pregel cell. ``cell.py`` (the ``KokoroSupportDirectoryCell`` graph)
stays non-deployable until Council ratification (Lv6+ ≥3, post Bootstrap
Council RFP 2026-06-19). Landing + testing this core does NOT activate the cell.

Output shape mirrors a directory-routing view over Lexicon
``com.etzhayyim.kokoro.supportLine`` (the registry's ``$schema``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ── confidence ordering (the registry's OWN ranking signal) ─────────────
# Lower sort-key sorts FIRST. The seed ships {"high", "medium"}; "low" is
# included for forward-compatibility. No other ranking signal is permitted.
CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}

# Known support-line kinds (ADR-2605263700). All are routing TARGETS; none is a
# clinical service rendered BY kokoro. An entry whose ``supportKind`` is outside
# this set raises in ``_to_line`` (no guessing, no unknown service routed).
SUPPORT_KINDS = frozenset(
    {
        "emergency-number",
        "crisis-hotline",
        "text-or-chat-line",
        "youth-line",
        "specialized-line",
        "intl-directory",
    }
)

# verificationStatus values routable when the caller declines unverified-seed
# entries; whether to surface ``unverified-seed`` is caller policy.
_VERIFIED_STATUSES = frozenset({"verified", "council-verified"})

# Free-text topic matching searches these registry fields. Wayfinding FILTERING
# only — it surfaces which lines cover a topic (e.g. "youth", "text"); it never
# classifies the member's state or renders a clinical opinion.
_SEARCH_FIELDS = ("title", "organization", "notes", "supportKind", "languages")


@dataclass(frozen=True)
class SupportQuery:
    """Member-confirmed routing facts. No PII beyond the jurisdiction string."""

    jurisdiction: str  # registry bloc code, e.g. jpn / usa / intl-iasp
    topic: str | None = None  # OPTIONAL free-text label; None = no filter
    support_kind: str | None = None  # OPTIONAL exact kind filter; None = any
    allow_unverified: bool = True  # surface unverified-seed entries (policy)


@dataclass(frozen=True)
class SupportLine:
    """One resolved directory TARGET — never a clinical service of kokoro's."""

    line_id: str
    title: str
    jurisdiction: str
    support_kind: str
    confidence: str
    verification_status: str
    organization: str
    contact: str
    hours: str
    languages: str
    cost: str
    provenance: str
    last_verified: str
    notes: str
    renders_clinical_opinion: bool  # ALWAYS False
    is_diagnosis: bool  # ALWAYS False
    is_treatment: bool  # ALWAYS False


@dataclass(frozen=True)
class SupportResult:
    jurisdiction: str
    topic: str | None
    support_kind: str | None
    renders_clinical_opinion: bool  # ALWAYS False
    is_diagnosis: bool  # ALWAYS False
    is_treatment: bool  # ALWAYS False
    lines: tuple[SupportLine, ...] = field(default_factory=tuple)


def _require_str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string, got {type(value).__name__}")
    norm = value.strip()
    if not norm:
        raise ValueError(f"{name} must be a non-empty string")
    return norm


def _confidence_rank(confidence: str) -> int:
    """Sort-key for a registry ``confidence`` value. Unknown → ValueError."""
    if confidence not in CONFIDENCE_ORDER:
        raise ValueError(
            f"unknown confidence {confidence!r}; "
            f"allowed: {sorted(CONFIDENCE_ORDER, key=CONFIDENCE_ORDER.get)}"
        )
    return CONFIDENCE_ORDER[confidence]


def _to_line(entry: dict) -> SupportLine:
    """Project one raw registry dict → a frozen :class:`SupportLine`.

    An unknown ``supportKind`` raises — no unknown service is ever routed.
    """
    if not isinstance(entry, dict):
        raise ValueError(f"registry entry must be a dict, got {type(entry).__name__}")
    line_id = _require_str(entry.get("lineId"), "lineId")
    title = _require_str(entry.get("title"), "title")
    jurisdiction = _require_str(entry.get("jurisdiction"), "jurisdiction")
    support_kind = _require_str(entry.get("supportKind"), "supportKind")
    if support_kind not in SUPPORT_KINDS:
        raise ValueError(
            f"unknown supportKind {support_kind!r}; allowed: {sorted(SUPPORT_KINDS)}"
        )
    confidence = _require_str(entry.get("confidence"), "confidence")
    _confidence_rank(confidence)  # validate early (raises on unknown)
    return SupportLine(
        line_id=line_id,
        title=title,
        jurisdiction=jurisdiction,
        support_kind=support_kind,
        confidence=confidence,
        verification_status=str(entry.get("verificationStatus", "")),
        organization=str(entry.get("organization", "")),
        contact=str(entry.get("contact", "")),
        hours=str(entry.get("hours", "")),
        languages=str(entry.get("languages", "")),
        cost=str(entry.get("cost", "")),
        provenance=str(entry.get("provenance", "")),
        last_verified=str(entry.get("lastVerified", "")),
        notes=str(entry.get("notes", "")),
        renders_clinical_opinion=False,  # kokoro renders no clinical opinion
        is_diagnosis=False,  # not a diagnosis
        is_treatment=False,  # not a treatment
    )


def _topic_matches(entry: dict, needle: str) -> bool:
    """Case-insensitive substring test over the registry's text fields.

    Wayfinding FILTERING only — surfaces which lines cover a topic; it does not
    classify the member's state or render any clinical opinion.
    """
    hay = " ".join(str(entry.get(k, "")) for k in _SEARCH_FIELDS).lower()
    return needle in hay


def resolve_support_lines(query: SupportQuery, registry: dict) -> SupportResult:
    """Pure registry query: jurisdiction (+ optional topic/kind) → support lines.

    Sorted by the registry's own ``confidence`` (high→medium→low) then ``title``
    (case-insensitive, stable). Unknown jurisdiction → empty result (never a
    guessed match). ``renders_clinical_opinion`` / ``is_diagnosis`` /
    ``is_treatment`` are hard-wired ``False``.
    """
    jurisdiction = _require_str(query.jurisdiction, "jurisdiction").lower()
    topic = query.topic
    if topic is not None:
        topic = _require_str(topic, "topic").lower()
    support_kind = query.support_kind
    if support_kind is not None:
        support_kind = _require_str(support_kind, "support_kind")
        if support_kind not in SUPPORT_KINDS:
            raise ValueError(
                f"unknown support_kind {support_kind!r}; allowed: {sorted(SUPPORT_KINDS)}"
            )

    if not isinstance(registry, dict):
        raise ValueError("registry must be a dict (parsed support-lines.seed.json)")
    raw = registry.get("lines")
    if not isinstance(raw, list):
        raise ValueError("registry must carry a 'lines' list")

    matches: list[SupportLine] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each support-line entry must be a dict")
        if str(entry.get("jurisdiction", "")).lower() != jurisdiction:
            continue
        if support_kind is not None and str(entry.get("supportKind", "")) != support_kind:
            continue
        if not query.allow_unverified:
            if str(entry.get("verificationStatus", "")) not in _VERIFIED_STATUSES:
                continue
        if topic is not None and not _topic_matches(entry, topic):
            continue
        matches.append(_to_line(entry))

    matches.sort(key=lambda ln: (_confidence_rank(ln.confidence), ln.title.casefold()))
    return SupportResult(
        jurisdiction=jurisdiction,
        topic=topic,
        support_kind=support_kind,
        renders_clinical_opinion=False,
        is_diagnosis=False,
        is_treatment=False,
        lines=tuple(matches),
    )


def _iso_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _line_view(ln: SupportLine) -> dict:
    return {
        "lineId": ln.line_id,
        "title": ln.title,
        "jurisdiction": ln.jurisdiction,
        "supportKind": ln.support_kind,
        "confidence": ln.confidence,
        "verificationStatus": ln.verification_status,
        "organization": ln.organization,
        "contact": ln.contact,
        "hours": ln.hours,
        "languages": ln.languages,
        "cost": ln.cost,
        "provenance": ln.provenance,
        "lastVerified": ln.last_verified,
    }


def to_support_routing_record(
    result: SupportResult,
    *,
    member_did: str,
    created_at: datetime,
    session_ref: str | None = None,
) -> dict:
    """Build a ``com.etzhayyim.kokoro.supportLine`` directory-routing record.

    ``rendersClinicalOpinion`` / ``isDiagnosis`` / ``isTreatment`` are asserted
    ``False`` before return — structural invariants this function cannot
    violate. The record is a pure wayfinding view to OFFICIAL support lines; it
    carries NO clinical content and NO compensation field (Public-Fund-routed,
    zero charge).
    """
    rec: dict = {
        "memberDid": member_did,
        "jurisdiction": result.jurisdiction,
        "rendersClinicalOpinion": False,
        "isDiagnosis": False,
        "isTreatment": False,
        "lineCount": len(result.lines),
        "lines": [_line_view(ln) for ln in result.lines],
        "createdAt": _iso_dt(created_at),
    }
    if result.topic is not None:
        rec["topicLabel"] = result.topic
    if result.support_kind is not None:
        rec["supportKindFilter"] = result.support_kind
    if session_ref is not None:
        rec["sessionRef"] = session_ref
    assert rec["rendersClinicalOpinion"] is False, "invariant: no clinical opinion"
    assert rec["isDiagnosis"] is False, "invariant: not a diagnosis"
    assert rec["isTreatment"] is False, "invariant: not a treatment"
    return rec


def load_registry(path: str | Path) -> dict:
    """Read + parse the support-line seed registry JSON. Stdlib only."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("lines"), list):
        raise ValueError(f"{path} is not a valid support-line registry")
    return data


__all__ = [
    "CONFIDENCE_ORDER",
    "SUPPORT_KINDS",
    "SupportQuery",
    "SupportLine",
    "SupportResult",
    "resolve_support_lines",
    "to_support_routing_record",
    "load_registry",
]
