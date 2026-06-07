"""Tests for pure helper functions in dispatcher_main.py."""

from __future__ import annotations

import sys
import types
import importlib.util
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# ── stub heavy deps before loading dispatcher_main ───────────────────────────
def _stub(name: str, **attrs: object) -> types.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


class _FakeApp:
    def router(self): pass

def _passthrough(f): return f
_web = _stub("aiohttp.web", Application=_FakeApp, Request=object, Response=object,
              RouteTableDef=object, run_app=lambda *a, **kw: None,
              middleware=_passthrough)

_aiohttp = _stub("aiohttp", web=_web)
_aiohttp.web = _web

class _FakeProcessInvalidError(Exception):
    pass
_pze_errors = _stub("pyzeebe.errors", process_errors=None)
_pze_errors_pe = _stub("pyzeebe.errors.process_errors",
                        ProcessInvalidError=_FakeProcessInvalidError)
_pze_errors.process_errors = _pze_errors_pe

_stub("pyzeebe", ZeebeClient=object, create_insecure_channel=lambda *a, **kw: None)
_stub("grpc")

# user_task_sink stub
_uts = _stub("kotodama.handlers.user_task_sink",
             register_routes=lambda *a, **kw: None,
             run_user_task_sink_loop=lambda *a, **kw: None)

