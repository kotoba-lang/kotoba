"""Tests for TemplateCorpusSensor (ADR-2605262800 — ``law/templates/<corpus>``).

The Template family was Protocol-only (``LegalTemplateSensor`` defined, no
concrete impl). This file ships + verifies the first concrete template
sensor, completing all 5 legal sensor families:
  - corpus selector → canonical subdataset path (ADR §1 layout);
  - NDJSON row → LegalTemplateObservation field mapping;
  - FULL body retained (chigiri instantiates the whole template — NOT a
    2000-char excerpt like statute/case/treaty/procedure);
  - per-row jurisdiction + chigiri_cell override sensor defaults;
  - blank + malformed JSON lines skipped;
  - deterministic reservoir hot_sample on (pin.revision, n) (G9);
  - latest_pin() resolves via StaticPinResolver;
  - LegalTemplateSensor Protocol conformance (runtime_checkable);
  - tier-A, internal_only never set;
  - missing subdataset / snapshot / ndjson raise FileNotFoundError.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kotodama.organism.sensors.base import DatasetPin, StaticPinResolver
from kotodama.organism.sensors.legal.base import (
    LegalTemplateObservation,
    LegalTemplateSensor,
)
from kotodama.organism.sensors.legal.template_corpus_sensor import (
    TemplateCorpusSensor,
)


def _write_snapshot(root: Path, name: str, rows: list[dict], *,
                    snapshot: str = "snap-20260601T000000Z",
                    raw_lines: list[str] | None = None) -> None:
    snap = root / name / snapshot
    snap.mkdir(parents=True, exist_ok=True)
    with (snap / "templates.ndjson").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
        for line in raw_lines or []:
            f.write(line + "\n")


def _pin(name: str, revision: str = "rev-1") -> DatasetPin:
    return DatasetPin(
        name=name,
        revision=revision,
        cid_map_cid="bafyTEST",
        license="open",
        tier="A",
        created_at="2026-06-01T00:00:00Z",
    )


def _sensor(tmp_path: Path, corpus: str = "apache-licenses",
            cls: str = "license", **kw) -> TemplateCorpusSensor:
    s = TemplateCorpusSensor(template_corpus=corpus, template_class=cls, **kw)  # type: ignore[arg-type]
    s.annex_root = tmp_path
    return s


def test_corpus_maps_to_canonical_subdataset_path():
    assert TemplateCorpusSensor("apache-licenses").name == "law/templates/apache-2.0-licenses"
    assert TemplateCorpusSensor("cc-licenses").name == "law/templates/creative-commons-licenses"
    assert TemplateCorpusSensor("charter-rider").name == "law/templates/etzhayyim-charter-rider"
    assert TemplateCorpusSensor("data-privacy-dsar").name == "law/templates/data-privacy-dsar"


def test_unknown_corpus_falls_back_to_literal():
    assert TemplateCorpusSensor("w2-corpus").name == "law/templates/w2-corpus"


def test_stream_retains_full_body(tmp_path):
    # Unlike other legal families, templates keep the FULL body (no excerpt).
    s = _sensor(tmp_path)
    big = "Apache License Version 2.0 " * 500  # > 2000 chars
    _write_snapshot(tmp_path, s.name, [
        {"template_id": "apache-2.0", "title": "Apache License 2.0", "body": big},
    ])
    o = list(s.stream(_pin(s.name)))[0]
    assert isinstance(o, LegalTemplateObservation)
    assert o.body == big                 # full body, not truncated
    assert len(o.body) > 2000
    assert o.template_class == "license"
    assert o.tier == "A"
    assert o.internal_only is False


def test_sensor_level_jurisdiction_and_hint(tmp_path):
    s = _sensor(tmp_path, corpus="covenant-ceremony", cls="ceremony",
                chigiri_consumer_cell_hint="chigiri.covenant")
    _write_snapshot(tmp_path, s.name, [{"template_id": "vow-1", "title": "Vow", "body": "..."}])
    o = list(s.stream(_pin(s.name)))[0]
    assert o.template_class == "ceremony"
    assert o.jurisdiction_iso3 is None              # ceremony templates are jurisdiction-agnostic
    assert o.chigiri_consumer_cell_hint == "chigiri.covenant"


def test_per_row_jurisdiction_and_cell_override(tmp_path):
    # A tax-receipt corpus spans jurisdictions — the row wins over the default.
    s = _sensor(tmp_path, corpus="donation-tax-receipt", cls="tax-receipt",
                jurisdiction_iso3=None, chigiri_consumer_cell_hint="chigiri.taxreceipt")
    _write_snapshot(tmp_path, s.name, [
        {"template_id": "jp-receipt", "title": "寄附金受領証明書", "body": "...",
         "jurisdiction": "JPN", "chigiri_cell": "chigiri.jp.taxreceipt"},
    ])
    o = list(s.stream(_pin(s.name)))[0]
    assert o.jurisdiction_iso3 == "JPN"
    assert o.chigiri_consumer_cell_hint == "chigiri.jp.taxreceipt"


def test_blank_and_malformed_lines_skipped(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(
        tmp_path, s.name,
        [{"template_id": "T-OK", "title": "ok", "body": "b"}],
        raw_lines=["", "   ", "{bad", "}{"],
    )
    obs = list(s.stream(_pin(s.name)))
    assert [o.template_id for o in obs] == ["T-OK"]


def test_missing_optional_fields_default(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [{"template_id": "T-MIN"}])
    o = list(s.stream(_pin(s.name)))[0]
    assert o.template_id == "T-MIN"
    assert o.title == ""
    assert o.body == ""
    assert o.jurisdiction_iso3 is None
    assert o.chigiri_consumer_cell_hint is None


def test_hot_sample_deterministic_on_revision(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [
        {"template_id": f"T{i}", "title": f"t{i}", "body": "b"} for i in range(30)
    ])
    pin = _pin(s.name)
    a = [o.template_id for o in s.hot_sample(pin, 6)]
    b = [o.template_id for o in s.hot_sample(pin, 6)]
    assert a == b and len(a) == 6


def test_hot_sample_varies_with_revision(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [
        {"template_id": f"T{i}", "title": f"t{i}", "body": "b"} for i in range(50)
    ])
    a = [o.template_id for o in s.hot_sample(_pin(s.name, "rev-A"), 5)]
    b = [o.template_id for o in s.hot_sample(_pin(s.name, "rev-B"), 5)]
    assert a != b


def test_latest_pin_via_resolver(tmp_path):
    s = _sensor(tmp_path)
    pin = _pin(s.name, "rev-resolved")
    s.pin_resolver = StaticPinResolver(pins={s.name: pin})
    assert s.latest_pin().revision == "rev-resolved"


def test_latest_snapshot_dir_is_selected(tmp_path):
    s = _sensor(tmp_path)
    _write_snapshot(tmp_path, s.name, [{"template_id": "OLD"}],
                    snapshot="snap-20250101T000000Z")
    _write_snapshot(tmp_path, s.name, [{"template_id": "NEW"}],
                    snapshot="snap-20260601T000000Z")
    obs = list(s.stream(_pin(s.name)))
    assert [o.template_id for o in obs] == ["NEW"]


def test_protocol_conformance():
    assert isinstance(TemplateCorpusSensor("apache-licenses"), LegalTemplateSensor)


def test_missing_subdataset_raises(tmp_path):
    s = _sensor(tmp_path)
    with pytest.raises(FileNotFoundError):
        list(s.stream(_pin(s.name)))


def test_no_ndjson_in_snapshot_raises(tmp_path):
    s = _sensor(tmp_path)
    (tmp_path / s.name / "snap-empty").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        list(s.stream(_pin(s.name)))
