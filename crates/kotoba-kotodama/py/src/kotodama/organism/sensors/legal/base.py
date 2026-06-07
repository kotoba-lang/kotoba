"""Legal-corpus sensor Protocols + Observation dataclasses.

Per ADR-2605262800 §3. Five sensor families specialize the DatasetSensor
Protocol from ADR-2605262400 §3:

- ``LegalStatuteSensor`` (per jurisdiction; statute_class enum)
- ``LegalCaseSensor`` (per court system)
- ``LegalTreatySensor`` (per treaty corpus)
- ``LegalProcedureSensor`` (per regulatory body)
- ``LegalTemplateSensor`` (chigiri-consumable templates)

Observation shapes diverge per family — statutes carry citation +
in_force_at; cases carry citation + parties_redacted + holding excerpt;
etc. The judicial_party_redactor (sibling module) is applied to
LegalCaseObservation prior to yield.

Inference of derived artifacts is Murakumo-only (ADR-2605215000).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal, Protocol, runtime_checkable

from ..base import DatasetPin, PiiFilterPolicy, Tier

StatuteClass = Literal["constitution", "code", "act", "regulation", "directive", "rule"]
ProcedureClass = Literal["administrative", "judicial", "regulatory", "tax", "registry"]
TemplateClass = Literal["license", "ceremony", "mediation", "tax-receipt", "dsar", "ip-claim"]


# ── Observation dataclasses (specialize ../base.SensorObservation) ──


@dataclass(frozen=True)
class LegalStatuteObservation:
    sensor: str
    tier: Tier
    pin_revision: str
    citation: str
    title: str
    body_excerpt: str
    jurisdiction_iso3: str
    statute_class: StatuteClass
    in_force_at: str | None
    license_tag: str
    captured_at_ms: int = 0
    internal_only: bool = False


@dataclass(frozen=True)
class LegalCaseObservation:
    sensor: str
    tier: Tier
    pin_revision: str
    citation: str
    court: str
    decision_date: str
    parties_redacted: tuple[str, ...]
    holding_excerpt: str
    license_tag: str
    captured_at_ms: int = 0
    internal_only: bool = False


@dataclass(frozen=True)
class LegalTreatyObservation:
    sensor: str
    tier: Tier
    pin_revision: str
    treaty_id: str
    title: str
    party_states_iso3: tuple[str, ...]
    in_force_at: str | None
    body_excerpt: str
    license_tag: str
    captured_at_ms: int = 0
    internal_only: bool = False


@dataclass(frozen=True)
class LegalProcedureObservation:
    sensor: str
    tier: Tier
    pin_revision: str
    procedure_id: str
    title: str
    steps_excerpt: str
    jurisdiction_iso3: str
    procedure_class: ProcedureClass
    license_tag: str
    captured_at_ms: int = 0
    internal_only: bool = False


@dataclass(frozen=True)
class LegalTemplateObservation:
    sensor: str
    tier: Tier
    pin_revision: str
    template_id: str
    title: str
    body: str
    jurisdiction_iso3: str | None
    template_class: TemplateClass
    license_tag: str
    chigiri_consumer_cell_hint: str | None
    captured_at_ms: int = 0
    internal_only: bool = False


# ── Sensor Protocols ───────────────────────────────────────────────


@runtime_checkable
class LegalStatuteSensor(Protocol):
    """Read-only sensor over a ``law/statutes/<jurisdiction>/`` subdataset.

    Implementations MUST be deterministic on ``hot_sample(pin, n)`` (G9).
    Implementations MUST NOT touch any network resource other than the
    religious-corp DID infrastructure and the local Kubo HTTP API (G8 +
    G7 — Westlaw / LexisNexis / Bloomberg Law explicitly added to lint
    deny-list at W1).
    """

    name: str
    license: str
    tier: Tier
    refresh_cadence_sec: int
    pii_filter: PiiFilterPolicy
    jurisdiction_iso3: str
    statute_class: StatuteClass

    def latest_pin(self) -> DatasetPin: ...

    def stream(self, pin: DatasetPin) -> Iterator[LegalStatuteObservation]: ...

    def hot_sample(self, pin: DatasetPin, n: int) -> list[LegalStatuteObservation]: ...


@runtime_checkable
class LegalCaseSensor(Protocol):
    """Read-only sensor over a ``law/cases/<court>/`` subdataset.

    Observation yield applies ``judicial_party_redactor`` per jurisdiction
    publication policy before constructing ``LegalCaseObservation``.
    """

    name: str
    license: str
    tier: Tier
    refresh_cadence_sec: int
    pii_filter: PiiFilterPolicy
    court_system: str

    def latest_pin(self) -> DatasetPin: ...

    def stream(self, pin: DatasetPin) -> Iterator[LegalCaseObservation]: ...

    def hot_sample(self, pin: DatasetPin, n: int) -> list[LegalCaseObservation]: ...


@runtime_checkable
class LegalTreatySensor(Protocol):
    """Read-only sensor over a ``law/treaties/<corpus>/`` subdataset."""

    name: str
    license: str
    tier: Tier
    refresh_cadence_sec: int
    pii_filter: PiiFilterPolicy
    treaty_corpus: str

    def latest_pin(self) -> DatasetPin: ...

    def stream(self, pin: DatasetPin) -> Iterator[LegalTreatyObservation]: ...

    def hot_sample(self, pin: DatasetPin, n: int) -> list[LegalTreatyObservation]: ...


@runtime_checkable
class LegalProcedureSensor(Protocol):
    """Read-only sensor over a ``law/procedures/<body>/`` subdataset."""

    name: str
    license: str
    tier: Tier
    refresh_cadence_sec: int
    pii_filter: PiiFilterPolicy
    procedural_body: str
    procedure_class: ProcedureClass

    def latest_pin(self) -> DatasetPin: ...

    def stream(self, pin: DatasetPin) -> Iterator[LegalProcedureObservation]: ...

    def hot_sample(self, pin: DatasetPin, n: int) -> list[LegalProcedureObservation]: ...


@runtime_checkable
class LegalTemplateSensor(Protocol):
    """Read-only sensor over a ``law/templates/<corpus>/`` subdataset.

    Template sensors carry an optional ``chigiri_consumer_cell_hint`` to
    aid chigiri cell wire-up (G6 in ADR-2605262800 — template corpus is
    structurally separate from raw-law corpus to avoid sub-licensing /
    UPL drift).
    """

    name: str
    license: str
    tier: Tier
    refresh_cadence_sec: int
    pii_filter: PiiFilterPolicy
    template_corpus: str
    template_class: TemplateClass

    def latest_pin(self) -> DatasetPin: ...

    def stream(self, pin: DatasetPin) -> Iterator[LegalTemplateObservation]: ...

    def hot_sample(self, pin: DatasetPin, n: int) -> list[LegalTemplateObservation]: ...


__all__ = [
    "LegalCaseObservation",
    "LegalCaseSensor",
    "LegalProcedureObservation",
    "LegalProcedureSensor",
    "LegalStatuteObservation",
    "LegalStatuteSensor",
    "LegalTemplateObservation",
    "LegalTemplateSensor",
    "LegalTreatyObservation",
    "LegalTreatySensor",
    "ProcedureClass",
    "StatuteClass",
    "TemplateClass",
]
