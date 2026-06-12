"""RisRoutingSensor — DatasetSensor over routing/ris-mrt + routing/routeviews.

Per ADR-2605262400 §3 + §4.2 + W2. Reads an MRT RIB snapshot
(``bview.*.gz`` from RIPE RIS, ``rib.*.bz2`` from Routeviews) and
yields one ``SensorObservation`` per (prefix, origin_asn, as_path)
tuple via the upstream ``mrtparse`` library.

Both collectors share the same RIB-encoded MRT format so a single
sensor handles both — the only difference is compression (gzip vs
bzip2) and the file naming, both handled by ``mrtparse``'s reader.

Hot-sample uses pin.revision-seeded reservoir sampling for G9
determinism.

The sensor is PASSIVE-ONLY (G8) — it reads from local annex bytes
only. No live BGP session is opened.
"""

from __future__ import annotations

import bz2
import gzip
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


# Wave-2 supports both .gz (RIS) and .bz2 (Routeviews) compression.
_COMPRESSED_SUFFIXES = (".gz", ".bz2")


def _open_compressed(path: Path) -> io.BufferedReader:
    if path.suffix == ".gz":
        return gzip.open(path, "rb")  # type: ignore[return-value]
    if path.suffix == ".bz2":
        return bz2.open(path, "rb")  # type: ignore[return-value]
    return path.open("rb")


def _iter_mrt_records(path: Path) -> Iterator[dict[str, Any]]:
    """Decode an MRT RIB file via mrtparse.

    ``mrtparse`` is the canonical Python decoder for MRT (RFC 6396).
    We hold the import lazy so the sensor module imports cleanly even
    on machines without the package — the import only matters when
    the sensor actually reads a snapshot.
    """
    try:
        from mrtparse import Reader  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "RisRoutingSensor requires the 'mrtparse' package "
            "(pip install mrtparse)."
        ) from exc
    # mrtparse's Reader takes a path string OR a file-like object;
    # we pass the path so it can pick the right codec from the suffix.
    yield from Reader(str(path))


def _extract_prefix_records(record: Any) -> list[dict[str, Any]]:
    """Normalize one mrtparse record into prefix-level rows.

    mrtparse yields one record per MRT TYPE; for TABLE_DUMP_V2 we
    care about the RIB_IPV4_UNICAST + RIB_IPV6_UNICAST subtypes,
    each of which has a Prefix + a list of RIB-entries (one per
    advertising peer). We flatten that to (prefix, origin_asn,
    as_path, peer_index) tuples.

    Best-effort: mrtparse's record shape is dict-like with stringified
    integer fields. We tolerate KeyErrors and skip malformed entries.
    """
    out: list[dict[str, Any]] = []
    try:
        data = record.data if hasattr(record, "data") else record
        # mrtparse uses dicts whose keys are typed via {"INT_VAL": "STR_VAL"};
        # we just iterate values defensively.
        prefix = data.get("prefix", "")
        plen = data.get("prefix_length", "")
        rib_entries = data.get("rib_entries", []) or []
        for ent in rib_entries:
            peer_idx = ent.get("peer_index", "")
            attrs = ent.get("path_attributes", []) or []
            origin_asn: int | None = None
            as_path: list[int] = []
            for attr in attrs:
                attr_type = attr.get("type", {})
                # AS_PATH attribute = type code 2.
                type_codes = list(attr_type.values()) if isinstance(attr_type, dict) else [attr_type]
                if not any("AS_PATH" in str(t) or t == 2 for t in type_codes):
                    continue
                value = attr.get("value", [])
                if not isinstance(value, list):
                    continue
                for seg in value:
                    asns = seg.get("value", []) if isinstance(seg, dict) else []
                    for asn in asns:
                        try:
                            as_path.append(int(asn))
                        except (TypeError, ValueError):
                            continue
            if as_path:
                origin_asn = as_path[-1]
            out.append({
                "prefix": f"{prefix}/{plen}" if prefix and plen != "" else prefix,
                "peerIndex": peer_idx,
                "originAsn": origin_asn,
                "asPath": as_path,
            })
    except (AttributeError, KeyError, TypeError):
        return out
    return out