_DM_MOD_NAME = "_dm_pure_helpers"
if _DM_MOD_NAME not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _DM_MOD_NAME,
        _py_src / "kotodama" / "dispatcher_main.py",
    )
    _mod = types.ModuleType(_DM_MOD_NAME)
    sys.modules[_DM_MOD_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

DM = sys.modules[_DM_MOD_NAME]


# ─── LangGraph routing helpers ───────────────────────────────────────────────

def test_langgraph_run_payload_preserves_input_and_promotes_identity() -> None:
    process_vars = {
        "actorDid": "did:web:yoro.etzhayyim.com",
        "threadId": "thread-1",
        "config": {"tags": ["resident"]},
        "_nsid": "com.etzhayyim.apps.yoro.platformPulse",
    }

    payload = DM._langgraph_run_payload("yoro_platform_pulse", process_vars)

    assert payload["assistant_id"] == "yoro_platform_pulse"
    assert payload["input"] is process_vars
    assert payload["actor_did"] == "did:web:yoro.etzhayyim.com"
    assert payload["thread_id"] == "thread-1"
    assert payload["config"] == {"tags": ["resident"]}


def test_langgraph_run_payload_ignores_blank_identity_and_non_dict_config() -> None:
    payload = DM._langgraph_run_payload(
        "assistant",
        {"actorDid": " ", "threadId": "", "config": "not-a-dict"},
    )

    assert payload == {
        "assistant_id": "assistant",
        "input": {"actorDid": " ", "threadId": "", "config": "not-a-dict"},
    }


def test_langgraph_request_headers_includes_internal_trust_when_secret(monkeypatch) -> None:
    monkeypatch.setattr(DM, "INTERNAL_SECRET", "secret-1")

    assert DM._langgraph_request_headers() == {"x-internal-trust": "secret-1"}


def test_langgraph_request_headers_empty_without_secret(monkeypatch) -> None:
    monkeypatch.setattr(DM, "INTERNAL_SECRET", "")

    assert DM._langgraph_request_headers() == {}


def test_maps_world_monitor_xrpcs_proxy_to_langserver() -> None:
    expected = {
        "com.etzhayyim.apps.maps.getWorldMonitorDashboard",
        "com.etzhayyim.apps.maps.listIntelEvents",
        "com.etzhayyim.apps.maps.getRiskSnapshot",
        "com.etzhayyim.apps.maps.getLatestBrief",
        "com.etzhayyim.apps.maps.listIntelAlerts",
    }

    assert expected <= DM.MAPS_LANGSERVER_PROXY_NSIDS
    assert {nsid.lower() for nsid in expected} <= DM.MAPS_LANGSERVER_PROXY_NSIDS_LOWER
    assert {"getworldmonitordashboard", "listintelevents"} <= DM.MAPS_LANGSERVER_PROXY_SUFFIXES


# ─── _xml_db_insert_tables ───────────────────────────────────────────────────

# The regex matches the unescaped-quote form (outer and inner attr quote overlap).
# Real BPMN files with &quot; encoding are NOT matched (the regex requires
# \s+ after the closing inner quote, but valid XML has a " outer-close first).
_BPMN_INSERT_SNIPPET = (
    '<zeebe:input source="="vertex_open_defence_event" target="table"/>'
)

_BPMN_MULTI_TABLES = (
    '<zeebe:input source="="vertex_ma_deal" target="table"/>\n'
    '<zeebe:input source="="vertex_ma_candidate" target="table"/>'
)

_BPMN_NO_INSERT = """
<serviceTask id="Task_1">
  <extensionElements>
    <zeebe:taskDefinition type="generic.llm.chat"/>
  </extensionElements>
</serviceTask>
"""

_BPMN_XML_ENCODED = (
    '<zeebe:input source="=&quot;vertex_encoded&quot;" target="table"/>'
)


def test_xml_db_insert_tables_finds_quoted_table() -> None:
    result = DM._xml_db_insert_tables(_BPMN_INSERT_SNIPPET)
    assert "vertex_open_defence_event" in result


def test_xml_db_insert_tables_returns_set() -> None:
    result = DM._xml_db_insert_tables(_BPMN_INSERT_SNIPPET)
    assert isinstance(result, set)


def test_xml_db_insert_tables_multiple_tables() -> None:
    result = DM._xml_db_insert_tables(_BPMN_MULTI_TABLES)
    assert "vertex_ma_deal" in result
    assert "vertex_ma_candidate" in result


def test_xml_db_insert_tables_empty_when_no_insert() -> None:
    result = DM._xml_db_insert_tables(_BPMN_NO_INSERT)
    assert result == set()


def test_xml_db_insert_tables_empty_string() -> None:
    result = DM._xml_db_insert_tables("")
    assert result == set()


def test_xml_db_insert_tables_no_duplicates() -> None:
    xml = _BPMN_MULTI_TABLES + "\n" + _BPMN_MULTI_TABLES
    result = DM._xml_db_insert_tables(xml)
    assert len(result) == 2  # set deduplication


def test_xml_db_insert_tables_xml_encoded_not_matched() -> None:
    # The regex does NOT match &quot; encoded form (known limitation)
    result = DM._xml_db_insert_tables(_BPMN_XML_ENCODED)
    assert result == set()


# ─── _detect_resource_kind ───────────────────────────────────────────────────

_DMN_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="https://www.omg.org/spec/DMN/20191111/MODEL/"
             id="Definitions_1">
</definitions>"""

_BPMN_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  id="Definitions_1">
</bpmn:definitions>"""


def test_detect_resource_kind_dmn() -> None:
    assert DM._detect_resource_kind(_DMN_HEADER) == "dmn"


def test_detect_resource_kind_bpmn() -> None:
    assert DM._detect_resource_kind(_BPMN_HEADER) == "bpmn"


def test_detect_resource_kind_empty_defaults_bpmn() -> None:
    assert DM._detect_resource_kind("") == "bpmn"


def test_detect_resource_kind_no_namespace_defaults_bpmn() -> None:
    assert DM._detect_resource_kind("<process id='p1'/>") == "bpmn"


def test_detect_resource_kind_returns_string() -> None:
    result = DM._detect_resource_kind(_BPMN_HEADER)
    assert isinstance(result, str)


def test_detect_resource_kind_case_insensitive_check() -> None:
    # Only checks first 512 chars
    xml = "x" * 600 + "https://www.omg.org/spec/DMN/"
    assert DM._detect_resource_kind(xml) == "bpmn"


# ─── _validate_deploy_scope ──────────────────────────────────────────────────

def test_validate_deploy_scope_unrestricted_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(DM, "_binding_write_allowlist_sync", lambda pid: None)
    result = DM._validate_deploy_scope("my_process", _BPMN_INSERT_SNIPPET)
    assert result is None


def test_validate_deploy_scope_no_tables_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(DM, "_binding_write_allowlist_sync", lambda pid: {"vertex_allowed"})
    result = DM._validate_deploy_scope("my_process", _BPMN_NO_INSERT)
    assert result is None


def test_validate_deploy_scope_allowed_table_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(
        DM, "_binding_write_allowlist_sync",
        lambda pid: {"vertex_open_defence_event"},
    )
    result = DM._validate_deploy_scope("my_process", _BPMN_INSERT_SNIPPET)
    assert result is None


def test_validate_deploy_scope_forbidden_table_returns_error(monkeypatch) -> None:
    monkeypatch.setattr(DM, "_binding_write_allowlist_sync", lambda pid: {"vertex_denied"})
    result = DM._validate_deploy_scope("my_process", _BPMN_INSERT_SNIPPET)
    assert result is not None
    assert "vertex_open_defence_event" in result


def test_validate_deploy_scope_empty_allowlist_with_tables_returns_error(monkeypatch) -> None:
    monkeypatch.setattr(DM, "_binding_write_allowlist_sync", lambda pid: set())
    result = DM._validate_deploy_scope("my_process", _BPMN_INSERT_SNIPPET)
    assert result is not None


def test_validate_deploy_scope_error_includes_process_id(monkeypatch) -> None:
    monkeypatch.setattr(DM, "_binding_write_allowlist_sync", lambda pid: {"vertex_denied"})
    result = DM._validate_deploy_scope("my_special_process", _BPMN_INSERT_SNIPPET)
    assert result is not None
    assert "my_special_process" in result


def test_public_malak_campaign_view_maps_row() -> None:
    row = (
        "cluster-1",
        "campaign-key",
        "platform",
        "adv-1",
        "Advertiser",
        "example.test",
        "secure-cloud",
        "Secure cloud",
        "Cloud body",
        3,
        2,
        "2026-05-06T10:00:00Z",
        "2026-05-06T11:00:00Z",
        240,
        "summary",
    )

    view = DM._public_malak_campaign_view(row)

    assert view["vertexId"] == "cluster-1"
    assert view["campaignKey"] == "campaign-key"
    assert view["creativeCount"] == 3
    assert view["platformCount"] == 2


def test_public_malak_cluster_creative_view_maps_row() -> None:
    row = (
        "creative-1",
        "linkedin",
        "li-1",
        "Advertiser",
        "Headline",
        "Body",
        "https://example.test",
        "2026-05-06T11:00:00Z",
        "advertiser_domain_claim",
    )

    view = DM._public_malak_cluster_creative_view(row)

    assert view["vertexId"] == "creative-1"
    assert view["platform"] == "linkedin"
    assert view["matchBasis"] == "advertiser_domain_claim"


def test_public_malak_scraper_run_view_maps_row() -> None:
    row = (
        "run-1",
        "line",
        "search",
        "security",
        "JP",
        "2026-05-06T12:00:00Z",
        "2026-05-06T12:01:00Z",
        "completed",
        3,
        2,
        1,
        None,
        "ua",
        "JP",
        "trace-cid",
        "robots-cid",
        1200,
    )

    view = DM._public_malak_scraper_run_view(row)

    assert view["vertexId"] == "run-1"
    assert view["platform"] == "line"
    assert view["status"] == "completed"
    assert view["adsSeen"] == 3
    assert view["rateLimitSleepMs"] == 1200


def test_public_malak_creative_view_maps_row() -> None:
    row = (
        "creative-1",
        "line",
        "ad-1",
        "adv-1",
        "Advertiser",
        "text",
        "Headline",
        "Body",
        "Learn More",
        "https://example.test",
        "example.test",
        None,
        None,
        None,
        "ja",
        "JPY",
        10,
        20,
        1.25,
        4.5,
        100,
        200,
        False,
        True,
        "2026-05-01",
        None,
        "2026-05-06T10:00:00Z",
        "2026-05-06T11:00:00Z",
        "https://source.test",
    )

    view = DM._public_malak_creative_view(row)

    assert view["vertexId"] == "creative-1"
    assert view["platformAdId"] == "ad-1"
    assert view["spendMinPermille"] == 1250
    assert view["isActive"] is True


def test_public_malak_snapshot_view_maps_row() -> None:
    row = (
        "snapshot-1",
        "creative-1",
        "line",
        "ad-1",
        "scraper",
        "run-1",
        "2026-05-06T11:00:00Z",
        "https://source.test",
        200,
        "html-cid",
        None,
        None,
        True,
        10,
        20,
        1.0,
        2.5,
        "line-ad-library-v1",
        True,
        None,
    )

    view = DM._public_malak_snapshot_view(row)

    assert view["vertexId"] == "snapshot-1"
    assert view["creativeVertexId"] == "creative-1"
    assert view["httpStatus"] == 200
    assert view["observedSpendMaxPermille"] == 2500


def test_list_public_malak_snapshots_orders_latest_deterministically(monkeypatch) -> None:
    class Cursor:
        description = None

        def __init__(self) -> None:
            self.sql = ""
            self.params = ()

        def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
            self.sql = sql
            self.params = params

        def fetchall(self) -> list[tuple[object, ...]]:
            return []

    class CursorFactory:
        def __init__(self) -> None:
            self.cursor = Cursor()

        def __call__(self):
            return self

        def __enter__(self) -> Cursor:
            return self.cursor

        def __exit__(self, *_exc: object) -> None:
            return None

    factory = CursorFactory()
    monkeypatch.setattr(DM, "sync_cursor", factory)

    out = DM._list_public_malak_snapshots_sync({"creativeVertexId": "creative-1", "limit": 1})

    assert out == {"snapshots": [], "cursor": None}
    assert "ORDER BY scraped_at DESC, vertex_id DESC" in factory.cursor.sql
    assert factory.cursor.params == ("creative-1",)


def test_public_malak_advertiser_view_maps_row() -> None:
    row = (
        "adv-1",
        "line",
        "platform-adv-1",
        "Advertiser",
        "Verified Advertiser",
        "Advertiser Inc.",
        "https://page.test",
        "public-ad-library",
        "JP",
        "Funding Entity",
        False,
        "did:web:example.test",
        "2026-05-06T10:00:00Z",
        "2026-05-06T11:00:00Z",
    )

    view = DM._public_malak_advertiser_view(row)

    assert view["vertexId"] == "adv-1"
    assert view["platformAdvertiserId"] == "platform-adv-1"
    assert view["isPolitical"] is False
    assert view["legalEntityDid"] == "did:web:example.test"


def test_public_malak_analysis_view_maps_row() -> None:
    row = (
        "analysis-1",
        "creative-1",
        "line",
        "ad-1",
        "claim",
        "heuristic-public-malak-v1",
        "completed",
        "claim analysis summary",
        420,
        '{"claims":[]}',
        '{"targets":[]}',
        '{"isActive":true}',
        "snapshot-1",
        "2026-05-06T12:00:00Z",
    )

    view = DM._public_malak_analysis_view(row)

    assert view["vertexId"] == "analysis-1"
    assert view["creativeVertexId"] == "creative-1"
    assert view["analysisKind"] == "claim"
    assert view["riskScorePermille"] == 420
    assert view["signalsJson"] == '{"isActive":true}'


def test_public_malak_search_terms_accepts_array_and_csv() -> None:
    assert DM._public_malak_search_terms({"searchTerms": ["alpha", " beta ", ""]}) == ["alpha", "beta"]
    assert DM._public_malak_search_terms({"searchTerms": "alpha, beta"}) == ["alpha", "beta"]


def test_public_malak_crawl_ads_builds_seed_payload(monkeypatch) -> None:
    from kotodama.primitives import public_malak_ads

    called = {}

    def _fake_queue_seed_runs(seeds, limit):
        called["seeds"] = seeds
        called["limit"] = limit
        return {
            "queued": 1,
            "skipped": 0,
            "runs": [{"vertexId": "run-1", "platform": "line", "queryValue": "security"}],
        }

    monkeypatch.setattr(public_malak_ads, "queue_seed_runs", _fake_queue_seed_runs)

    out = DM._public_malak_crawl_ads_sync({
        "platform": "line",
        "searchTerms": ["security"],
        "country": "jp",
        "limit": 25,
    })

    assert called["limit"] == 25
    assert called["seeds"] == [{
        "platform": "line",
        "queryKind": "search",
        "queryValue": "security",
        "country": "JP",
    }]
    assert out["status"] == "queued"
    assert out["scraperRunUri"] == "run-1"


def test_public_malak_process_queue_accepts_limit_and_timeout(monkeypatch) -> None:
    from kotodama.primitives import public_malak_ads

    called = {}

    def _fake_process_queue(max_runs, timeout_sec, platform, reclaim_after_sec):
        called.update({
            "max_runs": max_runs,
            "timeout_sec": timeout_sec,
            "platform": platform,
            "reclaim_after_sec": reclaim_after_sec,
        })
        return {"processed": max_runs, "completed": max_runs, "failed": 0, "runs": []}

    monkeypatch.setattr(public_malak_ads, "process_queue", _fake_process_queue)

    out = DM._public_malak_process_scraper_queue_sync({
        "limit": 1,
        "timeoutSec": 30,
        "platform": "telegram",
        "reclaimAfterSec": 120,
    })

    assert called == {
        "max_runs": 1,
        "timeout_sec": 30.0,
        "platform": "telegram",
        "reclaim_after_sec": 120,
    }
    assert out["processed"] == 1


def test_public_malak_analyze_ad_requires_creative_vertex_id() -> None:
    out = DM._public_malak_analyze_ad_sync({})

    assert out["error"] == "creativeVertexId required"
    assert out["status"] == "failed"


def test_public_malak_analyze_ad_delegates_to_primitive(monkeypatch) -> None:
    from kotodama.primitives import public_malak_ads

    called = {}

    def _fake_analyze_creative(creative_vertex_id, analysis_kind, model_id):
        called["creative_vertex_id"] = creative_vertex_id
        called["analysis_kind"] = analysis_kind
        called["model_id"] = model_id
        return {"status": "completed", "creativeVertexId": creative_vertex_id}

    monkeypatch.setattr(public_malak_ads, "analyze_creative", _fake_analyze_creative)

    out = DM._public_malak_analyze_ad_sync({
        "creativeVertexId": "creative-1",
        "analysisKind": "claim",
        "modelId": "model-1",
    })

    assert called == {
        "creative_vertex_id": "creative-1",
        "analysis_kind": "claim",
        "model_id": "model-1",
    }
    assert out["status"] == "completed"
