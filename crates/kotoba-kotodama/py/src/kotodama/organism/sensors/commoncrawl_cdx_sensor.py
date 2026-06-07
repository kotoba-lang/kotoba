"""CommonCrawlCdxSensor — Tier-C DatasetSensor over web/commoncrawl-cdx/.

Per ADR-2605262400 §3 + §4.2 + W4. Reads a Common Crawl CDX-J shard
(one JSON object per line, optionally gzipped) and yields one
SensorObservation per archived URL record.

CDX-J row shape (canonical Common Crawl form) — keys ``url``, ``mime``,
``status``, ``digest``, ``length``, ``offset``, ``filename``. The
``url`` field is the only PII-sensitive column; the others are size /
content-type / WARC-offset metadata.

PII filter targets:
  - ``url`` — query strings can embed user-bearing tokens, session ids,
    email addresses.

Tier C. internal_only=True attaches automatically via
make_observation. G13 fleet-internal-only enforced downstream by
TierGate.
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


def _parse_cdx_j_line(line: str) -> dict | None:
    """Parse one CDX-J row.

    Real Common Crawl CDX-J rows are of the form

      <surt_url> <timestamp> {<json>}

    Wave-4 supports both:
      - Pure JSON-per-line (some derived archives use this).
      - SURT + timestamp + JSON suffix (canonical CC-MAIN form).
    """
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if s.startswith("{") and s.endswith("}"):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return None
    # Canonical form: split into 3 fields where the third is JSON.
    parts = s.split(maxsplit=2)
    if len(parts) < 3:
        return None
    surt_url, ts, body = parts
    if not body.startswith("{"):
        return None
    try:
        rec = json.loads(body)
    except json.JSONDecodeError:
        return None
    rec.setdefault("surt", surt_url)
    rec.setdefault("timestamp", ts)
    return rec


@dataclass
class CommonCrawlCdxSensor:
    """Sensor over a Common Crawl CDX-J shard."""

    name: str = "web/commoncrawl-cdx"
    annex_root: Path = field(default_factory=lambda: Path("."))
    pin_resolver: StaticPinResolver = field(default_factory=StaticPinResolver)
    license: str = "commoncrawl-research-use"
    tier: Tier = "C"
    refresh_cadence_sec: int = 30 * 24 * 3600  # monthly crawl cadence
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    pii_fields: tuple[str, ...] = ("url",)
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
        for pattern in ("cdx-*.gz", "cdx-*.cdx", "*.cdx.gz", "*.cdx"):
            shards = list(snapshot_dir.glob(pattern))
            if shards:
                return shards[0]
        raise FileNotFoundError(
            f"no CDX shard (cdx-*.gz / *.cdx) in {snapshot_dir}"
        )

    def stream(self, pin: DatasetPin) -> Iterator[SensorObservation]:
        shard_path = self._resolve_shard_path(pin)
        with _open_compressed(shard_path) as f:
            for line in f:
                row = _parse_cdx_j_line(line)
                if row is None:
                    continue
                redacted, _stats = redact_payload(
                    row, policy=self.pii_filter, fields=self.pii_fields,
                )
                yield make_observation(
                    sensor=self.name,
                    tier=self.tier,
                    pin=pin,
                    payload=redacted,
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


__all__ = ["CommonCrawlCdxSensor"]
