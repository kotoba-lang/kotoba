from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest.fund import ids
from kotodama.ingest.fund.gleif import apply_gleif_enrichment
from kotodama.ingest.fund.sec_adv import normalize_sec_adv_rows, plan_sec_adv_shards
from kotodama.ingest.fund import writer as W
from kotodama.ingest.fund.writer import graph_rows, upsert_graph_rows
from kotodama.ingest.fund.zeebe_tasks import task_fund_write_graph


def test_fund_manager_id_prefers_sec_cik() -> None:
    out = ids.manager_id(source_id="sec-adv", cik="0001067983", name="Berkshire Hathaway Inc")
    assert out == "sec-cik-1067983"
    assert ids.manager_vertex_id(out).endswith("/sec-cik-1067983")


def test_sec_adv_normalize_manager_and_private_fund() -> None:
    managers, funds = normalize_sec_adv_rows(
        [
            {
                "Primary Business Name": "Acme Capital LLC",
                "CIK": "0000123456",
                "State": "US-DE",
                "Regulatory Assets Under Management": "1,250,000,000",
                "Private Fund Name": "Acme Growth Fund I",
                "Private Fund ID": "805-1",
                "Gross Asset Value": "250000000",
            }
        ],
        source_url="https://www.sec.gov/example.csv",
    )

    assert managers[0].manager_id == "sec-cik-123456"
    assert managers[0].aum_amount == 1_250_000_000.0
    assert funds[0].fund_id == "sec-adv-805-1"
    assert funds[0].manager_id == managers[0].manager_id


def test_plan_sec_adv_shards_is_bounded() -> None:
    shards = plan_sec_adv_shards(limit=1000)
    assert len(shards) == 50
    assert shards[0].source_id == "sec-adv"


def test_gleif_enrichment_sets_legal_entity_did_without_overwriting_name() -> None:
    out = apply_gleif_enrichment(
        {"manager_name": "Acme Capital", "confidence": 0.4},
        {"lei": "5493001KJTIIGC8Y1R12", "jurisdiction": "US-DE", "country": "US"},
    )

    assert out["manager_name"] == "Acme Capital"
    assert out["legal_entity_did"].endswith("/5493001kjtiigc8y1r12")
    assert out["jurisdiction"] == "US-DE"
    assert out["domicile"] == "US"
    assert out["confidence"] == 0.8


def test_graph_rows_prepares_existing_fund_tables() -> None:
    managers, funds = normalize_sec_adv_rows(
        [{"Primary Business Name": "Acme Capital LLC", "CIK": "123", "Private Fund Name": "Fund I"}]
    )
    rows = graph_rows(managers, funds)

    assert set(rows) == {"vertex_fund_manager", "vertex_fund", "edge_fund_managed_by"}
    assert rows["vertex_fund_manager"][0]["manager_id"] == "sec-cik-123"
    assert rows["edge_fund_managed_by"][0]["relationship"] == "managed_by"


def test_write_graph_dry_run_prepares_rows() -> None:
    managers, funds = normalize_sec_adv_rows(
        [{"Primary Business Name": "Acme Capital LLC", "CIK": "123", "Private Fund Name": "Fund I"}]
    )
    out = asyncio.run(
        task_fund_write_graph(
            managers=[x.to_dict() for x in managers],
            funds=[x.to_dict() for x in funds],
            dryRun=True,
        )
    )

    assert out["ok"] is True
    assert out["dryRun"] is True
    assert out["recordsPrepared"] == 3


class _Cursor:
    def __init__(self) -> None:
        self.sqls: list[str] = []
        self.params: list[tuple] = []
        self.rowcount = 1
        self._fetch_counts = [1, 1, 1]

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.sqls.append(sql)
        self.params.append(params)

    def fetchone(self) -> tuple[int]:
        return (self._fetch_counts.pop(0),)


class _SyncCursorFactory:
    def __init__(self) -> None:
        self.cursor = _Cursor()

    def __call__(self):
        factory = self

        class _Ctx:
            def __enter__(self):
                return factory.cursor

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Ctx()


def test_upsert_graph_rows_writes_and_checks_visibility(monkeypatch) -> None:
    factory = _SyncCursorFactory()
    monkeypatch.setattr(W, "sync_cursor", factory)
    managers, funds = normalize_sec_adv_rows(
        [{"Primary Business Name": "Acme Capital LLC", "CIK": "123", "Private Fund Name": "Fund I"}]
    )

    out = upsert_graph_rows(graph_rows(managers, funds))

    assert out["ok"] is True
    assert out["recordsPrepared"] == 3
    assert out["recordsVisible"] == 3
    sql_text = "\n".join(factory.cursor.sqls)
    assert "INSERT INTO vertex_fund_manager" in sql_text
    assert "INSERT INTO vertex_fund" in sql_text
    assert "INSERT INTO edge_fund_managed_by" in sql_text
    assert "SELECT COUNT(*) FROM vertex_fund_manager" in sql_text


def test_write_graph_requires_rw_healthy_when_not_dry_run() -> None:
    managers, funds = normalize_sec_adv_rows(
        [{"Primary Business Name": "Acme Capital LLC", "CIK": "123", "Private Fund Name": "Fund I"}]
    )
    out = asyncio.run(
        task_fund_write_graph(
            managers=[x.to_dict() for x in managers],
            funds=[x.to_dict() for x in funds],
            dryRun=False,
            rwHealthy=False,
        )
    )

    assert out["ok"] is False
    assert out["degraded"] is True
    assert out["recordsPrepared"] == 3


def test_write_graph_writes_when_rw_healthy(monkeypatch) -> None:
    factory = _SyncCursorFactory()
    monkeypatch.setattr(W, "sync_cursor", factory)
    managers, funds = normalize_sec_adv_rows(
        [{"Primary Business Name": "Acme Capital LLC", "CIK": "123", "Private Fund Name": "Fund I"}]
    )

    out = asyncio.run(
        task_fund_write_graph(
            managers=[x.to_dict() for x in managers],
            funds=[x.to_dict() for x in funds],
            dryRun=False,
            rwHealthy=True,
        )
    )

    assert out["ok"] is True
    assert out["dryRun"] is False
    assert out["recordsVisible"] == 3
