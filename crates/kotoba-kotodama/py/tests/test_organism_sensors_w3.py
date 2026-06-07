"""W3 sensor + R9 leak-test tests (ADR-2605262400).

Three things under test:
  1. Tier-C sensors attach internal_only=True automatically via
     make_observation.
  2. TierGate.guard drops tier-C internal_only=True observations at
     EXTERNAL_FACING sinks and records LeakAttempts.
  3. Those LeakAttempts fed into TierCLeakBackstopRule fire a
     critical KaizenProposal — full chain integration of R9.
"""

from __future__ import annotations

import bz2
import json
from pathlib import Path

import pytest

from kotodama.organism.kaizen import (
    Observation,
    TierCLeakBackstopRule,
)
from kotodama.organism.sensors import (
    CaidaSensor,
    DatasetPin,
    OpenIntelSensor,
    Rapid7SonarSensor,
    SensorObservation,
    SinkClassification,
    StaticPinResolver,
    TierGate,
    make_observation,
)
from kotodama.organism.sensors import openintel_sensor as _oi_mod


# ── Rapid7SonarSensor ──────────────────────────────────────────────────


def _make_rapid7_snapshot(tmp_path: Path, rows: list[dict]) -> Path:
    subdir = tmp_path / "dns" / "rapid7-sonar-fdns" / "snap-20260523"
    subdir.mkdir(parents=True, exist_ok=True)
    shard = subdir / "2026-05-23-fdns_any.ndjson"
    with shard.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return tmp_path


def test_rapid7_sonar_sensor_attaches_internal_only(tmp_path):
    annex_root = _make_rapid7_snapshot(
        tmp_path,
        [
            {"timestamp": "1716708823", "name": "example.com",
             "type": "txt", "value": "v=spf1 mx ~all"},
            {"timestamp": "1716708824", "name": "example.org",
             "type": "txt",
             "value": "ops contact: alice@example.com"},
        ],
    )
    pins = StaticPinResolver(
        pins={
            "dns/rapid7-sonar-fdns": DatasetPin(
                name="dns/rapid7-sonar-fdns",
                revision="sha256:r7",
                cid_map_cid="bafy...",
                license="rapid7-research-use",
                tier="C",
                created_at="2026-05-26T00:00:00Z",
            )
        }
    )
    sensor = Rapid7SonarSensor(annex_root=annex_root, pin_resolver=pins)
    pin = sensor.latest_pin()
    observations = list(sensor.stream(pin))
    assert len(observations) == 2
    assert all(o.tier == "C" for o in observations)
    assert all(o.internal_only is True for o in observations)
    # PII filter should have redacted the email in row 2's value.
    assert "alice@example.com" not in observations[1].payload["value"]


# ── CaidaSensor ────────────────────────────────────────────────────────


def _make_caida_snapshot(tmp_path: Path, lines: list[str]) -> Path:
    subdir = tmp_path / "routing" / "caida-as-rank" / "snap-20260501"
    subdir.mkdir(parents=True, exist_ok=True)
    dump = subdir / "20260501.as-rel.txt.bz2"
    dump.write_bytes(bz2.compress("\n".join(lines).encode("utf-8")))
    return tmp_path


def test_caida_sensor_parses_as_relationship(tmp_path):
    annex_root = _make_caida_snapshot(
        tmp_path,
        [
            "# CAIDA AS-relationship file header",
            "1|2|0|bgp",       # peer-to-peer
            "1|3|-1|bgp",      # customer
            "4|1|1|bgp",       # provider
            "malformed-row",   # skipped
        ],
    )
    pins = StaticPinResolver(
        pins={
            "routing/caida-as-rank": DatasetPin(
                name="routing/caida-as-rank",
                revision="sha256:caida",
                cid_map_cid="bafy...",
                license="CC-BY-NC-4.0",
                tier="C",
                created_at="2026-05-26T00:00:00Z",
            )
        }
    )
    sensor = CaidaSensor(
        dataset_kind="as-relationship",
        annex_root=annex_root,
        pin_resolver=pins,
    )
    pin = sensor.latest_pin()
    observations = list(sensor.stream(pin))
    assert len(observations) == 3
    assert all(o.tier == "C" and o.internal_only is True for o in observations)
    assert observations[0].payload["asnA"] == 1
    assert observations[0].payload["asnB"] == 2
    assert observations[0].payload["relation"] == 0
    assert observations[2].payload["relation"] == 1


# ── OpenIntelSensor (synthetic row iterator) ───────────────────────────


@pytest.fixture
def synthetic_openintel(monkeypatch):
    rows = [
        {"timestamp": 1716708823, "name": "example.com",
         "type": "A", "response_rdata": "203.0.113.1"},
        {"timestamp": 1716708824, "name": "example.org",
         "type": "TXT",
         "response_rdata": "ops contact: alice@example.com"},
    ]

    def fake_iter(_path):
        for r in rows:
            yield r

    monkeypatch.setattr(_oi_mod, "_iter_parquet_rows", fake_iter)
    return rows


