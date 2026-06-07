"""RirDelegatedSensor — DatasetSensor over a `netreg/rir-delegated/<rir>` subdataset.

Per ADR-2605262400 §3 + §4.2. Reads the NDJSON sidecar emitted by
`e7m_dataset.fetchers.rir_delegated.fetch` and yields one
SensorObservation per resource record (IPv4 prefix / IPv6 prefix / ASN).

Hot-sample is deterministic on `pin.revision`: we seed Python's `random`
with a hash of pin.revision and take a stable subset.
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
class RirDelegatedSensor:
    """Sensor that reads a RIR delegated-stats NDJSON sidecar."""

    name: str
    annex_root: Path
    pin_resolver: StaticPinResolver
    license: str = "public-domain-defacto"
    tier: Tier = "A"
    refresh_cadence_sec: int = 24 * 3600  # daily upstream cadence
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    ndjson_suffix: str = "-extended-latest.ndjson"
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
        ndjson_files = list(snapshot_dir.glob(f"*{self.ndjson_suffix}"))
        if not ndjson_files:
            raise FileNotFoundError(
                f"no '*{self.ndjson_suffix}' in {snapshot_dir}"
            )
        return ndjson_files[0]

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
                        "registry": row.get("registry"),
                        "cc": row.get("cc"),
                        "type": row.get("type"),
                        "start": row.get("start"),
                        "value": row.get("value"),
                        "date": row.get("date"),
                        "status": row.get("status"),
                        "opaqueId": row.get("opaqueId"),
                    },
                )

    def hot_sample(self, pin: DatasetPin, n: int) -> list[SensorObservation]:
        # Reservoir sample over the NDJSON. Deterministic on
        # (pin.revision, n) so that two ticks against the same pin yield
        # the same sample — required by G9.
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


__all__ = ["RirDelegatedSensor"]
