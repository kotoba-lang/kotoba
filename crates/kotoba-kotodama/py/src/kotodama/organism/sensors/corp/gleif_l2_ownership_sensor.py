# Apache-2.0 + etzhayyim Charter Compliance Rider v2.0 (see /CHARTER-RIDER.md)
"""GleifL2OwnershipSensor — first concrete ``CorpOwnershipSensor``.

Per ADR-2605263800 §3 (CorpOwnershipSensor family). This is the W1
ownership-edge anchor: the GLEIF **Level-2 relationship-record (RR)**
view, ``corp/ownership/gleif-l2/``.

GLEIF (Global Legal Entity Identifier Foundation) publishes its
Relationship Record golden-copy as Concatenated Data Files under
**CC0 1.0** (public-domain dedication) — Tier-A globally. Each RR row
asserts a **publicly disclosed** accounting-consolidation relationship
between two LEI-bearing entities. This is the canonical, non-covert,
public-disclosure source for the corporate ownership / control graph
that danjo (ADR-2605301600) + kanae (ADR-2605302300) cross-reference.

Relationship-type mapping (GLEIF RR ``relationshipType`` →
``OwnershipKind`` from ``base.py``):

  - ``IS_DIRECTLY_CONSOLIDATED_BY``    → ``parent-subsidiary``
    (the subject is the consolidated child; the owner is its direct
    accounting parent)
  - ``IS_ULTIMATELY_CONSOLIDATED_BY``  → ``control-relationship``
    (the owner is the ultimate accounting parent — GLEIF L2's control
    record; this is the edge a UBO chain is reconstructed from)

Any other ``relationshipType`` (e.g. ``IS_FUND-MANAGED_BY``,
``IS_SUBFUND_OF``) is **skipped** per G7 schema discipline in W1 — W2+
extends the map with explicit Lexicon registration rather than guessing.

**Direction convention (CRITICAL).** In a GLEIF RR, the relationship
reads ``startNode <relationshipType> endNode``. For the consolidation
types above, ``startNode`` is the *child* (consolidated entity) and
``endNode`` is the *parent* (consolidator). This sensor therefore sets
``subject_* = startNode`` and ``owner_* = endNode`` so that an
``owner → subject`` reading is "parent owns/controls subject".

**Non-adjudicating.** This sensor emits observed edges only. It never
asserts that an undisclosed owner was "uncovered"; it only surfaces
relationships the registrant itself reported to GLEIF (danjo/kanae are
the censor's eye, no sword).

**Percentage.** GLEIF L2 RR records are accounting-consolidation
assertions and do not carry an ownership percentage. ``pct_held`` is
therefore ``None`` unless the upstream fetcher joined a ``pctHeld``
field from a percentage-bearing source; ``parent-subsidiary`` /
``control-relationship`` edges normally have ``pct_held=None`` per the
``base.py`` field contract.

Hot-sample is deterministic on ``(pin.revision, n)`` per G7
(reservoir sampling seeded by pin revision).

**Passive-only invariant.** NEVER hits a GLEIF live API endpoint at
organism-tick time — only reads the pre-fetched IPFS-pinned subdataset
NDJSON view emitted by the (W1 fetcher) ``gleif_rr.py``. Vendor
commercial-terminal imports (Bloomberg Terminal / S&P Capital IQ /
Refinitiv Eikon / FactSet / Moody's Orbis / D&B Hoovers / Pitchbook /
Crunchbase Pro) are CONSTITUTIONALLY PROHIBITED per Charter Rider
§2(e) + §2(c). Derived-artifact inference is Murakumo-only
(ADR-2605215000).
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ..base import DatasetPin, PiiFilterPolicy, StaticPinResolver, Tier
from .base import CorpOwnershipObservation, OwnershipKind


# GLEIF RR relationshipType → canonical OwnershipKind. Intentionally
# narrow in W1 — only the two accounting-consolidation edges that form
# the control graph. Unknown types are skipped per G7 (no guessing).
_RELATIONSHIP_KIND_MAP: dict[str, OwnershipKind] = {
    "IS_DIRECTLY_CONSOLIDATED_BY": "parent-subsidiary",
    "IS_ULTIMATELY_CONSOLIDATED_BY": "control-relationship",
}


def _canonical_ownership_kind(relationship_type: str) -> OwnershipKind | None:
    """Map a GLEIF RR relationshipType to a canonical OwnershipKind.

    Returns ``None`` for unmapped types so ``stream`` skips the row per
    G7 schema discipline rather than emitting an out-of-enum kind.
    """
    return _RELATIONSHIP_KIND_MAP.get(relationship_type.strip().upper())


@dataclass
class GleifL2OwnershipSensor:
    """Sensor over a ``corp/ownership/gleif-l2/<rev>/`` subdataset NDJSON view.

    Expected NDJSON row shape (minimum):
      - subjectLei         (20-char LEI of the consolidated child; required)
      - ownerLei           (20-char LEI of the consolidating parent; required)
      - relationshipType   (GLEIF RR type, e.g. "IS_DIRECTLY_CONSOLIDATED_BY";
                            required — unmapped types are skipped per G7)
      - relationshipStatus (optional "ACTIVE"/"INACTIVE"; rows whose
                            status is present and not ACTIVE are skipped
                            so only currently-true edges are surfaced)
      - subjectJurisdictionIso3 (optional incorporation jurisdiction)
      - ownerJurisdictionIso3   (optional incorporation jurisdiction)
      - pctHeld            (optional float 0..100; normally absent for
                            GLEIF consolidation edges → pct_held=None)
      - asOf               (optional ISO-8601 last-update date)

    Both ``subjectLei`` and ``ownerLei`` MUST be 20 chars (G7); rows
    failing that are skipped without halting the stream.
    """

    name: str = "corp/ownership/gleif-l2"
    annex_root: Path = Path("90-docs/baien/datasets")
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "CC0-1.0"
    tier: Tier = "A"
    source_id: str = "gleif-l2"
    # GLEIF RR golden-copy is published daily.
    refresh_cadence_sec: int = 24 * 3600
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    # Restrict to a subset of OwnershipKind at construction time
    # (e.g. only control-relationship). Empty tuple = no restriction.
    ownership_kind_filter: tuple[OwnershipKind, ...] = ()
    ndjson_suffix: str = ".ndjson"
    _cached_pin: DatasetPin | None = field(default=None, init=False, repr=False)

    def latest_pin(self) -> DatasetPin:
        pin = self.pin_resolver.latest(self.name)
        self._cached_pin = pin
        return pin

    def _resolve_ndjson_paths(self, pin: DatasetPin) -> list[Path]:
        subdataset_dir = self.annex_root / self.name
        if not subdataset_dir.exists():
            raise FileNotFoundError(
                f"subdataset '{self.name}' not present at {subdataset_dir}"
            )
        candidates = sorted(
            (p for p in subdataset_dir.iterdir() if p.is_dir()),
            reverse=True,
        )
        if not candidates:
            raise FileNotFoundError(f"no snapshot directory under {subdataset_dir}")
        snapshot_dir = candidates[0]
        ndjson_files = sorted(snapshot_dir.glob(f"*{self.ndjson_suffix}"))
        if not ndjson_files:
            raise FileNotFoundError(
                f"no '*{self.ndjson_suffix}' under {snapshot_dir}"
            )
        return ndjson_files

    @staticmethod
    def _lei_or_none(raw: object) -> str | None:
        s = str(raw).strip() if isinstance(raw, str) else ""
        return s if len(s) == 20 else None

    @staticmethod
    def _pct_or_none(raw: object) -> float | None:
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            v = float(raw)
            # G7: ownership percentage is bounded [0, 100]; drop nonsense.
            return v if 0.0 <= v <= 100.0 else None
        return None

    def stream(self, pin: DatasetPin) -> Iterator[CorpOwnershipObservation]:
        sensor_name = self.name
        filter_set = (
            set(self.ownership_kind_filter) if self.ownership_kind_filter else None
        )
        for path in self._resolve_ndjson_paths(pin):
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s:
                        continue
                    try:
                        row = json.loads(s)
                    except json.JSONDecodeError:
                        continue

                    subject_lei = self._lei_or_none(row.get("subjectLei"))
                    owner_lei = self._lei_or_none(row.get("ownerLei"))
                    if subject_lei is None or owner_lei is None:
                        # G7 — both endpoints must be valid 20-char LEIs.
                        continue
                    if subject_lei == owner_lei:
                        # G7 — a self-loop is not a meaningful control edge.
                        continue

                    rel_type = str(row.get("relationshipType", "")).strip()
                    ownership_kind = _canonical_ownership_kind(rel_type)
                    if ownership_kind is None:
                        # G7 — unmapped relationship type: skip without halt.
                        continue
                    if filter_set is not None and ownership_kind not in filter_set:
                        continue

                    # Only surface currently-true edges. If the upstream
                    # row carries a status and it is not ACTIVE, skip it;
                    # if the field is absent we treat the edge as active
                    # (the fetcher pre-filters golden-copy to ACTIVE).
                    status_raw = row.get("relationshipStatus")
                    if isinstance(status_raw, str) and status_raw.strip():
                        if status_raw.strip().upper() != "ACTIVE":
                            continue

                    subj_juris = str(
                        row.get("subjectJurisdictionIso3", "")
                    ).upper()[:3]
                    owner_juris_raw = row.get("ownerJurisdictionIso3")
                    owner_juris = (
                        str(owner_juris_raw).upper()[:3]
                        if isinstance(owner_juris_raw, str) and owner_juris_raw.strip()
                        else None
                    )
                    as_of_raw = row.get("asOf")
                    as_of = (
                        str(as_of_raw).strip()
                        if isinstance(as_of_raw, str) and as_of_raw.strip()
                        else None
                    )

                    yield CorpOwnershipObservation(
                        sensor=sensor_name,
                        tier=self.tier,
                        pin_revision=pin.revision,
                        subject_lei=subject_lei,
                        subject_local_id=None,
                        subject_jurisdiction_iso3=subj_juris,
                        owner_lei=owner_lei,
                        owner_local_id=None,
                        owner_jurisdiction_iso3=owner_juris,
                        ownership_kind=ownership_kind,
                        pct_held=self._pct_or_none(row.get("pctHeld")),
                        as_of=as_of,
                        license_tag=self.license,
                        internal_only=False,
                    )

    def hot_sample(self, pin: DatasetPin, n: int) -> list[CorpOwnershipObservation]:
        """Reservoir sample; deterministic on (pin.revision, n) per G7."""
        rng = random.Random(f"{pin.revision}:{n}")
        reservoir: list[CorpOwnershipObservation] = []
        for i, obs in enumerate(self.stream(pin)):
            if i < n:
                reservoir.append(obs)
            else:
                j = rng.randint(0, i)
                if j < n:
                    reservoir[j] = obs
        return reservoir


__all__ = ["GleifL2OwnershipSensor"]
