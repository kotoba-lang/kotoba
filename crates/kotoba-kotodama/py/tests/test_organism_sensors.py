"""Tests for kotodama.organism.sensors.* (ADR-2605262400 W1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kotodama.organism.kaizen import (
    CharterFalsePositiveRateRule,
    LeakAttempt,
    Observation,
    RULE_REGISTRY,
    SensorHealth,
    StaleSensorPinRule,
    TierCLeakBackstopRule,
)
from kotodama.organism.sensors import (
    DatasetPin,
    Geolite2Sensor,
    PiiFilterPolicy,
    RirDelegatedSensor,
    SensorObservation,
    StaticPinResolver,
    make_observation,
    redact_emails,
    redact_payload,
    redact_phones,
    redact_postal,
    redact_text,
    redact_whois_values,
)


# ── DatasetSensor base contract ────────────────────────────────────────


def test_make_observation_attaches_internal_only_for_tier_c():
    pin = DatasetPin(
        name="dns/rapid7-sonar-fdns",
        revision="sha256:abc",
        cid_map_cid="bafy...",
        license="research-use",
        tier="C",
        created_at="2026-05-26T00:00:00Z",
    )
    obs = make_observation(
        sensor="dns/rapid7-sonar-fdns",
        tier="C",
        pin=pin,
        payload={"q": "example.com"},
    )
    assert obs.internal_only is True
    assert obs.tier == "C"


def test_make_observation_tier_a_is_external_safe():
    pin = DatasetPin(
        name="netreg/rir-delegated/apnic",
        revision="sha256:def",
        cid_map_cid="bafy...",
        license="public-domain-defacto",
        tier="A",
        created_at="2026-05-26T00:00:00Z",
    )
    obs = make_observation(
        sensor="netreg/rir-delegated/apnic",
        tier="A",
        pin=pin,
        payload={"prefix": "1.0.0.0/24"},
    )
    assert obs.internal_only is False


def test_with_internal_only_flag_can_be_promoted():
    pin = DatasetPin(
        name="any",
        revision="r",
        cid_map_cid="bafy",
        license="X",
        tier="A",
        created_at="t",
    )
    obs = make_observation(sensor="any", tier="A", pin=pin, payload={})
    promoted = obs.with_internal_only(True)
    assert promoted.internal_only is True
    assert obs.internal_only is False


# ── PII filter ─────────────────────────────────────────────────────────


def test_redact_emails_simple():
    out = redact_emails("contact alice@example.com if needed")
    assert "alice@example.com" not in out
    assert "[redacted-pii]" in out


def test_redact_phones_e164():
    out = redact_phones("call +1-415-555-2671 today")
    assert "+1-415-555-2671" not in out
    assert "[redacted-pii]" in out


def test_redact_whois_values_keeps_key():
    raw = "registrant: John Doe\ntech-c: tech@example.com\nstatus: active"
    out = redact_whois_values(raw)
    assert "registrant: [redacted-pii]" in out
    assert "tech-c: [redacted-pii]" in out
    assert "status: active" in out


def test_redact_postal_us_pattern():
    raw = "1600 Pennsylvania Ave NW, Washington, 20500, US"
    out = redact_postal(raw)
    assert "[redacted-pii]" in out
    assert "1600 Pennsylvania" not in out


def test_redact_text_pipeline_strict():
    raw = (
        "Contact: registrant: alice@example.com\n"
        "Phone: +1-415-555-2671\n"
        "Office: 1600 Pennsylvania Ave NW, Washington, 20500, US"
    )
    out, stats = redact_text(raw, policy=PiiFilterPolicy.STRICT)
    assert "alice@example.com" not in out
    assert "+1-415-555-2671" not in out
    assert "1600 Pennsylvania" not in out
    assert stats.total >= 3


def test_redact_text_off_policy_is_passthrough():
    raw = "alice@example.com +1-415-555-2671"
    out, stats = redact_text(raw, policy=PiiFilterPolicy.OFF)
    assert out == raw
    assert stats.total == 0


def test_redact_payload_only_named_fields():
    payload = {
        "email": "alice@example.com",
        "phone": "+1-415-555-2671",
        "country": "JP",
    }
    out, stats = redact_payload(payload, fields=["email", "phone"])
    assert out["email"] == "[redacted-pii]"
    assert out["phone"] == "[redacted-pii]"
    assert out["country"] == "JP"
    assert stats.emails == 1
    assert stats.phones == 1


# ── RirDelegatedSensor ─────────────────────────────────────────────────


def _make_rir_snapshot(tmp_path: Path, rir: str, rows: list[dict]) -> Path:
    subdir = tmp_path / "netreg" / "rir-delegated" / rir / "rir-delegated-snap-260526"
    subdir.mkdir(parents=True, exist_ok=True)
    ndjson_path = subdir / f"delegated-{rir}-extended-latest.ndjson"
    with ndjson_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return tmp_path


def test_rir_sensor_stream_yields_observations(tmp_path):
    annex_root = _make_rir_snapshot(
        tmp_path,
        "apnic",
        [
            {"registry": "apnic", "cc": "JP", "type": "ipv4",
             "start": "1.0.0.0", "value": 256, "date": "20200101",
             "status": "allocated", "opaqueId": "A0001"},
            {"registry": "apnic", "cc": "KR", "type": "asn",
             "start": "9924", "value": 1, "date": "20100101",
             "status": "assigned", "opaqueId": "A0002"},
        ],
    )
    pins = StaticPinResolver(
        pins={
            "netreg/rir-delegated/apnic": DatasetPin(
                name="netreg/rir-delegated/apnic",
                revision="sha256:fixed",
                cid_map_cid="bafy...",
                license="public-domain-defacto",
                tier="A",
                created_at="2026-05-26T00:00:00Z",
            )
        }
    )
    sensor = RirDelegatedSensor(
        name="netreg/rir-delegated/apnic",
        annex_root=annex_root,
        pin_resolver=pins,
    )
    pin = sensor.latest_pin()
    observations = list(sensor.stream(pin))
    assert len(observations) == 2
    assert all(isinstance(o, SensorObservation) for o in observations)
    assert observations[0].tier == "A"
    assert observations[0].internal_only is False
    assert observations[0].payload["registry"] == "apnic"
    assert observations[0].payload["cc"] == "JP"


def test_rir_sensor_hot_sample_deterministic(tmp_path):
    annex_root = _make_rir_snapshot(
        tmp_path,
        "ripe",
        [
            {"registry": "ripe", "cc": "DE", "type": "ipv4",
             "start": "10.0.0.0", "value": i,
             "date": "20200101", "status": "allocated"}
            for i in range(50)
        ],
    )
    pins = StaticPinResolver(
        pins={
            "netreg/rir-delegated/ripe": DatasetPin(
                name="netreg/rir-delegated/ripe",
                revision="sha256:fixed",
                cid_map_cid="bafy...",
                license="public-domain-defacto",
                tier="A",
                created_at="2026-05-26T00:00:00Z",
            )
        }
    )
    sensor = RirDelegatedSensor(
        name="netreg/rir-delegated/ripe",
        annex_root=annex_root,
        pin_resolver=pins,
    )
    pin = sensor.latest_pin()
    s1 = sensor.hot_sample(pin, 5)
    s2 = sensor.hot_sample(pin, 5)
    assert [o.payload["value"] for o in s1] == [o.payload["value"] for o in s2]
    assert len(s1) == 5


# ── Kaizen R7/R8/R9 rules ──────────────────────────────────────────────


def test_three_new_rules_registered():
    expected = {"stale-sensor-pin", "charter-fail-rate", "tier-c-leak"}
    assert expected <= set(RULE_REGISTRY.keys())


def test_r7_stale_pin_fires_when_pin_age_over_4x_cadence():
    now_ms = 5 * 3600 * 1000
    obs = Observation(
        ts=now_ms,
        sensors=[
            SensorHealth(
                name="netreg/rir-delegated/apnic",
                tier="A",
                license="public-domain-defacto",
                refresh_cadence_sec=3600,
                latest_pin_created_at_ms=0,
            )
        ],
    )
    proposals = StaleSensorPinRule()(obs)
    assert len(proposals) == 1
    assert proposals[0].rule_id == "stale-sensor-pin"
    assert proposals[0].severity == "warn"


def test_r7_does_not_fire_when_pin_fresh():
    now_ms = 1 * 3600 * 1000
    obs = Observation(
        ts=now_ms,
        sensors=[
            SensorHealth(
                name="netreg/rir-delegated/apnic",
                tier="A",
                license="public-domain-defacto",
                refresh_cadence_sec=3600,
                latest_pin_created_at_ms=now_ms - 1800 * 1000,
            )
        ],
    )
    proposals = StaleSensorPinRule()(obs)
    assert proposals == []


def test_r8_charter_fp_rate_over_5pct_fires():
    obs = Observation(
        ts=0,
        sensors=[
            SensorHealth(
                name="dns/rapid7-sonar-fdns",
                tier="C",
                license="research-use",
                refresh_cadence_sec=30 * 24 * 3600,
                last_charter_fp_count=15,
                last_charter_total_count=200,
            )
        ],
    )
    proposals = CharterFalsePositiveRateRule()(obs)
    assert len(proposals) == 1
    assert proposals[0].rule_id == "charter-fail-rate"
    assert proposals[0].severity == "warn"


def test_r8_does_not_fire_under_threshold():
    obs = Observation(
        ts=0,
        sensors=[
            SensorHealth(
                name="dns/rapid7-sonar-fdns",
                tier="C",
                license="research-use",
                refresh_cadence_sec=30 * 24 * 3600,
                last_charter_fp_count=5,
                last_charter_total_count=200,
            )
        ],
    )
    assert CharterFalsePositiveRateRule()(obs) == []


def test_r9_tier_c_leak_fires_critical():
    obs = Observation(
        ts=0,
        leak_attempts=[
            LeakAttempt(
                sensor="dns/rapid7-sonar-fdns",
                tier="C",
                sink_kind="social-post",
                actor_did="did:web:etzhayyim.com:actor:test",
                ts_ms=1000,
                detail="forbidden sink reached",
            )
        ],
    )
    proposals = TierCLeakBackstopRule()(obs)
    assert len(proposals) == 1
    assert proposals[0].rule_id == "tier-c-leak"
    assert proposals[0].severity == "critical"
    assert "tier-C leak attempt" in proposals[0].summary


def test_r9_does_not_fire_on_tier_a_attempts():
    """R9 is constitutional backstop; only tier-C triggers it."""
    obs = Observation(
        ts=0,
        leak_attempts=[
            LeakAttempt(
                sensor="netreg/rir-delegated/apnic",
                tier="A",
                sink_kind="social-post",
                actor_did="did:web:etzhayyim.com:actor:test",
                ts_ms=1000,
            )
        ],
    )
    assert TierCLeakBackstopRule()(obs) == []