def test_openintel_sensor_attaches_internal_only_and_redacts(
    tmp_path, synthetic_openintel
):
    subdir = tmp_path / "dns" / "openintel-tranco1m" / "snap-20260526"
    subdir.mkdir(parents=True)
    (subdir / "tranco1m-20260526.parquet").write_bytes(b"\x00")

    pins = StaticPinResolver(
        pins={
            "dns/openintel-tranco1m": DatasetPin(
                name="dns/openintel-tranco1m",
                revision="sha256:oi",
                cid_map_cid="bafy...",
                license="CC-BY-NC-4.0",
                tier="C",
                created_at="2026-05-26T00:00:00Z",
            )
        }
    )
    sensor = OpenIntelSensor(annex_root=tmp_path, pin_resolver=pins)
    pin = sensor.latest_pin()
    observations = list(sensor.stream(pin))
    assert len(observations) == 2
    assert all(o.tier == "C" and o.internal_only is True for o in observations)
    # Email in the second row's response_rdata should have been redacted.
    assert "alice@example.com" not in observations[1].payload["response_rdata"]


# ── TierGate + R9 backstop integration ─────────────────────────────────


def _make_tier_a_obs() -> SensorObservation:
    pin = DatasetPin(
        name="x", revision="r", cid_map_cid="c",
        license="public-domain-defacto", tier="A",
        created_at="2026-05-26T00:00:00Z",
    )
    return make_observation(sensor="x", tier="A", pin=pin, payload={"y": 1})


def _make_tier_c_obs() -> SensorObservation:
    pin = DatasetPin(
        name="dns/rapid7-sonar-fdns", revision="r", cid_map_cid="c",
        license="rapid7-research-use", tier="C",
        created_at="2026-05-26T00:00:00Z",
    )
    return make_observation(
        sensor="dns/rapid7-sonar-fdns", tier="C", pin=pin,
        payload={"name": "example.com", "type": "txt", "value": "v=spf1"},
    )


def test_tier_gate_passes_tier_a_to_external_sink():
    gate = TierGate(actor_did="did:web:etzhayyim.com:actor:test")
    seen: list[SensorObservation] = []
    routed = gate.guard(
        SinkClassification.EXTERNAL_FACING,
        sink_kind="public-ndjson",
        wrapped=seen.append,
    )
    routed(_make_tier_a_obs())
    assert len(seen) == 1
    assert gate.pop_leaks() == []


def test_tier_gate_drops_tier_c_at_external_sink_and_records_leak():
    gate = TierGate(actor_did="did:web:etzhayyim.com:actor:test")
    seen: list[SensorObservation] = []
    routed = gate.guard(
        SinkClassification.EXTERNAL_FACING,
        sink_kind="public-ndjson",
        wrapped=seen.append,
    )
    routed(_make_tier_c_obs())
    assert seen == []  # dropped, never reached the external sink
    leaks = gate.pop_leaks()
    assert len(leaks) == 1
    assert leaks[0].sensor == "dns/rapid7-sonar-fdns"
    assert leaks[0].tier == "C"
    assert leaks[0].sink_kind == "public-ndjson"
    assert leaks[0].actor_did == "did:web:etzhayyim.com:actor:test"


def test_tier_gate_passes_tier_c_to_internal_sink():
    gate = TierGate(actor_did="did:web:etzhayyim.com:actor:test")
    seen: list[SensorObservation] = []
    routed = gate.guard(
        SinkClassification.INTERNAL_ONLY,
        sink_kind="judah-litellm",
        wrapped=seen.append,
    )
    routed(_make_tier_c_obs())
    assert len(seen) == 1
    assert gate.pop_leaks() == []


def test_r9_leak_test_harness_full_chain():
    """Construct a tier-C obs → route to EXTERNAL_FACING sink → confirm
    TierGate dropped it AND R9 fires a critical KaizenProposal off the
    resulting LeakAttempt."""
    gate = TierGate(actor_did="did:web:etzhayyim.com:actor:test")
    routed = gate.guard(
        SinkClassification.EXTERNAL_FACING,
        sink_kind="public-ndjson",
        wrapped=lambda _obs: None,
    )
    # Step 1: leak attempt.
    routed(_make_tier_c_obs())
    leaks = gate.pop_leaks()
    assert len(leaks) == 1

    # Step 2: KaizenObserver Observation receives the leak attempts.
    obs = Observation(ts=0, leak_attempts=leaks)
    proposals = TierCLeakBackstopRule()(obs)
    assert len(proposals) == 1
    assert proposals[0].rule_id == "tier-c-leak"
    assert proposals[0].severity == "critical"
    assert "tier-C leak attempt" in proposals[0].summary
