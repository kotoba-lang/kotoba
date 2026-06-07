"""Corporate-disclosure sensor Protocols + Observation dataclasses.

Per ADR-2605263800 §3. Five sensor families specialize the DatasetSensor
Protocol from ADR-2605262400 §3:

- ``CorpRegistrySensor`` (per-jurisdiction legal-entity registry)
- ``CorpDisclosureSensor`` (per-jurisdiction periodic financial filings)
- ``LeiSensor`` (GLEIF LEI canonical + relationship, global cross-juris)
- ``CorpOwnershipSensor`` (UBO / parent-subsidiary / control graph)
- ``CorpFilingEventSensor`` (material-event filings; low-latency hot-path)

Observation shapes diverge per family — registry yields filer reference;
disclosure yields form_type + filing artifact CID; LEI yields canonical
LEI + relationship-record subset; ownership yields control edge;
filing-event yields material-event header.

Per-jurisdiction publication-redaction policy honors upstream rules
(SEC pass-through / Companies House pass-through / EDINET pass-through /
EU member-state per-state honor / GDPR right-to-be-forgotten DSARs route
through chigiri.data_privacy to upstream publisher).

Vendor commercial terminal imports (Bloomberg Terminal / S&P Capital IQ /
Refinitiv Eikon / FactSet / Moody's Orbis / D&B Hoovers / Pitchbook /
Crunchbase Pro) are CONSTITUTIONALLY PROHIBITED per Charter Rider §2(e)
+ §2(c). Sensor implementations MUST NOT import or call those vendor
SDKs / hostnames — lint enforced at W1.

Inference of derived artifacts is Murakumo-only (ADR-2605215000).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal, Protocol, runtime_checkable

from ..base import DatasetPin, PiiFilterPolicy, Tier

# Form classes (intentionally narrow — extend in W2+ per-jurisdiction
# adapter, with explicit Lexicon registration).
FormClass = Literal[
    "annual-report",          # 10-K / yuho / annual-accounts / UK CS01
    "interim-report",         # 10-Q / hanki / EU half-year
    "material-event",         # 8-K / 大量保有報告書 / similar
    "insider-transaction",    # Form 4 / SC 13D/G / EDINET 大量保有
    "institutional-holding",  # 13F / similar
    "registration",           # S-1 / S-3 / IPO prospectus
    "filer-amendment",        # amendments to any of the above
]

OwnershipKind = Literal[
    "ubo",                    # Ultimate Beneficial Owner (>=25% per FATF)
    "direct-shareholder",     # named >=5% / per-juris threshold
    "parent-subsidiary",      # consolidated-group edge
    "control-relationship",   # GLEIF L2 control relationship record
    "officer",                # named officer / director
]


# ── Observation dataclasses (specialize ../base.SensorObservation) ──


@dataclass(frozen=True)
class CorpRegistryObservation:
    sensor: str
    tier: Tier
    pin_revision: str
    jurisdiction_iso3: str
    entity_local_id: str      # CIK / EDINET 提出者 ID / UK CRN / JP 法人番号
    entity_lei: str | None    # GLEIF LEI 20-char; None if non-LEI-bearing
    registered_name: str
    registered_at: str | None
    license_tag: str
    captured_at_ms: int = 0
    internal_only: bool = False


@dataclass(frozen=True)
class CorpDisclosureObservation:
    sensor: str
    tier: Tier
    pin_revision: str
    jurisdiction_iso3: str
    entity_local_id: str
    entity_lei: str | None
    form_class: FormClass
    form_type_native: str     # raw per-juris form code, e.g. "10-K" / "yuho"
    filed_at_utc: str
    payload_cid: str          # IPFS CID of normalized JSON payload
    license_tag: str
    captured_at_ms: int = 0
    internal_only: bool = False
    pii_redacted: bool = False


@dataclass(frozen=True)
class LeiObservation:
    sensor: str
    tier: Tier
    pin_revision: str
    entity_lei: str           # 20-char GLEIF LEI (canonical)
    legal_name: str
    jurisdiction_iso3: str    # incorporation jurisdiction
    registration_status: str  # ISSUED / LAPSED / RETIRED / etc.
    parent_lei: str | None    # GLEIF L2 direct-parent
    ultimate_parent_lei: str | None
    license_tag: str          # CC0 1.0 canonical
    captured_at_ms: int = 0
    internal_only: bool = False


@dataclass(frozen=True)
class CorpOwnershipObservation:
    sensor: str
    tier: Tier
    pin_revision: str
    subject_lei: str | None
    subject_local_id: str | None
    subject_jurisdiction_iso3: str
    owner_lei: str | None
    owner_local_id: str | None
    owner_jurisdiction_iso3: str | None
    ownership_kind: OwnershipKind
    pct_held: float | None    # 0.0..100.0; None for officer / control-edge
    as_of: str | None
    license_tag: str
    captured_at_ms: int = 0
    internal_only: bool = False


@dataclass(frozen=True)
class CorpFilingEventObservation:
    sensor: str
    tier: Tier
    pin_revision: str
    jurisdiction_iso3: str
    entity_local_id: str
    entity_lei: str | None
    event_kind: str           # per-juris taxonomy (e.g. "8-K item 1.01")
    event_summary: str        # short header excerpt (NOT full body)
    filed_at_utc: str
    payload_cid: str
    license_tag: str
    captured_at_ms: int = 0
    internal_only: bool = False


# ── Sensor Protocols ───────────────────────────────────────────────


@runtime_checkable
class CorpRegistrySensor(Protocol):
    """Read-only sensor over a ``corp/registries/<jurisdiction>/`` subdataset.

    Implementations MUST be deterministic on ``hot_sample(pin, n)``
    (G7 in ADR-2605263800). Implementations MUST NOT touch any network
    resource other than the religious-corp DID infrastructure and the
    local Kubo HTTP API (G6 + G12 — vendor commercial terminal hostnames
    added to lint deny-list at W1).
    """

    name: str
    license: str
    tier: Tier
    refresh_cadence_sec: int
    pii_filter: PiiFilterPolicy
    jurisdiction_iso3: str

    def latest_pin(self) -> DatasetPin: ...

    def stream(self, pin: DatasetPin) -> Iterator[CorpRegistryObservation]: ...

    def hot_sample(self, pin: DatasetPin, n: int) -> list[CorpRegistryObservation]: ...


@runtime_checkable
class CorpDisclosureSensor(Protocol):
    """Read-only sensor over a ``corp/disclosures/<jurisdiction>/<form>/``
    subdataset.

    Per-jurisdiction publication-redaction policy (§5 in ADR-2605263800)
    is applied prior to yielding CorpDisclosureObservation. ``pii_redacted``
    is set True iff that policy modified the payload view.
    """

    name: str
    license: str
    tier: Tier
    refresh_cadence_sec: int
    pii_filter: PiiFilterPolicy
    jurisdiction_iso3: str
    form_class: FormClass

    def latest_pin(self) -> DatasetPin: ...

    def stream(self, pin: DatasetPin) -> Iterator[CorpDisclosureObservation]: ...

    def hot_sample(self, pin: DatasetPin, n: int) -> list[CorpDisclosureObservation]: ...


@runtime_checkable
class LeiSensor(Protocol):
    """Read-only sensor over the ``corp/lei/gleif/`` subdataset.

    GLEIF concatenated files (Level-1 entity + Level-2 relationship)
    are CC0 1.0 / Tier-A globally. This sensor is the canonical
    cross-jurisdiction key resolver — other corp sensors set
    ``entity_lei`` by looking up the local registry ID against this
    sensor's pin.
    """

    name: str
    license: str
    tier: Tier
    refresh_cadence_sec: int
    pii_filter: PiiFilterPolicy

    def latest_pin(self) -> DatasetPin: ...

    def stream(self, pin: DatasetPin) -> Iterator[LeiObservation]: ...

    def hot_sample(self, pin: DatasetPin, n: int) -> list[LeiObservation]: ...


@runtime_checkable
class CorpOwnershipSensor(Protocol):
    """Read-only sensor over a ``corp/ownership/<source>/`` subdataset.

    Sources include GLEIF L2 (Tier-A CC0), EU per-member-state UBO
    registers (Tier-A per-state license), US FinCEN BOI (Tier-A when
    publicly accessible; currently gov-only — W4 re-evaluate), and
    OpenCorporates open-data control graph (Tier-B CC-BY-SA;
    ``-tierB-`` infix per G4).
    """

    name: str
    license: str
    tier: Tier
    refresh_cadence_sec: int
    pii_filter: PiiFilterPolicy
    source_id: str            # e.g. "gleif-l2" / "eu-ubo-de" / "opencorporates-opendata"
    ownership_kind_filter: tuple[OwnershipKind, ...] = ()

    def latest_pin(self) -> DatasetPin: ...

    def stream(self, pin: DatasetPin) -> Iterator[CorpOwnershipObservation]: ...

    def hot_sample(self, pin: DatasetPin, n: int) -> list[CorpOwnershipObservation]: ...


@runtime_checkable
class CorpFilingEventSensor(Protocol):
    """Read-only sensor over a ``corp/filing-events/<source>/`` subdataset.

    Filing-event sensors run at HIGHER cadence than periodic-report
    sensors (W3 anchor sources = SEC EDGAR RSS + JP EDINET API
    snapshots), and yield material-event headers only — full body is
    referenced via ``payload_cid`` for the cold-path training corpus.
    """

    name: str
    license: str
    tier: Tier
    refresh_cadence_sec: int
    pii_filter: PiiFilterPolicy
    source_id: str            # e.g. "sec-edgar-rss" / "jp-edinet-api"

    def latest_pin(self) -> DatasetPin: ...

    def stream(self, pin: DatasetPin) -> Iterator[CorpFilingEventObservation]: ...

    def hot_sample(self, pin: DatasetPin, n: int) -> list[CorpFilingEventObservation]: ...


__all__ = [
    "CorpDisclosureObservation",
    "CorpDisclosureSensor",
    "CorpFilingEventObservation",
    "CorpFilingEventSensor",
    "CorpOwnershipObservation",
    "CorpOwnershipSensor",
    "CorpRegistryObservation",
    "CorpRegistrySensor",
    "FormClass",
    "LeiObservation",
    "LeiSensor",
    "OwnershipKind",
]
