"""W2 sensor tests (ADR-2605262400) — IanaRootSensor + RisRoutingSensor.

The RisRoutingSensor relies on the external ``mrtparse`` C-extension
to decode MRT bytes; we substitute the record iterator with a synthetic
in-memory generator to avoid pulling that dependency into CI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kotodama.organism.sensors import (
    DatasetPin,
    IanaRootSensor,
    RisRoutingSensor,
    StaticPinResolver,
)
from kotodama.organism.sensors import ris_routing_sensor as _ris_mod


# ── IanaRootSensor ─────────────────────────────────────────────────────


def _make_iana_snapshot(tmp_path: Path, rows: list[dict]) -> Path:
    subdir = tmp_path / "netreg" / "iana-root" / "iana-root-snap"
    subdir.mkdir(parents=True, exist_ok=True)
    ndjson_path = subdir / "root.zone.ndjson"
    with ndjson_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return tmp_path


def test_iana_root_sensor_stream(tmp_path):
    annex_root = _make_iana_snapshot(
        tmp_path,
        [
            {"tld": "example", "ns": ["a.iana-servers.net."], "ds": [], "glue": []},
            {"tld": "test", "ns": ["ns.test."], "ds": [], "glue": [
                {"host": "ns.test", "type": "A", "addr": "192.0.2.1"}
            ]},
        ],
    )
    pins = StaticPinResolver(
        pins={
            "netreg/iana-root": DatasetPin(
                name="netreg/iana-root",
                revision="sha256:fixed-root",
                cid_map_cid="bafy...",
                license="public-domain",
                tier="A",
                created_at="2026-05-26T00:00:00Z",
            )
        }
    )
    sensor = IanaRootSensor(
        annex_root=annex_root,
        pin_resolver=pins,
    )
    pin = sensor.latest_pin()
    observations = list(sensor.stream(pin))
    assert len(observations) == 2
    tlds = [o.payload["tld"] for o in observations]
    assert tlds == ["example", "test"]
    assert all(o.tier == "A" and o.internal_only is False for o in observations)
    assert observations[1].payload["glue"][0]["addr"] == "192.0.2.1"


def test_iana_root_sensor_hot_sample_deterministic(tmp_path):
    annex_root = _make_iana_snapshot(
        tmp_path,
        [{"tld": f"tld{i}", "ns": [], "ds": [], "glue": []} for i in range(30)],
    )
    pins = StaticPinResolver(
        pins={
            "netreg/iana-root": DatasetPin(
                name="netreg/iana-root",
                revision="sha256:fixed-root",
                cid_map_cid="bafy...",
                license="public-domain",
                tier="A",
                created_at="2026-05-26T00:00:00Z",
            )
        }
    )
    sensor = IanaRootSensor(annex_root=annex_root, pin_resolver=pins)
    pin = sensor.latest_pin()
    a = [o.payload["tld"] for o in sensor.hot_sample(pin, 5)]
    b = [o.payload["tld"] for o in sensor.hot_sample(pin, 5)]
    assert a == b  # G9 determinism
    assert len(a) == 5


# ── RisRoutingSensor ───────────────────────────────────────────────────


def _make_mrt_dir(tmp_path: Path, name: str, suffix: str = ".gz") -> Path:
    """Stage an empty file with the right suffix so the sensor's path
    resolution finds it. The synthetic record iterator (below) ignores
    the file contents."""
    subdir = tmp_path / name / "snap-260526-0800"
    subdir.mkdir(parents=True, exist_ok=True)
    mrt = subdir / f"bview.20260526.0800{suffix}"
    mrt.write_bytes(b"")
    return tmp_path


@pytest.fixture
def synthetic_records(monkeypatch):
    """Replace mrtparse with an in-memory generator yielding 3 records."""
    def fake_iter(_path):
        for i in range(3):
            yield type("Rec", (), {
                "data": {
                    "prefix": f"203.0.113.{i}",
                    "prefix_length": 32,
                    "rib_entries": [
                        {
                            "peer_index": 0,
                            "path_attributes": [
                                {
                                    "type": {2: "AS_PATH"},
                                    "value": [
                                        {"value": [64500, 64501, 64502 + i]},
                                    ],
                                }
                            ],
                        }
                    ],
                },
            })()

    monkeypatch.setattr(_ris_mod, "_iter_mrt_records", fake_iter)
    return fake_iter


def test_ris_routing_sensor_stream_yields_observations(
    tmp_path, synthetic_records
):
    annex_root = _make_mrt_dir(tmp_path, "routing/ris-mrt/rrc00")
    pins = StaticPinResolver(
        pins={
            "routing/ris-mrt/rrc00": DatasetPin(
                name="routing/ris-mrt/rrc00",
                revision="sha256:fixed-ris",
                cid_map_cid="bafy...",
                license="ripe-tou-open",
                tier="A",
                created_at="2026-05-26T00:00:00Z",
            )
        }
    )
    sensor = RisRoutingSensor(
        name="routing/ris-mrt/rrc00",
        annex_root=annex_root,
        pin_resolver=pins,
    )
    pin = sensor.latest_pin()
    observations = list(sensor.stream(pin))
    assert len(observations) == 3
    first = observations[0]
    assert first.tier == "A"
    assert first.internal_only is False
    assert first.payload["prefix"] == "203.0.113.0/32"
    assert first.payload["originAsn"] == 64502
    assert first.payload["asPath"] == [64500, 64501, 64502]


def test_ris_routing_sensor_hot_sample_deterministic(
    tmp_path, synthetic_records
):
    annex_root = _make_mrt_dir(tmp_path, "routing/ris-mrt/rrc00")
    pins = StaticPinResolver(
        pins={
            "routing/ris-mrt/rrc00": DatasetPin(
                name="routing/ris-mrt/rrc00",
                revision="sha256:fixed-ris",
                cid_map_cid="bafy...",
                license="ripe-tou-open",
                tier="A",
                created_at="2026-05-26T00:00:00Z",
            )
        }
    )
    sensor = RisRoutingSensor(
        name="routing/ris-mrt/rrc00",
        annex_root=annex_root,
        pin_resolver=pins,
    )
    pin = sensor.latest_pin()
    a = [o.payload["prefix"] for o in sensor.hot_sample(pin, 2)]
    b = [o.payload["prefix"] for o in sensor.hot_sample(pin, 2)]
    assert a == b  # G9 determinism
    assert len(a) == 2


def test_ris_routing_sensor_supports_bz2(tmp_path, synthetic_records):
    """Routeviews uses .bz2; the sensor handles both compressions."""
    annex_root = _make_mrt_dir(tmp_path, "routing/routeviews/rv2", suffix=".bz2")
    pins = StaticPinResolver(
        pins={
            "routing/routeviews/rv2": DatasetPin(
                name="routing/routeviews/rv2",
                revision="sha256:fixed-rv",
                cid_map_cid="bafy...",
                license="uo-tou-open",
                tier="A",
                created_at="2026-05-26T00:00:00Z",
            )
        }
    )
    sensor = RisRoutingSensor(
        name="routing/routeviews/rv2",
        annex_root=annex_root,
        pin_resolver=pins,
    )
    pin = sensor.latest_pin()
    observations = list(sensor.stream(pin))
    assert len(observations) == 3
