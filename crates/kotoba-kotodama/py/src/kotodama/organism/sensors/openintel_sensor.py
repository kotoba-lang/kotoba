"""OpenIntelSensor — Tier-C DatasetSensor over dns/openintel-*.

Per ADR-2605262400 §3 + §4.2 + W3. Reads an OpenINTEL Parquet shard
(one row per (zone, name, type, response_record) DNS observation) via
``pyarrow`` and yields PII-redacted SensorObservations.

Tier C. internal_only=True attaches automatically via make_observation
(G4).

Hot-sample uses pin.revision-seeded reservoir sampling. pyarrow is
lazy-imported so the sensor module loads even without pyarrow
installed (operators install at deploy time).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .base import (
    DatasetPin,
    PiiFilterPolicy,
    SensorObservation,
    StaticPinResolver,
    Tier,
    make_observation,
)
from .pii_filter import redact_payload


def _iter_parquet_rows(path: Path) -> Iterator[dict[str, Any]]:
    """Read a Parquet shard row by row."""
    try:
        import pyarrow.parquet as pq  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "OpenIntelSensor requires the 'pyarrow' package "
            "(pip install pyarrow)."
        ) from exc
    pf = pq.ParquetFile(str(path))
    for batch in pf.iter_batches():
        rows = batch.to_pylist()
        for row in rows:
            yield row


@dataclass
class OpenIntelSensor:
    """Tier-C sensor over an OpenINTEL Parquet shard."""

    name: str = "dns/openintel-tranco1m"
    annex_root: Path = field(default_factory=lambda: Path("."))
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "CC-BY-NC-4.0"
    tier: Tier = "C"
    refresh_cadence_sec: int = 24 * 3600  # daily upstream cadence
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    pii_fields: tuple[str, ...] = (
        "response_rdata", "response_rname", "soa_rname",
    )
    _cached_pin: DatasetPin | None = field(default=None, init=False, repr=False)

    def latest_pin(self) -> DatasetPin:
        pin = self.pin_resolver.latest(self.name)
        self._cached_pin = pin
        return pin

    def _resolve_parquet_path(self, pin: DatasetPin) -> Path:
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
        parquet_files = list(snapshot_dir.glob("*.parquet"))
        if not parquet_files:
            raise FileNotFoundError(f"no *.parquet in {snapshot_dir}")
        return parquet_files[0]

    def stream(self, pin: DatasetPin) -> Iterator[SensorObservation]:
        path = self._resolve_parquet_path(pin)
        for row in _iter_parquet_rows(path):
            payload, _stats = redact_payload(
                row, policy=self.pii_filter, fields=self.pii_fields,
            )
            yield make_observation(
                sensor=self.name,
                tier=self.tier,
                pin=pin,
                payload=payload,
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


# Test seam.
def _set_row_iter(fn) -> None:  # type: ignore[no-untyped-def]
    global _iter_parquet_rows
    _iter_parquet_rows = fn


__all__ = ["OpenIntelSensor", "_set_row_iter"]
