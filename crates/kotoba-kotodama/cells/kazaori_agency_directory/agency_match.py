"""Pure civilian disaster-agency DIRECTORY-QUERY core for ``kazaori`` (風折).

Per ADR-2605263200 (kazaori — non-profit religious-corp **civilian** disaster
response substrate Tier-B actor) and the worldwide seed directory shipped at
``20-actors/kazaori/registry/agencies.seed.json``.

CONSTITUTIONAL CEILING (CRITICAL — IMMUTABLE):
  * **Issues no alerts** — kazaori "issues no alerts of its own and commands no
    response" (seed ``_comment``). This module ROUTES a member to the OFFICIAL
    public civilian disaster-management agency / early-warning / public-alert
    channel that does. ``issues_alerts`` / ``issuesAlerts`` is ALWAYS ``False``
    and there is no code path that can set it ``True``.
  * **Commands no response** — this is a wayfinding DIRECTORY, never an incident
    command. ``commands_response`` / ``commandsResponse`` is ALWAYS ``False``.
  * **Not an official emergency service** — kazaori is NOT 119 / 110 / 911 / a
    municipal EOC. ``is_official_emergency_service`` is ALWAYS ``False``;
    surfacing an agency is NOT a substitute for contacting it directly.
  * **Civilian-only (G5)** — kazaori MUST NOT coordinate armed-force actions
    (force authorization is separate per ADR-2605192315). This core refuses to
    project any entry whose ``agencyKind`` is not one of the known CIVILIAN
    kinds; an unknown kind raises rather than being silently routed, so a
    non-civilian entry is structurally unroutable.
  * **No surveillance / no inference (G6 + G7)** — pure registry query: no
    network, no PII persistence beyond the jurisdiction string, no Murakumo /
    commercial-disaster-AI inference, no ranking other than the registry's own
    ``confidence`` then ``title``. Unknown jurisdiction → ``[]`` (never a
    guessed / nearest-neighbour match).

R0/R1 BOUNDARY (CRITICAL): this pure core is importable independently of the
deployable Pregel cell. ``cell.py`` (the ``KazaoriAgencyDirectoryCell`` graph)
stays non-deployable until Council ratification (Lv6+ ≥3, post Bootstrap
Council RFP 2026-06-19). Landing + testing this core does NOT activate the cell.

Output shape mirrors a directory-routing view over Lexicon
``com.etzhayyim.kazaori.disasterAgency`` (the registry's ``$schema``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ── confidence ordering (the registry's OWN ranking signal) ─────────────
# Lower sort-key sorts FIRST. The seed registry currently ships only
# {"high", "medium"}; "low" is included for forward-compatibility. No other
# ranking signal is permitted (G6/G7 — no inference-flavoured relevance score).
CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}

# The known CIVILIAN agency kinds (ADR-2605263200 G5 civilian-only invariant).
# None of these is a military / armed-force body. An entry whose ``agencyKind``
# is outside this set is structurally unroutable (raises in ``_to_agency``),
# so a non-civilian entry can never be surfaced.
AGENCY_KINDS = frozenset(
    {
        "disaster-management-agency",
        "early-warning-system",
        "official-alert-channel",
        "civilian-relief-coordination",
        "intl-disaster-body",
    }
)

# verificationStatus values that may be ROUTED against when the caller declines
# unverified-seed entries. Per the seed's own note, an ``unverified-seed`` entry
# is wayfinding scaffold only; whether to surface it is the CALLER's policy,
# exposed via the ``allow_unverified`` flag.
_VERIFIED_STATUSES = frozenset({"verified", "council-verified"})

# Free-text hazard matching searches these registry fields. There is no
# structured hazard taxonomy in the registry, so a label match is a plain
# case-insensitive substring test over the human-readable scaffold text. A
# match only FILTERS which agencies are surfaced — it never characterises the
# member's situation or implies an alert (issues no alerts).
_SEARCH_FIELDS = ("title", "hazards", "alertChannel", "organization", "notes")


@dataclass(frozen=True)
class AgencyQuery:
    """Member-confirmed routing facts. No PII beyond the jurisdiction string."""

    jurisdiction: str  # registry bloc code, e.g. jpn / usa / intl-ocha
    hazard: str | None = None  # OPTIONAL free-text label; None = no filter
    agency_kind: str | None = None  # OPTIONAL exact kind filter; None = any
    allow_unverified: bool = True  # surface unverified-seed entries (policy)


@dataclass(frozen=True)
class DisasterAgency:
    """One resolved directory TARGET — never an alert source (issues no alerts)."""

    agency_id: str
    title: str
    jurisdiction: str
    agency_kind: str
    confidence: str
    verification_status: str
    organization: str
    access_url: str
    hazards: str
    alert_channel: str
    language: str
    provenance: str
    last_verified: str
    notes: str
    issues_alerts: bool  # ALWAYS False
    commands_response: bool  # ALWAYS False
    is_official_emergency_service: bool  # ALWAYS False


@dataclass(frozen=True)
class AgencyResult:
    jurisdiction: str
    hazard: str | None
    agency_kind: str | None
    issues_alerts: bool  # ALWAYS False
    commands_response: bool  # ALWAYS False
    is_official_emergency_service: bool  # ALWAYS False
    agencies: tuple[DisasterAgency, ...] = field(default_factory=tuple)


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


def _to_agency(entry: dict) -> DisasterAgency:
    """Project one raw registry dict → a frozen :class:`DisasterAgency`.

    A non-CIVILIAN ``agencyKind`` raises (G5 civilian-only structural pin) —
    such an entry can never be surfaced.
    """
    if not isinstance(entry, dict):
        raise ValueError(f"registry entry must be a dict, got {type(entry).__name__}")
    agency_id = _require_str(entry.get("agencyId"), "agencyId")
    title = _require_str(entry.get("title"), "title")
    jurisdiction = _require_str(entry.get("jurisdiction"), "jurisdiction")
    agency_kind = _require_str(entry.get("agencyKind"), "agencyKind")
    if agency_kind not in AGENCY_KINDS:
        raise ValueError(
            f"non-civilian or unknown agencyKind {agency_kind!r} (G5); "
            f"allowed: {sorted(AGENCY_KINDS)}"
        )
    confidence = _require_str(entry.get("confidence"), "confidence")
    _confidence_rank(confidence)  # validate early (raises on unknown)
    return DisasterAgency(
        agency_id=agency_id,
        title=title,
        jurisdiction=jurisdiction,
        agency_kind=agency_kind,
        confidence=confidence,
        verification_status=str(entry.get("verificationStatus", "")),
        organization=str(entry.get("organization", "")),
        access_url=str(entry.get("accessUrl", "")),
        hazards=str(entry.get("hazards", "")),
        alert_channel=str(entry.get("alertChannel", "")),
        language=str(entry.get("language", "")),
        provenance=str(entry.get("provenance", "")),
        last_verified=str(entry.get("lastVerified", "")),
        notes=str(entry.get("notes", "")),
        issues_alerts=False,  # kazaori issues no alerts of its own
        commands_response=False,  # kazaori commands no response
        is_official_emergency_service=False,  # not an official emergency service
    )


def _hazard_matches(entry: dict, needle: str) -> bool:
    """Case-insensitive substring test over the registry's text fields.

    Wayfinding FILTERING only — it surfaces which agencies cover the hazard; it
    does not classify the member's situation or issue any alert.
    """
    hay = " ".join(str(entry.get(k, "")) for k in _SEARCH_FIELDS).lower()
    return needle in hay


def resolve_agencies(query: AgencyQuery, registry: dict) -> AgencyResult:
    """Pure registry query: jurisdiction (+ optional hazard/kind) → agencies.

    Sorted by the registry's own ``confidence`` (high→medium→low) then ``title``
    (case-insensitive, stable). Unknown jurisdiction → empty result (never a
    guessed match). ``issues_alerts`` / ``commands_response`` /
    ``is_official_emergency_service`` are hard-wired ``False``.
    """
    jurisdiction = _require_str(query.jurisdiction, "jurisdiction").lower()
    hazard = query.hazard
    if hazard is not None:
        hazard = _require_str(hazard, "hazard").lower()
    agency_kind = query.agency_kind
    if agency_kind is not None:
        agency_kind = _require_str(agency_kind, "agency_kind")
        if agency_kind not in AGENCY_KINDS:
            raise ValueError(
                f"unknown agency_kind {agency_kind!r}; allowed: {sorted(AGENCY_KINDS)}"
            )

    if not isinstance(registry, dict):
        raise ValueError("registry must be a dict (parsed agencies.seed.json)")
    raw = registry.get("agencies")
    if not isinstance(raw, list):
        raise ValueError("registry must carry an 'agencies' list")

    matches: list[DisasterAgency] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each agency entry must be a dict")
        if str(entry.get("jurisdiction", "")).lower() != jurisdiction:
            continue
        if agency_kind is not None and str(entry.get("agencyKind", "")) != agency_kind:
            continue
        if not query.allow_unverified:
            if str(entry.get("verificationStatus", "")) not in _VERIFIED_STATUSES:
                continue
        if hazard is not None and not _hazard_matches(entry, hazard):
            continue
        matches.append(_to_agency(entry))

    matches.sort(key=lambda a: (_confidence_rank(a.confidence), a.title.casefold()))
    return AgencyResult(
        jurisdiction=jurisdiction,
        hazard=hazard,
        agency_kind=agency_kind,
        issues_alerts=False,
        commands_response=False,
        is_official_emergency_service=False,
        agencies=tuple(matches),
    )


def _iso_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _agency_view(a: DisasterAgency) -> dict:
    return {
        "agencyId": a.agency_id,
        "title": a.title,
        "jurisdiction": a.jurisdiction,
        "agencyKind": a.agency_kind,
        "confidence": a.confidence,
        "verificationStatus": a.verification_status,
        "organization": a.organization,
        "accessUrl": a.access_url,
        "hazards": a.hazards,
        "alertChannel": a.alert_channel,
        "language": a.language,
        "provenance": a.provenance,
        "lastVerified": a.last_verified,
    }


def to_agency_routing_record(
    result: AgencyResult,
    *,
    member_did: str,
    created_at: datetime,
    session_ref: str | None = None,
) -> dict:
    """Build a ``com.etzhayyim.kazaori.disasterAgency`` directory-routing record.

    ``issuesAlerts`` / ``commandsResponse`` / ``isOfficialEmergencyService`` are
    asserted ``False`` before return — structural invariants this function
    cannot violate. The record is a pure wayfinding view to OFFICIAL civilian
    sources; it carries NO alert, NO incident command, and NO compensation field
    (Public-Fund-routed, zero charge).
    """
    rec: dict = {
        "memberDid": member_did,
        "jurisdiction": result.jurisdiction,
        "issuesAlerts": False,
        "commandsResponse": False,
        "isOfficialEmergencyService": False,
        "civilianOnly": True,
        "agencyCount": len(result.agencies),
        "agencies": [_agency_view(a) for a in result.agencies],
        "createdAt": _iso_dt(created_at),
    }
    if result.hazard is not None:
        rec["hazardLabel"] = result.hazard
    if result.agency_kind is not None:
        rec["agencyKindFilter"] = result.agency_kind
    if session_ref is not None:
        rec["sessionRef"] = session_ref
    assert rec["issuesAlerts"] is False, "invariant: issuesAlerts must be False"
    assert rec["commandsResponse"] is False, "invariant: commandsResponse must be False"
    assert (
        rec["isOfficialEmergencyService"] is False
    ), "invariant: isOfficialEmergencyService must be False"
    return rec


def load_registry(path: str | Path) -> dict:
    """Read + parse the disaster-agency seed registry JSON. Stdlib only."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("agencies"), list):
        raise ValueError(f"{path} is not a valid disaster-agency registry")
    return data


__all__ = [
    "CONFIDENCE_ORDER",
    "AGENCY_KINDS",
    "AgencyQuery",
    "DisasterAgency",
    "AgencyResult",
    "resolve_agencies",
    "to_agency_routing_record",
    "load_registry",
]
