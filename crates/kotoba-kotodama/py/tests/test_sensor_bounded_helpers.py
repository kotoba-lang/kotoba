"""Tests for the generic stream_bounded + hot_sample_bounded helpers.

Per ADR-2605262400 §3 sensor protocol. Tests use a synthetic
DatasetSensor stub yielding N pre-canned observations — no real
dataset needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator

import pytest

from kotodama.organism.sensors import (
    DatasetPin,
    DatasetSensor,
    PiiFilterPolicy,
    SensorObservation,
    Tier,
    hot_sample_bounded,
    stream_bounded,
)


@dataclass
class _StubSensor:
    """N observations on demand. ``total`` controls how many records
    ``stream()`` produces."""

    name: str = "test/stub"
    license: str = "test"
    tier: Tier = "A"
    refresh_cadence_sec: int = 60
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    total: int = 100
    pin: DatasetPin = field(default_factory=lambda: DatasetPin(
        name="test/stub", revision="sha256:rev1",
        cid_map_cid="bafy...", license="test", tier="A",
        created_at="2026-05-27T00:00:00Z",
    ))

    def latest_pin(self) -> DatasetPin:
        return self.pin

    def stream(self, pin: DatasetPin) -> Iterator[SensorObservation]:
        for i in range(self.total):
            yield SensorObservation(
                sensor=self.name,
                tier=self.tier,
                pin_revision=pin.revision,
                payload={"i": i, "ip": f"10.0.0.{i % 254}"},
                internal_only=(self.tier == "C"),
            )

    def hot_sample(self, pin: DatasetPin, n: int) -> list[SensorObservation]:
        return list(self.stream(pin))[:n]


# ── stream_bounded ────────────────────────────────────────────────────


def test_stream_bounded_yields_at_most_limit():
    s = _StubSensor(total=1000)
    obs = list(stream_bounded(s, s.latest_pin(), limit=50))
    assert len(obs) == 50
    assert obs[0].payload["i"] == 0
    assert obs[-1].payload["i"] == 49


def test_stream_bounded_yields_all_when_limit_exceeds_total():
    s = _StubSensor(total=20)
    obs = list(stream_bounded(s, s.latest_pin(), limit=1000))
    assert len(obs) == 20


def test_stream_bounded_zero_limit_yields_nothing():
    s = _StubSensor(total=100)
    obs = list(stream_bounded(s, s.latest_pin(), limit=0))
    assert obs == []


def test_stream_bounded_works_on_any_sensor_protocol():
    """Verify it doesn't require a particular concrete sensor class."""
    s = _StubSensor(name="custom/whatever", tier="C")
    assert isinstance(s, DatasetSensor)
    obs = list(stream_bounded(s, s.latest_pin(), limit=5))
    assert len(obs) == 5
    assert all(o.tier == "C" for o in obs)
    assert all(o.internal_only is True for o in obs)


# ── hot_sample_bounded ────────────────────────────────────────────────


def test_hot_sample_bounded_returns_n_observations():
    s = _StubSensor(total=10000)
    sample = hot_sample_bounded(s, s.latest_pin(), n=20, max_iter=5000)
    assert len(sample) == 20


def test_hot_sample_bounded_deterministic_on_seed_key():
    s = _StubSensor(total=10000)
    a = hot_sample_bounded(s, s.latest_pin(), n=20, max_iter=5000)
    b = hot_sample_bounded(s, s.latest_pin(), n=20, max_iter=5000)
    a_ids = sorted(o.payload["i"] for o in a)
    b_ids = sorted(o.payload["i"] for o in b)
    assert a_ids == b_ids


def test_hot_sample_bounded_seed_includes_max_iter():
    """Different max_iter ⇒ different seed ⇒ different sample."""
    s = _StubSensor(total=10000)
    a = hot_sample_bounded(s, s.latest_pin(), n=20, max_iter=5000)
    b = hot_sample_bounded(s, s.latest_pin(), n=20, max_iter=10000)
    a_ids = sorted(o.payload["i"] for o in a)
    b_ids = sorted(o.payload["i"] for o in b)
    assert a_ids != b_ids


def test_hot_sample_bounded_seed_includes_sensor_name():
    """Two sensors at the same revision still produce independent samples."""
    s1 = _StubSensor(name="s1", total=10000)
    s2 = _StubSensor(name="s2", total=10000)
    # Same pin revision across both.
    a = hot_sample_bounded(s1, s1.latest_pin(), n=20, max_iter=5000)
    b = hot_sample_bounded(s2, s2.latest_pin(), n=20, max_iter=5000)
    a_ids = sorted(o.payload["i"] for o in a)
    b_ids = sorted(o.payload["i"] for o in b)
    assert a_ids != b_ids


def test_hot_sample_bounded_uniform_below_max_iter():
    """When total ≤ max_iter, every record is in the reservoir candidate
    pool — the sample is uniform over the full stream."""
    s = _StubSensor(total=50)
    sample = hot_sample_bounded(s, s.latest_pin(), n=20, max_iter=100)
    assert len(sample) == 20
    # Indices come from somewhere in [0, 50). No duplicates.
    ids = [o.payload["i"] for o in sample]
    assert len(set(ids)) == 20


def test_hot_sample_bounded_handles_small_streams():
    s = _StubSensor(total=5)
    sample = hot_sample_bounded(s, s.latest_pin(), n=20, max_iter=100)
    # Only 5 records available → reservoir holds all 5.
    assert len(sample) == 5
