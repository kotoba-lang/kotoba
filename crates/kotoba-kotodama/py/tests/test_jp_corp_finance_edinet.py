from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest.jp_corp_finance.ids import coverage_vid, disclosure_vid, fact_vid
from kotodama.ingest.jp_corp_finance import writer as W
from kotodama.ingest.jp_corp_finance.extractor import extract_financial_facts_from_ocr, parse_number
from kotodama.ingest.jp_corp_finance.langgraph_disclosure_extract import GRAPH_ID, disclosure_extract_graph
from kotodama.ingest.jp_corp_finance import coverage as C
from kotodama.ingest.jp_corp_finance.coverage import get_coverage, list_missing
from kotodama.ingest.jp_corp_finance.sources import kanpo as K
from kotodama.ingest.jp_corp_finance.sources.edinet import normalize_documents
from kotodama.ingest.jp_corp_finance.writer import graph_rows, upsert_graph_rows
from kotodama.ingest.jp_corp_finance.zeebe_tasks import (
    task_jp_corp_finance_normalize,
    task_jp_corp_finance_extract_financial_facts,
    task_jp_corp_finance_fetch_source,
    task_jp_corp_finance_plan_shards,
    task_jp_corp_finance_validate_rows,
    task_jp_corp_finance_verify_visibility,
    task_jp_corp_finance_write_graph,
)


EDINET_PAYLOAD = {
    "results": [
        {
            "docID": "S100TEST",
            "edinetCode": "E02144",
            "secCode": "72030",
            "JCN": "1180301008652",
            "filerName": "トヨタ自動車株式会社",
            "formCode": "030000",
            "periodStart": "2025-04-01",
            "periodEnd": "2026-03-31",
            "submitDateTime": "2026-06-24 15:00",
        }
    ]
}

OCR_PAGES = [
    {
        "pageIndex": 0,
        "result": {
            "tables": [
                {
                    "title": "貸借対照表 千円",
                    "rows": [
                        ["科目", "金額"],
                        ["資産合計", "1,234"],
                        ["負債合計", "456"],
                        ["純資産合計", "778"],
                    ],
                },
                {
                    "title": "損益計算書 百万円",
                    "rows": [
                        ["売上高", "12"],
                        ["営業利益", "3"],
                        ["当期純利益", "△1"],
                    ],
                },
            ]
        },
    }
]

KANPO_CONTENTS_HTML = """
<html><body>
<a href="20260428g00099/20260428g000990108f.html">
  <span class="text">会社決算公告</span>
  <span class="date">108</span>
</a>
</body></html>
"""

KANPO_PAGE_HTML = '<html><body><embed src="pdf/20260428g000990108.pdf"></body></html>'
KANPO_FRAME_HTML = '<html><body><iframe src="./20260428g000990108.html"></iframe></body></html>'


def test_disclosure_vid_is_deterministic() -> None:
    a = disclosure_vid("edinet-v2", "S100TEST")
    b = disclosure_vid("edinet-v2", "S100TEST")
    assert a == b
    assert a.startswith("at://did:web:jp-corp-finance.etzhayyim.com/")


def test_fact_vid_changes_by_location() -> None:
    a = fact_vid("disc", "BS", "assets_total", "p1:r1")
    b = fact_vid("disc", "BS", "assets_total", "p1:r2")
    assert a != b


def test_coverage_vid_contains_jcn() -> None:
    assert "1180301008652" in coverage_vid("1180301008652")


def test_get_coverage_requires_identifier() -> None:
    result = get_coverage()
    assert result["ok"] is False
    assert "jcn or edinetCode" in result["error"]


def test_get_coverage_by_jcn(monkeypatch) -> None:
    calls: list[tuple[str, tuple]] = []

    def _fake_fetch_all(sql: str, params: tuple = ()):
        calls.append((sql, params))
        return [("1180301008652", "トヨタ自動車株式会社", "kanpo", "2026-03-31", "disc", "covered", "", "2026-04-29T00:00:00Z")]

    monkeypatch.setattr(C, "fetch_all", _fake_fetch_all)

    result = get_coverage(jcn="1180301008652")

    assert result["ok"] is True
    assert result["found"] is True
    assert result["coverageStatus"] == "covered"
    assert calls[0][1] == ("1180301008652",)


def test_get_coverage_missing_returns_missing_status(monkeypatch) -> None:
    monkeypatch.setattr(C, "fetch_all", lambda sql, params=(): [])

    result = get_coverage(edinet_code="E02144")

    assert result["ok"] is True
    assert result["found"] is False
    assert result["coverageStatus"] == "missing"
    assert result["missingReason"] == "coverage_not_found"


