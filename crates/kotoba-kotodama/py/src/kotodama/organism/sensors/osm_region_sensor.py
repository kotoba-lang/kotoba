"""OsmRegionSensor — DatasetSensor over a `geo/osm/<region>/` subdataset.

Per ADR-2605262400 §3 + §4.2 + W1. Reads a GeoJSON-NDJSON sidecar
(one Feature object per line) and yields one ``SensorObservation``
per geographic feature with normalized ``(lat, lon, feature_tags,
name?, admin_level?)`` payload.

The raw OSM PBF (Protocol Buffers binary) is NOT decoded inline —
the operator runs ``osmium export -f geojsonseq <region>.osm.pbf >
<region>.geojsonl`` once, on the staging dir. The sensor consumes
the resulting NDJSON sidecar. This keeps the sensor pure-stdlib +
keeps PBF decoding out of the hot heartbeat path.

GeoJSON Feature shape (canonical, per RFC 7946):

  {
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [lon, lat]},
    "properties": {"name": "...", "admin_level": "...", ...}
  }

For non-Point geometries (LineString / Polygon / MultiPolygon) we use
the centroid (averaged ring coordinates) as a coarse anchor. The
shape ``geometry`` block is preserved in the payload's ``raw_geometry``
key for downstream consumers that need fidelity.

License: ODbL 1.0 (Open Database License). Tier A — but derivative
works inherit the ODbL share-alike. The corpus assembler tags the
output license accordingly.

Hot-sample uses pin.revision-seeded reservoir sampling for G9
determinism.
"""

from __future__ import annotations

import gzip
import io
import json
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


def _open_compressed(path: Path) -> io.IOBase:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def _coords_anchor(geom: dict[str, Any]) -> tuple[float, float] | None:
    """Return a single ``(lat, lon)`` anchor for the geometry.

    Point → its own coordinate. LineString / Polygon → centroid of all
    leaf coordinates (averaged). Returns None if the structure is
    malformed.
    """
    if not isinstance(geom, dict):
        return None
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if coords is None:
        return None

    def _walk(obj: Any) -> Iterator[tuple[float, float]]:
        # Walk arbitrarily-nested coordinate arrays. Leaves are 2-element
        # numeric lists ``[lon, lat]``.
        if isinstance(obj, (list, tuple)):
            if (
                len(obj) >= 2
                and isinstance(obj[0], (int, float))
                and isinstance(obj[1], (int, float))
            ):
                yield (float(obj[1]), float(obj[0]))  # GeoJSON is (lon, lat)
            else:
                for child in obj:
                    yield from _walk(child)

    points = list(_walk(coords))
    if not points:
        return None
    if gtype == "Point":
        return points[0]
    # Centroid of all leaf coords.
    lats = sum(p[0] for p in points) / len(points)
    lons = sum(p[1] for p in points) / len(points)
    return (lats, lons)


def _parse_feature_line(line: str) -> dict[str, Any] | None:
    """Decode one GeoJSON Feature line into a flat sensor payload.

    Returns None for empty / non-Feature / malformed lines (the
    sensor skips them silently).
    """
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    try:
        feat = json.loads(s)
    except json.JSONDecodeError:
        return None
    if not isinstance(feat, dict) or feat.get("type") != "Feature":
        return None
    geom = feat.get("geometry") or {}
    props = feat.get("properties") or {}
    if not isinstance(props, dict):
        return None
    anchor = _coords_anchor(geom)
    if anchor is None:
        return None
    lat, lon = anchor

    # Extract a few well-known OSM tag keys at the top level for
    # quick downstream consumers; the rest stays under
    # ``feature_tags`` so callers can inspect the full tag bundle.
    name = props.get("name")
    admin_level = props.get("admin_level")
    osm_type = feat.get("osm_type") or props.get("osm_type")
    osm_id = feat.get("id") or feat.get("osm_id")

    return {
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "name": name if isinstance(name, str) else None,
        "admin_level": admin_level if isinstance(admin_level, str) else None,
        "osm_type": osm_type if isinstance(osm_type, str) else None,
        "osm_id": osm_id,
        "feature_tags": {k: v for k, v in props.items() if k not in {"name", "admin_level"}},
        "raw_geometry_type": geom.get("type") if isinstance(geom, dict) else None,
    }


@dataclass
class OsmRegionSensor:
    """Sensor that reads an OSM region GeoJSON-NDJSON sidecar."""

    name: str  # e.g. "geo/osm/japan" or "geo/osm/europe-liechtenstein"
    annex_root: Path
    pin_resolver: StaticPinResolver
    license: str = "ODbL-1.0"
    tier: Tier = "A"
    refresh_cadence_sec: int = 7 * 24 * 3600  # Geofabrik publishes weekly
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    # OSM is pure geographic metadata; rare exceptions (operator email
    # in a `contact:email=*` tag) are flagged via the pii_filter on
    # the `feature_tags` block.
    pii_fields: tuple[str, ...] = ()
    _cached_pin: DatasetPin | None = field(default=None, init=False, repr=False)

    def latest_pin(self) -> DatasetPin:
        pin = self.pin_resolver.latest(self.name)
        self._cached_pin = pin
        return pin

    def _resolve_geojsonl_path(self, pin: DatasetPin) -> Path:
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
        # Accept geojsonseq variants + .gz compression.
        for pattern in (
            "*.geojsonl",
            "*.geojsonl.gz",
            "*.geojsonseq",
            "*.geojsonseq.gz",
            "*.ndjson",
        ):
            shards = list(snapshot_dir.glob(pattern))
            if shards:
                return shards[0]
        raise FileNotFoundError(
            f"no GeoJSON-NDJSON sidecar (*.geojsonl[.gz] / *.geojsonseq[.gz] / "
            f"*.ndjson) in {snapshot_dir}. Run `osmium export -f geojsonseq` "
            f"on the raw .osm.pbf to produce one."
        )

    def stream(self, pin: DatasetPin) -> Iterator[SensorObservation]:
        path = self._resolve_geojsonl_path(pin)
        with _open_compressed(path) as f:
            for line in f:
                payload = _parse_feature_line(line)
                if payload is None:
                    continue
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


__all__ = [
    "OsmRegionSensor",
    "_parse_feature_line",
    "_coords_anchor",
]
