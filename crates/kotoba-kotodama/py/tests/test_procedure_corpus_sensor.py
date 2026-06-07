"""Tests for ProcedureCorpusSensor (ADR-2605262800 — ``law/procedures/<body>``).

The Procedure family was Protocol-only (``LegalProcedureSensor`` defined,
no concrete impl). This file ships + verifies the first concrete procedure
sensor as a passive ``LegalProcedureSensor``:
  - body selector → subdataset path (ADR §1 layout) + alias smoothing;
  - NDJSON row → LegalProcedureObservation field mapping;
  - procedure_class + jurisdiction propagate from the sensor;
  - steps excerpt truncated to 2000 chars;
  - blank + malformed JSON lines skipped;
  - deterministic reservoir hot_sample on (pin.revision, n) (G9);
  - latest_pin() resolves via StaticPinResolver;
  - LegalProcedureSensor Protocol conformance (runtime_checkable);
  - tier-A, internal_only never set;
  - missing subdataset / snapshot / ndjson raise FileNotFoundError.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kotodama.organism.sensors.base import DatasetPin, StaticPinResolver
from kotodama.organism.sensors.legal.base import (
    LegalProcedureObservation,
    LegalProcedureSensor,
)
from kotodama.organism.sensors.legal.procedure_corpus_sensor import (
    ProcedureCorpusSensor,
)


def _write_snapshot(root: Path, name: str, rows: list[dict], *,
                    snapshot: str = "snap-20260601T000000Z",
                    raw_lines: list[str] | None = None) -> None:
    snap = root / name / snapshot
    snap.mkdir(parents=True, exist_ok=True)
    with (snap / "procedures.ndjson").open("w", encoding="utf-8") as f:
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


def _sensor(tmp_path: Path, body: str = "us-federal-rules",
            iso3: str = "USA", cls: str = "judicial") -> ProcedureCorpusSensor:
    s = ProcedureCorpusSensor(
        procedural_body=body, jurisdiction_iso3=iso3, procedure_class=cls,  # type: ignore[arg-type]
    )
    s.annex_root = tmp_path
    return s


def test_body_maps_to_subdataset_path():
    s = ProcedureCorpusSensor(procedural_body="us-federal-rules", jurisdiction_iso3="USA")
    assert s.name == "law/procedures/us-federal-rules"
    assert ProcedureCorpusSensor("jp-koku-zei", "JPN").name == "law/procedures/jp-koku-zei"


def test_body_alias_smoothing():
    assert ProcedureCorpusSensor("us-cfr", "USA").name == "law/procedures/us-cfr-procedures"
    assert (ProcedureCorpusSensor("international-arbitration", "INT").name
            == "law/procedures/international-arbitration-rules")


def test_unknown_body_falls_back_to_literal():
    assert ProcedureCorpusSensor("w2-body", "USA").name == "law/procedures/w2-body"


def test_stream_maps_procedure_fields(tmp_path):
    s = _sensor(tmp_path, body="uk-gov-procedures", iso3="GBR", cls="administrative")
    _write_snapshot(tmp_path, s.name, [
        {"procedure_id": "GOVUK-register-birth",
         "title": "Register a birth",
         "steps": "1. Make an appointment. 2. Bring documents. 3. Register."},
    ])
    obs = list(s.stream(_pin(s.name)))
    assert len(obs) == 1
    o = obs[0]
    assert isinstance(o, LegalProcedureObservation)
    assert o.procedure_id == "GOVUK-register-birth"
    assert o.title == "Register a birth"
    assert o.steps_excerpt.startswith("1. Make an appointment")
    assert o.jurisdiction_iso3 == "GBR"
    assert o.procedure_class == "administrative"
    assert o.license_tag == "public-domain"
    assert o.tier == "A"
    assert o.internal_only is False


def test_procedure_class_propagates(tmp_path):
    s = _sensor(tmp_path, body="jp-koku-zei", iso3="JPN", cls="tax")
    _write_snapshot(tmp_path, s.name, [{"procedure_id": "通達-1", "title": "t", "steps": "s"}])
    o = list(s.stream(_pin(s.name)))[0]
    assert o.procedure_class == "tax"
    assert o.jurisdiction_iso3 == "JPN"


def test_steps_excerpt_truncated_to_2000(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [
        {"procedure_id": "P1", "title": "t", "steps": "z" * 4096},
    ])
    o = list(s.stream(_pin(s.name)))[0]
    assert len(o.steps_excerpt) == 2000


def test_blank_and_malformed_lines_skipped(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(
        tmp_path, s.name,
        [{"procedure_id": "P-OK", "title": "ok", "steps": "s"}],
        raw_lines=["", "   ", "{bad", "}{"],
    )
    obs = list(s.stream(_pin(s.name)))
    assert [o.procedure_id for o in obs] == ["P-OK"]


def test_missing_optional_fields_default(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [{"procedure_id": "P-MIN"}])
    o = list(s.stream(_pin(s.name)))[0]
    assert o.procedure_id == "P-MIN"
    assert o.title == ""
    assert o.steps_excerpt == ""


def test_hot_sample_deterministic_on_revision(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [
        {"procedure_id": f"P{i}", "title": f"t{i}", "steps": "s"} for i in range(30)
    ])
    pin = _pin(s.name)
    a = [o.procedure_id for o in s.hot_sample(pin, 6)]
    b = [o.procedure_id for o in s.hot_sample(pin, 6)]
    assert a == b and len(a) == 6


def test_hot_sample_varies_with_revision(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [
        {"procedure_id": f"P{i}", "title": f"t{i}", "steps": "s"} for i in range(50)
    ])
    a = [o.procedure_id for o in s.hot_sample(_pin(s.name, "rev-A"), 5)]
    b = [o.procedure_id for o in s.hot_sample(_pin(s.name, "rev-B"), 5)]
    assert a != b


def test_latest_pin_via_resolver(tmp_path):
    s = _sensor(tmp_path)
    pin = _pin(s.name, "rev-resolved")
    s.pin_resolver = StaticPinResolver(pins={s.name: pin})
    assert s.latest_pin().revision == "rev-resolved"


def test_latest_snapshot_dir_is_selected(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [{"procedure_id": "OLD"}],
                    snapshot="snap-20250101T000000Z")
    _write_snapshot(tmp_path, s.name, [{"procedure_id": "NEW"}],
                    snapshot="snap-20260601T000000Z")
    obs = list(s.stream(_pin(s.name)))
    assert [o.procedure_id for o in obs] == ["NEW"]


def test_protocol_conformance():
    assert isinstance(
        ProcedureCorpusSensor("us-federal-rules", "USA"), LegalProcedureSensor
    )


def test_missing_subdataset_raises(tmp_path):
    s = _sensor(tmp_path)
    with pytest.raises(FileNotFoundError):
        list(s.stream(_pin(s.name)))


def test_no_ndjson_in_snapshot_raises(tmp_path):
    s = _sensor(tmp_path)
    (tmp_path / s.name / "snap-empty").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        list(s.stream(_pin(s.name)))
