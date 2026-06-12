from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import business_person as BP


def test_normalize_public_roles_creates_stable_vertex() -> None:
    out = asyncio.run(
        BP.task_business_person_normalize_public_roles(
            sourceId="sec-edgar",
            jurisdiction="USA",
            sourceUrl="https://www.sec.gov/example",
            rows=[
                {
                    "fullName": "Jane Doe",
                    "title": "Chief Financial Officer",
                    "orgName": "Acme Inc.",
                    "lei": "5493001KJTIIGC8Y1R12",
                }
            ],
        )
    )

    assert out["ok"] is True
    assert out["publicOnly"] is True
    assert out["recordsPrepared"] == 1
    row = out["roles"][0]
    assert row["vertex_id"].startswith("at://did:web:business-person.etzhayyim.com/")
    assert row["display_name"] == "Jane Doe"
    assert row["org_name"] == "Acme Inc."
    assert row["source"] == "sec-edgar"
    assert row["country"] == "usa"
    assert '"publicOnly": true' in row["props"]


def test_write_graph_dry_run_prepares_vertex_business_person() -> None:
    normalized = asyncio.run(
        BP.task_business_person_normalize_public_roles(
            sourceId="corporate-hp",
            rows=[{"fullName": "John Smith", "role": "director", "companyName": "Example plc"}],
        )
    )

    out = asyncio.run(BP.task_business_person_write_graph(roles=normalized["roles"], dryRun=True))

    assert out["ok"] is True
    assert out["dryRun"] is True
    assert out["recordsPrepared"] == 1
    assert set(out["tables"]) == {"vertex_business_person"}


def test_prepare_source_request_builds_companies_house_url() -> None:
    out = asyncio.run(
        BP.task_business_person_prepare_source_request(
            sourceId="companies-house",
            companyNumber="00000006",
        )
    )

    assert out["ok"] is True
    assert out["fetch"] is True
    assert out["requestPrepared"] is True
    assert out["sourceUrl"].startswith("https://api.company-information.service.gov.uk/company/00000006/officers")
    assert "items_per_page=100" in out["sourceUrl"]
    assert "start_index=0" in out["sourceUrl"]
    assert out["requiresAuthEnv"] == "COMPANIES_HOUSE_API_KEY"


def test_prepare_source_request_builds_sec_edgar_url() -> None:
    out = asyncio.run(BP.task_business_person_prepare_source_request(sourceId="sec-edgar", cik="320193"))

    assert out["ok"] is True
    assert out["sourceUrl"] == "https://data.sec.gov/submissions/CIK0000320193.json"
    assert out["usesHeaderEnv"] == "SEC_USER_AGENT"


def test_prepare_source_request_skips_without_identifier() -> None:
    out = asyncio.run(BP.task_business_person_prepare_source_request(sourceId="edinet"))

    assert out["ok"] is True
    assert out["fetch"] is False
    assert out["requestPrepared"] is False


def test_prepare_source_request_builds_companies_house_url_with_cursor() -> None:
    out = asyncio.run(
        BP.task_business_person_prepare_source_request(
            sourceId="companies-house",
            companyNumber="00000006",
            cursor="50",
            pageSize=25,
        )
    )

    assert out["ok"] is True
    assert out["pageSize"] == 25
    assert "items_per_page=25" in out["sourceUrl"]
    assert "start_index=50" in out["sourceUrl"]


def test_advance_source_cursor_companies_house_next_page() -> None:
    out = asyncio.run(
        BP.task_business_person_advance_source_cursor(
            sourceId="companies-house",
            sourceUrl="https://api.company-information.service.gov.uk/company/00000006/officers?items_per_page=25&start_index=0",
            pageSize=25,
            pagesFetched=0,
            maxPages=3,
            companiesHouseJson={
                "items": [{"name": "DOE, Jane"}],
                "items_per_page": 25,
                "start_index": 0,
                "total_results": 60,
            },
        )
    )

    assert out["ok"] is True
    assert out["hasNextPage"] is True
    assert out["cursor"] == "25"
    assert "start_index=25" in out["nextSourceUrl"]


def test_advance_source_cursor_stops_at_max_pages() -> None:
    out = asyncio.run(
        BP.task_business_person_advance_source_cursor(
            sourceId="companies-house",
            sourceUrl="https://api.company-information.service.gov.uk/company/00000006/officers",
            pageSize=25,
            pagesFetched=0,
            maxPages=1,
            companiesHouseJson={"items_per_page": 25, "start_index": 0, "total_results": 60},
        )
    )

    assert out["nextSourceUrl"]
    assert out["hasNextPage"] is False