def test_list_missing_filters_and_paginates(monkeypatch) -> None:
    calls: list[tuple[str, tuple]] = []

    def _fake_fetch_all(sql: str, params: tuple = ()):
        calls.append((sql, params))
        return [
            ("1", "A", "", "", "", "missing", "source_unknown", "t1"),
            ("2", "B", "", "", "", "missing", "source_unknown", "t2"),
            ("3", "C", "", "", "", "missing", "source_unknown", "t3"),
        ]

    monkeypatch.setattr(C, "fetch_all", _fake_fetch_all)

    result = list_missing(coverage_status="missing", missing_reason="source_unknown", limit=2, cursor="0")

    assert result["ok"] is True
    assert [item["jcn"] for item in result["items"]] == ["1", "2"]
    assert result["cursor"] == "2"
    assert calls[0][1] == ("missing", "source_unknown", "0", 3)


def test_list_missing_rejects_unknown_status() -> None:
    result = list_missing(coverage_status="covered")
    assert result["ok"] is False
    assert result["items"] == []


def test_normalize_documents_yuho() -> None:
    rows = normalize_documents(EDINET_PAYLOAD, target_date="2026-06-24", observed_at="2026-06-24T00:00:00Z")
    assert len(rows) == 1
    row = rows[0]
    assert row.disclosure_kind == "EDINET_YUHO"
    assert row.statement_scope == "BS_PL_CF"
    assert row.jcn == "1180301008652"
    assert row.fiscal_year == 2026
    assert row.source_record_id == "S100TEST"


def test_task_plan_shards_defaults_to_date() -> None:
    result = asyncio.run(task_jp_corp_finance_plan_shards(sourceId="edinet-v2", targetDate="2026-06-24"))
    assert result["ok"] is True
    assert result["shards"][0]["targetDate"] == "2026-06-24"


def test_task_normalize_payload() -> None:
    result = asyncio.run(task_jp_corp_finance_normalize(payload=EDINET_PAYLOAD, targetDate="2026-06-24"))
    assert result["ok"] is True
    assert result["recordsRead"] == 1
    assert result["disclosures"][0]["edinet_code"] == "E02144"


def test_parse_kanpo_contents_finds_company_financial_notice() -> None:
    entries = K.parse_contents(KANPO_CONTENTS_HTML, base_url="https://www.kanpo.go.jp/20260428/20260428.fullcontents.html")

    assert len(entries) == 1
    assert entries[0].title == "会社決算公告"
    assert entries[0].page == 108
    assert entries[0].issue_kind == "gogai"
    assert entries[0].page_url.endswith("/20260428g00099/20260428g000990108f.html")


def test_kanpo_pdf_url_from_page_html() -> None:
    out = K.pdf_url_from_page_html(
        "https://www.kanpo.go.jp/20260428/20260428g00099/20260428g000990108f.html",
        KANPO_PAGE_HTML,
    )

    assert out == "https://www.kanpo.go.jp/20260428/20260428g00099/pdf/20260428g000990108.pdf"


def test_kanpo_iframe_url_from_page_html() -> None:
    out = K.iframe_url_from_page_html(
        "https://www.kanpo.go.jp/20260428/20260428g00099/20260428g000990108f.html",
        KANPO_FRAME_HTML,
    )

    assert out == "https://www.kanpo.go.jp/20260428/20260428g00099/20260428g000990108.html"


def test_task_fetch_source_kanpo_dry_run(monkeypatch) -> None:
    monkeypatch.setattr(K, "fetch_text", lambda url: KANPO_CONTENTS_HTML)

    result = asyncio.run(task_jp_corp_finance_fetch_source(sourceId="kanpo", targetDate="2026-04-28", dryRun=True))

    assert result["ok"] is True
    assert result["recordsRead"] == 1
    assert result["payload"]["results"][0]["title"] == "会社決算公告"