@dataclass
class RisRoutingSensor:
    """Sensor over an MRT RIB snapshot (RIS bview or Routeviews rib)."""

    name: str
    annex_root: Path
    pin_resolver: StaticPinResolver
    license: str = "ripe-tou-open"
    tier: Tier = "A"
    refresh_cadence_sec: int = 8 * 3600  # RIS bview cadence
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    _cached_pin: DatasetPin | None = field(default=None, init=False, repr=False)

    def latest_pin(self) -> DatasetPin:
        pin = self.pin_resolver.latest(self.name)
        self._cached_pin = pin
        return pin

    def _resolve_mrt_path(self, pin: DatasetPin) -> Path:
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
        for suffix in _COMPRESSED_SUFFIXES:
            mrt_files = list(snapshot_dir.glob(f"*{suffix}"))
            if mrt_files:
                return mrt_files[0]
        raise FileNotFoundError(
            f"no compressed MRT file (.gz / .bz2) in {snapshot_dir}"
        )

    def stream(self, pin: DatasetPin) -> Iterator[SensorObservation]:
        mrt_path = self._resolve_mrt_path(pin)
        for record in _iter_mrt_records(mrt_path):
            for row in _extract_prefix_records(record):
                yield make_observation(
                    sensor=self.name,
                    tier=self.tier,
                    pin=pin,
                    payload=row,
                )

    def stream_bounded(
        self, pin: DatasetPin, limit: int
    ) -> Iterator[SensorObservation]:
        """Yield at most ``limit`` observations, then stop.

        Forward to the generic ``base.stream_bounded`` helper. Kept as
        a thin wrapper for API compatibility — callers who already
        depend on ``sensor.stream_bounded(...)`` continue to work.
        New code should prefer the free function
        ``kotodama.organism.sensors.base.stream_bounded(sensor,
        pin, limit)`` which works uniformly across all sensors.
        """
        from .base import stream_bounded as _gen_stream_bounded
        return _gen_stream_bounded(self, pin, limit)

    def hot_sample_bounded(
        self, pin: DatasetPin, n: int, max_iter: int
    ) -> list[SensorObservation]:
        """Reservoir-sample ``n`` from the first ``max_iter`` records.

        Forward to the generic ``base.hot_sample_bounded`` helper.

        NOTE: G9 seed key differs from the original per-class
        implementation — the generic helper includes
        ``sensor.name`` in the seed so two different sensors with
        the same revision+n+max_iter still produce independent
        samples. Tests that pinned exact reservoir outputs against
        the old key need a one-time refresh; the determinism
        property itself is preserved.
        """
        from .base import hot_sample_bounded as _gen_hot_sample_bounded
        return _gen_hot_sample_bounded(self, pin, n, max_iter)

    def hot_sample(self, pin: DatasetPin, n: int) -> list[SensorObservation]:
        # Performance note (measured 2026-05-27 on mac-260317, real
        # 421 MB RIPE-RIS rrc00 bview): mrtparse + this reservoir loop
        # streams ~15K observations/second. A full bview has roughly
        # 5-10M RIB entries, so a complete reservoir sample takes
        # several minutes. For the heartbeat hot-path, callers SHOULD
        # use a much smaller bounded prefix-iteration strategy. A
        # follow-up wave will add ``stream_prefix(limit)`` that
        # early-exits after N records (uniform near the head; biased
        # toward early peers but suitable for tick-cadence sampling).
        # Until then, ``hot_sample`` on RIPE-RIS / Routeviews should
        # be reserved for cold-path corpus assembly, not organism
        # heartbeats.
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


# Test-only seam: lets the test suite inject a synthetic record stream
# without depending on mrtparse (which is a heavyweight C-extension).
def _set_record_iter(fn) -> None:  # type: ignore[no-untyped-def]
    global _iter_mrt_records
    _iter_mrt_records = fn


__all__ = [
    "RisRoutingSensor",
    "_extract_prefix_records",
    "_set_record_iter",
]
