"""Rapid7SonarSensor — Tier-C DatasetSensor over dns/rapid7-sonar-fdns/*.

Per ADR-2605262400 §3 + §4.2 + W3. Reads NDJSON shards from a
Rapid7 Sonar FDNS archive (one row per DNS observation) and yields
PII-redacted SensorObservations.

Tier C. internal_only=True attaches automatically via make_observation
helper (G4). G13 fleet-internal-only artifact enforcement is the
downstream assembler / PostSink path's responsibility.

Each row is JSON-shaped:

    {"timestamp": "1716708823",
     "name": "example.com",
     "type": "txt",
     "value": "v=spf1 mx ~all contact: ops@example.com"}

The sensor:
  1. parses the JSON;
  2. runs the configured PII filter over string-typed fields (`value`
     is the highest-risk column);
  3. constructs the observation via ``make_observation`` so tier="C"
     drives ``internal_only=True``.

Hot-sample is reservoir-sampled with pin.revision seed (G9).
"""

from __future__ import annotations

import gzip
import io
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
from .pii_filter import redact_payload


def _open_compressed(path: Path) -> io.IOBase:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


@dataclass
class Rapid7SonarSensor:
    """Tier-C sensor over Rapid7 Sonar FDNS shards."""

    name: str = "dns/rapid7-sonar-fdns"
    annex_root: Path = field(default_factory=lambda: Path("."))
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "rapid7-research-use"
    tier: Tier = "C"
    refresh_cadence_sec: int = 30 * 24 * 3600  # monthly archives
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    # Fields to run the PII redactor over. Sonar's "value" column is
    # the highest-risk; "name" is rarely PII but pi-redacted for
    # defense-in-depth on hostname-style operator addresses.
    pii_fields: tuple[str, ...] = ("value", "name")
    _cached_pin: DatasetPin | None = field(default=None, init=False, repr=False)

    def latest_pin(self) -> DatasetPin:
        pin = self.pin_resolver.latest(self.name)
        self._cached_pin = pin
        return pin

    def _resolve_shard_path(self, pin: DatasetPin) -> Path:
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
        for pattern in ("*.json.gz", "*.ndjson.gz", "*.json", "*.ndjson"):
            shards = list(snapshot_dir.glob(pattern))
            if shards:
                return shards[0]
        raise FileNotFoundError(
            f"no Sonar shard (*.json[.gz] / *.ndjson[.gz]) in {snapshot_dir}"
        )

    def stream(self, pin: DatasetPin) -> Iterator[SensorObservation]:
        shard_path = self._resolve_shard_path(pin)
        with _open_compressed(shard_path) as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    raw = json.loads(s)
                except json.JSONDecodeError:
                    continue
                payload, _stats = redact_payload(
                    raw, policy=self.pii_filter, fields=self.pii_fields,
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


__all__ = ["Rapid7SonarSensor"]
