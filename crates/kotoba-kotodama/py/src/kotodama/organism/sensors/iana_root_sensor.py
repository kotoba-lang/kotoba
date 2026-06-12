"""IanaRootSensor — DatasetSensor over a `netreg/iana-root` subdataset.

Per ADR-2605262400 §3 + §4.2 + W2. Reads the NDJSON sidecar produced
by ``e7m_dataset.fetchers.iana_root.fetch`` (one row per delegated TLD
with ``ns``, ``ds``, ``glue`` blocks) and yields one
``SensorObservation`` per TLD.

Hot-sample uses pin.revision-seeded reservoir sampling for G9
determinism.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from .base import (
    DatasetPin,
    PiiFilterPolicy,
    SensorObservation,
    StaticPinResolver,
    Tier,
    make_observation,
)


@dataclass
class IanaRootSensor:
    """Sensor that reads the per-TLD NDJSON sidecar of an IANA root snapshot."""

    name: str = "netreg/iana-root"
    annex_root: Path = field(default_factory=lambda: Path("."))
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "public-domain"
    tier: Tier = "A"
    refresh_cadence_sec: int = 24 * 3600  # multiple times daily upstream;
                                          # daily floor avoids over-polling
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    ndjson_filename: str = "root.zone.ndjson"
    _cached_pin: DatasetPin | None = field(default=None, init=False, repr=False)

    def latest_pin(self) -> DatasetPin:
        pin = self.pin_resolver.latest(self.name)
        self._cached_pin = pin
        return pin

    def _resolve_ndjson_path(self, pin: DatasetPin) -> Path:
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
            raise FileNotFoundError(
                f"no snapshot directory under {subdataset_dir}"
            )
        snapshot_dir = candidates[0]
        ndjson_path = snapshot_dir / self.ndjson_filename
        if not ndjson_path.exists():
            raise FileNotFoundError(
                f"no {self.ndjson_filename} in {snapshot_dir}"
            )
        return ndjson_path

    def stream(self, pin: DatasetPin) -> Iterator[SensorObservation]:
        ndjson_path = self._resolve_ndjson_path(pin)
        with ndjson_path.open("r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    row = json.loads(s)
                except json.JSONDecodeError:
                    continue
                yield make_observation(
                    sensor=self.name,
                    tier=self.tier,
                    pin=pin,
                    payload={
                        "tld": row.get("tld"),
                        "ns": row.get("ns", []),
                        "ds": row.get("ds", []),
                        "glue": row.get("glue", []),
                    },
                )

    def hot_sample(self, pin: DatasetPin, n: int) -> list[SensorObservation]:
        rng = random.Random(f"{pin.revision}:{n}")
        reservoir: list[SensorObservation] = []
        for i, obs in enumerate(self.stream(pin)):
            if i < n:
                reservoir.append(obs)
            else:
                j = rng.randint(0, i)
                if j < n:
                    reservoir[j] = obs
        return reservoir


__all__ = ["IanaRootSensor"]
