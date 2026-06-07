"""JudiciaryCorpusSensor — ``law/cases/<court-system>`` (judicial decisions).

Per ADR-2605262800 (legal corpus) + ADR-2605302345 §D4/§D5/§D6 (global
judiciary corpus). A passive ``LegalCaseSensor`` over a pre-pinned subdataset
of PUBLISHED judicial decisions. Mirrors ``UsUscSensor`` structure.

CONSTITUTIONAL discipline (ADR-2605302345):
  - Passive-only (G3): reads pre-captured NDJSON shards from the annex view;
    no live portal scraping, no commercial legal terminals (Westlaw /
    LexisNexis / Bloomberg Law are lint-deny per ADR-2605262800 §G7/G8).
  - Pseudonymization (D6): every row's parties pass through
    ``JudicialPartyRedactor`` before an observation is constructed. Rows from
    REJECT_IF_NON_ANONYMIZED court systems (jp-juvenile / jp-family /
    us-juvenile) that are NOT upstream-anonymized are DROPPED — this is the
    sealed/juvenile exclusion of §D4.
  - Judge-analytics prohibition (G19; France loi 2019-222 art.33): the
    ``LegalCaseObservation`` carries NO judge field and NO scoring/ranking
    surface. Judge identity, if ever ingested, lives in a separate factual
    ``judgeReference`` record — never as an analytics target. This sensor
    therefore cannot, by construction, emit a judge profile.

Hot-sample is deterministic on ``pin.revision`` per G9.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ..base import DatasetPin, PiiFilterPolicy, StaticPinResolver, Tier
from .base import LegalCaseObservation
from .judicial_party_redactor import JudicialPartyRedactor


@dataclass
class JudiciaryCorpusSensor:
    """Sensor over a ``law/cases/<court-system>/<rev>/`` subdataset NDJSON view.

    NDJSON row shape (one published decision per line):
      ``{citation, court, decision_date, parties: [...], holding,
         upstream_anonymized: bool}``
    """

    court_system: str
    jurisdiction_iso3: str
    name: str = ""
    annex_root: Path = Path("90-docs/baien/datasets")
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    redactor: JudicialPartyRedactor = field(default_factory=JudicialPartyRedactor)
    license: str = "court-published-public-record"
    tier: Tier = "A"
    refresh_cadence_sec: int = 7 * 24 * 3600  # weekly upstream cadence
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    ndjson_suffix: str = ".ndjson"
    _cached_pin: DatasetPin | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"law/cases/{self.court_system}"

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

    def stream(self, pin: DatasetPin) -> Iterator[LegalCaseObservation]:
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
                    obs = self._row_to_observation(pin, row)
                    if obs is not None:
                        yield obs

    def _row_to_observation(
        self, pin: DatasetPin, row: dict
    ) -> LegalCaseObservation | None:
        raw_parties = tuple(str(p) for p in row.get("parties", []))
        parties_after, dropped = self.redactor.apply(
            parties=raw_parties,
            jurisdiction_iso3=self.jurisdiction_iso3,
            court_system=self.court_system,
            upstream_anonymized=bool(row.get("upstream_anonymized", False)),
        )
        if dropped:
            # REJECT_IF_NON_ANONYMIZED (sealed / juvenile / family, §D4).
            return None
        return LegalCaseObservation(
            sensor=self.name,
            tier=self.tier,
            pin_revision=pin.revision,
            citation=str(row.get("citation", "")),
            court=str(row.get("court", "")),
            decision_date=str(row.get("decision_date", "")),
            parties_redacted=parties_after,
            holding_excerpt=str(row.get("holding", ""))[:2000],
            license_tag=self.license,
            internal_only=False,
        )

    def hot_sample(self, pin: DatasetPin, n: int) -> list[LegalCaseObservation]:
        # Reservoir sample; deterministic on (pin.revision, n) per G9.
        rng = random.Random(f"{pin.revision}:{n}")
        reservoir: list[LegalCaseObservation] = []
        for i, obs in enumerate(self.stream(pin)):
            if i < n:
                reservoir.append(obs)
            else:
                j = rng.randint(0, i)
                if j < n:
                    reservoir[j] = obs
        return reservoir


__all__ = ["JudiciaryCorpusSensor"]
