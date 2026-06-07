from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import legal_entity


def test_registry_entity_row_maps_core_columns() -> None:
    row = legal_entity._registry_entity_row(
        name="Example Ltd",
        registration_number="12345678",
        jurisdiction="GB",
        country="GB",
        entity_type="ltd",
        entity_status="ACTIVE",
        industry_code="62010",
        incorporation_date="2020-01-02",
        source="CH_GBR",
        source_record_id="12345678",
        raw={"company_number": "12345678"},
    )

    assert row is not None
    assert row["vertex_id"].endswith("/ch-gbr-12345678")
    assert row["did"] == "did:web:legal-entity.etzhayyim.com:ch-gbr-12345678"
    assert row["source"] == "ch-gbr"
    assert row["source_record_id"] == "12345678"
    assert row["status"] == "active"
    assert row["country"] == "GB"


def test_registry_entity_row_rejects_missing_identity() -> None:
    assert legal_entity._registry_entity_row(
        name="",
        registration_number="",
        jurisdiction="CZ",
        country="CZ",
        source="ARES_CZE",
        source_record_id="",
    ) is None


def test_basic_auth_header_companies_house_shape() -> None:
    header = legal_entity._basic_auth_header("secret-key")
    assert header["Accept"] == "application/json"
    assert header["Authorization"].startswith("Basic ")


def test_collect_country_registry_dry_run_skips_db(monkeypatch) -> None:
    async def fake_fetch(session, suffix, page, page_size, variables):  # noqa: ANN001
        return [
            legal_entity._registry_entity_row(
                name="Skoda Auto",
                registration_number="00177041",
                jurisdiction="CZ",
                country="CZ",
                source="ARES_CZE",
                source_record_id="00177041",
            )
        ], 1, {}

    def fail_insert(rows):  # noqa: ANN001
        raise AssertionError("dryRun must not insert rows")

    monkeypatch.setattr(legal_entity, "_fetch_country_registry_page", fake_fetch)
    monkeypatch.setattr(legal_entity, "_insert_many_entities", fail_insert)

    out = asyncio.run(
        legal_entity._collect_country_registry("Cze", pages=1, pageSize=1, dryRun=True, query="skoda")
    )
    result = out["result"]
    assert result["ok"] is True
    assert result["dryRun"] is True
    assert result["pages"][0]["submitted"] == 1
    assert result["totalInserted"] == 0


def test_collect_country_registry_reports_missing_env(monkeypatch) -> None:
    monkeypatch.delenv("COMPANIES_HOUSE_API_KEY", raising=False)

    out = asyncio.run(legal_entity._collect_country_registry("Gbr", pages=1, pageSize=1))
    result = out["result"]
    assert result["ok"] is False
    assert result["requiresAuthEnv"] == ["COMPANIES_HOUSE_API_KEY"]
    assert "missing required env" in result["firstError"]


def test_collect_country_registry_reports_new_authenticated_sources(monkeypatch) -> None:
    monkeypatch.delenv("CVR_API_ENABLED", raising=False)
    monkeypatch.delenv("EST_ARIREGISTER_DATA_URL", raising=False)
    monkeypatch.delenv("ZEFIX_USERNAME", raising=False)
    monkeypatch.delenv("ZEFIX_PASSWORD", raising=False)

    dnk = asyncio.run(legal_entity._collect_country_registry("Dnk", pages=1, pageSize=1, search="lego"))["result"]
    est = asyncio.run(legal_entity._collect_country_registry("Est", pages=1, pageSize=1))["result"]
    che = asyncio.run(legal_entity._collect_country_registry("Che", pages=1, pageSize=1))["result"]

    assert dnk["ok"] is False
    assert dnk["requiresAuthEnv"] == ["CVR_API_ENABLED"]
    assert est["ok"] is False
    assert est["requiresAuthEnv"] == ["EST_ARIREGISTER_DATA_URL"]
    assert che["ok"] is False
    assert che["requiresAuthEnv"] == ["ZEFIX_USERNAME", "ZEFIX_PASSWORD"]


def test_collect_country_registry_reports_missing_query() -> None:
    out = asyncio.run(legal_entity._collect_country_registry("Cze", pages=1, pageSize=1))
    result = out["result"]
    assert result["ok"] is False
    assert "query" in result["requiresQuery"]
    assert "missing required query" in result["firstError"]


def test_collect_country_registry_rejects_nor_deep_page_window() -> None:
    out = asyncio.run(legal_entity._collect_country_registry("Nor", pages=2, pageSize=100, startPage=99))
    result = out["result"]
    assert result["ok"] is False
    assert result["maxPageWindow"] == 10_000
    assert "10000" in result["firstError"]


def test_collect_country_registry_includes_page_meta(monkeypatch) -> None:
    monkeypatch.setenv("INSEE_API_TOKEN", "token")

    async def fake_fetch(session, suffix, page, page_size, variables):  # noqa: ANN001
        return [], 10, {"nextCursor": "cursor-2"}

    monkeypatch.setattr(legal_entity, "_fetch_country_registry_page", fake_fetch)
    out = asyncio.run(legal_entity._collect_country_registry("Fra", pages=1, pageSize=1, dryRun=True))
    result = out["result"]
    assert result["ok"] is True
    assert result["pages"][0]["nextCursor"] == "cursor-2"


def test_list_payload_supports_wrapped_shapes() -> None:
    assert legal_entity._list_payload([{"a": 1}], "items") == [{"a": 1}]
    assert legal_entity._list_payload({"items": [{"b": 2}]}, "items") == [{"b": 2}]
    assert legal_entity._list_payload({"companies": [{"c": 3}]}, "items", "companies") == [{"c": 3}]
    assert legal_entity._list_payload({"items": "bad"}, "items") == []


def test_fin_registry_current_open_data_shape(monkeypatch) -> None:
    async def fake_get_json(session, url, *, params=None, headers=None):  # noqa: ANN001
        assert url.endswith("/opendata-ytj-api/v3/companies")
        return {
            "totalResults": 1,
            "companies": [{
                "businessId": {"value": "0100002-9", "registrationDate": "1978-03-15"},
                "names": [{"name": "Artjarven Metalli Oy"}],
                "companyForm": {"descriptions": [{"languageCode": "3", "description": "Limited company"}]},
                "mainBusinessLine": {"type": "29120"},
            }],
        }

    monkeypatch.setattr(legal_entity, "_get_json", fake_get_json)
    rows, total, meta = asyncio.run(
        legal_entity._fetch_country_registry_page(None, "Fin", 0, 1, {})  # type: ignore[arg-type]
    )

    assert total == 1
    assert meta == {}
    assert rows[0]["name"] == "Artjarven Metalli Oy"
    assert rows[0]["source"] == "prh-fin"
    assert rows[0]["source_record_id"] == "0100002-9"


def test_register_covers_legal_entity_task_types() -> None:
    class Worker:
        def __init__(self) -> None:
            self.task_types: list[str] = []

        def task(self, *, task_type: str, single_value: bool, timeout_ms: int):  # noqa: ANN001
            assert single_value is False
            assert timeout_ms == 123
            self.task_types.append(task_type)

            def deco(fn):  # noqa: ANN001
                return fn

            return deco

    worker = Worker()
    legal_entity.register(worker, timeout_ms=123)

    assert "legalEntity.gleif.fetchPages" in worker.task_types
    assert "legalEntity.edgar.collectUsa" in worker.task_types
    assert "legalEntity.registry.collectCze" in worker.task_types
    assert "legalEntity.registry.collectJpn" in worker.task_types
    assert len(worker.task_types) == 16