def test_schedule_next_page_builds_collection_job_payload() -> None:
    out = asyncio.run(
        BP.task_business_person_schedule_next_page(
            sourceId="companies-house",
            nextSourceUrl="https://api.company-information.service.gov.uk/company/00000006/officers?items_per_page=25&start_index=25",
            hasNextPage=True,
            cursor="25",
            pageSize=25,
            pagesFetched=1,
            maxPages=3,
            companyNumber="00000006",
            operatorDid="did:web:operator.etzhayyim.com",
        )
    )

    assert out["ok"] is True
    assert out["nextPageScheduled"] is True
    job = out["nextPageJob"]
    assert job["type"] == "com.atproto.repo.createRecord"
    assert job["payload"]["repo"] == BP.BUSINESS_PERSON_DID
    record = job["payload"]["record"]
    assert record["sourceId"] == "companies-house"
    assert record["cursor"] == "25"
    assert record["pageSize"] == 25
    assert record["companyNumber"] == "00000006"
    assert record["publicOnly"] is True


def test_schedule_next_page_noops_without_next_page() -> None:
    out = asyncio.run(BP.task_business_person_schedule_next_page(sourceId="companies-house"))

    assert out["ok"] is True
    assert out["nextPageScheduled"] is False


def test_fetch_public_source_maps_companies_house_payload(monkeypatch) -> None:
    async def fake_get(url: str, *, timeout_sec: int, headers: dict | None = None, auth=None) -> dict:
        assert url == "https://api.company-information.service.gov.uk/company/00000006/officers"
        assert timeout_sec == 5
        assert headers
        assert "User-Agent" in headers
        return {
            "httpStatus": 200,
            "contentType": "application/json",
            "body": {"items": [{"name": "DOE, Jane"}]},
            "bytesFetched": 32,
        }

    monkeypatch.setattr(BP, "_http_get_public_source", fake_get)
    out = asyncio.run(
        BP.task_business_person_fetch_public_source(
            sourceId="companies-house",
            sourceUrl="https://api.company-information.service.gov.uk/company/00000006/officers",
            timeoutSec=5,
        )
    )

    assert out["ok"] is True
    assert out["fetched"] is True
    assert out["companiesHouseJson"] == {"items": [{"name": "DOE, Jane"}]}
    assert out["bytesFetched"] == 32


def test_fetch_public_source_maps_corporate_hp_html(monkeypatch) -> None:
    async def fake_get(url: str, *, timeout_sec: int, headers: dict | None = None, auth=None) -> dict:
        return {
            "httpStatus": 200,
            "contentType": "text/html",
            "body": "<html><body>John Smith - Chief Executive Officer</body></html>",
            "bytesFetched": 64,
        }

    monkeypatch.setattr(BP, "_http_get_public_source", fake_get)
    out = asyncio.run(
        BP.task_business_person_fetch_public_source(
            sourceId="corporate-hp",
            sourceUrl="https://example.com/leadership",
        )
    )

    assert out["ok"] is True
    assert out["htmlText"].startswith("<html>")


def test_fetch_public_source_rejects_non_http_url() -> None:
    out = asyncio.run(BP.task_business_person_fetch_public_source(sourceUrl="file:///tmp/roles.json"))

    assert out["ok"] is False
    assert out["fetched"] is False
    assert "http(s)" in out["error"]


def test_extract_corporate_hp_roles_from_jsonld() -> None:
    html = """
    <html><head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": "Jane Leader",
        "jobTitle": "Chief Executive Officer",
        "worksFor": {"@type": "Organization", "name": "Acme Holdings"}
      }
      </script>
    </head><body></body></html>
    """

    out = asyncio.run(
        BP.task_business_person_extract_corporate_hp_roles(
            sourceUrl="https://example.com/leadership",
            jurisdiction="USA",
            htmlText=html,
        )
    )

    assert out["ok"] is True
    assert out["recordsExtracted"] == 1
    assert out["rows"][0]["fullName"] == "Jane Leader"
    assert out["rows"][0]["title"] == "Chief Executive Officer"
    assert out["rows"][0]["orgName"] == "Acme Holdings"


def test_extract_corporate_hp_roles_from_text_line() -> None:
    out = asyncio.run(
        BP.task_business_person_extract_corporate_hp_roles(
            sourceUrl="https://example.com/leadership",
            orgName="Example plc",
            text="John Smith - Chief Financial Officer\nAbout us\n",
        )
    )

    assert out["recordsExtracted"] == 1
    assert out["rows"][0]["fullName"] == "John Smith"
    assert out["rows"][0]["title"] == "Chief Financial Officer"
    assert out["rows"][0]["orgName"] == "Example plc"


