"""Pure legal-aid REFERRAL RESOLVER core for ``chigiri_legal_aid_clinic``.

Per ADR-2605262700 (契 chigiri — legal-procedure substrate Tier-B actor), the
G14 UPL prohibition, and the worldwide referral registry shipped at
``20-actors/chigiri/registry/legal-aid.seed.json``.

CONSTITUTIONAL CEILING (CRITICAL — IMMUTABLE):
  * G14 / UPL — this module is a PURE REGISTRY QUERY. It ROUTES a consenting
    member to licensed human counsel / public-interest legal-aid orgs; it
    renders NO legal advice, opinion, eligibility determination, or analysis.
    ``renders_advice`` / ``rendersAdvice`` is ALWAYS ``False`` and there is no
    code path that can set it ``True``. Zero compensation; Public-Fund-routed.
  * NO eligibility / means-test computation — income/asset thresholds are
    jurisdiction-specific data that drift; this core NEVER computes or asserts
    eligibility. It only ROUTES to the referral org, which performs its own
    intake + means test. Returning a referral is NOT a statement that the
    member qualifies.
  * NO ranking other than the registry's own ``confidence`` then ``title``.
    The resolver invents no relevance score of its own.
  * Unknown jurisdiction → ``[]`` (never a guessed / nearest-neighbour match).
  * No network, no PII persistence, no inference, no dispatch. Pure stdlib.

R0/R1 BOUNDARY (CRITICAL): this pure core is importable independently of the
deployable Pregel cell. ``cell.py`` (the ``ChigiriLegalAidClinicCell`` intake
graph) stays non-deployable until Council ratification (Lv6+ ≥3, post Bootstrap
Council RFP 2026-06-19). Landing + testing this core does NOT activate the cell;
once Council activates, the intake graph may call :func:`resolve_referrals` /
:func:`to_referral_routing_record` for the wayfinding leg.

Output shape mirrors a referral-routing view over Lexicon
``com.etzhayyim.chigiri.legalAidReferral`` (the registry's ``$schema``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ── confidence ordering (the registry's OWN ranking signal) ─────────────
# Lower sort-key sorts FIRST. The seed registry currently ships only
# {"high", "medium"}; "low" is included for forward-compatibility. No other
# ranking signal is permitted (G14 — no advice-flavoured relevance scoring).
CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}
_CONFIDENCE = frozenset(CONFIDENCE_ORDER)

# verificationStatus values that may be ROUTED against. Per the seed's own G14
# note, an ``unverified-seed`` entry is wayfinding scaffold only; whether to
# surface it is the CALLER's policy, exposed via the ``allow_unverified`` flag.
_VERIFIED_STATUSES = frozenset({"verified", "council-verified"})

# Free-text practice-area matching searches these registry fields. There is no
# structured practice-area field in the registry, so a label match is a plain
# case-insensitive substring test over the human-readable scaffold text. A
# match only FILTERS which referral orgs are surfaced — it never produces or
# implies advice about the member's matter (G14).
_SEARCH_FIELDS = ("title", "authority", "legalBasis", "notes", "channel")


@dataclass(frozen=True)
class ReferralQuery:
    """Member-confirmed routing facts. No PII beyond the jurisdiction string."""

    jurisdiction: str  # ISO-ish bloc code as used by the registry, e.g. jpn / usa / fra
    practice_area: str | None = None  # OPTIONAL free-text label; None = no filter
    allow_unverified: bool = True  # surface unverified-seed entries (caller policy)


@dataclass(frozen=True)
class Referral:
    """One resolved referral TARGET — never an advice source (G14)."""

    referral_id: str
    title: str
    jurisdiction: str
    confidence: str
    verification_status: str
    authority: str
    channel: str
    legal_basis: str
    language: str
    bloc: str
    notes: str
    last_verified: str
    provenance: str
    renders_advice: bool  # ALWAYS False (G14)


@dataclass(frozen=True)
class ReferralResult:
    jurisdiction: str
    practice_area: str | None
    renders_advice: bool  # ALWAYS False (G14)
    referrals: tuple[Referral, ...] = field(default_factory=tuple)


def _require_str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string, got {type(value).__name__}")
    norm = value.strip()
    if not norm:
        raise ValueError(f"{name} must be a non-empty string")
    return norm


def _confidence_rank(confidence: str) -> int:
    """Sort-key for a registry ``confidence`` value. Unknown → ValueError (G8)."""
    if confidence not in CONFIDENCE_ORDER:
        raise ValueError(
            f"unknown confidence {confidence!r}; "
            f"allowed: {sorted(CONFIDENCE_ORDER, key=CONFIDENCE_ORDER.get)}"
        )
    return CONFIDENCE_ORDER[confidence]


def _to_referral(entry: dict) -> Referral:
    """Project one raw registry dict → a frozen :class:`Referral` (G14-pinned)."""
    if not isinstance(entry, dict):
        raise ValueError(f"registry entry must be a dict, got {type(entry).__name__}")
    referral_id = _require_str(entry.get("referralId"), "referralId")
    title = _require_str(entry.get("title"), "title")
    jurisdiction = _require_str(entry.get("jurisdiction"), "jurisdiction")
    confidence = _require_str(entry.get("confidence"), "confidence")
    _confidence_rank(confidence)  # validate early (raises on unknown)
    return Referral(
        referral_id=referral_id,
        title=title,
        jurisdiction=jurisdiction,
        confidence=confidence,
        verification_status=str(entry.get("verificationStatus", "")),
        authority=str(entry.get("authority", "")),
        channel=str(entry.get("channel", "")),
        legal_basis=str(entry.get("legalBasis", "")),
        language=str(entry.get("language", "")),
        bloc=str(entry.get("bloc", "")),
        notes=str(entry.get("notes", "")),
        last_verified=str(entry.get("lastVerified", "")),
        provenance=str(entry.get("provenance", "")),
        renders_advice=False,  # G14 — no path may set this True
    )


def _label_matches(entry: dict, needle: str) -> bool:
    """Case-insensitive substring test over the registry's text fields.

    This is wayfinding FILTERING only — it surfaces which orgs handle the
    member's area; it does not classify, advise, or characterise the matter.
    """
    hay = " ".join(str(entry.get(k, "")) for k in _SEARCH_FIELDS).lower()
    return needle in hay


def resolve_referrals(query: ReferralQuery, registry: dict) -> ReferralResult:
    """Pure registry query: jurisdiction (+ optional area label) → referrals.

    Sorted by the registry's own ``confidence`` (high→medium→low) then ``title``
    (case-insensitive, stable). Unknown jurisdiction → empty result (never a
    guessed match). ``renders_advice`` is hard-wired ``False`` (G14).
    """
    jurisdiction = _require_str(query.jurisdiction, "jurisdiction").lower()
    area = query.practice_area
    if area is not None:
        area = _require_str(area, "practice_area").lower()

    if not isinstance(registry, dict):
        raise ValueError("registry must be a dict (parsed legal-aid.seed.json)")
    raw = registry.get("referrals")
    if not isinstance(raw, list):
        raise ValueError("registry must carry a 'referrals' list")

    matches: list[Referral] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each referral entry must be a dict")
        if str(entry.get("jurisdiction", "")).lower() != jurisdiction:
            continue
        if not query.allow_unverified:
            if str(entry.get("verificationStatus", "")) not in _VERIFIED_STATUSES:
                continue
        if area is not None and not _label_matches(entry, area):
            continue
        matches.append(_to_referral(entry))

    matches.sort(key=lambda r: (_confidence_rank(r.confidence), r.title.casefold()))
    return ReferralResult(
        jurisdiction=jurisdiction,
        practice_area=area,
        renders_advice=False,  # G14
        referrals=tuple(matches),
    )


def _iso_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _referral_view(r: Referral) -> dict:
    return {
        "referralId": r.referral_id,
        "title": r.title,
        "jurisdiction": r.jurisdiction,
        "confidence": r.confidence,
        "verificationStatus": r.verification_status,
        "authority": r.authority,
        "channel": r.channel,
        "legalBasis": r.legal_basis,
        "language": r.language,
        "bloc": r.bloc,
        "provenance": r.provenance,
        "lastVerified": r.last_verified,
    }


def to_referral_routing_record(
    result: ReferralResult,
    *,
    member_did: str,
    created_at: datetime,
    session_ref: str | None = None,
) -> dict:
    """Build an ``com.etzhayyim.chigiri.legalAidReferral`` routing-view record.

    ``rendersAdvice`` is asserted ``False`` before return — a G14 schema
    invariant this function structurally cannot violate. The record is a pure
    wayfinding view; it carries NO eligibility verdict and NO compensation
    field (Public-Fund-routed, zero charge).
    """
    rec: dict = {
        "memberDid": member_did,
        "jurisdiction": result.jurisdiction,
        "rendersAdvice": False,  # G14
        "isEligibilityDetermination": False,  # never a means-test verdict
        "zeroCompensation": True,
        "referralCount": len(result.referrals),
        "referrals": [_referral_view(r) for r in result.referrals],
        "createdAt": _iso_dt(created_at),
    }
    if result.practice_area is not None:
        rec["practiceAreaLabel"] = result.practice_area
    if session_ref is not None:
        rec["sessionRef"] = session_ref
    assert rec["rendersAdvice"] is False, "G14 invariant: rendersAdvice must be False"
    assert rec["isEligibilityDetermination"] is False, "no eligibility determination"
    return rec


def load_registry(path: str | Path) -> dict:
    """Read + parse the legal-aid seed registry JSON. Stdlib only, no network."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("referrals"), list):
        raise ValueError(f"{path} is not a valid legal-aid registry")
    return data


__all__ = [
    "CONFIDENCE_ORDER",
    "ReferralQuery",
    "Referral",
    "ReferralResult",
    "resolve_referrals",
    "to_referral_routing_record",
    "load_registry",
]
