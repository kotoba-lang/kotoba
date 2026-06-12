"""TreatyCorpusSensor — ``law/treaties/<corpus>`` (international treaties).

Per ADR-2605262800 (legal corpus) §2 Source ladder + §3
``LegalTreatySensor`` Protocol. A passive ``LegalTreatySensor`` over a
pre-pinned subdataset of PUBLISHED international instruments. Mirrors
``UsUscSensor`` / ``JudiciaryCorpusSensor`` structure.

CONSTITUTIONAL discipline:
  - Passive-only (ADR-2605262400 §7): reads pre-captured NDJSON shards
    from the annex view; no live scraping at organism-tick time.
  - Tier-A by nature: treaty text is public (UN Treaty Collection /
    UNCITRAL / WIPO / Hague / ILO / Geneva Conventions are all public).
    No PII concern — treaty parties are sovereign states (ISO-3 codes),
    not natural persons, so no judicial-party redactor is applied.

The ``treaty_corpus`` selector maps to the canonical subdataset path
from the ADR §1 layout (``treaties/un-treaty-collection/`` etc.). Unknown
corpora fall back to ``law/treaties/<corpus>`` so a new W2+ corpus can be
pinned without a code change.

Hot-sample is deterministic on ``pin.revision`` per G9.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ..base import DatasetPin, PiiFilterPolicy, StaticPinResolver, Tier
from .base import LegalTreatyObservation

# Canonical corpus → subdataset path (ADR-2605262800 §1 `law/treaties/` layout).
_CORPUS_SUBDATASET: dict[str, str] = {
    "un-treaty": "un-treaty-collection",
    "uncitral": "uncitral-instruments",
    "wipo": "wipo-treaties",
    "hague": "hague-conference",
    "ilo": "ilo-conventions",
    "geneva": "geneva-conventions",
    "icrc": "geneva-conventions",
}


@dataclass
class TreatyCorpusSensor:
    """Sensor over a ``law/treaties/<corpus>/<rev>/`` subdataset NDJSON view.

    NDJSON row shape (one published instrument per line)::

        {treaty_id, title, party_states: ["USA", "JPN", ...],
         in_force_at, body}
    """

    treaty_corpus: str
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
            sub = _CORPUS_SUBDATASET.get(self.treaty_corpus, self.treaty_corpus)
            self.name = f"law/treaties/{sub}"

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

    def stream(self, pin: DatasetPin) -> Iterator[LegalTreatyObservation]:
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
    ) -> LegalTreatyObservation:
        party_states = tuple(str(p) for p in row.get("party_states", []))
        return LegalTreatyObservation(
            sensor=self.name,
            tier=self.tier,
            pin_revision=pin.revision,
            treaty_id=str(row.get("treaty_id", "")),
            title=str(row.get("title", "")),
            party_states_iso3=party_states,
            in_force_at=row.get("in_force_at"),
            body_excerpt=str(row.get("body", ""))[:2000],
            license_tag=self.license,
            internal_only=False,
        )

    def hot_sample(self, pin: DatasetPin, n: int) -> list[LegalTreatyObservation]:
        # Reservoir sample; deterministic on (pin.revision, n) per G9.
        rng = random.Random(f"{pin.revision}:{n}")
        reservoir: list[LegalTreatyObservation] = []
        for i, obs in enumerate(self.stream(pin)):
            if i < n:
                reservoir.append(obs)
            else:
                j = rng.randint(0, i)
                if j < n:
                    reservoir[j] = obs
        return reservoir


__all__ = ["TreatyCorpusSensor"]
