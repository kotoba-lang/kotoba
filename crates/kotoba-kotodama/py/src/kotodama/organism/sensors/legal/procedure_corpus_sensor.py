"""ProcedureCorpusSensor — ``law/procedures/<body>`` (legal procedures).

Per ADR-2605262800 (legal corpus) §1 ``procedures/`` layout + §3
``LegalProcedureSensor`` Protocol. A passive ``LegalProcedureSensor`` over
a pre-pinned subdataset of PUBLISHED procedural rules / guidance (CFR
procedural titles, US Federal Rules, GOV.UK procedure pages, 国税庁 通達,
法務省 登記 procedures, EU procedures portal, international arbitration
rules). Mirrors ``TreatyCorpusSensor`` / ``UsUscSensor`` structure.

CONSTITUTIONAL discipline:
  - Passive-only (ADR-2605262400 §7): reads pre-captured NDJSON shards
    from the annex view; no live portal scraping at organism-tick time.
  - Tier-A by nature: procedural rules + government how-to guidance are
    public (public domain / OGL v3.0 / public). No PII concern — procedure
    text describes steps, not natural persons.

This is the substrate chigiri (ADR-2605262700) procedural cells consume.
Per ADR-2605262700 UPL boundary, this sensor only INGESTS published
procedure text; it does not give legal advice.

Hot-sample is deterministic on ``pin.revision`` per G9.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ..base import DatasetPin, PiiFilterPolicy, StaticPinResolver, Tier
from .base import LegalProcedureObservation, ProcedureClass

# Convenience aliases → canonical subdataset slug (ADR §1 `law/procedures/`).
# The ADR's procedural_body names are already the path slugs; this map only
# smooths a couple of short aliases. Unknown bodies fall back to the literal.
_BODY_SUBDATASET: dict[str, str] = {
    "us-cfr": "us-cfr-procedures",
    "international-arbitration": "international-arbitration-rules",
}


@dataclass
class ProcedureCorpusSensor:
    """Sensor over a ``law/procedures/<body>/<rev>/`` subdataset NDJSON view.

    NDJSON row shape (one published procedure per line)::

        {procedure_id, title, steps, in_force_at?}
    """

    procedural_body: str
    jurisdiction_iso3: str
    procedure_class: ProcedureClass = "administrative"
    name: str = ""
    annex_root: Path = Path("90-docs/baien/datasets")
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "public-domain"
    tier: Tier = "A"
    refresh_cadence_sec: int = 7 * 24 * 3600  # weekly upstream cadence
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    ndjson_suffix: str = ".ndjson"
    _cached_pin: DatasetPin | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.name:
            sub = _BODY_SUBDATASET.get(self.procedural_body, self.procedural_body)
            self.name = f"law/procedures/{sub}"

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
            (p for p in subdataset_dir.iterdir() if p.is_dir()), reverse=True
        )
        if not candidates:
            raise FileNotFoundError(f"no snapshot directory under {subdataset_dir}")
        ndjson_files = sorted(candidates[0].glob(f"*{self.ndjson_suffix}"))
        if not ndjson_files:
            raise FileNotFoundError(
                f"no '*{self.ndjson_suffix}' under {candidates[0]}"
            )
        return ndjson_files

    def stream(self, pin: DatasetPin) -> Iterator[LegalProcedureObservation]:
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
                    yield self._row_to_observation(pin, row)

    def _row_to_observation(
        self, pin: DatasetPin, row: dict
    ) -> LegalProcedureObservation:
        return LegalProcedureObservation(
            sensor=self.name,
            tier=self.tier,
            pin_revision=pin.revision,
            procedure_id=str(row.get("procedure_id", "")),
            title=str(row.get("title", "")),
            steps_excerpt=str(row.get("steps", ""))[:2000],
            jurisdiction_iso3=self.jurisdiction_iso3,
            procedure_class=self.procedure_class,
            license_tag=self.license,
            internal_only=False,
        )

    def hot_sample(self, pin: DatasetPin, n: int) -> list[LegalProcedureObservation]:
        # Reservoir sample; deterministic on (pin.revision, n) per G9.
        rng = random.Random(f"{pin.revision}:{n}")
        reservoir: list[LegalProcedureObservation] = []
        for i, obs in enumerate(self.stream(pin)):
            if i < n:
                reservoir.append(obs)
            else:
                j = rng.randint(0, i)
                if j < n:
                    reservoir[j] = obs
        return reservoir


__all__ = ["ProcedureCorpusSensor"]
