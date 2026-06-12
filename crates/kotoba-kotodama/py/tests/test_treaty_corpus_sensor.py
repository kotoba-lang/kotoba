"""Tests for TreatyCorpusSensor (ADR-2605262800 — ``law/treaties/<corpus>``).

The Treaty family was Protocol-only (``LegalTreatySensor`` defined, no
concrete impl). This file ships + verifies the first concrete treaty
sensor as a passive ``LegalTreatySensor``:
  - corpus selector → canonical subdataset path (ADR §1 layout);
  - NDJSON row → LegalTreatyObservation field mapping (party_states ISO3);
  - body excerpt truncated to 2000 chars;
  - blank + malformed JSON lines skipped;
  - deterministic reservoir hot_sample on (pin.revision, n) (G9);
  - latest_pin() resolves via StaticPinResolver;
  - LegalTreatySensor Protocol conformance (runtime_checkable);
  - tier-A, internal_only never set (treaties are public by nature);
  - unknown corpus falls back to ``law/treaties/<corpus>``;
  - missing subdataset / snapshot / ndjson raise FileNotFoundError.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kotodama.organism.sensors.base import DatasetPin, StaticPinResolver
from kotodama.organism.sensors.legal.base import (
    LegalTreatyObservation,
    LegalTreatySensor,
)
from kotodama.organism.sensors.legal.treaty_corpus_sensor import TreatyCorpusSensor


def _write_snapshot(root: Path, name: str, rows: list[dict], *,
                    snapshot: str = "snap-20260601T000000Z",
                    raw_lines: list[str] | None = None) -> None:
    snap = root / name / snapshot
    snap.mkdir(parents=True, exist_ok=True)
    with (snap / "treaties.ndjson").open("w", encoding="utf-8") as f:
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


def _sensor(tmp_path: Path, corpus: str = "un-treaty") -> TreatyCorpusSensor:
    s = TreatyCorpusSensor(treaty_corpus=corpus)
    s.annex_root = tmp_path
    return s


def test_corpus_maps_to_canonical_subdataset_path():
    assert TreatyCorpusSensor("un-treaty").name == "law/treaties/un-treaty-collection"
    assert TreatyCorpusSensor("uncitral").name == "law/treaties/uncitral-instruments"
    assert TreatyCorpusSensor("wipo").name == "law/treaties/wipo-treaties"
    assert TreatyCorpusSensor("geneva").name == "law/treaties/geneva-conventions"


def test_unknown_corpus_falls_back_to_literal_path():
    assert TreatyCorpusSensor("some-w2-corpus").name == "law/treaties/some-w2-corpus"


def test_stream_maps_treaty_fields(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [
        {"treaty_id": "UNTS-12345", "title": "Vienna Convention on the Law of Treaties",
         "party_states": ["AUT", "USA", "JPN"], "in_force_at": "1980-01-27",
         "body": "Every treaty in force is binding upon the parties ..."},
    ])
    obs = list(s.stream(_pin(s.name)))
    assert len(obs) == 1
    o = obs[0]
    assert isinstance(o, LegalTreatyObservation)
    assert o.treaty_id == "UNTS-12345"
    assert o.title.startswith("Vienna Convention")
    assert o.party_states_iso3 == ("AUT", "USA", "JPN")
    assert o.in_force_at == "1980-01-27"
    assert o.body_excerpt.startswith("Every treaty in force")
    assert o.license_tag == "public-domain"
    assert o.tier == "A"
    assert o.internal_only is False  # treaties are public by nature


def test_body_excerpt_truncated_to_2000(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [
        {"treaty_id": "T1", "title": "t", "party_states": ["USA"], "body": "y" * 4096},
    ])
    o = list(s.stream(_pin(s.name)))[0]
    assert len(o.body_excerpt) == 2000


def test_blank_and_malformed_lines_skipped(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(
        tmp_path, s.name,
        [{"treaty_id": "T-OK", "title": "ok", "party_states": ["FRA"], "body": "b"}],
        raw_lines=["", "   ", "{bad json", "]["],
    )
    obs = list(s.stream(_pin(s.name)))
    assert [o.treaty_id for o in obs] == ["T-OK"]


def test_missing_optional_fields_default(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [{"treaty_id": "T-MIN"}])
    o = list(s.stream(_pin(s.name)))[0]
    assert o.treaty_id == "T-MIN"
    assert o.title == ""
    assert o.party_states_iso3 == ()
    assert o.in_force_at is None
    assert o.body_excerpt == ""


def test_hot_sample_deterministic_on_revision(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [
        {"treaty_id": f"T{i}", "title": f"t{i}", "party_states": ["USA"], "body": "b"}
        for i in range(30)
    ])
    pin = _pin(s.name)
    a = [o.treaty_id for o in s.hot_sample(pin, 6)]
    b = [o.treaty_id for o in s.hot_sample(pin, 6)]
    assert a == b and len(a) == 6


def test_hot_sample_varies_with_revision(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [
        {"treaty_id": f"T{i}", "title": f"t{i}", "party_states": ["USA"], "body": "b"}
        for i in range(50)
    ])
    a = [o.treaty_id for o in s.hot_sample(_pin(s.name, "rev-A"), 5)]
    b = [o.treaty_id for o in s.hot_sample(_pin(s.name, "rev-B"), 5)]
    assert a != b


def test_latest_pin_via_resolver(tmp_path):
    s = _sensor(tmp_path)
    pin = _pin(s.name, "rev-resolved")
    s.pin_resolver = StaticPinResolver(pins={s.name: pin})
    assert s.latest_pin().revision == "rev-resolved"


def test_latest_snapshot_dir_is_selected(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [{"treaty_id": "OLD"}],
                    snapshot="snap-20250101T000000Z")
    _write_snapshot(tmp_path, s.name, [{"treaty_id": "NEW"}],
                    snapshot="snap-20260601T000000Z")
    obs = list(s.stream(_pin(s.name)))
    assert [o.treaty_id for o in obs] == ["NEW"]


def test_protocol_conformance():
    assert isinstance(TreatyCorpusSensor("un-treaty"), LegalTreatySensor)


def test_missing_subdataset_raises(tmp_path):
    s = _sensor(tmp_path)
    with pytest.raises(FileNotFoundError):
        list(s.stream(_pin(s.name)))


def test_no_ndjson_in_snapshot_raises(tmp_path):
    s = _sensor(tmp_path)
    (tmp_path / s.name / "snap-empty").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        list(s.stream(_pin(s.name)))
