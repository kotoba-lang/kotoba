"""Tests for JudiciaryCorpusSensor (ADR-2605302345 §D4/§D5/§D6).

Verifies the constitutional discipline of the global judiciary corpus sensor:
  - passive NDJSON ingestion + deterministic hot_sample (G9);
  - D6 pseudonymization via JudicialPartyRedactor;
  - §D4 sealed/juvenile exclusion (REJECT_IF_NON_ANONYMIZED court systems);
  - G19: observations carry no judge field / no analytics surface.
"""

from __future__ import annotations

import json
from pathlib import Path

from kotodama.organism.sensors.base import DatasetPin
from kotodama.organism.sensors.legal.base import LegalCaseObservation
from kotodama.organism.sensors.legal.judiciary_corpus_sensor import (
    JudiciaryCorpusSensor,
)


def _write_snapshot(root: Path, name: str, rows: list[dict]) -> None:
    snap = root / name / "snap-20260530T000000Z"
    snap.mkdir(parents=True, exist_ok=True)
    with (snap / "cases.ndjson").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _pin(name: str) -> DatasetPin:
    return DatasetPin(
        name=name,
        revision="rev-1",
        cid_map_cid="bafyTEST",
        license="court-published-public-record",
        tier="A",
        created_at="2026-05-30T00:00:00Z",
    )


def _sensor(tmp_path: Path, court_system: str, iso3: str) -> JudiciaryCorpusSensor:
    s = JudiciaryCorpusSensor(court_system=court_system, jurisdiction_iso3=iso3)
    s.annex_root = tmp_path
    return s


def test_passthrough_jurisdiction_keeps_parties(tmp_path):
    s = _sensor(tmp_path, court_system="us-district", iso3="USA")
    _write_snapshot(tmp_path, s.name, [
        {"citation": "1 F.Supp. 1", "court": "D. Mass.",
         "decision_date": "2025-01-02", "parties": ["Alice Co", "Bob LLC"],
         "holding": "summary judgment denied", "upstream_anonymized": False},
    ])
    obs = list(s.stream(_pin(s.name)))
    assert len(obs) == 1
    assert isinstance(obs[0], LegalCaseObservation)
    assert obs[0].parties_redacted == ("Alice Co", "Bob LLC")  # USA = PASS_THROUGH


def test_pseudonymized_jurisdiction_trusts_upstream(tmp_path):
    # FRA = PASS_THROUGH_PSEUDONYMIZED (upstream already pseudonymized, art.33).
    s = _sensor(tmp_path, court_system="fr-cassation", iso3="FRA")
    _write_snapshot(tmp_path, s.name, [
        {"citation": "Cass. civ. 1, n°25-001", "court": "Cour de cassation",
         "decision_date": "2025-05-07", "parties": ["M. X", "Mme Y"],
         "holding": "pourvoi rejeté", "upstream_anonymized": True},
    ])
    obs = list(s.stream(_pin(s.name)))
    assert len(obs) == 1
    assert obs[0].parties_redacted == ("M. X", "Mme Y")


def test_juvenile_court_non_anonymized_is_dropped(tmp_path):
    # jp-juvenile-court = REJECT_IF_NON_ANONYMIZED — §D4 sealed/juvenile exclusion.
    s = _sensor(tmp_path, court_system="jp-juvenile-court", iso3="JPN")
    _write_snapshot(tmp_path, s.name, [
        {"citation": "家裁 2025-001", "court": "家庭裁判所",
         "decision_date": "2025-03-01", "parties": ["少年A", "保護者B"],
         "holding": "保護処分", "upstream_anonymized": False},  # not anonymized → DROP
        {"citation": "家裁 2025-002", "court": "家庭裁判所",
         "decision_date": "2025-03-02", "parties": ["[匿名]"],
         "holding": "保護処分", "upstream_anonymized": True},   # anonymized → keep
    ])
    obs = list(s.stream(_pin(s.name)))
    assert len(obs) == 1                       # the non-anonymized juvenile case is dropped
    assert obs[0].citation == "家裁 2025-002"


def test_g19_observation_has_no_judge_analytics_surface(tmp_path):
    s = _sensor(tmp_path, court_system="us-district", iso3="USA")
    _write_snapshot(tmp_path, s.name, [
        {"citation": "1 F.Supp. 2", "court": "D. Mass.",
         "decision_date": "2025-01-03", "parties": ["X"], "holding": "h",
         # even if upstream rows carried judge scoring, the observation cannot:
         "judge": "Hon. Foo", "winRate": 0.9},
    ])
    obs = list(s.stream(_pin(s.name)))[0]
    fields = set(vars(obs).keys())
    for forbidden in ("judge", "winRate", "rulingPrediction", "leanScore"):
        assert forbidden not in fields, f"G19: {forbidden} must not be representable"


def test_hot_sample_deterministic(tmp_path):
    s = _sensor(tmp_path, court_system="us-district", iso3="USA")
    _write_snapshot(tmp_path, s.name, [
        {"citation": f"{i} F.Supp. 1", "court": "D. Mass.",
         "decision_date": "2025-01-02", "parties": [f"P{i}"], "holding": "h",
         "upstream_anonymized": False}
        for i in range(20)
    ])
    pin = _pin(s.name)
    a = [o.citation for o in s.hot_sample(pin, 5)]
    b = [o.citation for o in s.hot_sample(pin, 5)]
    assert a == b and len(a) == 5
