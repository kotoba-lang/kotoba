"""Pure death-registration REGISTRY DIRECTORY-QUERY core for ``shidemori`` (死出守).

Per ADR-2605263800 (shidemori — memorial + cemetery / death-record wayfinding
Tier-B actor) and the worldwide seed directory shipped at
``20-actors/shidemori/registry/registries.seed.json``.

CONSTITUTIONAL CEILING (CRITICAL — IMMUTABLE):
  * **Renders no advice (UPL boundary)** — this module ROUTES a bereaved member
    to the OFFICIAL death-registration authority / civil-registry office /
    burial-cremation-permit issuer. It renders NO legal advice, opinion, or
    procedural determination of its own. ``renders_advice`` / ``rendersAdvice``
    is ALWAYS ``False`` with no code path to flip it. The registry's own
    ``procedure`` text is wayfinding scaffold quoting the official process, not
    counsel.
  * **Not an eligibility / obligation determination** — ``is_eligibility_
    determination`` is ALWAYS ``False``. Surfacing an authority is NOT a ruling
    on who must notify, who may collect a permit, or any deadline applying to a
    given person; the official authority performs its own intake.
  * **No ranking beyond the registry's own ``confidence`` then ``title``** — no
    inference, no relevance scoring. Unknown jurisdiction → ``[]`` (never a
    guessed / nearest-neighbour match).
  * **No surveillance, no PII persistence** beyond the jurisdiction string;
    pure stdlib, no network.

R0/R1 BOUNDARY (CRITICAL): this pure core is importable independently of the
deployable Pregel cell. ``cell.py`` (the ``ShidemoriRegistryDirectoryCell``
graph) stays non-deployable until Council ratification (Lv6+ ≥3, post Bootstrap
Council RFP 2026-06-19). Landing + testing this core does NOT activate the cell.

Output shape mirrors a directory-routing view over Lexicon
``com.etzhayyim.shidemori.deathRegistration`` (the registry's ``$schema``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ── confidence ordering (the registry's OWN ranking signal) ─────────────
# Lower sort-key sorts FIRST. The seed ships {"high", "medium", "low"}.
# No other ranking signal is permitted (no advice-flavoured relevance score).
CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}

# Known record kinds (ADR-2605263800). All are routing TARGETS — official
# death-record authorities/offices or open guidance. An entry whose
# ``recordKind`` is outside this set raises in ``_to_record`` (no guessing).
RECORD_KINDS = frozenset(
    {
        "death-registration-authority",
        "death-certificate-issuer",
        "burial-cremation-permit",
        "civil-registry-office",
        "intl-guidance",
    }
)

# verificationStatus values routable when the caller declines unverified-seed
# entries; whether to surface ``unverified-seed`` is caller policy.
_VERIFIED_STATUSES = frozenset({"verified", "council-verified"})

# Free-text topic matching searches these registry fields. Wayfinding FILTERING
# only — it surfaces which authorities handle a step; it never advises or
# determines an obligation.
_SEARCH_FIELDS = ("title", "authority", "procedure", "legalBasis", "notes", "recordKind")


@dataclass(frozen=True)
class RegistryQuery:
    """Member-confirmed routing facts. No PII beyond the jurisdiction string."""

    jurisdiction: str  # registry bloc code, e.g. jpn / usa / intl-guidance
    topic: str | None = None  # OPTIONAL free-text label; None = no filter
    record_kind: str | None = None  # OPTIONAL exact kind filter; None = any
    allow_unverified: bool = True  # surface unverified-seed entries (policy)


@dataclass(frozen=True)
class RegistryRecord:
    """One resolved directory TARGET — never an advice source (UPL boundary)."""

    registry_id: str
    title: str
    jurisdiction: str
    record_kind: str
    confidence: str
    verification_status: str
    authority: str
    access_url: str
    procedure: str
    deadline: str
    legal_basis: str
    language: str
    provenance: str
    last_verified: str
    notes: str
    renders_advice: bool  # ALWAYS False
    is_eligibility_determination: bool  # ALWAYS False


@dataclass(frozen=True)
class RegistryResult:
    jurisdiction: str
    topic: str | None
    record_kind: str | None
    renders_advice: bool  # ALWAYS False
    is_eligibility_determination: bool  # ALWAYS False
    records: tuple[RegistryRecord, ...] = field(default_factory=tuple)


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


def _to_record(entry: dict) -> RegistryRecord:
    """Project one raw registry dict → a frozen :class:`RegistryRecord`.

    An unknown ``recordKind`` raises — no unknown record type is ever routed.
    """
    if not isinstance(entry, dict):
        raise ValueError(f"registry entry must be a dict, got {type(entry).__name__}")
    registry_id = _require_str(entry.get("registryId"), "registryId")
    title = _require_str(entry.get("title"), "title")
    jurisdiction = _require_str(entry.get("jurisdiction"), "jurisdiction")
    record_kind = _require_str(entry.get("recordKind"), "recordKind")
    if record_kind not in RECORD_KINDS:
        raise ValueError(
            f"unknown recordKind {record_kind!r}; allowed: {sorted(RECORD_KINDS)}"
        )
    confidence = _require_str(entry.get("confidence"), "confidence")
    _confidence_rank(confidence)  # validate early (raises on unknown)
    return RegistryRecord(
        registry_id=registry_id,
        title=title,
        jurisdiction=jurisdiction,
        record_kind=record_kind,
        confidence=confidence,
        verification_status=str(entry.get("verificationStatus", "")),
        authority=str(entry.get("authority", "")),
        access_url=str(entry.get("accessUrl", "")),
        procedure=str(entry.get("procedure", "")),
        deadline=str(entry.get("deadline", "")),
        legal_basis=str(entry.get("legalBasis", "")),
        language=str(entry.get("language", "")),
        provenance=str(entry.get("provenance", "")),
        last_verified=str(entry.get("lastVerified", "")),
        notes=str(entry.get("notes", "")),
        renders_advice=False,  # UPL boundary — routes, never advises
        is_eligibility_determination=False,  # not an obligation ruling
    )


def _topic_matches(entry: dict, needle: str) -> bool:
    """Case-insensitive substring test over the registry's text fields.

    Wayfinding FILTERING only — surfaces which authorities handle a step; it
    does not advise or determine an obligation.
    """
    hay = " ".join(str(entry.get(k, "")) for k in _SEARCH_FIELDS).lower()
    return needle in hay


def resolve_registries(query: RegistryQuery, registry: dict) -> RegistryResult:
    """Pure registry query: jurisdiction (+ optional topic/kind) → records.

    Sorted by the registry's own ``confidence`` (high→medium→low) then ``title``
    (case-insensitive, stable). Unknown jurisdiction → empty result (never a
    guessed match). ``renders_advice`` / ``is_eligibility_determination`` are
    hard-wired ``False``.
    """
    jurisdiction = _require_str(query.jurisdiction, "jurisdiction").lower()
    topic = query.topic
    if topic is not None:
        topic = _require_str(topic, "topic").lower()
    record_kind = query.record_kind
    if record_kind is not None:
        record_kind = _require_str(record_kind, "record_kind")
        if record_kind not in RECORD_KINDS:
            raise ValueError(
                f"unknown record_kind {record_kind!r}; allowed: {sorted(RECORD_KINDS)}"
            )

    if not isinstance(registry, dict):
        raise ValueError("registry must be a dict (parsed registries.seed.json)")
    raw = registry.get("registries")
    if not isinstance(raw, list):
        raise ValueError("registry must carry a 'registries' list")

    matches: list[RegistryRecord] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each registry entry must be a dict")
        if str(entry.get("jurisdiction", "")).lower() != jurisdiction:
            continue
        if record_kind is not None and str(entry.get("recordKind", "")) != record_kind:
            continue
        if not query.allow_unverified:
            if str(entry.get("verificationStatus", "")) not in _VERIFIED_STATUSES:
                continue
        if topic is not None and not _topic_matches(entry, topic):
            continue
        matches.append(_to_record(entry))

    matches.sort(key=lambda r: (_confidence_rank(r.confidence), r.title.casefold()))
    return RegistryResult(
        jurisdiction=jurisdiction,
        topic=topic,
        record_kind=record_kind,
        renders_advice=False,
        is_eligibility_determination=False,
        records=tuple(matches),
    )


def _iso_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _record_view(r: RegistryRecord) -> dict:
    return {
        "registryId": r.registry_id,
        "title": r.title,
        "jurisdiction": r.jurisdiction,
        "recordKind": r.record_kind,
        "confidence": r.confidence,
        "verificationStatus": r.verification_status,
        "authority": r.authority,
        "accessUrl": r.access_url,
        "procedure": r.procedure,
        "deadline": r.deadline,
        "legalBasis": r.legal_basis,
        "language": r.language,
        "provenance": r.provenance,
        "lastVerified": r.last_verified,
    }


def to_registry_routing_record(
    result: RegistryResult,
    *,
    member_did: str,
    created_at: datetime,
    session_ref: str | None = None,
) -> dict:
    """Build a ``com.etzhayyim.shidemori.deathRegistration`` routing record.

    ``rendersAdvice`` / ``isEligibilityDetermination`` are asserted ``False``
    before return — structural invariants this function cannot violate. The
    record is a pure wayfinding view to OFFICIAL death-record authorities; it
    carries NO advice and NO compensation field (Public-Fund-routed, zero charge).
    """
    rec: dict = {
        "memberDid": member_did,
        "jurisdiction": result.jurisdiction,
        "rendersAdvice": False,
        "isEligibilityDetermination": False,
        "zeroCompensation": True,
        "recordCount": len(result.records),
        "records": [_record_view(r) for r in result.records],
        "createdAt": _iso_dt(created_at),
    }
    if result.topic is not None:
        rec["topicLabel"] = result.topic
    if result.record_kind is not None:
        rec["recordKindFilter"] = result.record_kind
    if session_ref is not None:
        rec["sessionRef"] = session_ref
    assert rec["rendersAdvice"] is False, "invariant: rendersAdvice must be False"
    assert (
        rec["isEligibilityDetermination"] is False
    ), "invariant: isEligibilityDetermination must be False"
    return rec


def load_registry(path: str | Path) -> dict:
    """Read + parse the death-registration seed registry JSON. Stdlib only."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("registries"), list):
        raise ValueError(f"{path} is not a valid death-registration registry")
    return data


__all__ = [
    "CONFIDENCE_ORDER",
    "RECORD_KINDS",
    "RegistryQuery",
    "RegistryRecord",
    "RegistryResult",
    "resolve_registries",
    "to_registry_routing_record",
    "load_registry",
]
