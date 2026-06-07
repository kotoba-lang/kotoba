"""OsmRegionSensor tests (ADR-2605262400 §3 + §4.2 + W1)."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from kotodama.organism.sensors import (
    DatasetPin,
    OsmRegionSensor,
    StaticPinResolver,
)
from kotodama.organism.sensors.osm_region_sensor import (
    _coords_anchor,
    _parse_feature_line,
)


# ── Centroid helper ───────────────────────────────────────────────────


def test_coords_anchor_point():
    geom = {"type": "Point", "coordinates": [139.6917, 35.6895]}
    assert _coords_anchor(geom) == (35.6895, 139.6917)


def test_coords_anchor_linestring_centroid():
    geom = {
        "type": "LineString",
        "coordinates": [[0.0, 0.0], [10.0, 10.0]],
    }
    lat, lon = _coords_anchor(geom)
    assert lat == pytest.approx(5.0)
    assert lon == pytest.approx(5.0)


def test_coords_anchor_polygon_centroid():
    geom = {
        "type": "Polygon",
        "coordinates": [[
            [0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0],
        ]],
    }
    lat, lon = _coords_anchor(geom)
    # Vertices average — closing point counted twice as expected of a
    # naive coordinate-average centroid (good enough as a coarse anchor).
    assert 3.0 <= lat <= 7.0
    assert 3.0 <= lon <= 7.0


def test_coords_anchor_malformed_returns_none():
    assert _coords_anchor(None) is None
    assert _coords_anchor({}) is None
    assert _coords_anchor({"type": "Point"}) is None


# ── Feature-line parser ───────────────────────────────────────────────


def test_parse_feature_point():
    line = json.dumps({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [139.6917, 35.6895]},
        "properties": {"name": "Tokyo Station", "admin_level": "10",
                       "highway": "stop"},
    })
    p = _parse_feature_line(line)
    assert p is not None
    assert p["lat"] == 35.6895
    assert p["lon"] == 139.6917
    assert p["name"] == "Tokyo Station"
    assert p["admin_level"] == "10"
    assert p["feature_tags"] == {"highway": "stop"}
    assert p["raw_geometry_type"] == "Point"


def test_parse_feature_polygon_uses_centroid():
    line = json.dumps({
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0], [0.0, 0.0],
            ]],
        },
        "properties": {"name": "Plaza", "amenity": "square"},
    })
    p = _parse_feature_line(line)
    assert p is not None
    assert 0.0 < p["lat"] < 2.0
    assert 0.0 < p["lon"] < 2.0
    assert p["name"] == "Plaza"
    assert p["feature_tags"] == {"amenity": "square"}


def test_parse_feature_skips_non_feature_lines():
    assert _parse_feature_line("") is None
    assert _parse_feature_line("# header comment") is None
    assert _parse_feature_line("not json") is None
    assert _parse_feature_line('{"type":"FeatureCollection"}') is None
    assert _parse_feature_line('{"type":"Feature"}') is None  # no geometry


# ── Full sensor wiring ────────────────────────────────────────────────


_SAMPLE_FEATURES = [
    {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [139.6917, 35.6895]},
        "properties": {"name": "Tokyo Station", "railway": "station"},
    },
    {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [135.5023, 34.6937]},
        "properties": {"name": "Osaka Station", "railway": "station"},
    },
    {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [136.8819, 35.1709]},
        "properties": {"name": "Nagoya Station", "railway": "station"},
    },
]


def _make_snapshot(tmp_path: Path, region: str, features: list[dict],
                   *, compress: bool = False) -> Path:
    subdir = tmp_path / "geo" / "osm" / region / "snap-20260526"
    subdir.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(f) for f in features) + "\n"
    if compress:
        (subdir / f"{region}.geojsonl.gz").write_bytes(gzip.compress(body.encode()))
    else:
        (subdir / f"{region}.geojsonl").write_text(body, encoding="utf-8")
    return tmp_path


def _make_pin(name: str) -> DatasetPin:
    return DatasetPin(
        name=name,
        revision="sha256:osm-test-fixed",
        cid_map_cid="bafy...",
        license="ODbL-1.0",
        tier="A",
        created_at="2026-05-26T00:00:00Z",
    )


def test_osm_sensor_stream_yields_per_feature_observations(tmp_path):
    annex_root = _make_snapshot(tmp_path, "japan-stations", _SAMPLE_FEATURES)
    pins = StaticPinResolver(pins={"geo/osm/japan-stations": _make_pin("geo/osm/japan-stations")})
    sensor = OsmRegionSensor(
        name="geo/osm/japan-stations",
        annex_root=annex_root,
        pin_resolver=pins,
    )
    pin = sensor.latest_pin()
    obs = list(sensor.stream(pin))
    assert len(obs) == 3
    assert all(o.tier == "A" for o in obs)
    assert all(o.internal_only is False for o in obs)
    names = {o.payload["name"] for o in obs}
    assert names == {"Tokyo Station", "Osaka Station", "Nagoya Station"}


def test_osm_sensor_handles_compressed_sidecar(tmp_path):
    annex_root = _make_snapshot(
        tmp_path, "japan-stations-gz", _SAMPLE_FEATURES, compress=True,
    )
    pins = StaticPinResolver(pins={"geo/osm/japan-stations-gz": _make_pin("geo/osm/japan-stations-gz")})
    sensor = OsmRegionSensor(
        name="geo/osm/japan-stations-gz",
        annex_root=annex_root,
        pin_resolver=pins,
    )
    pin = sensor.latest_pin()
    obs = list(sensor.stream(pin))
    assert len(obs) == 3


def test_osm_sensor_hot_sample_deterministic(tmp_path):
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(i), float(i)]},
            "properties": {"name": f"point-{i}", "ref": str(i)},
        }
        for i in range(40)
    ]
    annex_root = _make_snapshot(tmp_path, "synthetic-grid", features)
    pins = StaticPinResolver(pins={"geo/osm/synthetic-grid": _make_pin("geo/osm/synthetic-grid")})
    sensor = OsmRegionSensor(
        name="geo/osm/synthetic-grid",
        annex_root=annex_root,
        pin_resolver=pins,
    )
    pin = sensor.latest_pin()
    a = [o.payload["name"] for o in sensor.hot_sample(pin, 5)]
    b = [o.payload["name"] for o in sensor.hot_sample(pin, 5)]
    assert a == b  # G9 determinism
    assert len(a) == 5
