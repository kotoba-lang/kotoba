"""LeiSensor — Wave-1 anchor: ``corp/lei/gleif/lei-l1`` (GLEIF LEI L1).

Per ADR-2605263800. GLEIF (Global Legal Entity Identifier Foundation)
publishes the LEI canonical entity-reference (Level-1) + relationship
records (Level-2 RR + RepEx) as Concatenated Data Files under
CC0 1.0 — public-domain dedication. ~2.5M LEIs globally.

This sensor reads the L1 NDJSON view emitted by the (TODO W1)
``gleif_lei.py`` fetcher. One row per LEI = one ``LeiObservation``.
LEI is the canonical cross-jurisdiction key — other corp sensors
(``CorpRegistrySensor`` / ``CorpDisclosureSensor`` / ``CorpOwnershipSensor``
/ ``CorpFilingEventSensor``) set their ``entity_lei`` field by
resolving local registry IDs against this sensor's pin.

Hot-sample is deterministic on ``(pin.revision, n)`` per G7 of
ADR-2605263800 (reservoir sampling seeded by pin revision).

Passive-only invariant: NEVER hits a per-LEI live API endpoint at
organism-tick time. Only reads pre-fetched IPFS-pinned subdataset.
Vendor commercial-terminal imports (Bloomberg Terminal / Refinitiv /
FactSet / Moody's Orbis / D&B Hoovers / Pitchbook / Crunchbase Pro)
are CONSTITUTIONALLY PROHIBITED per Charter Rider §2(e)+§2(c).
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from ..base import DatasetPin, PiiFilterPolicy, StaticPinResolver, Tier
from .base import LeiObservation


@dataclass
class GleifLeiSensor:
    """Sensor over a ``corp/lei/gleif/lei-l1/<rev>/`` subdataset NDJSON view.

    Each NDJSON row carries at minimum:
      - lei              (20-char GLEIF LEI; required)
      - legalName        (entity legal name; required)
      - jurisdictionIso3 (incorporation jurisdiction; required)
      - registrationStatus (GLEIF status enum; required)
      - parentLei              (optional; from L2-RR fanout if joined upstream)
      - ultimateParentLei      (optional; from L2-RR fanout if joined upstream)

    The fetcher (gleif_lei.py W1) is responsible for joining L1 + L2-RR
    + L2-RepEx into a single NDJSON if cross-edge fields are desired.
    """

    name: str = "corp/lei/gleif/lei-l1"
    annex_root: Path = Path("90-docs/baien/datasets")
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "CC0-1.0"
    tier: Tier = "A"
    refresh_cadence_sec: int = 24 * 3600  # daily upstream cadence (GLEIF GoldenCopy daily)
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    ndjson_suffix: str = ".ndjson"
    _cached_pin: DatasetPin | None = field(default=None, init=False, repr=False)

    def latest_pin(self) -> DatasetPin:
        pin = self.pin_resolver.latest(self.name)
        self._cached_pin = pin
        return pin

    def _resolve_ndjson_paths(self, pin: DatasetPin) -> list[Path]:
        """Resolve NDJSON file list for the latest snapshot.

        Layout: ``<annex_root>/<name-with-slashes>/<latest-snapshot>/*.ndjson``.
        """
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

    def stream(self, pin: DatasetPin) -> Iterator[LeiObservation]:
        sensor_name = self.name
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
                    lei = str(row.get("lei", "")).strip()
                    if len(lei) != 20:
                        # G7 (schema discipline): GLEIF LEI MUST be 20 chars;
                        # skip malformed rows without halting the stream.
                        continue
                    yield LeiObservation(
                        sensor=sensor_name,
                        tier=self.tier,
                        pin_revision=pin.revision,
                        entity_lei=lei,
                        legal_name=str(row.get("legalName", ""))[:512],
                        jurisdiction_iso3=str(row.get("jurisdictionIso3", "")).upper()[:3],
                        registration_status=str(row.get("registrationStatus", "")),
                        parent_lei=(row.get("parentLei") or None),
                        ultimate_parent_lei=(row.get("ultimateParentLei") or None),
                        license_tag=self.license,
                        internal_only=False,
                    )

    def hot_sample(self, pin: DatasetPin, n: int) -> list[LeiObservation]:
        """Reservoir sample; deterministic on (pin.revision, n) per G7."""
        rng = random.Random(f"{pin.revision}:{n}")
        reservoir: list[LeiObservation] = []
        for i, obs in enumerate(self.stream(pin)):
            if i < n:
                reservoir.append(obs)
            else:
                j = rng.randint(0, i)
                if j < n:
                    reservoir[j] = obs
        return reservoir


__all__ = ["GleifLeiSensor"]
