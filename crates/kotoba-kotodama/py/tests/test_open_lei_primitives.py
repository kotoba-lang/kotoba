from __future__ import annotations

import importlib.util as _ilu
import asyncio
import sys
from pathlib import Path as _P


ROOT = _P(__file__).resolve().parents[1] / "src" / "kotodama"


def _load(name: str, rel: str):
    spec = _ilu.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = _ilu.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


open_lei = _load("_open_lei_primitives", "primitives/open_lei.py")


def test_gleif_manifest_and_bulk_collect_plan_cover_global_datasets():
    manifest = open_lei.gleif_manifest_plan(as_of_date="2026-04-25")["openLeiGleifManifestPlan"]
    collect = open_lei.gleif_bulk_collect(
        dataset_kind="lei-cdf",
        as_of_date="2026-04-25",
        shard=2,
        shard_count=16,
    )["openLeiGleifBulkCollect"]
    assert [dataset["datasetKind"] for dataset in manifest["datasets"]] == ["lei-cdf", "rr-cdf", "reporting-exception"]
    assert collect["source"]["apiEndpoint"] == "https://api.gleif.org/api/v1/lei-records"
    assert "vertex_open_lei_entity" in collect["targetTables"]
    assert collect["fetchMode"] == "plan"


def test_gleif_bulk_collect_fetches_lei_cdf_page(monkeypatch):
    record = {"id": "529900T8BM49AURSDO55", "attributes": {"lei": "529900T8BM49AURSDO55"}}

    def fake_fetch(*, page_number: int, page_size: int):
        assert page_number == 3
        assert page_size == 50
        return [record], "abc123", 42

    monkeypatch.setattr(open_lei, "_fetch_lei_cdf_page", fake_fetch)

    collect = open_lei.gleif_bulk_collect(
        dataset_kind="lei-cdf",
        as_of_date="2026-04-25",
        shard=2,
        shard_count=16,
        page_size=50,
        fetch=True,
    )["openLeiGleifBulkCollect"]

    assert collect["fetchMode"] == "api-page"
    assert collect["pageNumber"] == 3
    assert collect["sourceCount"] == 1
    assert collect["records"] == [record]
    assert collect["sha256"] == "abc123"


def test_gleif_record_normalize_and_ems_match():
    record = {
        "id": "529900T8BM49AURSDO55",
        "attributes": {
            "lei": "529900T8BM49AURSDO55",
            "entity": {
                "legalName": {"name": "Example Electronics Manufacturing Ltd"},
                "legalAddress": {"country": "JP"},
                "legalForm": {"id": "KABU"},
                "registeredAt": {"id": "RA000001"},
            },
            "registration": {
                "status": "ISSUED",
                "initialRegistrationDate": "2026-01-01T00:00:00Z",
                "nextRenewalDate": "2027-01-01T00:00:00Z",
            },
        },
    }
    normalized = open_lei.gleif_record_normalize(
        dataset_kind="lei-cdf",
        records=[record],
        as_of_date="2026-04-25",
    )["openLeiGleifRecordNormalize"]
    match = open_lei.gleif_ems_match(
        entity_rows=normalized["entityRows"],
        countries=["JP"],
        keywords=["electronics", "manufacturing"],
    )["openLeiGleifEmsMatch"]
    assert normalized["entityRows"][0]["registration_status"] == "ISSUED"
    assert match["candidateCount"] == 1
    assert match["candidates"][0]["lei"] == "529900T8BM49AURSDO55"


def test_gleif_record_normalize_accepts_bulk_collect_output():
    record = {
        "id": "529900T8BM49AURSDO55",
        "attributes": {
            "lei": "529900T8BM49AURSDO55",
            "entity": {"legalName": {"name": "Example Manufacturing Ltd"}},
            "registration": {"status": "ISSUED"},
        },
    }

    out = asyncio.run(
        open_lei.task_gleif_record_normalize(
            openLeiGleifBulkCollect={
                "datasetKind": "lei-cdf",
                "asOfDate": "2026-04-25",
                "records": [record],
            }
        )
    )

    normalized = out["openLeiGleifRecordNormalize"]
    assert normalized["asOfDate"] == "2026-04-25"
    assert normalized["recordsRead"] == 1
    assert normalized["entityRows"][0]["lei"] == "529900T8BM49AURSDO55"


def test_register_exposes_gleif_task_types():
    registered: list[str] = []

    class FakeWorker:
        def task(self, *, task_type: str, single_value: bool, timeout_ms: int):
            assert single_value is False
            assert timeout_ms == 123
            registered.append(task_type)

            def decorator(fn):
                return fn

            return decorator

    open_lei.register(FakeWorker(), timeout_ms=123)
    assert registered == [
        "openLei.gleif.manifest.plan",
        "openLei.gleif.bulk.collect",
        "openLei.gleif.record.normalize",
        "openLei.gleif.ems.match",
    ]
