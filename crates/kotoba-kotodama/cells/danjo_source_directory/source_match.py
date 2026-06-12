"""Pure public-accountability fiscal-SOURCE DIRECTORY-QUERY core for ``danjo`` (弾正).

Per ADR-2605301600 (danjo — public-accountability oversight Tier-B actor; the
"censor's eye, no sword": it ingests official public-fiscal records and emits
NON-ADJUDICATING discrepancy observations only) and the worldwide seed directory
shipped at ``20-actors/danjo/registry/sources.seed.json``. This directory routes
to OFFICIAL public-accountability data sources — audit institutions, budget
portals, legislature records, procurement systems, open-spending datasets, and
international aggregators.

CONSTITUTIONAL CEILING (CRITICAL — IMMUTABLE):
  * **Non-adjudicating (censor's eye, no sword)** — danjo finds + observes; it
    never rules, sanctions, or adjudicates. ``is_adjudication`` /
    ``isAdjudication`` is ALWAYS ``False`` with no code path to flip it.
  * **Asserts no wrongdoing** — surfacing a fiscal source is NOT an allegation,
    finding, or imputation of wrongdoing against any entity; it is wayfinding to
    the official dataset. ``asserts_wrongdoing`` / ``assertsWrongdoing`` is
    ALWAYS ``False``.
  * **Observational, public-source-only** — routes to OFFICIAL public-fiscal
    sources; no surveillance, no private-target dossier. No ranking beyond the
    registry's own ``confidence`` then ``title``. Unknown jurisdiction → ``[]``
    (never a guessed / nearest-neighbour match).
  * **No PII persistence** beyond the jurisdiction string; pure stdlib, no
    network.

R0/R1 BOUNDARY (CRITICAL): this pure core is importable independently of the
deployable Pregel cell. ``cell.py`` (the ``DanjoSourceDirectoryCell`` graph)
stays non-deployable until Council ratification (Lv6+ ≥3, post Bootstrap
Council RFP 2026-06-19). Landing + testing this core does NOT activate the cell.

Output shape mirrors a directory-routing view over Lexicon
``com.etzhayyim.danjo.fiscalSource`` (the registry's ``$schema``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ── confidence ordering (the registry's OWN ranking signal) ─────────────
# Lower sort-key sorts FIRST. The seed ships {"high", "medium", "low"}.
# No other ranking signal is permitted (no adjudication-flavoured scoring).
CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}

# Known fiscal-source kinds (ADR-2605301600). All are routing TARGETS — official
# public-accountability datasets. An entry whose ``sourceKind`` is outside this
# set raises in ``_to_source`` (no guessing, no unknown source routed).
SOURCE_KINDS = frozenset(
    {
        "audit-institution",
        "budget-portal",
        "legislature-record",
        "procurement-system",
        "open-spending",
        "intl-aggregator",
    }
)

# verificationStatus values routable when the caller declines unverified-seed
# entries; whether to surface ``unverified-seed`` is caller policy.
_VERIFIED_STATUSES = frozenset({"verified", "council-verified"})

# Free-text topic matching searches these registry fields. Wayfinding FILTERING
# only — surfaces which sources cover a fiscal area; it never adjudicates or
# imputes wrongdoing.
_SEARCH_FIELDS = ("title", "authority", "format", "legalBasis", "notes", "sourceKind")


@dataclass(frozen=True)
class SourceQuery:
    """Member-confirmed routing facts. No PII beyond the jurisdiction string."""

    jurisdiction: str  # registry bloc code, e.g. jpn / usa / intl-*
    topic: str | None = None  # OPTIONAL free-text label; None = no filter
    source_kind: str | None = None  # OPTIONAL exact kind filter; None = any
    allow_unverified: bool = True  # surface unverified-seed entries (policy)


@dataclass(frozen=True)
class FiscalSource:
    """One resolved directory TARGET — never an adjudication or allegation."""

    source_id: str
    title: str
    jurisdiction: str
    source_kind: str
    confidence: str
    verification_status: str
    authority: str
    dataset_url: str
    format: str
    legal_basis: str
    language: str
    provenance: str
    last_verified: str
    notes: str
    is_adjudication: bool  # ALWAYS False
    asserts_wrongdoing: bool  # ALWAYS False


@dataclass(frozen=True)
class SourceResult:
    jurisdiction: str
    topic: str | None
    source_kind: str | None
    is_adjudication: bool  # ALWAYS False
    asserts_wrongdoing: bool  # ALWAYS False
    sources: tuple[FiscalSource, ...] = field(default_factory=tuple)


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


def _to_source(entry: dict) -> FiscalSource:
    """Project one raw registry dict → a frozen :class:`FiscalSource`.

    An unknown ``sourceKind`` raises — no unknown source is ever routed.
    """
    if not isinstance(entry, dict):
        raise ValueError(f"registry entry must be a dict, got {type(entry).__name__}")
    source_id = _require_str(entry.get("sourceId"), "sourceId")
    title = _require_str(entry.get("title"), "title")
    jurisdiction = _require_str(entry.get("jurisdiction"), "jurisdiction")
    source_kind = _require_str(entry.get("sourceKind"), "sourceKind")
    if source_kind not in SOURCE_KINDS:
        raise ValueError(
            f"unknown sourceKind {source_kind!r}; allowed: {sorted(SOURCE_KINDS)}"
        )
    confidence = _require_str(entry.get("confidence"), "confidence")
    _confidence_rank(confidence)  # validate early (raises on unknown)
    return FiscalSource(
        source_id=source_id,
        title=title,
        jurisdiction=jurisdiction,
        source_kind=source_kind,
        confidence=confidence,
        verification_status=str(entry.get("verificationStatus", "")),
        authority=str(entry.get("authority", "")),
        dataset_url=str(entry.get("datasetUrl", "")),
        format=str(entry.get("format", "")),
        legal_basis=str(entry.get("legalBasis", "")),
        language=str(entry.get("language", "")),
        provenance=str(entry.get("provenance", "")),
        last_verified=str(entry.get("lastVerified", "")),
        notes=str(entry.get("notes", "")),
        is_adjudication=False,  # censor's eye, no sword — never adjudicates
        asserts_wrongdoing=False,  # routes to a source, imputes nothing
    )


def _topic_matches(entry: dict, needle: str) -> bool:
    """Case-insensitive substring test over the registry's text fields.

    Wayfinding FILTERING only — surfaces which sources cover a fiscal area; it
    never adjudicates or imputes wrongdoing.
    """
    hay = " ".join(str(entry.get(k, "")) for k in _SEARCH_FIELDS).lower()
    return needle in hay


def resolve_sources(query: SourceQuery, registry: dict) -> SourceResult:
    """Pure registry query: jurisdiction (+ optional topic/kind) → sources.

    Sorted by the registry's own ``confidence`` (high→medium→low) then ``title``
    (case-insensitive, stable). Unknown jurisdiction → empty result (never a
    guessed match). ``is_adjudication`` / ``asserts_wrongdoing`` are hard-wired
    ``False``.
    """
    jurisdiction = _require_str(query.jurisdiction, "jurisdiction").lower()
    topic = query.topic
    if topic is not None:
        topic = _require_str(topic, "topic").lower()
    source_kind = query.source_kind
    if source_kind is not None:
        source_kind = _require_str(source_kind, "source_kind")
        if source_kind not in SOURCE_KINDS:
            raise ValueError(
                f"unknown source_kind {source_kind!r}; allowed: {sorted(SOURCE_KINDS)}"
            )

    if not isinstance(registry, dict):
        raise ValueError("registry must be a dict (parsed sources.seed.json)")
    raw = registry.get("sources")
    if not isinstance(raw, list):
        raise ValueError("registry must carry a 'sources' list")

    matches: list[FiscalSource] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each source entry must be a dict")
        if str(entry.get("jurisdiction", "")).lower() != jurisdiction:
            continue
        if source_kind is not None and str(entry.get("sourceKind", "")) != source_kind:
            continue
        if not query.allow_unverified:
            if str(entry.get("verificationStatus", "")) not in _VERIFIED_STATUSES:
                continue
        if topic is not None and not _topic_matches(entry, topic):
            continue
        matches.append(_to_source(entry))

    matches.sort(key=lambda s: (_confidence_rank(s.confidence), s.title.casefold()))
    return SourceResult(
        jurisdiction=jurisdiction,
        topic=topic,
        source_kind=source_kind,
        is_adjudication=False,
        asserts_wrongdoing=False,
        sources=tuple(matches),
    )


def _iso_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _source_view(s: FiscalSource) -> dict:
    return {
        "sourceId": s.source_id,
        "title": s.title,
        "jurisdiction": s.jurisdiction,
        "sourceKind": s.source_kind,
        "confidence": s.confidence,
        "verificationStatus": s.verification_status,
        "authority": s.authority,
        "datasetUrl": s.dataset_url,
        "format": s.format,
        "legalBasis": s.legal_basis,
        "language": s.language,
        "provenance": s.provenance,
        "lastVerified": s.last_verified,
    }


def to_source_routing_record(
    result: SourceResult,
    *,
    member_did: str,
    created_at: datetime,
    session_ref: str | None = None,
) -> dict:
    """Build a ``com.etzhayyim.danjo.fiscalSource`` directory-routing record.

    ``isAdjudication`` / ``assertsWrongdoing`` are asserted ``False`` before
    return — structural invariants this function cannot violate. The record is a
    pure wayfinding view to OFFICIAL public-fiscal sources; it carries NO ruling,
    NO allegation, and NO compensation field (Public-Fund-routed, zero charge).
    """
    rec: dict = {
        "memberDid": member_did,
        "jurisdiction": result.jurisdiction,
        "isAdjudication": False,
        "assertsWrongdoing": False,
        "sourceCount": len(result.sources),
        "sources": [_source_view(s) for s in result.sources],
        "createdAt": _iso_dt(created_at),
    }
    if result.topic is not None:
        rec["topicLabel"] = result.topic
    if result.source_kind is not None:
        rec["sourceKindFilter"] = result.source_kind
    if session_ref is not None:
        rec["sessionRef"] = session_ref
    assert rec["isAdjudication"] is False, "invariant: isAdjudication must be False"
    assert rec["assertsWrongdoing"] is False, "invariant: assertsWrongdoing must be False"
    return rec


def load_registry(path: str | Path) -> dict:
    """Read + parse the fiscal-source seed registry JSON. Stdlib only."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("sources"), list):
        raise ValueError(f"{path} is not a valid fiscal-source registry")
    return data


__all__ = [
    "CONFIDENCE_ORDER",
    "SOURCE_KINDS",
    "SourceQuery",
    "FiscalSource",
    "SourceResult",
    "resolve_sources",
    "to_source_routing_record",
    "load_registry",
]