def test_extract_companies_house_officers_from_api_json() -> None:
    out = asyncio.run(
        BP.task_business_person_extract_companies_house_officers(
            sourceUrl="https://api.company-information.service.gov.uk/company/00000006/officers",
            orgName="Example Ltd",
            companyNumber="00000006",
            companiesHouseJson={
                "items": [
                    {
                        "name": "DOE, Jane",
                        "officer_role": "director",
                        "appointed_on": "2020-01-02",
                        "address": {"country": "England"},
                        "links": {"officer": {"appointments": "/officers/abc/appointments"}},
                    }
                ]
            },
        )
    )

    assert out["ok"] is True
    assert out["recordsExtracted"] == 1
    assert out["rows"][0]["fullName"] == "DOE, Jane"
    assert out["rows"][0]["title"] == "director"
    assert out["rows"][0]["sourceId"] == "companies-house"
    assert out["rows"][0]["registryType"] == "companies-house-officer"
    assert out["rows"][0]["status"] == "active"


def test_extract_companies_house_preserves_existing_rows_without_payload() -> None:
    existing = [{"fullName": "John Smith", "title": "CEO", "sourceId": "corporate-hp"}]
    out = asyncio.run(BP.task_business_person_extract_companies_house_officers(rows=existing))

    assert out["recordsExtracted"] == 0
    assert out["rows"] == [{**existing[0], "publicOnly": True}]


def test_extract_gbizinfo_representatives_from_api_json() -> None:
    out = asyncio.run(
        BP.task_business_person_extract_gbizinfo_representatives(
            sourceUrl="https://info.gbiz.go.jp/hojin/v1/hojin/1234567890123",
            gbizInfoJson={
                "hojin-infos": [
                    {
                        "corporateNumber": "1234567890123",
                        "name": "サンプル株式会社",
                        "representativeName": "山田 太郎",
                        "representativePosition": "代表取締役",
                        "updateDate": "2026-04-01",
                        "status": "active",
                    }
                ]
            },
        )
    )

    assert out["ok"] is True
    assert out["recordsExtracted"] == 1
    assert out["rows"][0]["fullName"] == "山田 太郎"
    assert out["rows"][0]["title"] == "代表取締役"
    assert out["rows"][0]["orgName"] == "サンプル株式会社"
    assert out["rows"][0]["sourceId"] == "gbizinfo"
    assert out["rows"][0]["registryId"] == "1234567890123"


def test_extract_gbizinfo_preserves_existing_rows_without_payload() -> None:
    existing = [{"fullName": "DOE, Jane", "title": "director", "sourceId": "companies-house"}]
    out = asyncio.run(BP.task_business_person_extract_gbizinfo_representatives(rows=existing))

    assert out["recordsExtracted"] == 0
    assert out["rows"] == [{**existing[0], "publicOnly": True}]


def test_extract_edinet_officers_from_filing_metadata() -> None:
    out = asyncio.run(
        BP.task_business_person_extract_edinet_officers(
            sourceUrl="https://disclosure2.edinet-fsa.go.jp/api/v2/documents/S100TEST",
            edinetJson={
                "results": [
                    {
                        "docID": "S100TEST",
                        "filerName": "サンプル上場株式会社",
                        "representativeName": "佐藤 花子",
                        "title": "代表取締役社長",
                        "formCode": "030000",
                        "submitDateTime": "2026-04-01T10:00:00",
                    }
                ]
            },
        )
    )

    assert out["ok"] is True
    assert out["recordsExtracted"] == 1
    assert out["rows"][0]["fullName"] == "佐藤 花子"
    assert out["rows"][0]["title"] == "代表取締役社長"
    assert out["rows"][0]["orgName"] == "サンプル上場株式会社"
    assert out["rows"][0]["sourceId"] == "edinet"
    assert out["rows"][0]["registryId"] == "S100TEST"


def test_extract_edinet_preserves_existing_rows_without_payload() -> None:
    existing = [{"fullName": "山田 太郎", "title": "代表取締役", "sourceId": "gbizinfo"}]
    out = asyncio.run(BP.task_business_person_extract_edinet_officers(rows=existing))

    assert out["recordsExtracted"] == 0
    assert out["rows"] == [{**existing[0], "publicOnly": True}]


