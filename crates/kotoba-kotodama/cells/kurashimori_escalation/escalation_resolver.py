"""Pure ESCALATION-FORUM RESOLVER core for ``kurashimori_escalation``.

Per ADR-2605312500 (暮らし守 kurashimori — citizen consumer-protection
concierge), the G5 / UPL ROUTE-NOT-REPRESENT invariant, and the worldwide
consumer-remedy registry shipped at
``20-actors/kurashimori/registry/targets.seed.json``.

WHAT THIS IS: a PURE REGISTRY QUERY. Given a member jurisdiction, it returns the
consumer-protection ESCALATION targets — a consumer-affairs centre / public
complaint authority / ADR body / ombudsman, i.e. entries whose ``remedyKind`` is
``escalation-public`` or ``escalation-adr`` — that a STALLED self-help case can
be routed to, sorted by the registry's own confidence signal then title. This is
the leg invoked when 自助 (cooling-off / refund / complaint) has stalled and the
member must be pointed at the lawful external forum.

CONSTITUTIONAL CEILING (CRITICAL — IMMUTABLE):
  * G5 / 弁護士法 / 司法書士法 / UPL — kurashimori ROUTES, it does NOT represent
    the member (代理), buy/assign a claim, charge a fee, or render a legal
    opinion. ``is_legal_opinion`` / ``isLegalOpinion`` is ALWAYS ``False`` and
    there is NO code path that can set it ``True``. Representation +
    characterization happen at the DESTINATION forum (and, where representation
    is needed, chigiri + licensed counsel) — never here. National analogs apply
    (German RDG, French monopole de l'avocat, Advocates Act 1961, Legal
    Profession Act, Law Society Act).
  * NO eligibility / means-test / rights determination — whether a given matter
    qualifies for a given forum is jurisdiction-specific data that this core
    NEVER computes or asserts. It only ROUTES. Returning an escalation target is
    NOT a statement that the member's matter qualifies, nor advice to pursue it.
  * NO date math — escalation routing carries no statutory window arithmetic
    (that informational date computation lives in the sibling ``cooloff`` core,
    G5-bounded there too). This resolver routes; it does not compute deadlines.
  * NO ranking other than the registry's OWN confidence signal then title. The
    resolver invents no relevance / quality score of its own. The registry has
    no literal ``confidence`` field today; its confidence-ordering signal is the
    per-entry ``verificationStatus`` (council-verified > verified >
    unverified-seed), the registry's own trust grade — NOT a fabricated score.
  * Unknown jurisdiction → ``[]`` (G8 — never a guessed / nearest-neighbour
    match). No network, no PII persistence, no inference, no dispatch. Pure
    stdlib.

R0/R1 BOUNDARY (CRITICAL): this pure core is importable independently of the
deployable Pregel cell. ``cell.py`` (the ``KurashimoriEscalationCell``) stays
import-time ``RuntimeError`` until Council ratification (Lv6+ ≥4, R2). Landing +
testing this core does NOT activate the cell — the activation gate in ``cell.py``
remains the sole switch; once Council activates, the cell may call
:func:`resolve_escalation_targets` / :func:`to_escalation_routing_record` for the
wayfinding leg.

Output shape mirrors an escalation-routing view over Lexicon
``com.etzhayyim.kurashimori.escalationReferral``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ── escalation remedy kinds (the registry's OWN coded remedyKind) ────────
# Only these remedy kinds are ESCALATION forums. Cooling-off / return-policy /
# warranty / chargeback entries are self-help remedies, never escalation
# destinations, and are filtered out — this resolver is escalation-only.
ESCALATION_KINDS = frozenset({"escalation-public", "escalation-adr"})

# ── confidence ordering (the registry's OWN trust signal) ────────────────
# The registry carries no literal ``confidence`` field; its confidence-ordering
# signal is the per-entry ``verificationStatus`` trust grade. Lower sort-key
# sorts FIRST: council-verified is the most-trusted, unverified-seed the least.
# The seed registry currently ships only {"unverified-seed"}; the verified
# grades are included for forward-compatibility (post Council/human verification
# per G14). No other ranking signal is permitted (G5 — no advice-flavoured
# relevance scoring).
CONFIDENCE_ORDER = {"council-verified": 0, "verified": 1, "unverified-seed": 2}
_CONFIDENCE = frozenset(CONFIDENCE_ORDER)


@dataclass(frozen=True)
class EscalationQuery:
    """Member-confirmed routing facts. No PII beyond the jurisdiction string."""

    jurisdiction: str  # ISO-ish bloc code as used by the registry, e.g. jpn / usa / eu-wide
    forum_kind: str | None = None  # OPTIONAL secondary filter: "escalation-public" | "escalation-adr"; None = both


@dataclass(frozen=True)
class EscalationTarget:
    """One resolved escalation FORUM — never a representative, never advice (G5)."""

    remedy_id: str
    title: str
    jurisdiction: str
    remedy_kind: str
    confidence: str  # the registry's verificationStatus trust grade
    verification_status: str
    escalation_forum: str
    delivery_channel: str
    legal_basis: str
    language: str
    provenance: str
    last_verified: str
    notes: str
    is_legal_opinion: bool  # ALWAYS False (G5 — no code path may set True)


@dataclass(frozen=True)
class EscalationResult:
    jurisdiction: str
    forum_kind: str | None
    is_legal_opinion: bool  # ALWAYS False (G5)
    targets: tuple[EscalationTarget, ...] = field(default_factory=tuple)


def _require_str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string, got {type(value).__name__}")
    norm = value.strip()
    if not norm:
        raise ValueError(f"{name} must be a non-empty string")
    return norm


def _confidence_rank(verification_status: str) -> int:
    """Sort-key for a registry ``verificationStatus`` value. Unknown → ValueError (G8)."""
    if verification_status not in CONFIDENCE_ORDER:
        raise ValueError(
            f"unknown verificationStatus {verification_status!r}; "
            f"allowed: {sorted(CONFIDENCE_ORDER, key=CONFIDENCE_ORDER.get)}"
        )
    return CONFIDENCE_ORDER[verification_status]


def _to_target(entry: dict) -> EscalationTarget:
    """Project one raw registry dict → a frozen :class:`EscalationTarget` (G5-pinned)."""
    if not isinstance(entry, dict):
        raise ValueError(f"registry entry must be a dict, got {type(entry).__name__}")
    remedy_id = _require_str(entry.get("remedyId"), "remedyId")
    title = _require_str(entry.get("title"), "title")
    jurisdiction = _require_str(entry.get("jurisdiction"), "jurisdiction")
    remedy_kind = _require_str(entry.get("remedyKind"), "remedyKind")
    verification_status = _require_str(
        entry.get("verificationStatus"), "verificationStatus"
    )
    _confidence_rank(verification_status)  # validate early (raises on unknown)
    return EscalationTarget(
        remedy_id=remedy_id,
        title=title,
        jurisdiction=jurisdiction,
        remedy_kind=remedy_kind,
        confidence=verification_status,
        verification_status=verification_status,
        escalation_forum=str(entry.get("escalationForum", "")),
        delivery_channel=str(entry.get("deliveryChannel", "")),
        legal_basis=str(entry.get("legalBasis", "")),
        language=str(entry.get("language", "")),
        provenance=str(entry.get("provenance", "")),
        last_verified=str(entry.get("lastVerified", "")),
        notes=str(entry.get("notes", "")),
        is_legal_opinion=False,  # G5 — no path may set this True
    )


def resolve_escalation_targets(
    query: EscalationQuery, registry: dict
) -> EscalationResult:
    """Pure registry query: jurisdiction (+ optional forum kind) → escalation forums.

    Returns only ``escalation-public`` / ``escalation-adr`` entries (self-help
    remedy kinds are filtered out). Sorted by the registry's own confidence
    signal (verificationStatus: council-verified → verified → unverified-seed)
    then ``title`` (case-insensitive, stable). Unknown jurisdiction → empty
    result (never a guessed match). ``is_legal_opinion`` is hard-wired ``False``
    (G5). NO eligibility determination, NO date math, NO advice — pure routing.
    """
    jurisdiction = _require_str(query.jurisdiction, "jurisdiction").lower()
    forum_kind = query.forum_kind
    if forum_kind is not None:
        forum_kind = _require_str(forum_kind, "forum_kind").lower()
        if forum_kind not in ESCALATION_KINDS:
            raise ValueError(
                f"forum_kind {forum_kind!r} is not an escalation kind; "
                f"allowed: {sorted(ESCALATION_KINDS)}"
            )

    if not isinstance(registry, dict):
        raise ValueError("registry must be a dict (parsed targets.seed.json)")
    raw = registry.get("targets")
    if not isinstance(raw, list):
        raise ValueError("registry must carry a 'targets' list")

    matches: list[EscalationTarget] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each registry entry must be a dict")
        if str(entry.get("jurisdiction", "")).lower() != jurisdiction:
            continue
        kind = str(entry.get("remedyKind", ""))
        if kind not in ESCALATION_KINDS:
            continue  # escalation-only: drop self-help remedy kinds
        if forum_kind is not None and kind != forum_kind:
            continue
        matches.append(_to_target(entry))

    matches.sort(
        key=lambda t: (_confidence_rank(t.verification_status), t.title.casefold())
    )
    return EscalationResult(
        jurisdiction=jurisdiction,
        forum_kind=forum_kind,
        is_legal_opinion=False,  # G5
        targets=tuple(matches),
    )


def _iso_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _target_view(t: EscalationTarget) -> dict:
    return {
        "remedyId": t.remedy_id,
        "title": t.title,
        "jurisdiction": t.jurisdiction,
        "remedyKind": t.remedy_kind,
        "verificationStatus": t.verification_status,
        "escalationForum": t.escalation_forum,
        "deliveryChannel": t.delivery_channel,
        "legalBasis": t.legal_basis,
        "language": t.language,
        "provenance": t.provenance,
        "lastVerified": t.last_verified,
    }


def to_escalation_routing_record(
    result: EscalationResult,
    *,
    member_did: str,
    created_at: datetime,
    session_ref: str | None = None,
) -> dict:
    """Build an ``com.etzhayyim.kurashimori.escalationReferral`` routing-view record.

    ``isLegalOpinion`` is asserted ``False`` before return — a G5 schema
    invariant this function structurally cannot violate. The record is a pure
    wayfinding view; it carries NO eligibility verdict, NO statutory-window date
    math, and NO compensation field (Public-Fund-routed, zero charge). Routing
    points the member at the forum — it does NOT represent the member there.
    """
    rec: dict = {
        "memberDid": member_did,
        "jurisdiction": result.jurisdiction,
        "isLegalOpinion": False,  # G5
        "isEligibilityDetermination": False,  # never a rights/means-test verdict
        "isRepresentation": False,  # ROUTE-NOT-REPRESENT (G5)
        "zeroCompensation": True,
        "targetCount": len(result.targets),
        "targets": [_target_view(t) for t in result.targets],
        "createdAt": _iso_dt(created_at),
    }
    if result.forum_kind is not None:
        rec["forumKind"] = result.forum_kind
    if session_ref is not None:
        rec["sessionRef"] = session_ref
    assert rec["isLegalOpinion"] is False, "G5 invariant: isLegalOpinion must be False"
    assert rec["isEligibilityDetermination"] is False, "no eligibility determination"
    assert rec["isRepresentation"] is False, "ROUTE-NOT-REPRESENT (G5)"
    return rec


def load_registry(path: str | Path) -> dict:
    """Read + parse the consumer-remedy seed registry JSON. Stdlib only, no network."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("targets"), list):
        raise ValueError(f"{path} is not a valid kurashimori remedy registry")
    return data


__all__ = [
    "ESCALATION_KINDS",
    "CONFIDENCE_ORDER",
    "EscalationQuery",
    "EscalationTarget",
    "EscalationResult",
    "resolve_escalation_targets",
    "to_escalation_routing_record",
    "load_registry",
]
