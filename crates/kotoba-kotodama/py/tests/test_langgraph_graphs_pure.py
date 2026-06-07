"""Pure tests for LangGraph graph implementations (ADR-2605080600 Phase 4).

Tests build_graph() compilation and node logic without live DB or LLM calls.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# shosha_agent_loop
# ---------------------------------------------------------------------------

class TestShoshaAgentLoopGraph:
    def test_build_graph_compiles(self):
        from kotodama.langgraph_graphs.shosha_agent_loop import build_graph
        graph = build_graph()
        assert graph is not None

    def test_graph_has_nodes(self):
        from kotodama.langgraph_graphs.shosha_agent_loop import build_graph
        graph = build_graph()
        # StateGraph compiled to a CompiledGraph — can invoke
        assert callable(graph.invoke) or hasattr(graph, "invoke")

    def test_state_typeddict_fields(self):
        from kotodama.langgraph_graphs.shosha_agent_loop import ShoshaAgentState
        import typing
        hints = typing.get_type_hints(ShoshaAgentState)
        assert "prompt" in hints
        assert "content" in hints
        assert "ok" in hints
        assert "error" in hints

    def test_fetch_context_returns_empty_on_db_error(self):
        from kotodama.langgraph_graphs.shosha_agent_loop import fetch_context
        with patch("kotodama.langgraph_graphs.shosha_agent_loop._rw_query", return_value=[]):
            result = fetch_context({"prompt": "test"})
        assert "_context" in result
        assert result.get("intelRowsUsed") == 0
        assert result.get("marketViewRowsUsed") == 0
        assert result.get("exposureRowsUsed") == 0

    def test_fetch_context_formats_rows(self):
        from kotodama.langgraph_graphs.shosha_agent_loop import fetch_context
        fake_intel = [("CL=F", 80.5, "USD/bbl", 1717000000000)]
        fake_views = [("oil", "up", 0.8, 85.0, "demand spike")]
        fake_exposure = [("oil", 9_000_000.0)]

        call_count = [0]
        def fake_query(sql, params=()):
            call_count[0] += 1
            if "vertex_shosha_intel" in sql:
                return fake_intel
            if "vertex_shosha_market_view" in sql:
                return fake_views
            if "mv_shosha_exposure_by_commodity" in sql:
                return fake_exposure
            return []

        with patch("kotodama.langgraph_graphs.shosha_agent_loop._rw_query", side_effect=fake_query):
            result = fetch_context({"prompt": "test"})

        assert result["intelRowsUsed"] == 1
        assert result["marketViewRowsUsed"] == 1
        assert result["exposureRowsUsed"] == 1
        assert "CL=F" in result["_context"]
        assert "oil" in result["_context"]

    def test_call_llm_returns_error_on_empty_prompt(self):
        from kotodama.langgraph_graphs.shosha_agent_loop import call_llm
        result = call_llm({"prompt": "", "_context": "some context"})
        assert result["ok"] is False
        assert result["error"] == "prompt is required"

    def test_call_llm_strips_think_blocks(self):
        from kotodama.langgraph_graphs.shosha_agent_loop import call_llm
        mock_resp = {
            "content": "<think>internal reasoning</think>Actual response",
            "model": "test-model",
            "latencyMs": 100,
        }
        with patch("kotodama.langgraph_graphs.shosha_agent_loop.llm") as mock_llm:
            mock_llm.call_tier.return_value = mock_resp
            mock_llm.LlmError = Exception
            result = call_llm({"prompt": "What is the oil price?", "_context": ""})
        assert result["ok"] is True
        assert "<think>" not in result.get("content", "")
        assert "Actual response" in result.get("content", "")

    def test_call_llm_handles_llm_error(self):
        from kotodama.langgraph_graphs.shosha_agent_loop import call_llm

        class FakeLlmError(Exception):
            pass

        with patch("kotodama.langgraph_graphs.shosha_agent_loop.llm") as mock_llm:
            mock_llm.LlmError = FakeLlmError
            mock_llm.call_tier.side_effect = FakeLlmError("model unavailable")
            result = call_llm({"prompt": "test", "_context": ""})

        assert result["ok"] is False
        assert "model unavailable" in result["error"]

    def test_emit_audit_is_nonfatal(self):
        from kotodama.langgraph_graphs.shosha_agent_loop import emit_audit
        with patch("kotodama.langgraph_graphs.shosha_agent_loop.sync_cursor") as mock_cur:
            mock_cur.side_effect = RuntimeError("DB down")
            result = emit_audit({"ok": True, "latencyMs": 42})
        # non-fatal — should return empty dict, not raise
        assert result == {}

    def test_strip_think_partial_block(self):
        from kotodama.langgraph_graphs.shosha_agent_loop import _strip_think
        # unclosed think block (truncated at max_tokens)
        assert _strip_think("<think>reasoning...") == ""
        # closed think block
        assert _strip_think("<think>hidden</think>visible") == "visible"
        # no think block
        assert _strip_think("plain text") == "plain text"


# ---------------------------------------------------------------------------
# webmk_proposal (graph exists — smoke test compilation)
# ---------------------------------------------------------------------------

class TestWebmkProposalGraph:
    def test_build_graph_compiles(self):
        try:
            from kotodama.langgraph_graphs.webmk_proposal import build_graph
            graph = build_graph()
            assert graph is not None
        except ImportError:
            pytest.skip("webmk_proposal not importable in this env")


# ---------------------------------------------------------------------------
# echo graph (registered in langgraph_server_app)
# ---------------------------------------------------------------------------

class TestEchoGraph:
    def test_echo_graph_produces_output(self):
        from langgraph.graph import END, StateGraph
        from typing import TypedDict

        class EchoState(TypedDict):
            input: str
            output: str

        def echo_node(state: EchoState) -> dict:
            return {"output": f"echo: {state.get('input', '')}"}

        builder = StateGraph(EchoState)
        builder.add_node("echo", echo_node)
        builder.set_entry_point("echo")
        builder.add_edge("echo", END)
        graph = builder.compile()

        result = graph.invoke({"input": "hello"})
        assert result["output"] == "echo: hello"

    def test_echo_graph_empty_input(self):
        from langgraph.graph import END, StateGraph
        from typing import TypedDict

        class EchoState(TypedDict):
            input: str
            output: str

        def echo_node(state: EchoState) -> dict:
            return {"output": f"echo: {state.get('input', '')}"}

        builder = StateGraph(EchoState)
        builder.add_node("echo", echo_node)
        builder.set_entry_point("echo")
        builder.add_edge("echo", END)
        graph = builder.compile()

        result = graph.invoke({"input": ""})
        assert result["output"] == "echo: "


# ---------------------------------------------------------------------------
# shosha_react_upstream (ADR-2605080600 Phase 5)
# ---------------------------------------------------------------------------

class TestShoshaReactUpstreamGraph:
    def test_build_graph_compiles(self):
        from kotodama.langgraph_graphs.shosha_react_upstream import build_graph
        graph = build_graph()
        assert graph is not None

    def test_state_typeddict_fields(self):
        from kotodama.langgraph_graphs.shosha_react_upstream import ShoshaReactUpstreamState
        import typing
        hints = typing.get_type_hints(ShoshaReactUpstreamState)
        assert "reactionsEmitted" in hints
        assert "recordsScanned" in hints
        assert "ok" in hints
        assert "error" in hints

    def test_emit_audit_nonfatal_on_db_error(self):
        from kotodama.langgraph_graphs.shosha_react_upstream import emit_audit
        from unittest.mock import patch
        with patch("kotodama.langgraph_graphs.shosha_react_upstream.sync_cursor") as m:
            m.side_effect = RuntimeError("DB down")
            result = emit_audit({"ok": True, "reactionsEmitted": 2})
        assert result == {}


# ---------------------------------------------------------------------------
# shosha_trade_book_recompute (ADR-2605080600 Phase 5)
# ---------------------------------------------------------------------------

class TestShoshaTradeBookRecomputeGraph:
    def test_build_graph_compiles(self):
        from kotodama.langgraph_graphs.shosha_trade_book_recompute import build_graph
        graph = build_graph()
        assert graph is not None

    def test_state_typeddict_fields(self):
        from kotodama.langgraph_graphs.shosha_trade_book_recompute import ShoshaTradeBookState
        import typing
        hints = typing.get_type_hints(ShoshaTradeBookState)
        assert "ok" in hints
        assert "error" in hints

    def test_emit_audit_nonfatal_on_db_error(self):
        from kotodama.langgraph_graphs.shosha_trade_book_recompute import emit_audit
        from unittest.mock import patch
        with patch("kotodama.langgraph_graphs.shosha_trade_book_recompute.sync_cursor") as m:
            m.side_effect = RuntimeError("DB down")
            result = emit_audit({"ok": True})
        assert result == {}


# ---------------------------------------------------------------------------
# shosha_trade_idea_synthesize (ADR-2605080600 Phase 5)
# ---------------------------------------------------------------------------

class TestShoshaTradeIdeaSynthesizeGraph:
    def test_build_graph_compiles(self):
        from kotodama.langgraph_graphs.shosha_trade_idea_synthesize import build_graph
        graph = build_graph()
        assert graph is not None

    def test_state_typeddict_fields(self):
        from kotodama.langgraph_graphs.shosha_trade_idea_synthesize import ShoshaTradeIdeaState
        import typing
        hints = typing.get_type_hints(ShoshaTradeIdeaState)
        assert "ok" in hints
        assert "error" in hints

    def test_emit_audit_nonfatal_on_db_error(self):
        from kotodama.langgraph_graphs.shosha_trade_idea_synthesize import emit_audit
        from unittest.mock import patch
        with patch("kotodama.langgraph_graphs.shosha_trade_idea_synthesize.sync_cursor") as m:
            m.side_effect = RuntimeError("DB down")
            result = emit_audit({"ok": True})
        assert result == {}


# ---------------------------------------------------------------------------
# shosha_daily_report (ADR-2605080600 Phase 5)
# ---------------------------------------------------------------------------

class TestShoshaDailyReportGraph:
    def test_build_graph_compiles(self):
        from kotodama.langgraph_graphs.shosha_daily_report import build_graph
        graph = build_graph()
        assert graph is not None

    def test_state_typeddict_fields(self):
        from kotodama.langgraph_graphs.shosha_daily_report import ShoshaDailyReportState
        import typing
        hints = typing.get_type_hints(ShoshaDailyReportState)
        assert "ok" in hints
        assert "error" in hints
        assert "summary" in hints
        assert "tradesCount" in hints

    def test_emit_audit_nonfatal_on_db_error(self):
        from kotodama.langgraph_graphs.shosha_daily_report import emit_audit
        from unittest.mock import patch
        with patch("kotodama.langgraph_graphs.shosha_daily_report.sync_cursor") as m:
            m.side_effect = RuntimeError("DB down")
            result = emit_audit({"ok": True, "reportText": "test"})
        assert result == {}


# ---------------------------------------------------------------------------
# copyright_ingest (ADR-2605080600 Phase 5)
# ---------------------------------------------------------------------------

class TestCopyrightIngestGraph:
    def test_build_graph_compiles(self):
        from kotodama.langgraph_graphs.copyright_ingest import build_graph
        graph = build_graph()
        assert graph is not None

    def test_graph_is_invocable(self):
        from kotodama.langgraph_graphs.copyright_ingest import build_graph
        graph = build_graph()
        assert callable(graph.ainvoke) or callable(getattr(graph, "invoke", None))

    def test_state_typeddict_fields(self):
        from kotodama.langgraph_graphs.copyright_ingest import CopyrightIngestState
        import typing
        hints = typing.get_type_hints(CopyrightIngestState)
        assert "crossrefItems" in hints
        assert "dataciteItems" in hints
        assert "crossrefRows" in hints
        assert "dataciteRows" in hints
        assert "crossrefError" in hints
        assert "dataciteError" in hints
        assert "ok" in hints

    def test_doi_rkey_replaces_slash(self):
        from kotodama.langgraph_graphs.copyright_ingest import _doi_rkey
        assert _doi_rkey("10.1234/example") == "doi-10.1234-example"
        assert _doi_rkey("10.5678/foo/bar") == "doi-10.5678-foo-bar"

    def test_crossref_row_returns_none_without_doi(self):
        from kotodama.langgraph_graphs.copyright_ingest import _crossref_row
        assert _crossref_row({}) is None
        assert _crossref_row({"title": "test"}) is None

    def test_crossref_row_maps_literary_kind(self):
        from kotodama.langgraph_graphs.copyright_ingest import _crossref_row
        row = _crossref_row({"DOI": "10.1/test", "type": "journal-article", "title": ["My Paper"]})
        assert row is not None
        assert row["kind"] == "literary"
        assert row["doi"] == "10.1/test"
        assert row["registry"] == "crossref"
        assert row["berne_automatic"] is True
        assert row["vertex_id"].startswith("at://")

    def test_crossref_row_maps_dataset_kind(self):
        from kotodama.langgraph_graphs.copyright_ingest import _crossref_row
        row = _crossref_row({"DOI": "10.2/ds", "type": "dataset"})
        assert row is not None
        assert row["kind"] == "dataset"

    def test_crossref_row_title_from_list(self):
        from kotodama.langgraph_graphs.copyright_ingest import _crossref_row
        row = _crossref_row({"DOI": "10.3/x", "title": ["First Title", "Alt"]})
        assert row["title"] == "First Title"

    def test_crossref_row_title_fallback(self):
        from kotodama.langgraph_graphs.copyright_ingest import _crossref_row
        row = _crossref_row({"DOI": "10.4/x"})
        assert row["title"] == "(no title)"

    def test_datacite_row_returns_none_without_doi(self):
        from kotodama.langgraph_graphs.copyright_ingest import _datacite_row
        assert _datacite_row({}) is None
        assert _datacite_row({"attributes": {}}) is None

    def test_datacite_row_maps_fields(self):
        from kotodama.langgraph_graphs.copyright_ingest import _datacite_row
        item = {
            "attributes": {
                "doi": "10.5/dc",
                "titles": [{"title": "DataCite Paper"}],
            }
        }
        row = _datacite_row(item)
        assert row is not None
        assert row["doi"] == "10.5/dc"
        assert row["title"] == "DataCite Paper"
        assert row["kind"] == "dataset"
        assert row["registry"] == "datacite"
        assert row["berne_automatic"] is True

    def test_datacite_row_uses_id_as_fallback_doi(self):
        from kotodama.langgraph_graphs.copyright_ingest import _datacite_row
        row = _datacite_row({"id": "10.6/fb", "attributes": {}})
        assert row is not None
        assert row["doi"] == "10.6/fb"

    def test_fetch_crossref_on_http_error_returns_empty(self):
        from kotodama.langgraph_graphs.copyright_ingest import fetch_crossref
        import httpx
        with patch("kotodama.langgraph_graphs.copyright_ingest.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.side_effect = httpx.TimeoutException("timeout")
            result = fetch_crossref({})
        assert result["crossrefItems"] == []
        assert "crossrefError" in result

    def test_fetch_datacite_on_http_error_returns_empty(self):
        from kotodama.langgraph_graphs.copyright_ingest import fetch_datacite
        import httpx
        with patch("kotodama.langgraph_graphs.copyright_ingest.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.side_effect = httpx.TimeoutException("timeout")
            result = fetch_datacite({})
        assert result["dataciteItems"] == []
        assert "dataciteError" in result

    def test_insert_crossref_skips_items_without_doi(self):
        from kotodama.langgraph_graphs.copyright_ingest import insert_crossref
        state = {"crossrefItems": [{"title": ["No DOI here"]}]}
        with patch("kotodama.langgraph_graphs.copyright_ingest._bulk_insert_vertex_work", return_value=0) as mock_insert:
            result = insert_crossref(state)
        mock_insert.assert_called_once_with([])
        assert result["crossrefRows"] == 0

    def test_insert_crossref_passes_valid_rows(self):
        from kotodama.langgraph_graphs.copyright_ingest import insert_crossref
        state = {"crossrefItems": [{"DOI": "10.9/x", "type": "journal-article"}]}
        with patch("kotodama.langgraph_graphs.copyright_ingest._bulk_insert_vertex_work", return_value=1) as mock_insert:
            result = insert_crossref(state)
        assert result["crossrefRows"] == 1
        args = mock_insert.call_args[0][0]
        assert len(args) == 1
        assert args[0]["doi"] == "10.9/x"

    def test_insert_datacite_sets_ok_true(self):
        from kotodama.langgraph_graphs.copyright_ingest import insert_datacite
        state = {"dataciteItems": [{"id": "10.8/dc", "attributes": {"titles": [{"title": "T"}]}}]}
        with patch("kotodama.langgraph_graphs.copyright_ingest._bulk_insert_vertex_work", return_value=1):
            result = insert_datacite(state)
        assert result["dataciteRows"] == 1
        assert result["ok"] is True

    def test_insert_datacite_sets_ok_false_on_error(self):
        from kotodama.langgraph_graphs.copyright_ingest import insert_datacite
        state = {"dataciteItems": [{"id": "10.7/dc", "attributes": {}}]}
        with patch("kotodama.langgraph_graphs.copyright_ingest._bulk_insert_vertex_work", side_effect=RuntimeError("db fail")):
            result = insert_datacite(state)
        assert result["ok"] is False
        assert result["dataciteRows"] == 0
        assert "db fail" in result["dataciteError"]

    def test_emit_audit_is_nonfatal(self):
        from kotodama.langgraph_graphs.copyright_ingest import emit_audit
        with patch("kotodama.langgraph_graphs.copyright_ingest.sync_cursor") as mock_cur:
            mock_cur.side_effect = RuntimeError("DB down")
            result = emit_audit({"crossrefRows": 5, "dataciteRows": 3, "ok": True})
        assert result == {}

    def test_fetch_crossref_parses_response(self):
        from kotodama.langgraph_graphs.copyright_ingest import fetch_crossref
        fake_response = MagicMock()
        fake_response.json.return_value = {
            "message": {"items": [{"DOI": "10.1/test", "type": "journal-article"}]}
        }
        fake_response.raise_for_status.return_value = None
        with patch("kotodama.langgraph_graphs.copyright_ingest.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.return_value = fake_response
            result = fetch_crossref({})
        assert len(result["crossrefItems"]) == 1
        assert result["crossrefItems"][0]["DOI"] == "10.1/test"

    def test_fetch_datacite_parses_response(self):
        from kotodama.langgraph_graphs.copyright_ingest import fetch_datacite
        fake_response = MagicMock()
        fake_response.json.return_value = {
            "data": [{"id": "10.2/dc", "attributes": {"doi": "10.2/dc", "titles": [{"title": "T"}]}}]
        }
        fake_response.raise_for_status.return_value = None
        with patch("kotodama.langgraph_graphs.copyright_ingest.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.return_value = fake_response
            result = fetch_datacite({})
        assert len(result["dataciteItems"]) == 1


# ---------------------------------------------------------------------------
# copyright_fulltext (ADR-2605080600 Phase 5)
# ---------------------------------------------------------------------------

class TestCopyrightFulltextGraph:
    def test_build_graph_compiles(self):
        from kotodama.langgraph_graphs.copyright_fulltext import build_graph
        graph = build_graph()
        assert graph is not None

    def test_state_typeddict_fields(self):
        from kotodama.langgraph_graphs.copyright_fulltext import CopyrightFulltextState
        import typing
        hints = typing.get_type_hints(CopyrightFulltextState)
        assert "works" in hints
        assert "blobs" in hints
        assert "blobsStored" in hints
        assert "blobsFailed" in hints
        assert "worksQueried" in hints
        assert "ok" in hints

    def test_work_blob_vertex_id_is_deterministic(self):
        from kotodama.langgraph_graphs.copyright_fulltext import _work_blob_vertex_id
        vid1 = _work_blob_vertex_id("10.1234/test")
        vid2 = _work_blob_vertex_id("10.1234/test")
        assert vid1 == vid2
        assert vid1.startswith("at://did:web:copyright.etzhayyim.com/")

    def test_work_blob_vertex_id_differs_per_doi(self):
        from kotodama.langgraph_graphs.copyright_fulltext import _work_blob_vertex_id
        assert _work_blob_vertex_id("10.1/a") != _work_blob_vertex_id("10.1/b")

    def test_query_oa_works_returns_empty_on_db_error(self):
        from kotodama.langgraph_graphs.copyright_fulltext import query_oa_works
        with patch("kotodama.langgraph_graphs.copyright_fulltext.sync_cursor") as m:
            m.side_effect = RuntimeError("DB down")
            result = query_oa_works({"batchSize": 10})
        assert result["works"] == []
        assert result["worksQueried"] == 0
        assert "error" in result

    def test_fetch_fulltext_skips_non_oa_license(self):
        from kotodama.langgraph_graphs.copyright_fulltext import fetch_fulltext
        fake_unp = MagicMock()
        fake_unp.status_code = 200
        fake_unp.json.return_value = {
            "best_oa_location": {
                "license": "all-rights-reserved",
                "url_for_pdf": "https://example.com/paper.pdf",
            }
        }
        fake_unp.raise_for_status.return_value = None
        state = {"works": [{"vertex_id": "v1", "doi": "10.1/x", "registry": "crossref"}]}
        with patch("kotodama.langgraph_graphs.copyright_fulltext.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.return_value = fake_unp
            result = fetch_fulltext(state)
        assert len(result["blobs"]) == 1
        assert result["blobs"][0]["status"] == "failed"
        assert result["blobs"][0]["fulltext"] is None

    def test_fetch_fulltext_marks_done_for_cc_by(self):
        from kotodama.langgraph_graphs.copyright_fulltext import fetch_fulltext
        fake_unp = MagicMock()
        fake_unp.status_code = 200
        fake_unp.json.return_value = {
            "best_oa_location": {
                "license": "cc-by",
                "url_for_pdf": None,
                "url_for_landing_page": "https://example.com/article",
            }
        }
        fake_unp.raise_for_status.return_value = None

        fake_doc = MagicMock()
        fake_doc.status_code = 200
        fake_doc.headers = {"content-type": "text/html"}
        fake_doc.content = b"<html><body>Open access paper content.</body></html>"
        fake_doc.raise_for_status.return_value = None

        state = {"works": [{"vertex_id": "v1", "doi": "10.1/cc", "registry": "crossref"}]}

        call_count = [0]
        def fake_get(url, **kwargs):
            call_count[0] += 1
            if "unpaywall" in url:
                return fake_unp
            return fake_doc

        with patch("kotodama.langgraph_graphs.copyright_fulltext.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.side_effect = fake_get
            result = fetch_fulltext(state)

        assert len(result["blobs"]) == 1
        blob = result["blobs"][0]
        assert blob["license"] == "cc-by"
        assert blob["status"] == "done"
        assert blob["fulltext"] is not None
        assert "Open access" in blob["fulltext"]

    def test_store_blobs_counts_stored_vs_failed(self):
        from kotodama.langgraph_graphs.copyright_fulltext import store_blobs
        blobs = [
            {"work_vertex_id": "v1", "doi": "10.1/a", "oa_url": "https://x.com",
             "fulltext": "text content", "lang": "en", "license": "cc-by",
             "status": "done", "error": None},
            {"work_vertex_id": "v2", "doi": "10.1/b", "oa_url": None,
             "fulltext": None, "lang": None, "license": None,
             "status": "failed", "error": "no_oa_text"},
        ]
        executed = []
        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: s
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.execute = lambda sql, params: executed.append(params)

        with patch("kotodama.langgraph_graphs.copyright_fulltext.sync_cursor", return_value=mock_cur):
            result = store_blobs({"blobs": blobs})

        assert result["blobsStored"] == 1
        assert result["blobsFailed"] == 1
        assert result["ok"] is True
        assert len(executed) == 2

    def test_emit_audit_is_nonfatal(self):
        from kotodama.langgraph_graphs.copyright_fulltext import emit_audit
        with patch("kotodama.langgraph_graphs.copyright_fulltext.sync_cursor") as m:
            m.side_effect = RuntimeError("DB down")
            result = emit_audit({"blobsStored": 3, "blobsFailed": 1, "ok": True, "worksQueried": 4})
        assert result == {}

    def test_extract_text_from_html_strips_tags(self):
        from kotodama.langgraph_graphs.copyright_fulltext import _extract_text_from_html
        html = b"<html><body><p>Hello <b>world</b></p></body></html>"
        text = _extract_text_from_html(html)
        assert "Hello" in text
        assert "world" in text
        assert "<" not in text


# ---------------------------------------------------------------------------
# webya_site_generation (ADR-2605080600 Phase 5 — smoke)
# ---------------------------------------------------------------------------

class TestWebYaSiteGenerationGraph:
    def test_build_graph_compiles(self):
        try:
            from kotodama.langgraph_graphs.webya_site_generation import build_graph
            graph = build_graph()
            assert graph is not None
        except ImportError:
            pytest.skip("webya_site_generation not importable in this env")