def test_extract_sec_edgar_officers_from_owner_json() -> None:
    out = asyncio.run(
        BP.task_business_person_extract_sec_edgar_officers(
            sourceUrl="https://data.sec.gov/submissions/CIK0000320193.json",
            orgName="Apple Inc.",
            cik="0000320193",
            secEdgarJson={
                "reportingOwners": [
                    {
                        "ownerName": "DOE JANE",
                        "officerTitle": "Chief Financial Officer",
                        "issuerCik": "0000320193",
                        "form": "4",
                        "filingDate": "2026-04-01",
                    }
                ]
            },
        )
    )

    assert out["ok"] is True
    assert out["recordsExtracted"] == 1
    assert out["rows"][0]["fullName"] == "DOE JANE"
    assert out["rows"][0]["title"] == "Chief Financial Officer"
    assert out["rows"][0]["orgName"] == "Apple Inc."
    assert out["rows"][0]["sourceId"] == "sec-edgar"
    assert out["rows"][0]["registryId"] == "0000320193"


def test_extract_sec_edgar_preserves_existing_rows_without_payload() -> None:
    existing = [{"fullName": "佐藤 花子", "title": "代表取締役社長", "sourceId": "edinet"}]
    out = asyncio.run(BP.task_business_person_extract_sec_edgar_officers(rows=existing))

    assert out["recordsExtracted"] == 0
    assert out["rows"] == [{**existing[0], "publicOnly": True}]


def test_extract_handelsregister_officers_from_register_json() -> None:
    out = asyncio.run(
        BP.task_business_person_extract_handelsregister_officers(
            sourceUrl="https://www.handelsregister.de/rp_web/mask.do",
            orgName="Muster GmbH",
            registerNumber="HRB 12345",
            handelsregisterJson={
                "items": [
                    {
                        "name": "Erika Musterfrau",
                        "role": "Geschäftsführerin",
                        "companyName": "Muster GmbH",
                        "registerNumber": "HRB 12345",
                        "court": "Berlin",
                        "date": "2026-04-01",
                    }
                ]
            },
        )
    )

    assert out["ok"] is True
    assert out["recordsExtracted"] == 1
    assert out["rows"][0]["fullName"] == "Erika Musterfrau"
    assert out["rows"][0]["title"] == "Geschäftsführerin"
    assert out["rows"][0]["orgName"] == "Muster GmbH"
    assert out["rows"][0]["sourceId"] == "handelsregister"
    assert out["rows"][0]["registryId"] == "HRB 12345"
    assert out["rows"][0]["registryType"] == "handelsregister-register-number"


def test_extract_handelsregister_preserves_existing_rows_without_payload() -> None:
    existing = [{"fullName": "DOE JANE", "title": "Chief Financial Officer", "sourceId": "sec-edgar"}]
    out = asyncio.run(BP.task_business_person_extract_handelsregister_officers(rows=existing))

    assert out["recordsExtracted"] == 0
    assert out["rows"] == [{**existing[0], "publicOnly": True}]


class _Cursor:
    def __init__(self) -> None:
        self.sqls: list[str] = []
        self.params: list[tuple] = []
        self.rowcount = 1

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.sqls.append(sql)
        self.params.append(params)

    def fetchone(self) -> tuple[int]:
        return (1,)


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
    monkeypatch.setattr(BP, "sync_cursor", factory)
    normalized = asyncio.run(
        BP.task_business_person_normalize_public_roles(
            sourceId="companies-house",
            rows=[{"fullName": "Alice Jones", "title": "secretary", "orgName": "Example Ltd"}],
        )
    )

    out = BP.upsert_graph_rows(normalized["roles"])

    assert out["ok"] is True
    assert out["recordsPrepared"] == 1
    assert out["recordsVisible"] == 1
    sql_text = "\n".join(factory.cursor.sqls)
    assert "INSERT INTO vertex_business_person" in sql_text
    assert "UPDATE vertex_business_person" in sql_text


# ─── task_business_person_plan_public_role_sources ───────────────────────────

def test_plan_sources_returns_ok() -> None:
    result = asyncio.run(BP.task_business_person_plan_public_role_sources())
    assert result["ok"] is True


def test_plan_sources_echoes_source_id() -> None:
    result = asyncio.run(BP.task_business_person_plan_public_role_sources(sourceId="companies-house"))
    assert result["sourceId"] == "companies-house"


def test_plan_sources_echoes_jurisdiction() -> None:
    result = asyncio.run(BP.task_business_person_plan_public_role_sources(jurisdiction="JPN"))
    assert result["jurisdiction"] == "JPN"


