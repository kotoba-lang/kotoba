"""Tests for UsUscSensor (ADR-2605262800 — ``law/statutes/us-usc``).

UsUscSensor was implemented at W1 but had no test coverage. This file
verifies its constitutional discipline as a LegalStatuteSensor:
  - passive NDJSON ingestion → LegalStatuteObservation field mapping;
  - body excerpt truncated to 2000 chars (bounded sample);
  - blank + malformed JSON lines are skipped (robust ingestion);
  - deterministic reservoir hot_sample on (pin.revision, n) (G9);
  - latest_pin() resolves via StaticPinResolver (W1 pin path);
  - LegalStatuteSensor Protocol conformance (runtime_checkable);
  - tier-A observation never sets internal_only (G4);
  - missing subdataset / snapshot / ndjson raise FileNotFoundError.
"""

from __future__ import annotations

import json
from pathlib import Path

from kotodama.organism.sensors.base import DatasetPin, StaticPinResolver
from kotodama.organism.sensors.legal.base import (
    LegalStatuteObservation,
    LegalStatuteSensor,
)
from kotodama.organism.sensors.legal.us_usc_sensor import UsUscSensor


def _write_snapshot(root: Path, name: str, rows: list[dict], *,
                    snapshot: str = "snap-20260601T000000Z",
                    raw_lines: list[str] | None = None) -> None:
    snap = root / name / snapshot
    snap.mkdir(parents=True, exist_ok=True)
    with (snap / "us-usc.ndjson").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
        for line in raw_lines or []:
            f.write(line + "\n")


def _pin(name: str, revision: str = "rev-1") -> DatasetPin:
    return DatasetPin(
        name=name,
        revision=revision,
        cid_map_cid="bafyTEST",
        license="public-domain",
        tier="A",
        created_at="2026-06-01T00:00:00Z",
    )


def _sensor(tmp_path: Path) -> UsUscSensor:
    s = UsUscSensor()
    s.annex_root = tmp_path
    return s


def test_stream_maps_statute_fields(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [
        {"citation": "17 U.S.C. § 106", "title": "Exclusive rights in copyrighted works",
         "body": "Subject to sections 107 through 122 ...",
         "in_force_at": "2025-01-01"},
    ])
    obs = list(s.stream(_pin(s.name)))
    assert len(obs) == 1
    o = obs[0]
    assert isinstance(o, LegalStatuteObservation)
    assert o.citation == "17 U.S.C. § 106"
    assert o.title == "Exclusive rights in copyrighted works"
    assert o.body_excerpt.startswith("Subject to sections")
    assert o.jurisdiction_iso3 == "USA"
    assert o.statute_class == "code"
    assert o.in_force_at == "2025-01-01"
    assert o.license_tag == "public-domain"
    assert o.tier == "A"
    assert o.internal_only is False  # G4: tier-A statutes are publishable


def test_body_excerpt_truncated_to_2000(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [
        {"citation": "1 U.S.C. § 1", "title": "Words denoting number",
         "body": "x" * 5000},
    ])
    o = list(s.stream(_pin(s.name)))[0]
    assert len(o.body_excerpt) == 2000


def test_blank_and_malformed_lines_skipped(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(
        tmp_path, s.name,
        [{"citation": "5 U.S.C. § 552", "title": "FOIA", "body": "public records"}],
        raw_lines=["", "   ", "{not valid json", "}{"],
    )
    obs = list(s.stream(_pin(s.name)))
    assert len(obs) == 1
    assert obs[0].citation == "5 U.S.C. § 552"


def test_missing_optional_fields_default_empty(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [{"citation": "26 U.S.C. § 1"}])
    o = list(s.stream(_pin(s.name)))[0]
    assert o.citation == "26 U.S.C. § 1"
    assert o.title == ""
    assert o.body_excerpt == ""
    assert o.in_force_at is None


def test_hot_sample_deterministic_on_revision(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [
        {"citation": f"{i} U.S.C. § 1", "title": f"t{i}", "body": "b"}
        for i in range(30)
    ])
    pin = _pin(s.name)
    a = [o.citation for o in s.hot_sample(pin, 7)]
    b = [o.citation for o in s.hot_sample(pin, 7)]
    assert a == b and len(a) == 7


def test_hot_sample_varies_with_revision(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [
        {"citation": f"{i} U.S.C. § 1", "title": f"t{i}", "body": "b"}
        for i in range(50)
    ])
    a = [o.citation for o in s.hot_sample(_pin(s.name, "rev-A"), 5)]
    b = [o.citation for o in s.hot_sample(_pin(s.name, "rev-B"), 5)]
    # Different revision seeds → different reservoir (overwhelmingly likely
    # at n=5 over 50 rows); guards against a constant-seed regression.
    assert a != b


def test_latest_pin_via_resolver(tmp_path):
    s = _sensor(tmp_path)
    pin = _pin(s.name, "rev-resolved")
    s.pin_resolver = StaticPinResolver(pins={s.name: pin})
    assert s.latest_pin().revision == "rev-resolved"


def test_latest_snapshot_dir_is_selected(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [{"citation": "OLD"}],
                    snapshot="snap-20250101T000000Z")
    _write_snapshot(tmp_path, s.name, [{"citation": "NEW"}],
                    snapshot="snap-20260601T000000Z")
    obs = list(s.stream(_pin(s.name)))
    assert [o.citation for o in obs] == ["NEW"]  # reverse-sorted → newest dir


def test_protocol_conformance():
    assert isinstance(UsUscSensor(), LegalStatuteSensor)


def test_missing_subdataset_raises(tmp_path):
    s = _sensor(tmp_path)  # nothing written
    import pytest
    with pytest.raises(FileNotFoundError):
        list(s.stream(_pin(s.name)))


def test_no_ndjson_in_snapshot_raises(tmp_path):
    s = _sensor(tmp_path)
    (tmp_path / s.name / "snap-empty").mkdir(parents=True)
    import pytest
    with pytest.raises(FileNotFoundError):
        list(s.stream(_pin(s.name)))
