"""Open-government-data sensor Protocols + Observation dataclasses.

Per ADR-2605263900 §3. Five sensor families specialize the DatasetSensor
Protocol from ADR-2605262400 §3:

- ``GovOpenDataSensor`` (per-jurisdiction open-data portal; data.gov class)
- ``GovParliamentSensor`` (per-legislature 議事録 / Hansard / OEIL /
  Congressional Record)
- ``GovBudgetSensor`` (per-jurisdiction budget + spending; USAspending,
  EU FTS, national budget bulletins)
- ``GovProcurementSensor`` (per-jurisdiction tender notices + awards;
  TED, SAM.gov, 政府調達情報)
- ``GovStatisticsSensor`` (per-IGO statistics; Eurostat, OECD.Stat,
  World Bank Open Data, IMF SDMX, UN data)

Observation shapes diverge per family — open-data yields dataset
catalog entry; parliament yields debate/vote/member-statement excerpt;
budget yields recipient + outlay + appropriation; procurement yields
tender / award / awardee; statistics yields indicator + dimensions +
observation values.

Per-jurisdiction publication-rule honoring (parliament transcripts +
procurement awards + budget recipients are public by design; GDPR
right-to-be-forgotten DSARs route through chigiri.data_privacy to
upstream publisher — religious-corp NEVER performs unilateral removal).

CN data carries ``state_aligned_flag=True`` per §2(g) (parallel to
ADR-2605262800 CN NPC handling): ingested as authoritative source of
record but non-substitution doctrine — downstream consumers MUST display
the flag in any derived publication.

Vendor commercial gov-intel terminal imports (GovWin IQ / Bloomberg
Government / Politico Pro / E&E News Pro / FiscalNote / CQ Roll Call Pro)
are CONSTITUTIONALLY PROHIBITED per Charter Rider §2(e) + §2(c).
Sensor implementations MUST NOT import or call those vendor SDKs /
hostnames — lint enforced at W1.

Inference of derived artifacts is Murakumo-only (ADR-2605215000).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal, Protocol, runtime_checkable

from ..base import DatasetPin, PiiFilterPolicy, Tier

GovFacet = Literal[
    "open-data", "parliament", "budget", "procurement", "statistics",
]

ParliamentRecordKind = Literal[
    "debate",            # plenary debate transcript
    "committee",         # committee record
    "bill",              # legislative bill text
    "vote",              # roll-call vote record
    "member-statement",  # individual member statement
    "petition",          # citizen petition
    "question",          # parliamentary question
]

BudgetRecordKind = Literal[
    "appropriation",     # legislative appropriation
    "obligation",        # obligated funds
    "outlay",            # actual disbursement
    "subaward",          # downstream sub-recipient
]

ProcurementRecordKind = Literal[
    "tender-notice",     # solicitation / RFP
    "award",             # contract award
    "modification",      # contract modification
    "cancellation",      # solicitation withdrawn
]


# ── Observation dataclasses (specialize ../base.SensorObservation) ──


@dataclass(frozen=True)
class GovOpenDataObservation:
    sensor: str
    tier: Tier
    pin_revision: str
    jurisdiction: str         # ISO-3 OR supra ("EU", "OECD", "UN", "WB", "IMF")
    dataset_id: str           # per-portal canonical ID (CKAN package name etc.)
    title: str
    description_excerpt: str
    license_tag: str
    publisher: str | None
    published_at_utc: str | None
    payload_cid: str
    state_aligned_flag: bool = False
    captured_at_ms: int = 0
    internal_only: bool = False


@dataclass(frozen=True)
class GovParliamentObservation:
    sensor: str
    tier: Tier
    pin_revision: str
    jurisdiction_iso3: str
    legislature: str          # e.g. "us-congress" / "uk-parliament" / "jp-kokkai"
    record_kind: ParliamentRecordKind
    record_id: str            # per-legislature canonical ID
    body_excerpt: str
    speaker_name: str | None  # named per upstream publication rule (G3)
    speaker_role: str | None
    session_date_utc: str
    license_tag: str
    payload_cid: str
    state_aligned_flag: bool = False
    captured_at_ms: int = 0
    internal_only: bool = False
    pii_redacted: bool = False


@dataclass(frozen=True)
class GovBudgetObservation:
    sensor: str
    tier: Tier
    pin_revision: str
    jurisdiction: str
    record_kind: BudgetRecordKind
    record_id: str
    program_name: str
    program_code: str | None
    amount_local: float
    currency_iso4217: str
    fiscal_year: int
    recipient_name: str | None       # named per upstream (transparency regime reason)
    recipient_local_id: str | None   # e.g. SAM.gov UEI, EU PIC
    recipient_lei: str | None        # cross-link to LEI sensor (ADR-2605263800)
    award_date_utc: str | None
    license_tag: str
    payload_cid: str
    state_aligned_flag: bool = False
    captured_at_ms: int = 0
    internal_only: bool = False


@dataclass(frozen=True)
class GovProcurementObservation:
    sensor: str
    tier: Tier
    pin_revision: str
    jurisdiction: str
    record_kind: ProcurementRecordKind
    notice_id: str
    title: str
    contracting_authority: str
    awardee_name: str | None
    awardee_local_id: str | None
    awardee_lei: str | None
    award_amount_local: float | None
    currency_iso4217: str | None
    award_date_utc: str | None
    license_tag: str
    payload_cid: str
    state_aligned_flag: bool = False
    captured_at_ms: int = 0
    internal_only: bool = False


@dataclass(frozen=True)
class GovStatisticsObservation:
    sensor: str
    tier: Tier
    pin_revision: str
    source: str               # "eurostat" / "oecd-stat" / "worldbank" / "imf-sdmx" / "un-data"
    indicator_code: str       # source-canonical indicator ID
    indicator_title: str
    dimensions: tuple[tuple[str, str], ...]  # ordered (dim_code, dim_value) pairs
    value: float | None       # None if missing-value flag set upstream
    value_unit: str | None
    observation_period: str   # ISO-8601 period (e.g. "2025-Q3" / "2025-12")
    license_tag: str
    payload_cid: str
    state_aligned_flag: bool = False
    captured_at_ms: int = 0
    internal_only: bool = False


# ── Sensor Protocols ───────────────────────────────────────────────


@runtime_checkable
class GovOpenDataSensor(Protocol):
    """Read-only sensor over a ``gov/open-data/<jurisdiction>/`` subdataset.

    Implementations MUST be deterministic on ``hot_sample(pin, n)``
    (G7 in ADR-2605263900). Implementations MUST NOT touch any network
    resource other than the religious-corp DID infrastructure and the
    local Kubo HTTP API (G6 + G12 — vendor commercial gov-intel terminal
    hostnames added to lint deny-list at W1).
    """

    name: str
    license: str
    tier: Tier
    refresh_cadence_sec: int
    pii_filter: PiiFilterPolicy
    jurisdiction: str

    def latest_pin(self) -> DatasetPin: ...

    def stream(self, pin: DatasetPin) -> Iterator[GovOpenDataObservation]: ...

    def hot_sample(self, pin: DatasetPin, n: int) -> list[GovOpenDataObservation]: ...


@runtime_checkable
class GovParliamentSensor(Protocol):
    """Read-only sensor over a ``gov/parliament/<jurisdiction>/`` subdataset.

    Speaker names are passed through per upstream publication rule
    (parliament transcripts are public by design across all W1-W3
    jurisdictions). ``pii_redacted`` is set True iff per-jurisdiction
    redaction policy was applied (e.g., DE/FR pseudonymization of
    petitioner names where upstream pseudonymizes).
    """

    name: str
    license: str
    tier: Tier
    refresh_cadence_sec: int
    pii_filter: PiiFilterPolicy
    jurisdiction_iso3: str
    legislature: str

    def latest_pin(self) -> DatasetPin: ...

    def stream(self, pin: DatasetPin) -> Iterator[GovParliamentObservation]: ...

    def hot_sample(self, pin: DatasetPin, n: int) -> list[GovParliamentObservation]: ...


@runtime_checkable
class GovBudgetSensor(Protocol):
    """Read-only sensor over a ``gov/budget/<jurisdiction>/`` subdataset.

    Cross-links to LEI sensor (ADR-2605263800 ``LeiSensor``) when
    recipient is a legal entity with a GLEIF LEI; used by toritate
    (ADR-2605262900) for recipient-vendor anti-related-party checks.
    """

    name: str
    license: str
    tier: Tier
    refresh_cadence_sec: int
    pii_filter: PiiFilterPolicy
    jurisdiction: str

    def latest_pin(self) -> DatasetPin: ...

    def stream(self, pin: DatasetPin) -> Iterator[GovBudgetObservation]: ...

    def hot_sample(self, pin: DatasetPin, n: int) -> list[GovBudgetObservation]: ...


@runtime_checkable
class GovProcurementSensor(Protocol):
    """Read-only sensor over a ``gov/procurement/<jurisdiction>/`` subdataset.

    Awardee fields are passed through (procurement transparency is the
    publication-regime reason for these data sources). Cross-links to
    LEI sensor used by toritate (ADR-2605262900).
    """

    name: str
    license: str
    tier: Tier
    refresh_cadence_sec: int
    pii_filter: PiiFilterPolicy
    jurisdiction: str

    def latest_pin(self) -> DatasetPin: ...

    def stream(self, pin: DatasetPin) -> Iterator[GovProcurementObservation]: ...

    def hot_sample(self, pin: DatasetPin, n: int) -> list[GovProcurementObservation]: ...


@runtime_checkable
class GovStatisticsSensor(Protocol):
    """Read-only sensor over a ``gov/statistics/<source>/`` subdataset.

    Powers manabi civic-literacy curriculum (Eurostat / OECD.Stat /
    World Bank / IMF / UN) + baien-distill civic-reasoning specialist.
    """

    name: str
    license: str
    tier: Tier
    refresh_cadence_sec: int
    pii_filter: PiiFilterPolicy
    source: str

    def latest_pin(self) -> DatasetPin: ...

    def stream(self, pin: DatasetPin) -> Iterator[GovStatisticsObservation]: ...

    def hot_sample(self, pin: DatasetPin, n: int) -> list[GovStatisticsObservation]: ...


__all__ = [
    "BudgetRecordKind",
    "GovBudgetObservation",
    "GovBudgetSensor",
    "GovFacet",
    "GovOpenDataObservation",
    "GovOpenDataSensor",
    "GovParliamentObservation",
    "GovParliamentSensor",
    "GovProcurementObservation",
    "GovProcurementSensor",
    "GovStatisticsObservation",
    "GovStatisticsSensor",
    "ParliamentRecordKind",
    "ProcurementRecordKind",
]
