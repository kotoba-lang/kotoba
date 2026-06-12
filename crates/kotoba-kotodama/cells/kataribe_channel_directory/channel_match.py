"""Pure publication-channel DIRECTORY-QUERY core for ``kataribe`` (語部).

Per ADR-2605263600 (kataribe — press + publishing + translation Tier-B actor)
and the worldwide seed directory shipped at
``20-actors/kataribe/registry/channels.seed.json``. This directory routes a
member to OFFICIAL public publication channels — official gazettes, legal
publications, open-access archives, press-freedom organisations, and translation
resources — i.e. where to FIND authoritative public-domain texts / official
notices / law translations. It is distinct from kataribe's OWN publishing cells
(community chronicle / doctrine commentary / translation / whistleblower).

CONSTITUTIONAL CEILING (CRITICAL — IMMUTABLE):
  * **Not the publisher** — kataribe is NOT the issuer of these channels'
    content; this is wayfinding to an external/official channel.
    ``is_original_publication`` / ``isOriginalPublication`` is ALWAYS ``False``
    with no code path to flip it.
  * **Asserts no content accuracy / authenticity** — surfacing a channel is NOT
    an endorsement of, or a determination about, the accuracy or authority of
    its content; the channel is authoritative on its own terms.
    ``asserts_content_accuracy`` / ``assertsContentAccuracy`` is ALWAYS ``False``.
  * **No editorial / eschatological framing (G4 + §1.15)** — the directory adds
    no commentary, tone, or apocalyptic framing of its own; it records, it does
    not sensationalize. No ranking beyond the registry's own ``confidence`` then
    ``title``.
  * **No surveillance, no PII persistence** beyond the jurisdiction string;
    pure stdlib, no network. Unknown jurisdiction → ``[]`` (never a guessed
    match).

R0/R1 BOUNDARY (CRITICAL): this pure core is importable independently of the
deployable Pregel cell. ``cell.py`` (the ``KataribeChannelDirectoryCell`` graph)
stays non-deployable until Council ratification (Lv6+ ≥3, post Bootstrap
Council RFP 2026-06-19). Landing + testing this core does NOT activate the cell.

Output shape mirrors a directory-routing view over Lexicon
``com.etzhayyim.kataribe.publicationChannel`` (the registry's ``$schema``).
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

# Known channel kinds (ADR-2605263600). All are routing TARGETS — official
# public publication channels. An entry whose ``channelKind`` is outside this
# set raises in ``_to_channel`` (no guessing, no unknown channel routed).
CHANNEL_KINDS = frozenset(
    {
        "official-gazette",
        "legal-publication",
        "open-access-archive",
        "press-freedom-org",
        "translation-resource",
    }
)

# verificationStatus values routable when the caller declines unverified-seed
# entries; whether to surface ``unverified-seed`` is caller policy.
_VERIFIED_STATUSES = frozenset({"verified", "council-verified"})

# Free-text topic matching searches these registry fields. Wayfinding FILTERING
# only — surfaces which channels carry a kind of text; it adds no editorial
# framing and asserts no accuracy.
_SEARCH_FIELDS = ("title", "publisher", "contentType", "notes", "channelKind")


@dataclass(frozen=True)
class ChannelQuery:
    """Member-confirmed routing facts. No PII beyond the jurisdiction string."""

    jurisdiction: str  # registry bloc code, e.g. jpn / usa / intl-*
    topic: str | None = None  # OPTIONAL free-text label; None = no filter
    channel_kind: str | None = None  # OPTIONAL exact kind filter; None = any
    allow_unverified: bool = True  # surface unverified-seed entries (policy)


@dataclass(frozen=True)
class PublicationChannel:
    """One resolved directory TARGET — never kataribe's own publication."""

    channel_id: str
    title: str
    jurisdiction: str
    channel_kind: str
    confidence: str
    verification_status: str
    publisher: str
    access_url: str
    content_type: str
    access: str
    language: str
    provenance: str
    last_verified: str
    notes: str
    is_original_publication: bool  # ALWAYS False
    asserts_content_accuracy: bool  # ALWAYS False


@dataclass(frozen=True)
class ChannelResult:
    jurisdiction: str
    topic: str | None
    channel_kind: str | None
    is_original_publication: bool  # ALWAYS False
    asserts_content_accuracy: bool  # ALWAYS False
    channels: tuple[PublicationChannel, ...] = field(default_factory=tuple)


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


def _to_channel(entry: dict) -> PublicationChannel:
    """Project one raw registry dict → a frozen :class:`PublicationChannel`.

    An unknown ``channelKind`` raises — no unknown channel is ever routed.
    """
    if not isinstance(entry, dict):
        raise ValueError(f"registry entry must be a dict, got {type(entry).__name__}")
    channel_id = _require_str(entry.get("channelId"), "channelId")
    title = _require_str(entry.get("title"), "title")
    jurisdiction = _require_str(entry.get("jurisdiction"), "jurisdiction")
    channel_kind = _require_str(entry.get("channelKind"), "channelKind")
    if channel_kind not in CHANNEL_KINDS:
        raise ValueError(
            f"unknown channelKind {channel_kind!r}; allowed: {sorted(CHANNEL_KINDS)}"
        )
    confidence = _require_str(entry.get("confidence"), "confidence")
    _confidence_rank(confidence)  # validate early (raises on unknown)
    return PublicationChannel(
        channel_id=channel_id,
        title=title,
        jurisdiction=jurisdiction,
        channel_kind=channel_kind,
        confidence=confidence,
        verification_status=str(entry.get("verificationStatus", "")),
        publisher=str(entry.get("publisher", "")),
        access_url=str(entry.get("accessUrl", "")),
        content_type=str(entry.get("contentType", "")),
        access=str(entry.get("access", "")),
        language=str(entry.get("language", "")),
        provenance=str(entry.get("provenance", "")),
        last_verified=str(entry.get("lastVerified", "")),
        notes=str(entry.get("notes", "")),
        is_original_publication=False,  # kataribe is not the publisher here
        asserts_content_accuracy=False,  # routes, never vouches for content
    )


