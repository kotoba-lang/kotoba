"""junkan.sink — EAVT ingest sink: sensor Observation → kotoba datoms.

ADR-2605262130 + ADR-2605312345. The passive sensors (legal / gov / corp
/ public-data) produce frozen Observation dataclasses; ``junkan.edn``
turns one dataclass into ``(e, a, v)`` facts + EDN. This module assembles
those primitives into a reusable INGEST component:

  observations ──EavtSink.ingest_all──▶ DatomStore (EAVT, append-only)
                                       └─▶ store.to_tx_edn() → kotoba-kqe

Entity identity is the crux of EAVT ingestion: the same real-world thing
must map to the same ``e`` across ticks so its history accretes (and a
re-pin of the same treaty updates, not duplicates, it). ``EavtSink``
derives ``e = "<ns>:<natural-key>"`` from a per-family key field (treaty_id
/ citation / procedure_id / …), so two ingests of the same statute share
one entity and time-travel works.

Pure + offline (no network, no inference) — consistent with the junkan
analysis-only discipline (G4). The DatomStore is the reference EAVT model;
kotoba-kqe is the canonical production binding (Charter Rider §2(e)+§2(c):
proprietary Datomic NOT used; EDN is the open wire format).
"""

from __future__ import annotations

import dataclasses
import enum
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .datom import DatomStore
from .edn import datoms_from_dataclass, ns_for, store_to_tx_edn

__all__ = [
    "EavtSink",
    "IngestReceipt",
    "DroppedObservation",
    "SinkClass",
    "DEFAULT_KEY_FIELDS",
]


class SinkClass(enum.Enum):
    """Where the ingested datoms ultimately flow.

    Mirrors ``sensors.tier_gate.SinkClassification`` (kept local so junkan
    stays self-contained / fleet-independent). The tier-C drop policy is the
    same: a ``internal_only=True`` observation MUST NOT reach an
    external-facing destination.
    """

    EXTERNAL_FACING = "external-facing"  # kotoba state that feeds public projections
    INTERNAL_ONLY = "internal-only"      # fleet-internal canonical store (default)


@dataclass(frozen=True)
class DroppedObservation:
    """Record of a tier-C observation dropped at an external-facing sink.

    Maps 1:1 to ``kaizen.LeakAttempt`` (sensor / tier / detail) so a cell
    wiring junkan ingest into the R9 backstop can forward these without
    coupling junkan to the kaizen package.
    """

    sensor: str
    tier: str
    detail: str

# Natural-key field per Observation family (the field whose value is stable
# across re-pins). Callers may extend / override via ``EavtSink(key_fields=…)``
# or per-call ``key_field=``.
DEFAULT_KEY_FIELDS: dict[str, str] = {
    "LegalStatuteObservation": "citation",
    "LegalCaseObservation": "citation",
    "LegalTreatyObservation": "treaty_id",
    "LegalProcedureObservation": "procedure_id",
    "LegalTemplateObservation": "template_id",
}


@dataclass(frozen=True)
class IngestReceipt:
    """Outcome of ingesting one observation: which entity, which tx, how many facts."""

    entity_id: str
    tx: int
    n_facts: int


