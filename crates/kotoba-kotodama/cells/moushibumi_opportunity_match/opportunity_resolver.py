"""Pure PARTICIPATION-OPPORTUNITY RESOLVER core for ``moushibumi_opportunity_match``.

Per ADR-2605312400 (申文 moushibumi — citizen democratic-participation
concierge), the G3 political-neutrality (公選法-equivalent) ceiling, and the
worldwide participation-target registry shipped at
``20-actors/moushibumi/registry/targets.seed.json``.

CONSTITUTIONAL CEILING (CRITICAL — IMMUTABLE):
  * POLITICAL NEUTRALITY (G3 / 公選法-equivalent) — this module is INFO ROUTING
    ONLY. It surfaces the OFFICIAL democratic-participation channels a member's
    jurisdiction offers (a public-comment window, a petition route, a citizen
    initiative, an official election-information source); it performs NO
    campaigning, NO endorsement, NO candidate/party ranking, and NO
    get-out-the-vote nudging. ``election-info`` entries point to OFFICIAL
    sources only. ``is_legal_opinion`` AND ``renders_advice`` are ALWAYS
    ``False`` and there is NO code path that can set either ``True``.
  * NO eligibility / means-test / rights determination — whether a member may
    petition, comment, sign an initiative, or vote is jurisdiction-specific data
    that drifts; this core NEVER computes or asserts it. It only ROUTES to the
    official channel, which applies its own rules. Surfacing a channel is NOT a
    statement that the member qualifies to use it.
  * NO ranking other than the registry's OWN ``confidence`` (when present) then
    ``title`` (with ``organization`` / ``organ`` as a deterministic final
    tiebreak). The resolver invents no relevance score of its own — no
    partisan, recency, or popularity weighting (G3).
  * Unknown jurisdiction → ``[]`` (never a guessed / nearest-neighbour match) (G8).
  * No network, no PII persistence, no inference, no dispatch. Pure stdlib.

R0/R1 BOUNDARY (CRITICAL): this pure core is importable independently of the
deployable Pregel cell. ``cell.py`` (the ``MoushibumiOpportunityMatchCell``
participation-match graph) stays import-time ``RuntimeError`` until Council
ratification (Lv6+ ≥3, post Bootstrap Council RFP 2026-06-19). Landing + testing
this core does NOT activate the cell; once Council activates, the graph may call
:func:`resolve_opportunities` / :func:`to_opportunity_routing_record` for the
neutral wayfinding leg.

Output shape mirrors a participation-routing view over Lexicon
``com.etzhayyim.moushibumi.participationTarget`` (the registry's ``$schema``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ── confidence ordering (the registry's OWN ranking signal, when present) ──
# Lower sort-key sorts FIRST. The seed registry presently ships NO ``confidence``
# field on its entries; entries without one are all assigned the same neutral
# rank (``_DEFAULT_CONFIDENCE_RANK``) so the deterministic secondary key (title,
# then organization) fully governs order. This mirrors the chigiri referral
# resolver idiom while remaining forward-compatible if the registry later adds a
# per-entry ``confidence``. No other ranking signal is permitted (G3 — no
# partisan / recency / popularity relevance scoring).
CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}
# entries with no confidence rank sort AFTER explicit high/medium/low but the
# stable title tiebreak still applies; keep this strictly greater than any
# explicit rank.
_DEFAULT_CONFIDENCE_RANK = len(CONFIDENCE_ORDER)

# verificationStatus values that are fully vetted. The seed ships only
# ``unverified-seed`` entries (wayfinding scaffold). Whether to surface
# unverified-seed entries is the CALLER's policy, exposed via ``allow_unverified``.
_VERIFIED_STATUSES = frozenset({"verified", "council-verified"})

# The optional secondary filter is the registry's structured ``channelKind``
# (petition / public-comment / citizen-initiative / election-info). It is an
# exact, case-insensitive match against the entry's own ``channelKind`` — a pure
# data filter that surfaces which official channels of that kind a jurisdiction
# offers. It never classifies, advises, or characterises the member's matter (G3).


@dataclass(frozen=True)
class OpportunityQuery:
    """Member-confirmed routing facts. No PII beyond the jurisdiction string."""

    jurisdiction: str  # ISO-ish bloc code as used by the registry, e.g. jpn / usa / fra
    channel_kind: str | None = None  # OPTIONAL exact channelKind; None = no filter
    allow_unverified: bool = True  # surface unverified-seed entries (caller policy)


@dataclass(frozen=True)
class Opportunity:
    """One resolved participation TARGET — never an advice/endorsement source (G3)."""

    target_id: str
    title: str
    jurisdiction: str
    channel_kind: str
    confidence: str | None
    verification_status: str
    organization: str
    channel_type: str
    submission_form: str
    deadline: str
    legal_basis: str
    language: str
    portal_url: str
    notes: str
    last_verified: str
    provenance: str
    is_legal_opinion: bool  # ALWAYS False (G3 ceiling)
    renders_advice: bool  # ALWAYS False (G3 ceiling)


@dataclass(frozen=True)
class OpportunityResult:
    jurisdiction: str
    channel_kind: str | None
    is_legal_opinion: bool  # ALWAYS False (G3)
    renders_advice: bool  # ALWAYS False (G3)
    opportunities: tuple[Opportunity, ...] = field(default_factory=tuple)


def _require_str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string, got {type(value).__name__}")
    norm = value.strip()
    if not norm:
        raise ValueError(f"{name} must be a non-empty string")
    return norm


def _confidence_rank(confidence: str | None) -> int:
    """Sort-key for a registry ``confidence`` value.

    ``None`` / missing → the neutral default rank (the seed carries no
    confidence). A PRESENT-but-unknown confidence string → ValueError (G8: the
    resolver does not silently guess a rank for malformed registry data).
    """
    if confidence is None:
        return _DEFAULT_CONFIDENCE_RANK
    if confidence not in CONFIDENCE_ORDER:
        raise ValueError(
            f"unknown confidence {confidence!r}; "
            f"allowed: {sorted(CONFIDENCE_ORDER, key=CONFIDENCE_ORDER.get)} or absent"
        )
    return CONFIDENCE_ORDER[confidence]


def _opt_confidence(entry: dict) -> str | None:
    """Read the optional ``confidence`` field, validating it if present (G8)."""
    raw = entry.get("confidence")
    if raw is None:
        return None
    conf = _require_str(raw, "confidence")
    _confidence_rank(conf)  # raises on an unknown value
    return conf


def _to_opportunity(entry: dict) -> Opportunity:
    """Project one raw registry dict → a frozen :class:`Opportunity` (G3-pinned)."""
    if not isinstance(entry, dict):
        raise ValueError(f"registry entry must be a dict, got {type(entry).__name__}")
    target_id = _require_str(entry.get("targetId"), "targetId")
    title = _require_str(entry.get("title"), "title")
    jurisdiction = _require_str(entry.get("jurisdiction"), "jurisdiction")
    channel_kind = _require_str(entry.get("channelKind"), "channelKind")
    confidence = _opt_confidence(entry)
    return Opportunity(
        target_id=target_id,
        title=title,
        jurisdiction=jurisdiction,
        channel_kind=channel_kind,
        confidence=confidence,
        verification_status=str(entry.get("verificationStatus", "")),
        organization=str(entry.get("organ", "")),
        channel_type=str(entry.get("channelType", "")),
        submission_form=str(entry.get("submissionForm", "")),
        deadline=str(entry.get("deadline", "")),
        legal_basis=str(entry.get("legalBasis", "")),
        language=str(entry.get("language", "")),
        portal_url=str(entry.get("portalUrl", "")),
        notes=str(entry.get("notes", "")),
        last_verified=str(entry.get("lastVerified", "")),
        provenance=str(entry.get("provenance", "")),
        is_legal_opinion=False,  # G3 — no path may set this True
        renders_advice=False,  # G3 — no path may set this True
    )


def resolve_opportunities(query: OpportunityQuery, registry: dict) -> OpportunityResult:
    """Pure registry query: jurisdiction (+ optional channelKind) → opportunities.

    Sorted by the registry's own ``confidence`` (high→medium→low→absent) then
    ``title`` (case-insensitive, stable) then ``organization`` (a deterministic
    final tiebreak). Unknown jurisdiction → empty result (never a guessed
    match). ``is_legal_opinion`` AND ``renders_advice`` are hard-wired ``False``
    (G3 political-neutrality ceiling — INFO routing only).
    """
    jurisdiction = _require_str(query.jurisdiction, "jurisdiction").lower()
    kind = query.channel_kind
    if kind is not None:
        kind = _require_str(kind, "channel_kind").lower()

    if not isinstance(registry, dict):
        raise ValueError("registry must be a dict (parsed targets.seed.json)")
    raw = registry.get("targets")
    if not isinstance(raw, list):
        raise ValueError("registry must carry a 'targets' list")

    matches: list[Opportunity] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each target entry must be a dict")
        if str(entry.get("jurisdiction", "")).lower() != jurisdiction:
            continue
        if not query.allow_unverified:
            if str(entry.get("verificationStatus", "")) not in _VERIFIED_STATUSES:
                continue
        if kind is not None and str(entry.get("channelKind", "")).lower() != kind:
            continue
        matches.append(_to_opportunity(entry))

    matches.sort(
        key=lambda o: (
            _confidence_rank(o.confidence),
            o.title.casefold(),
            o.organization.casefold(),
        )
    )
    return OpportunityResult(
        jurisdiction=jurisdiction,
        channel_kind=kind,
        is_legal_opinion=False,  # G3
        renders_advice=False,  # G3
        opportunities=tuple(matches),
    )


def _iso_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _opportunity_view(o: Opportunity) -> dict:
    return {
        "targetId": o.target_id,
        "title": o.title,
        "jurisdiction": o.jurisdiction,
        "channelKind": o.channel_kind,
        "verificationStatus": o.verification_status,
        "organization": o.organization,
        "channelType": o.channel_type,
        "submissionForm": o.submission_form,
        "deadline": o.deadline,
        "legalBasis": o.legal_basis,
        "language": o.language,
        "portalUrl": o.portal_url,
        "provenance": o.provenance,
        "lastVerified": o.last_verified,
    }


def to_opportunity_routing_record(
    result: OpportunityResult,
    *,
    member_did: str,
    created_at: datetime,
    session_ref: str | None = None,
) -> dict:
    """Build an ``com.etzhayyim.moushibumi.participationTarget`` routing-view record.

    ``isLegalOpinion`` AND ``rendersAdvice`` are asserted ``False`` before return
    — G3 schema invariants this function structurally cannot violate. The record
    is a pure, politically-neutral wayfinding view: it carries NO eligibility
    verdict, NO endorsement, NO candidate/party reference, and NO get-out-the-vote
    payload — only official-channel routing.
    """
    rec: dict = {
        "memberDid": member_did,
        "jurisdiction": result.jurisdiction,
        "isLegalOpinion": False,  # G3
        "rendersAdvice": False,  # G3 — INFO routing only, no advice/endorsement
        "isEligibilityDetermination": False,  # never a rights / means-test verdict
        "politicallyNeutral": True,  # 公選法-equivalent: no campaigning / endorsement / GOTV
        "officialSourcesOnly": True,  # election-info points to OFFICIAL sources only
        "opportunityCount": len(result.opportunities),
        "opportunities": [_opportunity_view(o) for o in result.opportunities],
        "createdAt": _iso_dt(created_at),
    }
    if result.channel_kind is not None:
        rec["channelKind"] = result.channel_kind
    if session_ref is not None:
        rec["sessionRef"] = session_ref
    assert rec["isLegalOpinion"] is False, "G3 invariant: isLegalOpinion must be False"
    assert rec["rendersAdvice"] is False, "G3 invariant: rendersAdvice must be False"
    assert rec["isEligibilityDetermination"] is False, "no eligibility determination"
    assert rec["politicallyNeutral"] is True, "G3 invariant: politically neutral"
    return rec


def load_registry(path: str | Path) -> dict:
    """Read + parse the participation-target seed registry JSON. Stdlib only, no network."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("targets"), list):
        raise ValueError(f"{path} is not a valid moushibumi participation registry")
    return data


__all__ = [
    "CONFIDENCE_ORDER",
    "OpportunityQuery",
    "Opportunity",
    "OpportunityResult",
    "resolve_opportunities",
    "to_opportunity_routing_record",
    "load_registry",
]