def test_plan_sources_limit_clamped_at_10000() -> None:
    result = asyncio.run(BP.task_business_person_plan_public_role_sources(limit=99999))
    assert result["limit"] == 10000


def test_plan_sources_limit_zero_falls_back_to_default() -> None:
    result = asyncio.run(BP.task_business_person_plan_public_role_sources(limit=0))
    # 0 or 100 → 100, so limit=0 is treated as the default 100
    assert result["limit"] == 100


def test_plan_sources_public_only_true() -> None:
    result = asyncio.run(BP.task_business_person_plan_public_role_sources())
    assert result["publicOnly"] is True


# ─── task_business_person_verify_coverage ────────────────────────────────────

def test_verify_coverage_ok_when_visible_lte_prepared() -> None:
    result = asyncio.run(BP.task_business_person_verify_coverage(recordsPrepared=10, recordsVisible=5))
    assert result["ok"] is True


def test_verify_coverage_ok_when_equal() -> None:
    result = asyncio.run(BP.task_business_person_verify_coverage(recordsPrepared=5, recordsVisible=5))
    assert result["ok"] is True


def test_verify_coverage_fails_when_visible_gt_prepared() -> None:
    result = asyncio.run(BP.task_business_person_verify_coverage(recordsPrepared=3, recordsVisible=10))
    assert result["ok"] is False


def test_verify_coverage_zero_zero_ok() -> None:
    result = asyncio.run(BP.task_business_person_verify_coverage())
    assert result["ok"] is True


def test_verify_coverage_echoes_counts() -> None:
    result = asyncio.run(BP.task_business_person_verify_coverage(recordsPrepared=7, recordsVisible=3))
    assert result["recordsPrepared"] == 7
    assert result["recordsVisible"] == 3


def test_verify_coverage_written_used_as_visible() -> None:
    result = asyncio.run(BP.task_business_person_verify_coverage(recordsPrepared=5, recordsWritten=5))
    assert result["ok"] is True


# ─── task_business_person_compute_influence_scores ───────────────────────────

def _person_row(**kw) -> dict:
    base: dict = {
        "person_id": "p1",
        "name_ja": "テスト太郎",
        "org_name": "NTT Corp",
        "hub_score": 2.5,
        "bridge_score": 1.0,
        "gov_score": 0.0,
        "out_degree": 3,
        "in_degree": 2,
        "strong_tie_count": 1,
        "career_event_count": 4,
    }
    base.update(kw)
    return base


def test_compute_influence_empty_persons_returns_empty_scores() -> None:
    result = asyncio.run(BP.task_business_person_compute_influence_scores(persons=[]))
    assert result["scores"] == []
    assert result["scoresCount"] == 0


def test_compute_influence_returns_score_for_each_person() -> None:
    result = asyncio.run(BP.task_business_person_compute_influence_scores(
        persons=[_person_row(), _person_row(person_id="p2")]
    ))
    assert result["scoresCount"] == 2


def test_compute_influence_score_has_faction_label() -> None:
    result = asyncio.run(BP.task_business_person_compute_influence_scores(
        persons=[_person_row(org_name="NTT Japan")]
    ))
    assert "faction_label" in result["scores"][0]


def test_compute_influence_ntt_faction() -> None:
    result = asyncio.run(BP.task_business_person_compute_influence_scores(
        persons=[_person_row(org_name="NTT Docomo")]
    ))
    assert result["scores"][0]["faction_label"] == "NTT派"


def test_compute_influence_softbank_faction() -> None:
    result = asyncio.run(BP.task_business_person_compute_influence_scores(
        persons=[_person_row(org_name="SoftBank Corp")]
    ))
    assert result["scores"][0]["faction_label"] == "SoftBank派"


def test_compute_influence_independent_faction() -> None:
    result = asyncio.run(BP.task_business_person_compute_influence_scores(
        persons=[_person_row(org_name="Random Corp", hub_score=1.0, bridge_score=0.5)]
    ))
    assert result["scores"][0]["faction_label"] == "independent"


def test_compute_influence_score_has_vertex_id() -> None:
    result = asyncio.run(BP.task_business_person_compute_influence_scores(
        persons=[_person_row()]
    ))
    assert "vertex_id" in result["scores"][0]
    assert result["scores"][0]["vertex_id"].startswith("at://")


def test_compute_influence_none_persons_returns_empty() -> None:
    result = asyncio.run(BP.task_business_person_compute_influence_scores(persons=None))
    assert result["scoresCount"] == 0