class EavtSink:
    """Transacts sensor observations into a DatomStore as EAVT datoms.

    Stateful only in the underlying append-only store (G9). Re-ingesting the
    same entity appends new facts; ``store.entity(e)`` returns the latest
    value of each attribute, and ``store.history(e, a)`` the full trajectory.
    """

    def __init__(
        self,
        store: DatomStore | None = None,
        *,
        key_fields: dict[str, str] | None = None,
        classification: SinkClass = SinkClass.INTERNAL_ONLY,
        content_scanner: Callable[[str], bool] | None = None,
    ) -> None:
        self.store = store if store is not None else DatomStore()
        self.key_fields = {**DEFAULT_KEY_FIELDS, **(key_fields or {})}
        self.classification = classification
        # G1: optional Charter Rider §2 content gate. Injected (not imported)
        # so junkan stays fleet-independent; a cell passes
        # sensors.charter_rider.is_clean. Returns True if the text is clean.
        self.content_scanner = content_scanner
        self.dropped: list[DroppedObservation] = []

    def _should_drop(self, obs: Any) -> bool:
        """True if ``obs`` is internal-only and this sink is external-facing."""
        return (
            self.classification is SinkClass.EXTERNAL_FACING
            and bool(getattr(obs, "internal_only", False))
        )

    @staticmethod
    def _observation_text(obs: Any) -> str:
        """Concatenate the string-valued fields of an observation for scanning."""
        if not dataclasses.is_dataclass(obs) or isinstance(obs, type):
            return str(obs)
        parts = [
            v for f in dataclasses.fields(obs)
            if isinstance((v := getattr(obs, f.name)), str)
        ]
        return "\n".join(parts)

    def pop_drops(self) -> list[DroppedObservation]:
        """Return + clear the tier-C observations dropped since the last call."""
        out = self.dropped
        self.dropped = []
        return out

    def entity_id_for(self, obs: Any, key_field: str | None = None) -> str:
        """Derive ``"<ns>:<natural-key>"`` for an observation.

        ``key_field`` overrides the per-family default. Raises ``KeyError`` if
        no key field is known for the observation type.
        """
        kf = key_field or self.key_fields.get(type(obs).__name__)
        if kf is None:
            raise KeyError(
                f"no natural-key field registered for {type(obs).__name__}; "
                f"pass key_field= or extend EavtSink(key_fields=…)"
            )
        key = getattr(obs, kf)
        return f"{ns_for(obs)}:{key}"

    def ingest(
        self,
        obs: Any,
        *,
        entity_id: str | None = None,
        key_field: str | None = None,
        skip: Iterable[str] = (),
    ) -> IngestReceipt | None:
        """Transact one observation. Returns an :class:`IngestReceipt`, or
        ``None`` if the observation was dropped by the tier-C gate (an
        ``internal_only`` observation at an ``EXTERNAL_FACING`` sink). Dropped
        observations are recorded for :meth:`pop_drops` (R9 backstop).
        """
        if self._should_drop(obs):
            self.dropped.append(
                DroppedObservation(
                    sensor=str(getattr(obs, "sensor", "?")),
                    tier=str(getattr(obs, "tier", "?")),
                    detail="dropped internal_only observation at external-facing kotoba sink",
                )
            )
            return None
        if self.content_scanner is not None and not self.content_scanner(
            self._observation_text(obs)
        ):
            # G1: Charter Rider §2 content gate — fail-closed.
            self.dropped.append(
                DroppedObservation(
                    sensor=str(getattr(obs, "sensor", "?")),
                    tier=str(getattr(obs, "tier", "?")),
                    detail="dropped: Charter Rider §2 content scan failed (G1)",
                )
            )
            return None
        eid = entity_id if entity_id is not None else self.entity_id_for(obs, key_field)
        facts = datoms_from_dataclass(obs, entity_id=eid, skip=skip)
        tx = self.store.transact(facts)
        return IngestReceipt(entity_id=eid, tx=tx, n_facts=len(facts))

    def ingest_all(
        self,
        observations: Iterable[Any],
        *,
        key_field: str | None = None,
        skip: Iterable[str] = (),
    ) -> list[IngestReceipt]:
        """Transact many observations (one tx each). Tier-C-dropped observations
        are omitted from the returned receipts (and recorded for :meth:`pop_drops`).
        """
        out: list[IngestReceipt] = []
        for o in observations:
            r = self.ingest(o, key_field=key_field, skip=skip)
            if r is not None:
                out.append(r)
        return out

    def to_tx_edn(self) -> str:
        """Serialize the whole store as kotoba-ingestable EDN tx-data."""
        return store_to_tx_edn(self.store)

    def __len__(self) -> int:
        return len(self.store)
