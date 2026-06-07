"""Creative-works sensor Protocols + Observation dataclasses.

Per ADR-2605265000 §4. Five sensor families specialize the DatasetSensor
Protocol from ADR-2605262400 §3:

- ``CreativeFilmSensor`` (film modality)
- ``CreativeVideoSensor`` (video modality)
- ``CreativeMusicSymbolicSensor`` (music-symbolic; G3 sidesteps recording layer)
- ``CreativeMusicRecordingSensor`` (music-recording; G3 dual-attestation required)
- ``CreativeAudioSensor`` (audio-speech + audio-sound)

Observation shapes per modality — film yields per-work title + duration +
URAA check; video yields per-clip duration + source; music-symbolic yields
score format (PDF / MusicXML / MIDI / LilyPond) + composer; music-recording
yields composition + recording dual-CIDs; audio yields runtime + narrator
volunteer CC0 attestation (LibriVox-class) or institution attribution
(LoC / British Library).

Per-work PD attestation CID (publicDomainStatusAttestation per ADR-2605265000
§5 L1) MANDATORY for admission — observation carries the attestation CID.

Commercial vendor imports (Adobe Stock / Getty / Shutterstock / Pond5 /
Audio Network / paid PD-collections) are CONSTITUTIONALLY PROHIBITED per
Charter Rider §2(e) + §2(c) — lint enforced at W1.

Inference of derived artifacts is Murakumo-only (ADR-2605215000).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal, Protocol, runtime_checkable

from ..base import DatasetPin, Tier


Modality = Literal[
    "film",
    "video",
    "music-symbolic",
    "music-recording",
    "audio-speech",
    "audio-sound",
]


TierClassification = Literal[
    "A",                       # Public Domain / CC0 1.0 — publishable
    "B-cc-by",                 # CC-BY 3.0/4.0 — Tier-B with attribution chain
    "B-cc-by-sa",              # CC-BY-SA 3.0/4.0 — Tier-B with attribution + SA propagation
    "B-nhk-cc-by-2.1-jp",      # NHK Creative Library — G13 fleet-internal carve-out
]


ScoreFormat = Literal[
    "musicxml",
    "midi",
    "lilypond",
    "pdf-engraved",
    "abc-notation",
    "kern",
]


# ── Observation dataclasses ────────────────────────────────────────


@dataclass(frozen=True)
class CreativeFilmObservation:
    sensor: str
    tier: Tier
    pin_revision: str
    work_id: str                     # 'librivox:12345' / 'ia:0000-feature' format
    title: str
    director: str | None
    director_death_year: int | None
    release_year: int
    runtime_seconds: int
    media_format: str                # 'mp4' / 'mkv' / 'webm'
    payload_cid: str                 # IPFS CID of the media file
    pd_attestation_cid: str          # IPFS CID of publicDomainStatusAttestation
    wellbecoming_scan_cid: str       # IPFS CID of wellbecomingFramingScan
    uraa_check_status: str           # 'not-applicable' / 'checked-not-restored' / etc.
    tier_classification: TierClassification
    license_tag: str                 # source archive license tag
    captured_at_ms: int = 0
    internal_only: bool = False


@dataclass(frozen=True)
class CreativeVideoObservation:
    sensor: str
    tier: Tier
    pin_revision: str
    work_id: str
    title: str
    creator: str | None
    creator_death_year: int | None
    publication_year: int
    runtime_seconds: int
    media_format: str
    payload_cid: str
    pd_attestation_cid: str
    wellbecoming_scan_cid: str
    tier_classification: TierClassification
    license_tag: str
    captured_at_ms: int = 0
    internal_only: bool = False


@dataclass(frozen=True)
class CreativeMusicSymbolicObservation:
    """Symbolic music (no recording layer per G3)."""
    sensor: str
    tier: Tier
    pin_revision: str
    work_id: str
    title: str
    composer: str
    composer_death_year: int          # Required for life+N rule
    composition_year: int | None
    score_format: ScoreFormat
    score_payload_cid: str            # IPFS CID of score file
    pd_attestation_cid: str           # CID of publicDomainStatusAttestation
    wellbecoming_scan_cid: str
    tier_classification: TierClassification
    license_tag: str                  # 'Public Domain' / 'CC0-1.0' / 'CC-BY-4.0' / etc.
    captured_at_ms: int = 0
    internal_only: bool = False


@dataclass(frozen=True)
class CreativeMusicRecordingObservation:
    """Music recording — dual-copyright (composition + recording)."""
    sensor: str
    tier: Tier
    pin_revision: str
    work_id: str
    title: str
    composer: str
    composer_death_year: int
    performer_names: tuple[str, ...]
    performer_death_years: tuple[int, ...]  # latest drives pessimistic threshold
    release_year: int
    runtime_seconds: int
    audio_format: str                 # 'wav' / 'flac' / 'mp3' / 'ogg'
    recording_payload_cid: str        # IPFS CID of audio file
    pd_attestation_cid: str
    wellbecoming_scan_cid: str
    chromaprint_fingerprint_cid: str  # For G6 spectral-fingerprint check
    uraa_check_status: str
    tier_classification: TierClassification
    license_tag: str
    captured_at_ms: int = 0
    internal_only: bool = False


@dataclass(frozen=True)
class CreativeAudioObservation:
    """Audio modality (speech + sound; LibriVox / LoC Folklife / British Library)."""
    sensor: str
    tier: Tier
    pin_revision: str
    work_id: str
    title: str
    modality_subkind: Literal["audio-speech", "audio-sound"]
    author: str | None                # e.g. PD-text author for LibriVox audiobook
    author_death_year: int | None
    narrator_or_performer: str | None
    volunteer_cc0_declaration: bool   # true for LibriVox volunteers + similar
    publication_year: int             # for derivative works: year of recording / publication
    source_text_year: int | None      # for audiobooks: year of original PD text
    runtime_seconds: int
    audio_format: str
    payload_cid: str
    pd_attestation_cid: str
    wellbecoming_scan_cid: str
    chromaprint_fingerprint_cid: str
    tier_classification: TierClassification
    license_tag: str
    captured_at_ms: int = 0
    internal_only: bool = False


# ── Sensor Protocols ───────────────────────────────────────────────


@runtime_checkable
class CreativeFilmSensor(Protocol):
    """Film modality sensor. PASSIVE-ONLY ingestion (G4)."""

    sensor_id: str
    source_archive: str

    def latest_pin(self) -> DatasetPin: ...
    def hot_sample(self, n: int = 32) -> Iterator[CreativeFilmObservation]: ...


@runtime_checkable
class CreativeVideoSensor(Protocol):
    """Video modality sensor."""

    sensor_id: str
    source_archive: str

    def latest_pin(self) -> DatasetPin: ...
    def hot_sample(self, n: int = 32) -> Iterator[CreativeVideoObservation]: ...


@runtime_checkable
class CreativeMusicSymbolicSensor(Protocol):
    """Symbolic-music sensor (Mutopia / IMSLP scores). G3 sidesteps recording layer."""

    sensor_id: str
    source_archive: str

    def latest_pin(self) -> DatasetPin: ...
    def hot_sample(self, n: int = 32) -> Iterator[CreativeMusicSymbolicObservation]: ...


@runtime_checkable
class CreativeMusicRecordingSensor(Protocol):
    """Music-recording sensor. G3 STRUCTURAL: composition AND recording dual-attestation required."""

    sensor_id: str
    source_archive: str

    def latest_pin(self) -> DatasetPin: ...
    def hot_sample(self, n: int = 32) -> Iterator[CreativeMusicRecordingObservation]: ...


@runtime_checkable
class CreativeAudioSensor(Protocol):
    """Audio sensor (speech + sound). LibriVox / LoC Folklife / British Library."""

    sensor_id: str
    source_archive: str

    def latest_pin(self) -> DatasetPin: ...
    def hot_sample(self, n: int = 32) -> Iterator[CreativeAudioObservation]: ...
