"""Pure DISCLOSURE-TARGET RESOLVER core for ``himotoki_deadline_check``.

Per ADR-2605302130 (繙き himotoki — ACTIVE disclosure-request filer; consent-bound
DSAR (APPI/GDPR/CCPA) + FOIA; own-data-only) and the worldwide disclosure-target
registry shipped at ``20-actors/himotoki/registry/targets.seed.json``.

BOUNDARY / CONSTITUTIONAL CEILING (CRITICAL — IMMUTABLE):
  * This module is a PURE REGISTRY QUERY — a DISCLOSURE-TARGET RESOLVER. Given a
    member jurisdiction (+ an OPTIONAL regime, e.g. ``gdpr-15`` / ``ccpa-110`` /
    ``foia-us-5usc552``), it ROUTES the member to the matching DSAR/FOIA
    disclosure target (the channel/contact a request is SENT to). It renders NO
    legal advice, opinion, eligibility / means / rights determination, or
    analysis. ``is_legal_opinion`` / ``isLegalOpinion`` is ALWAYS ``False`` and
    there is NO code path that can set it ``True``.
  * Consent-gated, own-data-only (DSAR) / public-records (FOIA), ROUTING ONLY —
    NO legal advice. This core NEVER computes or asserts eligibility, deadlines,
    standing, or rights — those are jurisdiction-specific data that drift; it
    only ROUTES to the target, which performs its own intake. Returning a target
    is NOT a statement that the member qualifies, nor a deadline computation
    (that informational date math lives in the sibling ``deadline.py``).
  * NO ranking other than the registry's OWN ``confidence`` then ``organization``.
    The resolver invents no relevance score of its own.
  * Unknown jurisdiction → ``[]`` (never a guessed / nearest-neighbour match, G8).
  * No network, no PII persistence, no inference, no dispatch. Pure stdlib.

R0/R1 BOUNDARY (CRITICAL): this pure core is importable independently of the
deployable Pregel cell. ``cell.py`` (the ``HimotokiDeadlineCheckCell`` graph)
stays non-deployable (import-time ``RuntimeError``) until Council ratification
(Lv6+ ≥3, post Bootstrap Council RFP 2026-06-19). Landing + testing this core
does NOT activate the cell; the activation gate in ``cell.py`` is the sole switch.

Output shape mirrors a routing view over Lexicon
``com.etzhayyim.himotoki.disclosureTarget`` (the registry's ``$schema``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ── confidence ordering (the registry's OWN ranking signal) ─────────────
# Lower sort-key sorts FIRST. The seed registry currently ships {"high",
# "medium"} on a subset of entries; "low" is included for forward-compat. An
# entry with NO confidence value is wayfinding scaffold; it sorts AFTER every
# graded entry (``_UNRANKED``) but is never dropped or guessed. No other ranking
# signal is permitted (no advice-flavoured relevance scoring).
CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}
_CONFIDENCE = frozenset(CONFIDENCE_ORDER)
_UNRANKED = max(CONFIDENCE_ORDER.values()) + 1  # ungraded entries sort last

# verificationStatus values that may be ROUTED against without caller opt-in.
# The seed currently ships only "unverified-seed" entries (wayfinding scaffold);
# whether to surface them is the CALLER's policy, exposed via ``allow_unverified``.
_VERIFIED_STATUSES = frozenset({"verified", "council-verified"})


@dataclass(frozen=True)
class TargetQuery:
    """Member-confirmed routing facts. No PII beyond the jurisdiction string."""

    jurisdiction: str  # ISO-ish code as used by the registry, e.g. usa / jpn / eu-wide
    regime: str | None = None  # OPTIONAL regime filter (e.g. gdpr-15); None = no filter
    allow_unverified: bool = True  # surface unverified-seed entries (caller policy)


@dataclass(frozen=True)
class DisclosureTarget:
    """One resolved disclosure TARGET — never an advice source."""

    organization: str
    jurisdiction: str
    regime: str
    confidence: str  # registry value, or "" when ungraded
    verification_status: str
    channel_type: str
    portal_url: str
    contact_email: str
    form_ref: str
    statutory_deadline_days: int | None
    alt_regimes: tuple[str, ...]
    authority: str
    legal_basis: str
    language: str
    bloc: str
    notes: str
    provenance: str
    last_verified: str
    is_legal_opinion: bool  # ALWAYS False (constitutional invariant)


@dataclass(frozen=True)
class TargetResult:
    jurisdiction: str
    regime: str | None
    is_legal_opinion: bool  # ALWAYS False (constitutional invariant)
    targets: tuple[DisclosureTarget, ...] = field(default_factory=tuple)


def _require_str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string, got {type(value).__name__}")
    norm = value.strip()
    if not norm:
        raise ValueError(f"{name} must be a non-empty string")
    return norm


def _confidence_rank(confidence: str) -> int:
    """Sort-key for a registry ``confidence`` value.

    Empty string = ungraded entry → sorts last (``_UNRANKED``). A non-empty
    value that is not a known grade → ValueError (G8: no guessing).
    """
    if confidence == "":
        return _UNRANKED
    if confidence not in CONFIDENCE_ORDER:
        raise ValueError(
            f"unknown confidence {confidence!r}; "
            f"allowed: {sorted(CONFIDENCE_ORDER, key=CONFIDENCE_ORDER.get)} or absent"
        )
    return CONFIDENCE_ORDER[confidence]


def _deadline_days(value: object) -> int | None:
    """Project ``statutoryDeadlineDays`` — int or None. NEVER computes a date.

    This is a passthrough of the registry's OWN stored window, not a deadline
    computation (that informational date math lives in ``deadline.py``).
    """
    if value is None:
        return None
    if isinstance(value, bool):  # bool is an int subclass — reject explicitly
        raise ValueError("statutoryDeadlineDays must be an int or null, not bool")
    if isinstance(value, int):
        return value
    raise ValueError(
        f"statutoryDeadlineDays must be an int or null, got {type(value).__name__}"
    )


def _to_target(entry: dict) -> DisclosureTarget:
    """Project one raw registry dict → a frozen :class:`DisclosureTarget`.

    ``is_legal_opinion`` is pinned ``False``; no path may set it ``True``.
    """
    if not isinstance(entry, dict):
        raise ValueError(f"registry entry must be a dict, got {type(entry).__name__}")
    organization = _require_str(entry.get("organization"), "organization")
    jurisdiction = _require_str(entry.get("jurisdiction"), "jurisdiction")
    regime = _require_str(entry.get("regime"), "regime")
    confidence = str(entry.get("confidence", "")).strip()
    _confidence_rank(confidence)  # validate early (raises on unknown non-empty)

    raw_alt = entry.get("altRegimes")
    if raw_alt is None:
        alt_regimes: tuple[str, ...] = ()
    elif isinstance(raw_alt, list):
        alt_regimes = tuple(str(a) for a in raw_alt)
    else:
        raise ValueError("altRegimes must be a list or null")

    return DisclosureTarget(
        organization=organization,
        jurisdiction=jurisdiction,
        regime=regime,
        confidence=confidence,
        verification_status=str(entry.get("verificationStatus", "")),
        channel_type=str(entry.get("channelType", "")),
        portal_url=str(entry.get("portalUrl", "")),
        contact_email=str(entry.get("contactEmail", "")),
        form_ref=str(entry.get("formRef", "")),
        statutory_deadline_days=_deadline_days(entry.get("statutoryDeadlineDays")),
        alt_regimes=alt_regimes,
        authority=str(entry.get("authority", "")),
        legal_basis=str(entry.get("legalBasis", "")),
        language=str(entry.get("language", "")),
        bloc=str(entry.get("bloc", "")),
        notes=str(entry.get("notes", "")),
        provenance=str(entry.get("provenance", "")),
        last_verified=str(entry.get("lastVerified", "")),
        is_legal_opinion=False,  # constitutional invariant — no path may set this True
    )


def _regime_matches(entry: dict, needle: str) -> bool:
    """True if the entry's ``regime`` OR any ``altRegimes`` value equals ``needle``.

    Exact (case-insensitive) regime code match — this is routing FILTERING only;
    it surfaces which targets accept that regime's request and never classifies,
    advises, or characterises the member's matter.
    """
    if str(entry.get("regime", "")).lower() == needle:
        return True
    raw_alt = entry.get("altRegimes")
    if isinstance(raw_alt, list):
        return any(str(a).lower() == needle for a in raw_alt)
    return False


def resolve_targets(query: TargetQuery, registry: dict) -> TargetResult:
    """Pure registry query: jurisdiction (+ optional regime) → disclosure targets.

    Sorted by the registry's own ``confidence`` (high→medium→low→ungraded) then
    ``organization`` (case-insensitive, stable). Unknown jurisdiction → empty
    result (never a guessed match). ``is_legal_opinion`` is hard-wired ``False``.
    """
    jurisdiction = _require_str(query.jurisdiction, "jurisdiction").lower()
    regime = query.regime
    if regime is not None:
        regime = _require_str(regime, "regime").lower()

    if not isinstance(registry, dict):
        raise ValueError("registry must be a dict (parsed targets.seed.json)")
    raw = registry.get("targets")
    if not isinstance(raw, list):
        raise ValueError("registry must carry a 'targets' list")

    matches: list[DisclosureTarget] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each target entry must be a dict")
        if str(entry.get("jurisdiction", "")).lower() != jurisdiction:
            continue
        if not query.allow_unverified:
            if str(entry.get("verificationStatus", "")) not in _VERIFIED_STATUSES:
                continue
        if regime is not None and not _regime_matches(entry, regime):
            continue
        matches.append(_to_target(entry))

    matches.sort(
        key=lambda t: (_confidence_rank(t.confidence), t.organization.casefold())
    )
    return TargetResult(
        jurisdiction=jurisdiction,
        regime=regime,
        is_legal_opinion=False,  # constitutional invariant
        targets=tuple(matches),
    )


def _iso_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _target_view(t: DisclosureTarget) -> dict:
    return {
        "organization": t.organization,
        "jurisdiction": t.jurisdiction,
        "regime": t.regime,
        "altRegimes": list(t.alt_regimes),
        "confidence": t.confidence,
        "verificationStatus": t.verification_status,
        "channelType": t.channel_type,
        "portalUrl": t.portal_url,
        "contactEmail": t.contact_email,
        "formRef": t.form_ref,
        "statutoryDeadlineDays": t.statutory_deadline_days,
        "authority": t.authority,
        "legalBasis": t.legal_basis,
        "language": t.language,
        "bloc": t.bloc,
        "provenance": t.provenance,
        "lastVerified": t.last_verified,
    }


def to_target_routing_record(
    result: TargetResult,
    *,
    member_did: str,
    created_at: datetime,
    session_ref: str | None = None,
) -> dict:
    """Build an ``com.etzhayyim.himotoki.disclosureTarget`` routing-view record.

    ``isLegalOpinion`` is asserted ``False`` before return — a constitutional
    schema invariant this function structurally cannot violate. The record is a
    pure wayfinding view; it carries NO eligibility verdict, NO deadline
    computation, and NO rights determination.
    """
    rec: dict = {
        "memberDid": member_did,
        "jurisdiction": result.jurisdiction,
        "isLegalOpinion": False,  # constitutional invariant
        "isEligibilityDetermination": False,  # never a means/standing verdict
        "isDeadlineComputation": False,  # routing only — date math is deadline.py
        "routingOnly": True,
        "targetCount": len(result.targets),
        "targets": [_target_view(t) for t in result.targets],
        "createdAt": _iso_dt(created_at),
    }
    if result.regime is not None:
        rec["regime"] = result.regime
    if session_ref is not None:
        rec["sessionRef"] = session_ref
    assert rec["isLegalOpinion"] is False, "invariant: isLegalOpinion must be False"
    assert rec["isEligibilityDetermination"] is False, "no eligibility determination"
    assert rec["isDeadlineComputation"] is False, "routing only, not date math"
    return rec


def load_registry(path: str | Path) -> dict:
    """Read + parse the disclosure-target seed registry JSON. Stdlib only, no network."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("targets"), list):
        raise ValueError(f"{path} is not a valid disclosure-target registry")
    return data


__all__ = [
    "CONFIDENCE_ORDER",
    "TargetQuery",
    "DisclosureTarget",
    "TargetResult",
    "resolve_targets",
    "to_target_routing_record",
    "load_registry",
]
