"""UnispscOrganism sensor integration (ADR-2605262400 §4.3).

Verifies that the organism polls its DatasetSensors on tick, honors
each sensor's `refresh_cadence_sec`, and stores observations in a
bounded ring.

Uses a tiny synthetic DatasetSensor so the test doesn't depend on
real-data fixtures or the broader langchain/pydantic import chain.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Iterator
from unittest.mock import MagicMock

import pytest

from kotodama.organism.sensors.base import (
    DatasetPin,
    PiiFilterPolicy,
    SensorObservation,
    Tier,
)
from kotodama.organism.unispsc_organism import (
    UnispscOrganism,
    _MAX_SENSOR_OBSERVATIONS,
)


@dataclass
class _StubSensor:
    """Minimal DatasetSensor stub. Returns N pre-canned observations per
    `hot_sample` call; tracks how many times it was called."""

    name: str = "test/stub"
    license: str = "test"
    tier: Tier = "A"
    refresh_cadence_sec: int = 60
    pii_filter: PiiFilterPolicy = PiiFilterPolicy.STRICT
    call_count: int = 0
    pin: DatasetPin = field(default_factory=lambda: DatasetPin(
        name="test/stub", revision="sha256:rev",
        cid_map_cid="bafy...", license="test", tier="A",
        created_at="2026-05-26T00:00:00Z",
    ))

    def latest_pin(self) -> DatasetPin:
        return self.pin

    def stream(self, pin: DatasetPin) -> Iterator[SensorObservation]:
        return iter(())  # unused by tests

    def hot_sample(self, pin: DatasetPin, n: int) -> list[SensorObservation]:
        self.call_count += 1
        return [
            SensorObservation(
                sensor=self.name,
                tier=self.tier,
                pin_revision=pin.revision,
                payload={"i": i, "call": self.call_count},
                internal_only=(self.tier == "C"),
            )
            for i in range(n)
        ]


def _make_organism(sensors: tuple = (), sample_size: int = 4) -> UnispscOrganism:
    """Build a UnispscOrganism with a no-op graph stub.

    Birthed to ACTIVE so ``tick()`` exercises the real heartbeat path:
    the lifecycle R1 state machine (commit c0d1099f5) gates ``tick()``
    behind ACTIVE/CLONED, and an INACTIVE organism legitimately skips
    polling. A live organism is what these integration tests intend.
    """
    org = UnispscOrganism(
        code="99999999",
        graph=MagicMock(),
        sensors=sensors,
        sensor_sample_size=sample_size,
    )
    org.lifecycle.handle_birth(org.actor_did)
    return org


# ── poll_sensors basic behavior ────────────────────────────────────────


def test_no_sensors_no_observations():
    org = _make_organism()
    org.tick(now_ms=1000)
    assert org.sensor_observations == []
    assert org.sensor_last_poll_ms == {}


def test_first_tick_polls_every_sensor():
    s1 = _StubSensor(name="a", refresh_cadence_sec=10)
    s2 = _StubSensor(name="b", refresh_cadence_sec=10)
    org = _make_organism(sensors=(s1, s2), sample_size=3)
    obs = org.poll_sensors(now_ms=1000)
    assert len(obs) == 6  # 2 sensors × 3 samples
    assert s1.call_count == 1
    assert s2.call_count == 1


def test_within_cadence_skips_poll():
    s = _StubSensor(refresh_cadence_sec=60)
    org = _make_organism(sensors=(s,), sample_size=2)
    org.poll_sensors(now_ms=1000)  # first poll
    assert s.call_count == 1
    org.poll_sensors(now_ms=1000 + 30_000)  # 30s later, still within 60s
    assert s.call_count == 1
    org.poll_sensors(now_ms=1000 + 90_000)  # 90s later, now due
    assert s.call_count == 2


def test_per_sensor_independent_cadence():
    s_fast = _StubSensor(name="fast", refresh_cadence_sec=10)
    s_slow = _StubSensor(name="slow", refresh_cadence_sec=120)
    org = _make_organism(sensors=(s_fast, s_slow), sample_size=2)
    org.poll_sensors(now_ms=1000)
    assert s_fast.call_count == 1
    assert s_slow.call_count == 1
    # 30s later: fast is due, slow is not.
    org.poll_sensors(now_ms=1000 + 30_000)
    assert s_fast.call_count == 2
    assert s_slow.call_count == 1


def test_tick_calls_poll_sensors():
    s = _StubSensor(refresh_cadence_sec=10)
    org = _make_organism(sensors=(s,), sample_size=4)
    org.tick(now_ms=1000)
    assert s.call_count == 1
    assert len(org.sensor_observations) == 4


def test_tier_c_sensor_marks_internal_only():
    s = _StubSensor(name="dns/rapid7-sonar-fdns", tier="C", refresh_cadence_sec=10)
    org = _make_organism(sensors=(s,), sample_size=3)
    obs = org.poll_sensors(now_ms=1000)
    assert all(o.tier == "C" for o in obs)
    assert all(o.internal_only is True for o in obs)


def test_ring_bounded():
    """sensor_observations ring stays at _MAX_SENSOR_OBSERVATIONS."""
    big_n = _MAX_SENSOR_OBSERVATIONS + 50
    s = _StubSensor(refresh_cadence_sec=1)
    org = _make_organism(sensors=(s,), sample_size=big_n)
    org.poll_sensors(now_ms=1000)
    assert len(org.sensor_observations) == _MAX_SENSOR_OBSERVATIONS


def test_sensor_exception_does_not_break_tick():
    """A misbehaving sensor must not crash the tick — best-effort policy."""
    class _BadSensor(_StubSensor):
        def hot_sample(self, pin, n):  # type: ignore[override]
            raise RuntimeError("upstream archive temporarily unreachable")

    bad = _BadSensor(name="bad", refresh_cadence_sec=10)
    good = _StubSensor(name="good", refresh_cadence_sec=10)
    org = _make_organism(sensors=(bad, good), sample_size=2)
    obs = org.poll_sensors(now_ms=1000)
    # The bad sensor's exception was caught; the good one still ran.
    assert good.call_count == 1
    assert len(obs) == 2
