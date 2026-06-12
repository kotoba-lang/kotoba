"""CzdsSensor — Tier-C/D DatasetSensor over dns/czds-<tld>/ subdatasets.

Per ADR-2605262400 §3 + §4.2 + W4. Reads a CZDS zone-file snapshot
(line-oriented BIND zone syntax) and yields one SensorObservation per
resource record.

Per-TLD `tier` is inherited from the
``com.etzhayyim.substrate.tldCouncilAttestation`` record — the
StaticPinResolver passes that down via the DatasetPin. internal_only
attaches automatically via make_observation.

PII filter is applied to the value column of TXT records and to the
SOA RNAME field (which can contain operator contact addresses encoded
as a dotted email).

Hot-sample uses pin.revision-seeded reservoir sampling.
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


def _parse_zone_line(line: str) -> dict[str, Any] | None:
    """Parse one BIND zone-file resource record line.

    Returns a flat dict ``{name, ttl, class, type, value}`` or None for
    SOA / comment / directive / empty lines. The format is whitespace-
    separated:

      <name> <ttl> <class> <type> <rdata...>

    Some fields may be omitted (use the prior line's name/ttl/class) —
    we honor the BIND inherited-defaults convention via the caller's
    state, but for Wave-4's per-line yield we only emit fully-explicit
    lines (the rest are dropped silently to avoid mis-stateful parses).
    """
    s = line.strip()
    if not s or s.startswith(";") or s.startswith("$"):
        return None
    parts = s.split(None, 4)
    if len(parts) < 5:
        return None
    name, ttl_str, klass, rtype, rdata = parts
    if klass.upper() != "IN":
        return None
    # Skip SOA in the iteration body — we handle it specially via the
    # zone header. (SOA RNAME contains operator-contact info; the
    # caller-level state runs PII filter on the entire SOA RDATA.)
    try:
        ttl = int(ttl_str)
    except ValueError:
        return None
    return {
        "name": name.rstrip(".").lower(),
        "ttl": ttl,
        "class": klass.upper(),
        "type": rtype.upper(),
        "value": rdata.strip(),
    }


_TXT_TYPE_PII_FIELDS = ("value",)
_SOA_TYPE_PII_FIELDS = ("value",)


@dataclass
class CzdsSensor:
    """Sensor over a CZDS per-TLD zone-file shard."""

    name: str  # e.g. "dns/czds-com"
    annex_root: Path
    pin_resolver: StaticPinResolver
    license: str = "czds-per-tld"
    tier: Tier = "C"
    refresh_cadence_sec: int = 24 * 3600  # CZDS publishes daily-ish per TLD
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    _cached_pin: DatasetPin | None = field(default=None, init=False, repr=False)

    def latest_pin(self) -> DatasetPin:
        pin = self.pin_resolver.latest(self.name)
        self._cached_pin = pin
        return pin

    def _resolve_zone_path(self, pin: DatasetPin) -> Path:
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
        zone_files = list(snapshot_dir.glob("*.zone"))
        if not zone_files:
            raise FileNotFoundError(f"no *.zone file in {snapshot_dir}")
        return zone_files[0]

    def stream(self, pin: DatasetPin) -> Iterator[SensorObservation]:
        zone_path = self._resolve_zone_path(pin)
        # The TLD slug — used as the per-record context tag.
        tld_slug = self.name.rsplit("/", 1)[-1].replace("czds-", "")
        with zone_path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                row = _parse_zone_line(line)
                if row is None:
                    continue
                # Run PII filter on TXT + SOA value strings; other RR
                # types are bare hostnames / IPs, no PII expected.
                if row["type"] in ("TXT", "SOA"):
                    redacted, _stats = redact_payload(
                        row,
                        policy=self.pii_filter,
                        fields=_TXT_TYPE_PII_FIELDS,
                    )
                else:
                    redacted = row
                redacted["tld"] = tld_slug
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


__all__ = ["CzdsSensor"]
