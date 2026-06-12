"""Pure ceremony CIVIL-RECOGNITION RESOLVER core for ``musubi_recognition_resolver``.

Per ADR-2605263400 (結 musubi — covenant-ceremony Tier-B actor) and the
worldwide ceremony-recognition registry shipped at
``20-actors/musubi/registry/ceremony-recognition.seed.json``.

CONSTITUTIONAL BOUNDARY (CRITICAL — IMMUTABLE):
  * musubi performs covenant ceremonies (Reformed 万人祭司 — NO clergy class, no
    officiant authority) and DOES NOT confer civil status. This module is a PURE
    REGISTRY QUERY: given a member jurisdiction (+ optional ceremony-type label
    e.g. marriage / naming / funeral) it ROUTES to the registry's own
    INFORMATIONAL recognition entries — which map whether a SEPARATE civil-
    registration step is required and what it is. It surfaces WHERE that civil
    step must be performed by the member themselves; it renders NO legal advice,
    NO eligibility / means-test / rights determination, and it NEVER claims to
    register a civil marriage.
  * G-invariants — ``is_legal_opinion`` AND ``confers_civil_status`` are ALWAYS
    ``False`` with NO code path that can set either ``True``. Every record
    builder asserts them ``False`` before return.
  * NO eligibility / means-test / rights determination — those are jurisdiction-
    specific data that drift; this core NEVER computes or asserts them. Returning
    a recognition entry is NOT a statement that the member qualifies for, or has
    obtained, any civil status. It only ROUTES.
  * NO ranking other than the registry's own ``confidence`` then ``title``. The
    resolver invents no relevance score of its own.
  * Unknown jurisdiction → ``[]`` (never a guessed / nearest-neighbour match, G8).
  * No network, no PII persistence, no inference, no dispatch. Pure stdlib.

R0/R1 BOUNDARY (CRITICAL): this pure core is importable independently of the
deployable Pregel cell. ``cell.py`` (the ``MusubiRecognitionResolverCell`` graph)
stays non-deployable (import-time RuntimeError) until Council ratification
(Lv6+ ≥3, post Bootstrap Council RFP 2026-06-19). Landing + testing this core
does NOT activate the cell; once Council activates, the cell may call
:func:`resolve_recognitions` / :func:`to_recognition_routing_record` for the
wayfinding leg.

Output shape mirrors a recognition-routing view over Lexicon
``com.etzhayyim.musubi.ceremonyRecognition`` (the registry's ``$schema``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ── confidence ordering (the registry's OWN ranking signal) ─────────────
# Lower sort-key sorts FIRST. The seed registry currently ships
# {"high", "medium", "low"}. No other ranking signal is permitted — no
# advice-flavoured relevance scoring (BOUNDARY).
CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}

# verificationStatus values that may be ROUTED against. Per the seed's own
# boundary note, an ``unverified-seed`` entry is wayfinding scaffold only; whether
# to surface it is the CALLER's policy, exposed via the ``allow_unverified`` flag.
_VERIFIED_STATUSES = frozenset({"verified", "council-verified"})


@dataclass(frozen=True)
class RecognitionQuery:
    """Member-confirmed routing facts. No PII beyond the jurisdiction string."""

    jurisdiction: str  # ISO-ish code as used by the registry, e.g. jpn / usa / fra
    ceremony_type: str | None = None  # OPTIONAL label (marriage/naming/funeral); None = no filter
    allow_unverified: bool = True  # surface unverified-seed entries (caller policy)


@dataclass(frozen=True)
class Recognition:
    """One resolved recognition entry — an INFORMATIONAL civil-step route.

    NEVER an advice source and NEVER a civil-status grant (BOUNDARY). The
    ``is_legal_opinion`` / ``confers_civil_status`` pins are ALWAYS False.
    """

    recognition_id: str
    title: str
    jurisdiction: str
    ceremony_type: str
    confidence: str
    verification_status: str
    authority: str
    channel: str
    legal_basis: str
    language: str
    notes: str
    last_verified: str
    provenance: str
    is_legal_opinion: bool  # ALWAYS False (G-invariant)
    confers_civil_status: bool  # ALWAYS False (G-invariant)


@dataclass(frozen=True)
class RecognitionResult:
    jurisdiction: str
    ceremony_type: str | None
    is_legal_opinion: bool  # ALWAYS False (G-invariant)
    confers_civil_status: bool  # ALWAYS False (G-invariant)
    recognitions: tuple[Recognition, ...] = field(default_factory=tuple)


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


def _to_recognition(entry: dict) -> Recognition:
    """Project one raw registry dict → a frozen :class:`Recognition`.

    The G-invariants (``is_legal_opinion`` / ``confers_civil_status``) are
    hard-wired ``False`` here — there is no code path that can set either True.
    This is INFORMATIONAL routing only: it surfaces where a separate civil step
    is required; it gives NO legal advice and NEVER claims to register a civil
    marriage (BOUNDARY).
    """
    if not isinstance(entry, dict):
        raise ValueError(f"registry entry must be a dict, got {type(entry).__name__}")
    recognition_id = _require_str(entry.get("recognitionId"), "recognitionId")
    title = _require_str(entry.get("title"), "title")
    jurisdiction = _require_str(entry.get("jurisdiction"), "jurisdiction")
    ceremony_type = _require_str(entry.get("ceremonyType"), "ceremonyType")
    confidence = _require_str(entry.get("confidence"), "confidence")
    _confidence_rank(confidence)  # validate early (raises on unknown)
    return Recognition(
        recognition_id=recognition_id,
        title=title,
        jurisdiction=jurisdiction,
        ceremony_type=ceremony_type,
        confidence=confidence,
        verification_status=str(entry.get("verificationStatus", "")),
        authority=str(entry.get("authority", "")),
        channel=str(entry.get("channel", "")),
        legal_basis=str(entry.get("legalBasis", "")),
        language=str(entry.get("language", "")),
        notes=str(entry.get("notes", "")),
        last_verified=str(entry.get("lastVerified", "")),
        provenance=str(entry.get("provenance", "")),
        is_legal_opinion=False,  # G-invariant — no path may set this True
        confers_civil_status=False,  # G-invariant — no path may set this True
    )


def resolve_recognitions(query: RecognitionQuery, registry: dict) -> RecognitionResult:
    """Pure registry query: jurisdiction (+ optional ceremony-type) → entries.

    Sorted by the registry's own ``confidence`` (high→medium→low) then ``title``
    (case-insensitive, stable). Unknown jurisdiction → empty result (never a
    guessed match, G8). ``is_legal_opinion`` / ``confers_civil_status`` are
    hard-wired ``False`` (BOUNDARY): musubi performs covenant ceremonies
    (Reformed 万人祭司, NO clergy class) and does NOT confer civil status — this
    routing only surfaces where a SEPARATE civil step is required; it gives NO
    legal advice and NEVER claims to register a civil marriage.
    """
    jurisdiction = _require_str(query.jurisdiction, "jurisdiction").lower()
    ceremony = query.ceremony_type
    if ceremony is not None:
        ceremony = _require_str(ceremony, "ceremony_type").lower()

    if not isinstance(registry, dict):
        raise ValueError("registry must be a dict (parsed ceremony-recognition.seed.json)")
    raw = registry.get("recognitions")
    if not isinstance(raw, list):
        raise ValueError("registry must carry a 'recognitions' list")

    matches: list[Recognition] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each recognition entry must be a dict")
        if str(entry.get("jurisdiction", "")).lower() != jurisdiction:
            continue
        if not query.allow_unverified:
            if str(entry.get("verificationStatus", "")) not in _VERIFIED_STATUSES:
                continue
        if ceremony is not None and str(entry.get("ceremonyType", "")).lower() != ceremony:
            continue
        matches.append(_to_recognition(entry))

    matches.sort(key=lambda r: (_confidence_rank(r.confidence), r.title.casefold()))
    return RecognitionResult(
        jurisdiction=jurisdiction,
        ceremony_type=ceremony,
        is_legal_opinion=False,  # G-invariant
        confers_civil_status=False,  # G-invariant
        recognitions=tuple(matches),
    )


def _iso_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _recognition_view(r: Recognition) -> dict:
    return {
        "recognitionId": r.recognition_id,
        "title": r.title,
        "jurisdiction": r.jurisdiction,
        "ceremonyType": r.ceremony_type,
        "confidence": r.confidence,
        "verificationStatus": r.verification_status,
        "authority": r.authority,
        "channel": r.channel,
        "legalBasis": r.legal_basis,
        "language": r.language,
        "provenance": r.provenance,
        "lastVerified": r.last_verified,
    }


def to_recognition_routing_record(
    result: RecognitionResult,
    *,
    member_did: str,
    created_at: datetime,
    session_ref: str | None = None,
) -> dict:
    """Build an ``com.etzhayyim.musubi.ceremonyRecognition`` routing-view record.

    ``isLegalOpinion`` AND ``confersCivilStatus`` are asserted ``False`` before
    return — G-invariants this function structurally cannot violate. The record
    is a pure wayfinding view: it carries NO eligibility verdict and NEVER claims
    that any civil marriage / naming / death registration has been performed.
    musubi performs covenant ceremonies (Reformed 万人祭司, NO clergy class), it
    does NOT confer civil status; this only surfaces where a SEPARATE civil step
    is required and gives NO legal advice.
    """
    rec: dict = {
        "memberDid": member_did,
        "jurisdiction": result.jurisdiction,
        "isLegalOpinion": False,  # G-invariant
        "confersCivilStatus": False,  # G-invariant
        "isEligibilityDetermination": False,  # never a means-test / rights verdict
        "recognitionCount": len(result.recognitions),
        "recognitions": [_recognition_view(r) for r in result.recognitions],
        "createdAt": _iso_dt(created_at),
    }
    if result.ceremony_type is not None:
        rec["ceremonyTypeLabel"] = result.ceremony_type
    if session_ref is not None:
        rec["sessionRef"] = session_ref
    assert rec["isLegalOpinion"] is False, "G-invariant: isLegalOpinion must be False"
    assert rec["confersCivilStatus"] is False, (
        "G-invariant: confersCivilStatus must be False"
    )
    assert rec["isEligibilityDetermination"] is False, "no eligibility determination"
    return rec


def load_registry(path: str | Path) -> dict:
    """Read + parse the ceremony-recognition seed registry JSON. Stdlib only, no network."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("recognitions"), list):
        raise ValueError(f"{path} is not a valid ceremony-recognition registry")
    return data


__all__ = [
    "CONFIDENCE_ORDER",
    "RecognitionQuery",
    "Recognition",
    "RecognitionResult",
    "resolve_recognitions",
    "to_recognition_routing_record",
    "load_registry",
]