def test_task_fetch_source_kanpo_materializes_pdf(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(K, "fetch_text", lambda url: KANPO_CONTENTS_HTML)

    def _fake_fetch_bytes(url: str):
        if url.endswith("f.html"):
            return KANPO_FRAME_HTML.encode(), "text/html"
        if url.endswith("108.html"):
            return KANPO_PAGE_HTML.encode(), "text/html"
        return b"%PDF-1.4\n%%EOF\n", "application/pdf"

    def _fake_materialize(content: bytes, *, filename: str):
        path = tmp_path / filename
        path.write_bytes(content)
        return str(path), len(content), K.sha256_bytes(content)

    monkeypatch.setattr(K, "fetch_bytes", _fake_fetch_bytes)
    monkeypatch.setattr(K, "materialize_bytes", _fake_materialize)

    result = asyncio.run(task_jp_corp_finance_fetch_source(sourceId="kanpo", targetDate="2026-04-28"))

    assert result["ok"] is True
    assert result["contentType"] == "application/pdf"
    assert Path(result["sourcePath"]).read_bytes().startswith(b"%PDF")
    assert result["sourceUrl"].endswith("/pdf/20260428g000990108.pdf")


def test_task_validate_rows_rejects_missing_id() -> None:
    result = asyncio.run(task_jp_corp_finance_validate_rows(disclosures=[{"source_id": "x"}]))
    assert result["ok"] is False
    assert result["invalidCount"] == 1
    assert result["invalidDisclosureCount"] == 1


def test_task_validate_rows_filters_bad_financial_fact() -> None:
    good = {
        "vertex_id": "fact-1",
        "disclosure_vid": "disc-1",
        "statement_type": "BS",
        "concept": "assets_total",
        "value_jpy": 0.0,
        "source_location": "page:1:row:2",
        "extraction_method": "ocr_table_rule",
    }
    bad = {**good, "vertex_id": "fact-2", "value_jpy": "not-a-number"}

    result = asyncio.run(task_jp_corp_finance_validate_rows(financialFacts=[good, bad]))

    assert result["ok"] is False
    assert result["invalidFactCount"] == 1
    assert result["financialFacts"] == [good]


def test_task_write_graph_dry_run() -> None:
    result = asyncio.run(task_jp_corp_finance_write_graph(disclosures=[{"vertex_id": "v"}], dryRun=True))
    assert result["ok"] is True
    assert result["recordsPrepared"] == 1


def test_parse_number_applies_japanese_unit() -> None:
    assert parse_number("1,234", "単位: 千円") == 1_234_000.0
    assert parse_number("△12", "百万円") == -12_000_000.0


def test_extract_financial_facts_from_ocr_tables() -> None:
    disclosures = [row.to_dict() for row in normalize_documents(EDINET_PAYLOAD, target_date="2026-06-24")]

    facts = extract_financial_facts_from_ocr(disclosures=disclosures, ocr_pages=OCR_PAGES)

    concepts = {fact["concept"]: fact for fact in facts}
    assert concepts["assets_total"]["value_jpy"] == 1_234_000.0
    assert concepts["liabilities_total"]["statement_type"] == "BS"
    assert concepts["revenue_net_sales"]["value_jpy"] == 12_000_000.0
    assert concepts["net_income"]["value_jpy"] == -1_000_000.0


def test_task_extract_financial_facts_outputs_rows() -> None:
    disclosures = [row.to_dict() for row in normalize_documents(EDINET_PAYLOAD, target_date="2026-06-24")]

    result = asyncio.run(task_jp_corp_finance_extract_financial_facts(disclosures=disclosures, ocrPages=OCR_PAGES))

    assert result["ok"] is True
    assert result["factsExtracted"] == 6
    assert result["financialFacts"][0]["disclosure_vid"] == disclosures[0]["vertex_id"]


def test_task_extract_financial_facts_prefers_langgraph_final_state() -> None:
    disclosures = [row.to_dict() for row in normalize_documents(EDINET_PAYLOAD, target_date="2026-06-24")]
    langgraph_fact = {
        "vertex_id": "fact-langgraph",
        "disclosure_vid": disclosures[0]["vertex_id"],
        "statement_type": "BS",
        "concept": "assets_total",
        "source_location": "page:1",
        "extraction_method": "langgraph",
        "value_jpy": 100.0,
    }

    result = asyncio.run(
        task_jp_corp_finance_extract_financial_facts(
            disclosures=disclosures,
            ocrPages=OCR_PAGES,
            extractState={
                "final_state": {
                    "disclosures": disclosures,
                    "financialFacts": [langgraph_fact],
                    "extractionStatus": "extracted",
                    "reviewReasons": [],
                }
            },
        )
    )

    assert result["method"] == "langgraph"
    assert result["factsExtracted"] == 1
    assert result["financialFacts"] == [langgraph_fact]
    assert result["extractionStatus"] == "extracted"


def test_langgraph_disclosure_extract_registers_and_returns_final_state() -> None:
    from kotodama.primitives import langgraph_registry

    assert langgraph_registry.get(GRAPH_ID) is disclosure_extract_graph


def test_langgraph_disclosure_extract_invokes_ocr_table_extractor() -> None:
    disclosures = [row.to_dict() for row in normalize_documents(EDINET_PAYLOAD, target_date="2026-06-24")]

    result = asyncio.run(
        disclosure_extract_graph.ainvoke(
            {
                "runId": "run-1",
                "sourceId": "kanpo",
                "sourceUrl": "https://www.kanpo.go.jp/example.pdf",
                "disclosures": disclosures,
                "ocrPages": OCR_PAGES,
            }
        )
    )

    final_state = result["final_state"]
    assert final_state["graphId"] == GRAPH_ID
    assert final_state["extractionStatus"] == "extracted"
    assert len(final_state["financialFacts"]) == 6


def test_langgraph_disclosure_extract_marks_needs_review_without_ocr() -> None:
    disclosures = [row.to_dict() for row in normalize_documents(EDINET_PAYLOAD, target_date="2026-06-24")]

    result = asyncio.run(disclosure_extract_graph.ainvoke({"disclosures": disclosures, "ocrPages": []}))

    final_state = result["final_state"]
    assert final_state["extractionStatus"] == "needs_review"
    assert "no_ocr_pages" in final_state["reviewReasons"]


class _Cursor:
    def __init__(self) -> None:
        self.sqls: list[str] = []
        self.params: list[tuple] = []
        self.rowcount = 1
        self._fetch_counts = [1, 1]

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


def test_graph_rows_adds_coverage_for_jcn() -> None:
    disclosures = [row.to_dict() for row in normalize_documents(EDINET_PAYLOAD, target_date="2026-06-24")]
    rows = graph_rows(disclosures)

    assert set(rows) == {
        "vertex_jp_corp_disclosure",
        "vertex_jp_corp_financial_fact",
        "vertex_jp_corp_finance_coverage",
    }
    assert rows["vertex_jp_corp_finance_coverage"][0]["jcn"] == "1180301008652"
    assert rows["vertex_jp_corp_finance_coverage"][0]["coverage_status"] == "covered"


def test_upsert_graph_rows_writes_and_checks_visibility(monkeypatch) -> None:
    factory = _SyncCursorFactory()
    monkeypatch.setattr(W, "sync_cursor", factory)
    disclosures = [row.to_dict() for row in normalize_documents(EDINET_PAYLOAD, target_date="2026-06-24")]

    out = upsert_graph_rows(graph_rows(disclosures))

    assert out["ok"] is True
    assert out["recordsPrepared"] == 2
    assert out["recordsVisible"] == 2
    sql_text = "\n".join(factory.cursor.sqls)
    assert "INSERT INTO vertex_jp_corp_disclosure" in sql_text
    assert "INSERT INTO vertex_jp_corp_finance_coverage" in sql_text
    assert "SELECT COUNT(*) FROM vertex_jp_corp_disclosure" in sql_text


def test_task_write_graph_requires_rw_healthy_when_not_dry_run() -> None:
    disclosures = [row.to_dict() for row in normalize_documents(EDINET_PAYLOAD, target_date="2026-06-24")]
    result = asyncio.run(task_jp_corp_finance_write_graph(disclosures=disclosures, dryRun=False, rwHealthy=False))

    assert result["ok"] is False
    assert result["degraded"] is True
    assert result["recordsPrepared"] == 2


def test_task_write_graph_writes_when_rw_healthy(monkeypatch) -> None:
    factory = _SyncCursorFactory()
    monkeypatch.setattr(W, "sync_cursor", factory)
    disclosures = [row.to_dict() for row in normalize_documents(EDINET_PAYLOAD, target_date="2026-06-24")]

    result = asyncio.run(task_jp_corp_finance_write_graph(disclosures=disclosures, dryRun=False, rwHealthy=True))

    assert result["ok"] is True
    assert result["dryRun"] is False
    assert result["recordsWritten"] == 2


def test_task_verify_visibility_bounds() -> None:
    ok = asyncio.run(task_jp_corp_finance_verify_visibility(recordsWritten=1, recordsPrepared=2))
    bad = asyncio.run(task_jp_corp_finance_verify_visibility(recordsWritten=3, recordsPrepared=2))
    assert ok["ok"] is True
    assert bad["ok"] is False
