"""Public-domain creative-works sensors for the artificial-organism ecosystem.

Per ADR-2605265000. Five sensor families specialize the DatasetSensor
Protocol from ADR-2605262400 §3:

- ``CreativeFilmSensor`` (film modality — single-work copyright + URAA check)
- ``CreativeVideoSensor`` (video modality — newsreels / NASA AV / Wiki Commons video)
- ``CreativeMusicSymbolicSensor`` (music-symbolic — Mutopia / IMSLP scores; G3 sidesteps recording layer)
- ``CreativeMusicRecordingSensor`` (music-recording — Musopen PD audio / Wiki Commons PD audio; G3 dual-attestation required)
- ``CreativeAudioSensor`` (audio-speech + audio-sound — LibriVox / LoC American Folklife / British Library Sounds)

Wave-1 anchor sensors (path-reserved; impl lands in W1 deliverable at
70-tools/e7m-dataset/src/e7m_dataset/fetchers/):

- ``librivox`` (LibriVox CC0+PD audiobook narration; cleanest first audio sensor)
- ``mutopia`` (Mutopia Project PD sheet music + MIDI + MusicXML)
- ``internet_archive_pd_films`` (archive.org /details/feature_films PD subset)

W2+ adds Prelinger + NASA + IMSLP + LoC American Folklife + Wikimedia Commons.
W3+ adds NHK Creative Library (G13 fleet-internal carve-out) + Tier-B Wikimedia Commons CC-BY/CC-BY-SA.
W4+ adds orphan-works research carve-out (Council Lv6+ ≥3; R3+ only; NOT training).

Per-work PD attestation MANDATORY (G1) before admission. Multi-juris
pessimistic threshold (G2) — work admitted only if PD in ALL of
{USA, EUR, GBR, JPN, AUS, CAN, CHN}. Music modality requires dual-
attestation (G3): composition AND recording both PD. Charter Rider
§2(d) Wellbecoming framing scan per work (G7) — pre-1929 racial
content / WWI+WWII newsreels / 1920s exotic travelogue / pre-1955
advertising auto-flag → Council Lv6+ ≥3 queue.

Passive-only invariant (G4): sensors MUST NOT perform live archive
scraping at organism-tick time; only pre-pinned IPFS snapshots
via ``e7m-dataset add`` / ``com.etzhayyim.substrate.datasetPin``.

Commercial vendor imports (Adobe Stock / Getty / Shutterstock / Pond5 /
Audio Network / paid PD-collections) are CONSTITUTIONALLY PROHIBITED
per Charter Rider §2(e) anti-gatekeeping + §2(c) vendor query-tracking
exposes member training-data interest profile.

Memorization guardrail (G6) at baien-distill commit_node: 3-pronged
eval (verbatim regurgitation probe ≤1% + DP-SGD ε≤8.0 R3+ +
Chromaprint spectral-fingerprint distance ≥0.2 for audio). Inference
of derived artifacts is Murakumo-only (ADR-2605215000).

Downstream consumers:
- baien-distill creative-foundations recipe family
- manabi arts-literacy + civic-literacy curriculum (Tier-A only)
- ossekai (ADR-2605264000) annual Public-Domain-Day Jan 1 advisory
"""

from __future__ import annotations

from .base import (
    CreativeAudioObservation,
    CreativeAudioSensor,
    CreativeFilmObservation,
    CreativeFilmSensor,
    CreativeMusicRecordingObservation,
    CreativeMusicRecordingSensor,
    CreativeMusicSymbolicObservation,
    CreativeMusicSymbolicSensor,
    CreativeVideoObservation,
    CreativeVideoSensor,
    Modality,
    TierClassification,
)

__all__ = [
    "CreativeAudioObservation",
    "CreativeAudioSensor",
    "CreativeFilmObservation",
    "CreativeFilmSensor",
    "CreativeMusicRecordingObservation",
    "CreativeMusicRecordingSensor",
    "CreativeMusicSymbolicObservation",
    "CreativeMusicSymbolicSensor",
    "CreativeVideoObservation",
    "CreativeVideoSensor",
    "Modality",
    "TierClassification",
]