def _topic_matches(entry: dict, needle: str) -> bool:
    """Case-insensitive substring test over the registry's text fields.

    Wayfinding FILTERING only — surfaces which channels carry a kind of text;
    it adds no editorial framing and asserts no accuracy.
    """
    hay = " ".join(str(entry.get(k, "")) for k in _SEARCH_FIELDS).lower()
    return needle in hay


def resolve_channels(query: ChannelQuery, registry: dict) -> ChannelResult:
    """Pure registry query: jurisdiction (+ optional topic/kind) → channels.

    Sorted by the registry's own ``confidence`` (high→medium→low) then ``title``
    (case-insensitive, stable). Unknown jurisdiction → empty result (never a
    guessed match). ``is_original_publication`` / ``asserts_content_accuracy``
    are hard-wired ``False``.
    """
    jurisdiction = _require_str(query.jurisdiction, "jurisdiction").lower()
    topic = query.topic
    if topic is not None:
        topic = _require_str(topic, "topic").lower()
    channel_kind = query.channel_kind
    if channel_kind is not None:
        channel_kind = _require_str(channel_kind, "channel_kind")
        if channel_kind not in CHANNEL_KINDS:
            raise ValueError(
                f"unknown channel_kind {channel_kind!r}; allowed: {sorted(CHANNEL_KINDS)}"
            )

    if not isinstance(registry, dict):
        raise ValueError("registry must be a dict (parsed channels.seed.json)")
    raw = registry.get("channels")
    if not isinstance(raw, list):
        raise ValueError("registry must carry a 'channels' list")

    matches: list[PublicationChannel] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("each channel entry must be a dict")
        if str(entry.get("jurisdiction", "")).lower() != jurisdiction:
            continue
        if channel_kind is not None and str(entry.get("channelKind", "")) != channel_kind:
            continue
        if not query.allow_unverified:
            if str(entry.get("verificationStatus", "")) not in _VERIFIED_STATUSES:
                continue
        if topic is not None and not _topic_matches(entry, topic):
            continue
        matches.append(_to_channel(entry))

    matches.sort(key=lambda c: (_confidence_rank(c.confidence), c.title.casefold()))
    return ChannelResult(
        jurisdiction=jurisdiction,
        topic=topic,
        channel_kind=channel_kind,
        is_original_publication=False,
        asserts_content_accuracy=False,
        channels=tuple(matches),
    )


def _iso_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _channel_view(c: PublicationChannel) -> dict:
    return {
        "channelId": c.channel_id,
        "title": c.title,
        "jurisdiction": c.jurisdiction,
        "channelKind": c.channel_kind,
        "confidence": c.confidence,
        "verificationStatus": c.verification_status,
        "publisher": c.publisher,
        "accessUrl": c.access_url,
        "contentType": c.content_type,
        "access": c.access,
        "language": c.language,
        "provenance": c.provenance,
        "lastVerified": c.last_verified,
    }


def to_channel_routing_record(
    result: ChannelResult,
    *,
    member_did: str,
    created_at: datetime,
    session_ref: str | None = None,
) -> dict:
    """Build a ``com.etzhayyim.kataribe.publicationChannel`` routing record.

    ``isOriginalPublication`` / ``assertsContentAccuracy`` are asserted ``False``
    before return — structural invariants this function cannot violate. The
    record is a pure wayfinding view to OFFICIAL publication channels; it carries
    NO editorial content and NO compensation field (Public-Fund-routed, zero charge).
    """
    rec: dict = {
        "memberDid": member_did,
        "jurisdiction": result.jurisdiction,
        "isOriginalPublication": False,
        "assertsContentAccuracy": False,
        "channelCount": len(result.channels),
        "channels": [_channel_view(c) for c in result.channels],
        "createdAt": _iso_dt(created_at),
    }
    if result.topic is not None:
        rec["topicLabel"] = result.topic
    if result.channel_kind is not None:
        rec["channelKindFilter"] = result.channel_kind
    if session_ref is not None:
        rec["sessionRef"] = session_ref
    assert rec["isOriginalPublication"] is False, "invariant: not original publication"
    assert rec["assertsContentAccuracy"] is False, "invariant: asserts no accuracy"
    return rec


def load_registry(path: str | Path) -> dict:
    """Read + parse the publication-channel seed registry JSON. Stdlib only."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("channels"), list):
        raise ValueError(f"{path} is not a valid publication-channel registry")
    return data


__all__ = [
    "CONFIDENCE_ORDER",
    "CHANNEL_KINDS",
    "ChannelQuery",
    "PublicationChannel",
    "ChannelResult",
    "resolve_channels",
    "to_channel_routing_record",
    "load_registry",
]
