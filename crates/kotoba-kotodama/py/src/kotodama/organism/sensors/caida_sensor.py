"""CaidaSensor — Tier-C DatasetSensor over routing/caida-* subdatasets.

Per ADR-2605262400 §3 + §4.2 + W3. Reads CAIDA AS-relationship /
prefix2as / AS-rank text dumps (one record per line, bz2-compressed)
and yields SensorObservations.

Tier C. internal_only=True attaches automatically via make_observation.

CAIDA datasets are pure-inference (no per-user PII); the sensor still
runs the PII filter for defense-in-depth on any free-text fields the
upstream schema might add later.

Schema by dataset:

  - **as-relationship**: `<ASa>|<ASb>|<rel>|<source>` where rel ∈ {-1, 0, 1}
  - **prefix2as**: `<prefix>\t<plen>\t<origin-asn>` (TSV)
  - **as-rank**: `<rank>\t<asn>\t<asname>\t<degree>\t<cc>\t...` (TSV with header)

Hot-sample uses pin.revision-seeded reservoir sampling.
"""

from __future__ import annotations

import bz2
import io
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


def _open_compressed(path: Path) -> io.IOBase:
    if path.suffix == ".bz2":
        return bz2.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def _parse_as_rel(line: str) -> dict[str, Any] | None:
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    parts = s.split("|")
    if len(parts) < 3:
        return None
    try:
        return {
            "dataset": "as-relationship",
            "asnA": int(parts[0]),
            "asnB": int(parts[1]),
            "relation": int(parts[2]),
            "source": parts[3] if len(parts) >= 4 else "",
        }
    except ValueError:
        return None


def _parse_prefix2as(line: str) -> dict[str, Any] | None:
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    parts = s.split("\t")
    if len(parts) < 3:
        return None
    return {
        "dataset": "prefix2as",
        "prefix": parts[0],
        "prefixLength": parts[1],
        "originAsn": parts[2],
    }


def _parse_as_rank(line: str) -> dict[str, Any] | None:
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    parts = s.split("\t")
    if len(parts) < 5:
        return None
    return {
        "dataset": "as-rank",
        "rank": parts[0],
        "asn": parts[1],
        "asName": parts[2],
        "degree": parts[3],
        "country": parts[4],
    }


_PARSERS = {
    "as-relationship": _parse_as_rel,
    "prefix2as":       _parse_prefix2as,
    "as-rank":         _parse_as_rank,
}


@dataclass
class CaidaSensor:
    """Tier-C sensor over a CAIDA dataset dump."""

    name: str = "routing/caida-as-rank"
    dataset_kind: str = "as-rank"  # one of _PARSERS keys
    annex_root: Path = field(default_factory=lambda: Path("."))
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "CC-BY-NC-4.0"
    tier: Tier = "C"
    refresh_cadence_sec: int = 30 * 24 * 3600
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    pii_fields: tuple[str, ...] = ("asName",)
    _cached_pin: DatasetPin | None = field(default=None, init=False, repr=False)

    def latest_pin(self) -> DatasetPin:
        if self.dataset_kind not in _PARSERS:
            raise ValueError(
                f"unknown CAIDA dataset_kind '{self.dataset_kind}'. "
                f"Known: {tuple(_PARSERS)}"
            )
        pin = self.pin_resolver.latest(self.name)
        self._cached_pin = pin
        return pin

    def _resolve_dump_path(self, pin: DatasetPin) -> Path:
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
        for pattern in ("*.bz2", "*.txt", "*.gz"):
            dumps = list(snapshot_dir.glob(pattern))
            if dumps:
                return dumps[0]
        raise FileNotFoundError(f"no CAIDA dump in {snapshot_dir}")

    def stream(self, pin: DatasetPin) -> Iterator[SensorObservation]:
        parser = _PARSERS[self.dataset_kind]
        dump_path = self._resolve_dump_path(pin)
        with _open_compressed(dump_path) as f:
            for line in f:
                row = parser(line)
                if row is None:
                    continue
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


__all__ = ["CaidaSensor"]
