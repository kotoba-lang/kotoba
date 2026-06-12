"""Geolite2Sensor — DatasetSensor over a `netreg/geolite2/<edition>` subdataset.

Per ADR-2605262400 §3 + §4.2. Reads the MaxMind MMDB file extracted by
`e7m_dataset.fetchers.maxmind_geolite.fetch` via the `maxminddb`
library and yields SensorObservations for caller-supplied IP / prefix
inputs.

Unlike RirDelegatedSensor, GeoLite2 is keyed by IP / prefix (not by
record-index), so `stream()` is not a "scan all records" operation —
the database is opaque outside its keyed-lookup contract. Wave-1
sensor surface:

  - ``lookup(pin, ip)`` — single IP lookup
  - ``hot_sample(pin, n)`` — emits n RIR-anchor IP lookups
    (deterministic on pin.revision via a hash-seeded RNG over the
    set of anchor IPs — used by organism heartbeat ticks)

License: CC-BY-SA-4.0 — derivative corpora MUST preserve attribution +
share-alike (ADR-2605192200 §3).
"""

from __future__ import annotations

import hashlib
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


# A small deterministic set of anchor IPs spanning every RIR region.
# Sensor implementations MUST NOT actively reach these IPs — they are
# pure database keys passed to maxminddb local lookup.
_ANCHOR_IPS: tuple[str, ...] = (
    "1.1.1.1",
    "8.8.8.8",
    "9.9.9.9",
    "203.0.113.1",
    "2606:4700:4700::1111",
    "2001:4860:4860::8888",
    "2620:fe::fe",
    "196.10.0.1",
    "200.7.84.1",
)


@dataclass
class Geolite2Sensor:
    """Sensor that reads a MaxMind GeoLite2 MMDB file."""

    name: str
    annex_root: Path
    pin_resolver: StaticPinResolver
    license: str = "CC-BY-SA-4.0"
    tier: Tier = "A"
    refresh_cadence_sec: int = 7 * 24 * 3600  # GeoLite2 publishes weekly
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    anchor_ips: tuple[str, ...] = _ANCHOR_IPS
    _cached_pin: DatasetPin | None = field(default=None, init=False, repr=False)

    def latest_pin(self) -> DatasetPin:
        pin = self.pin_resolver.latest(self.name)
        self._cached_pin = pin
        return pin

    def _resolve_mmdb_path(self, pin: DatasetPin) -> Path:
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
        mmdb_files = list(snapshot_dir.rglob("*.mmdb"))
        if not mmdb_files:
            raise FileNotFoundError(f"no MMDB file in {snapshot_dir}")
        return mmdb_files[0]

    def lookup(self, pin: DatasetPin, ip: str) -> SensorObservation | None:
        """Single IP lookup. Returns None if the IP is not in the DB."""
        try:
            import maxminddb  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Geolite2Sensor.lookup requires the 'maxminddb' package "
                "(pip install maxminddb)."
            ) from exc
        mmdb_path = self._resolve_mmdb_path(pin)
        with maxminddb.open_database(str(mmdb_path)) as reader:
            row = reader.get(ip)
            if row is None:
                return None
            return make_observation(
                sensor=self.name,
                tier=self.tier,
                pin=pin,
                payload={
                    "ip": ip,
                    "row": row,
                },
            )

    def stream(self, pin: DatasetPin) -> Iterator[SensorObservation]:
        """Stream over the anchor IPs only.

        The MMDB format is not a row-scannable file (it's a trie). Use
        the corpus assembler for full sweeps with an explicit IP /
        prefix input list.
        """
        for ip in self.anchor_ips:
            obs = self.lookup(pin, ip)
            if obs is not None:
                yield obs

    def hot_sample(self, pin: DatasetPin, n: int) -> list[SensorObservation]:
        seed = int(
            hashlib.sha256(f"{pin.revision}:{n}".encode("utf-8")).hexdigest()[:16],
            16,
        )
        rng = random.Random(seed)
        ips = list(self.anchor_ips)
        rng.shuffle(ips)
        ips = ips[: max(0, min(n, len(ips)))]
        out: list[SensorObservation] = []
        for ip in ips:
            obs = self.lookup(pin, ip)
            if obs is not None:
                out.append(obs)
        return out


__all__ = ["Geolite2Sensor"]
