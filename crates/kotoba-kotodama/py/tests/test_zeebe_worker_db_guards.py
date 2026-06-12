"""Tests for early-return guard paths in zeebe_worker_main.py.

Only validation guards that fire before any DB or LLM call are tested:
  task_generic_db_select    — table required
  task_generic_db_insert    — table/values required; all-null strip
  task_generic_db_bulk_insert — table required; empty rows short-circuit
  task_generic_db_delete    — table/whereExpr required; allowlist check
  task_generic_llm_chat     — user prompt required
  task_generic_llm_json     — user prompt required
  task_generic_db_purge_*   — empty rows → zero counts
  task_generic_rules_evaluate — stable with empty inputs
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# ── pyzeebe stub ────────────────────────────────────────────────────────────
_pyzeebe_stub = types.ModuleType("pyzeebe")
_pyzeebe_stub.ZeebeClient = object  # type: ignore[attr-defined]
_pyzeebe_stub.ZeebeWorker = object  # type: ignore[attr-defined]
_pyzeebe_stub.create_insecure_channel = lambda *a, **kw: None  # type: ignore[attr-defined]
sys.modules.setdefault("pyzeebe", _pyzeebe_stub)

# ── kotodama.llm stub ─────────────────────────────────────────────────────
_llm_stub = types.ModuleType("kotodama.llm")

class _LlmError(Exception):
    pass

_llm_stub.LlmError = _LlmError  # type: ignore[attr-defined]
_llm_stub.call_tier = lambda *a, **kw: {"content": "", "model": "", "latencyMs": 0, "attempts": 1, "usage": {}}  # type: ignore[attr-defined]
_llm_stub.call_tier_json = lambda *a, **kw: {"ok": False, "error": "stub"}  # type: ignore[attr-defined]
_llm_stub.parse_json_content = lambda content: None  # type: ignore[attr-defined]
sys.modules.setdefault("kotodama.llm", _llm_stub)

# ── kotodama.db_sync stub ─────────────────────────────────────────────────
_db_stub = types.ModuleType("kotodama.db_sync")

def _noop_cursor():
    class _C:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **kw): pass
        def fetchone(self): return None
        def fetchall(self): return []
        description = None
        rowcount = 0
    return _C()

_db_stub.sync_cursor = _noop_cursor  # type: ignore[attr-defined]
sys.modules.setdefault("kotodama.db_sync", _db_stub)

# ── kotodama base package stub ────────────────────────────────────────────
_pkg_stub = types.ModuleType("kotodama")
_pkg_stub.llm = _llm_stub  # type: ignore[attr-defined]
sys.modules.setdefault("kotodama", _pkg_stub)

# ── load module with isolated name ──────────────────────────────────────────
_MOD_NAME = "_zeebe_worker_db_guards"
if _MOD_NAME not in sys.modules:
    _src = _py_src / "kotodama" / "zeebe_worker_main.py"
    _spec = importlib.util.spec_from_file_location(_MOD_NAME, _src)
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_MOD_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

Z = sys.modules[_MOD_NAME]


# ─── task_generic_db_select — no table ──────────────────────────────────────

def test_db_select_no_table_returns_error() -> None:
    result = asyncio.run(Z.task_generic_db_select())
    assert "error" in result


def test_db_select_no_table_error_mentions_table() -> None:
    result = asyncio.run(Z.task_generic_db_select())
    assert "table" in result["error"]


def test_db_select_no_table_rows_empty() -> None:
    result = asyncio.run(Z.task_generic_db_select())
    assert result.get("rows", []) == [] or "error" in result


def test_db_select_returns_dict() -> None:
    result = asyncio.run(Z.task_generic_db_select())
    assert isinstance(result, dict)


def test_db_select_raw_sql_no_error_with_stub() -> None:
    # raw-SQL path: stubs the cursor so returns rows=[]
    result = asyncio.run(Z.task_generic_db_select(
        sql="SELECT 1 AS n",
        params=[],
    ))
    assert isinstance(result, dict)
    assert "rows" in result or "error" in result


def test_db_select_invalid_order_by_returns_error() -> None:
    result = asyncio.run(Z.task_generic_db_select(
        table="vertex_actor",
        orderBy="1; DROP TABLE vertex_actor",
    ))
    assert "error" in result


def test_db_select_invalid_filter_op_returns_error() -> None:
    result = asyncio.run(Z.task_generic_db_select(
        table="vertex_actor",
        extraFilters=[{"column": "vertex_id", "op": "INVALID_OP", "value": "x"}],
    ))
    assert "error" in result


def test_db_select_invalid_filter_column_returns_error() -> None:
    result = asyncio.run(Z.task_generic_db_select(
        table="vertex_actor",
        extraFilters=[{"column": "'; DROP TABLE vertex_actor --", "op": "=", "value": "x"}],
    ))
    assert "error" in result


# ─── task_generic_db_insert — no table / no values ──────────────────────────

def test_db_insert_no_table_returns_error() -> None:
    result = asyncio.run(Z.task_generic_db_insert())
    assert "error" in result


def test_db_insert_no_table_error_mentions_table() -> None:
    result = asyncio.run(Z.task_generic_db_insert())
    assert "table" in result["error"]


def test_db_insert_no_table_returns_dict() -> None:
    result = asyncio.run(Z.task_generic_db_insert())
    assert isinstance(result, dict)


def test_db_insert_all_null_values_returns_error() -> None:
    # All values are None → stripped → error before DB
    result = asyncio.run(Z.task_generic_db_insert(
        table="vertex_actor",
        values={"vertex_id": None, "name": None},
    ))
    assert "error" in result


def test_db_insert_all_null_values_inserted_zero() -> None:
    result = asyncio.run(Z.task_generic_db_insert(
        table="vertex_actor",
        values={"vertex_id": None},
    ))
    assert result.get("inserted", 0) == 0 or "error" in result


# ─── task_generic_db_bulk_insert — no table / empty rows ─────────────────────

def test_db_bulk_insert_no_table_returns_error() -> None:
    result = asyncio.run(Z.task_generic_db_bulk_insert())
    assert "error" in result


def test_db_bulk_insert_no_table_error_mentions_table() -> None:
    result = asyncio.run(Z.task_generic_db_bulk_insert())
    assert "table" in result["error"]


def test_db_bulk_insert_no_table_inserted_zero() -> None:
    result = asyncio.run(Z.task_generic_db_bulk_insert())
    assert result.get("inserted", 0) == 0


def test_db_bulk_insert_returns_dict() -> None:
    result = asyncio.run(Z.task_generic_db_bulk_insert())
    assert isinstance(result, dict)


def test_db_bulk_insert_empty_rows_no_db_call() -> None:
    # Empty rows list → short-circuits before DB
    result = asyncio.run(Z.task_generic_db_bulk_insert(
        table="vertex_actor",
        rows=[],
    ))
    assert result.get("inserted") == 0


def test_db_bulk_insert_none_rows_no_db_call() -> None:
    result = asyncio.run(Z.task_generic_db_bulk_insert(
        table="vertex_actor",
        rows=None,
    ))
    assert result.get("inserted") == 0


# ─── task_generic_db_delete — guards ─────────────────────────────────────────

def test_db_delete_no_table_returns_error() -> None:
    result = asyncio.run(Z.task_generic_db_delete())
    assert "error" in result


def test_db_delete_no_table_error_mentions_table() -> None:
    result = asyncio.run(Z.task_generic_db_delete())
    assert "table" in result["error"]


def test_db_delete_no_table_deleted_zero() -> None:
    result = asyncio.run(Z.task_generic_db_delete())
    assert result.get("deleted", 0) == 0


def test_db_delete_returns_dict() -> None:
    result = asyncio.run(Z.task_generic_db_delete())
    assert isinstance(result, dict)


def test_db_delete_invalid_table_returns_error() -> None:
    result = asyncio.run(Z.task_generic_db_delete(
        table="not_a_valid_table",
        whereExpr="vertex_id = %s",
    ))
    assert "error" in result


def test_db_delete_invalid_table_allowlist_message() -> None:
    result = asyncio.run(Z.task_generic_db_delete(
        table="not_a_valid_table",
        whereExpr="vertex_id = %s",
    ))
    assert "allowlist" in result["error"] or "table" in result["error"]


def test_db_delete_empty_where_expr_returns_error() -> None:
    result = asyncio.run(Z.task_generic_db_delete(
        table="vertex_actor",
        whereExpr="",
    ))
    assert "error" in result


def test_db_delete_empty_where_expr_refuses_full_delete() -> None:
    result = asyncio.run(Z.task_generic_db_delete(
        table="vertex_actor",
        whereExpr="   ",
    ))
    assert "error" in result


def test_db_delete_empty_where_expr_deleted_zero() -> None:
    result = asyncio.run(Z.task_generic_db_delete(
        table="vertex_actor",
        whereExpr="",
    ))
    assert result.get("deleted", 0) == 0


# ─── task_generic_llm_chat — no user prompt ──────────────────────────────────

def test_llm_chat_no_user_returns_error() -> None:
    result = asyncio.run(Z.task_generic_llm_chat())
    assert "error" in result


def test_llm_chat_empty_user_returns_error() -> None:
    result = asyncio.run(Z.task_generic_llm_chat(user=""))
    assert "error" in result


def test_llm_chat_no_user_error_mentions_prompt() -> None:
    result = asyncio.run(Z.task_generic_llm_chat())
    assert "prompt" in result["error"] or "user" in result["error"]


def test_llm_chat_returns_dict() -> None:
    result = asyncio.run(Z.task_generic_llm_chat())
    assert isinstance(result, dict)


# ─── task_generic_llm_json — no user prompt ──────────────────────────────────

def test_llm_json_no_user_returns_error() -> None:
    result = asyncio.run(Z.task_generic_llm_json())
    assert "error" in result


def test_llm_json_empty_user_returns_error() -> None:
    result = asyncio.run(Z.task_generic_llm_json(user=""))
    assert "error" in result


def test_llm_json_returns_dict() -> None:
    result = asyncio.run(Z.task_generic_llm_json())
    assert isinstance(result, dict)


# ─── task_generic_db_purge_fuyou_pii — empty rows ────────────────────────────

def test_purge_fuyou_pii_no_rows_returns_zero() -> None:
    result = asyncio.run(Z.task_generic_db_purge_fuyou_pii())
    assert result.get("deleted") == 0


def test_purge_fuyou_pii_empty_list_returns_zero() -> None:
    result = asyncio.run(Z.task_generic_db_purge_fuyou_pii(rows=[]))
    assert result.get("deleted") == 0


def test_purge_fuyou_pii_returns_dict() -> None:
    result = asyncio.run(Z.task_generic_db_purge_fuyou_pii())
    assert isinstance(result, dict)


# ─── task_generic_db_purge_datacenter_access_pii — empty rows ────────────────

def test_purge_datacenter_pii_no_rows_returns_zero() -> None:
    result = asyncio.run(Z.task_generic_db_purge_datacenter_access_pii())
    assert result.get("deleted") == 0


def test_purge_datacenter_pii_empty_list_returns_zero() -> None:
    result = asyncio.run(Z.task_generic_db_purge_datacenter_access_pii(rows=[]))
    assert result.get("deleted") == 0


def test_purge_datacenter_pii_returns_dict() -> None:
    result = asyncio.run(Z.task_generic_db_purge_datacenter_access_pii())
    assert isinstance(result, dict)


# ─── task_generic_rules_evaluate — stable with empty/minimal input ────────────

def test_rules_evaluate_empty_ruleset_returns_dict() -> None:
    result = asyncio.run(Z.task_generic_rules_evaluate())
    assert isinstance(result, dict)


def test_rules_evaluate_has_findings_key() -> None:
    result = asyncio.run(Z.task_generic_rules_evaluate())
    assert "findings" in result or "ok" in result or "error" in result


def test_rules_evaluate_unknown_ruleset_returns_error() -> None:
    result = asyncio.run(Z.task_generic_rules_evaluate(ruleSet="unknown_rule_xyz"))
    assert isinstance(result, dict)


# ─── task_chat — no prompt ───────────────────────────────────────────────────

def test_chat_no_prompt_returns_error() -> None:
    result = asyncio.run(Z.task_chat())
    assert "error" in result


def test_chat_empty_prompt_returns_error() -> None:
    result = asyncio.run(Z.task_chat(prompt=""))
    assert "error" in result


def test_chat_no_prompt_error_mentions_prompt() -> None:
    result = asyncio.run(Z.task_chat())
    assert "prompt" in result["error"]


def test_chat_returns_dict() -> None:
    result = asyncio.run(Z.task_chat())
    assert isinstance(result, dict)


# ─── task_storyboard — no story ──────────────────────────────────────────────

def test_storyboard_no_story_returns_error() -> None:
    result = asyncio.run(Z.task_storyboard())
    assert "error" in result


def test_storyboard_empty_story_returns_error() -> None:
    result = asyncio.run(Z.task_storyboard(story=""))
    assert "error" in result


def test_storyboard_no_story_error_mentions_story() -> None:
    result = asyncio.run(Z.task_storyboard())
    assert "story" in result["error"]


def test_storyboard_returns_dict() -> None:
    result = asyncio.run(Z.task_storyboard())
    assert isinstance(result, dict)


# ─── task_translate — no text ────────────────────────────────────────────────

def test_translate_no_text_returns_translated_empty() -> None:
    # empty text → short-circuit with {"translated": ""}
    result = asyncio.run(Z.task_translate())
    assert "translated" in result
    assert result["translated"] == ""


def test_translate_no_text_returns_dict() -> None:
    result = asyncio.run(Z.task_translate())
    assert isinstance(result, dict)


def test_translate_same_src_dst_skips() -> None:
    # same language → skipped short-circuit
    result = asyncio.run(Z.task_translate(text="hello", sourceLang="en", targetLang="en"))
    assert result.get("skipped") is True


def test_translate_same_src_dst_preserves_text() -> None:
    result = asyncio.run(Z.task_translate(text="hello", sourceLang="en", targetLang="en"))
    assert result.get("translated") == "hello"


def test_translate_empty_dst_lang_skips() -> None:
    result = asyncio.run(Z.task_translate(text="hello", targetLang=""))
    assert result.get("skipped") is True or "translated" in result


# ─── task_shinka_* — no actorDid ─────────────────────────────────────────────

def test_shinka_load_and_resolve_no_actor_returns_error() -> None:
    result = asyncio.run(Z.task_shinka_load_and_resolve())
    assert "error" in result


def test_shinka_load_and_resolve_error_mentions_actor() -> None:
    result = asyncio.run(Z.task_shinka_load_and_resolve())
    assert "actorDid" in result["error"] or "actor" in result["error"].lower()


def test_shinka_load_and_resolve_returns_dict() -> None:
    result = asyncio.run(Z.task_shinka_load_and_resolve())
    assert isinstance(result, dict)


def test_shinka_compose_no_actor_returns_error() -> None:
    result = asyncio.run(Z.task_shinka_compose())
    assert "error" in result


def test_shinka_compose_returns_dict() -> None:
    result = asyncio.run(Z.task_shinka_compose())
    assert isinstance(result, dict)


def test_shinka_write_heartbeat_no_actor_returns_error() -> None:
    result = asyncio.run(Z.task_shinka_write_heartbeat())
    assert "error" in result


def test_shinka_write_heartbeat_returns_dict() -> None:
    result = asyncio.run(Z.task_shinka_write_heartbeat())
    assert isinstance(result, dict)


def test_shinka_emit_evolution_no_actor_returns_error() -> None:
    result = asyncio.run(Z.task_shinka_emit_evolution())
    assert "error" in result


def test_shinka_emit_evolution_returns_dict() -> None:
    result = asyncio.run(Z.task_shinka_emit_evolution())
    assert isinstance(result, dict)


# ─── task_generic_db_purge_* — additional purge variants ────────────────────

def test_purge_epfo_pii_no_rows_returns_zero() -> None:
    result = asyncio.run(Z.task_generic_db_purge_epfo_pii())
    assert result.get("deleted") == 0


def test_purge_epfo_pii_returns_dict() -> None:
    result = asyncio.run(Z.task_generic_db_purge_epfo_pii())
    assert isinstance(result, dict)


def test_purge_esic_pii_no_rows_returns_zero() -> None:
    result = asyncio.run(Z.task_generic_db_purge_esic_pii())
    assert result.get("deleted") == 0


def test_purge_itr1_pii_no_rows_returns_zero() -> None:
    result = asyncio.run(Z.task_generic_db_purge_itr1_pii())
    assert result.get("deleted") == 0


def test_purge_gstr3b_pii_no_rows_returns_zero() -> None:
    result = asyncio.run(Z.task_generic_db_purge_gstr3b_pii())
    assert result.get("deleted") == 0


def test_purge_seiyaku_confidential_no_rows_returns_zero() -> None:
    result = asyncio.run(Z.task_generic_db_purge_seiyaku_confidential())
    assert result.get("deleted") == 0


def test_purge_seiyaku_confidential_returns_dict() -> None:
    result = asyncio.run(Z.task_generic_db_purge_seiyaku_confidential())
    assert isinstance(result, dict)


# ─── task_generic_audit_emit — missing actor/action ──────────────────────────

def test_audit_emit_no_actor_returns_error() -> None:
    result = asyncio.run(Z.task_generic_audit_emit())
    assert "error" in result


def test_audit_emit_no_action_returns_error() -> None:
    result = asyncio.run(Z.task_generic_audit_emit(actor="did:web:test.etzhayyim.com"))
    assert "error" in result


def test_audit_emit_no_args_error_mentions_actor_and_action() -> None:
    result = asyncio.run(Z.task_generic_audit_emit())
    assert "actor" in result["error"] or "action" in result["error"]


def test_audit_emit_no_args_returns_dict() -> None:
    result = asyncio.run(Z.task_generic_audit_emit())
    assert isinstance(result, dict)


def test_audit_emit_accepts_bpmn_aliases(monkeypatch) -> None:
    calls: list[tuple[str, tuple]] = []

    class _Cursor:
        rowcount = 1

        def execute(self, sql: str, params: tuple = ()) -> None:
            calls.append((sql, params))

    class _Ctx:
        def __enter__(self):
            return _Cursor()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(Z, "sync_cursor", lambda: _Ctx())

    result = asyncio.run(
        Z.task_generic_audit_emit(
            actor_did="did:web:jp-corp-finance.etzhayyim.com",
            event_type="jpCorpFinance.dailyIngest.completed",
            attributes={"case_id": "run-1", "recordsWritten": 3},
        )
    )

    assert result["emitted"] is True
    assert calls
    payload = calls[0][1][6]
    assert "jpCorpFinance.dailyIngest.completed" in payload
    assert "recordsWritten" in payload


# ─── task_ingest_run_mark_completed — missing runId ──────────────────────────

def test_ingest_run_mark_completed_no_run_id_returns_error() -> None:
    result = asyncio.run(Z.task_ingest_run_mark_completed())
    assert result["ok"] is False


def test_ingest_run_mark_completed_no_run_id_error_mentions_runid() -> None:
    result = asyncio.run(Z.task_ingest_run_mark_completed())
    assert "runId" in result.get("error", "")


def test_ingest_run_mark_completed_returns_dict() -> None:
    result = asyncio.run(Z.task_ingest_run_mark_completed())
    assert isinstance(result, dict)


# ─── task_blockchain_head_ingest — missing runId / sourceId ──────────────────

def test_blockchain_head_ingest_no_run_id_returns_error() -> None:
    result = asyncio.run(Z.task_blockchain_head_ingest())
    assert result["ok"] is False


def test_blockchain_head_ingest_no_run_id_error_mentions_runid() -> None:
    result = asyncio.run(Z.task_blockchain_head_ingest())
    assert "runId" in result.get("error", "")


def test_blockchain_head_ingest_no_source_id_returns_error() -> None:
    result = asyncio.run(Z.task_blockchain_head_ingest(runId="run-001"))
    assert result["ok"] is False


def test_blockchain_head_ingest_no_source_id_error_mentions_sourceid() -> None:
    result = asyncio.run(Z.task_blockchain_head_ingest(runId="run-001"))
    assert "sourceId" in result.get("error", "")


def test_blockchain_head_ingest_returns_dict() -> None:
    result = asyncio.run(Z.task_blockchain_head_ingest())
    assert isinstance(result, dict)


# ─── task_rw_health_probe — missing script returns probe-unavailable ─────────

def test_rw_health_probe_missing_script_returns_unhealthy() -> None:
    import os as _os
    env_bak = _os.environ.get("RW_HEALTH_GATE_SCRIPT")
    _os.environ["RW_HEALTH_GATE_SCRIPT"] = "/nonexistent/path/to/rw-health-gate.sh"
    try:
        result = asyncio.run(Z.task_rw_health_probe())
    finally:
        if env_bak is None:
            _os.environ.pop("RW_HEALTH_GATE_SCRIPT", None)
        else:
            _os.environ["RW_HEALTH_GATE_SCRIPT"] = env_bak
    assert result["healthy"] is False


def test_rw_health_probe_missing_script_exit_code_2() -> None:
    import os as _os
    env_bak = _os.environ.get("RW_HEALTH_GATE_SCRIPT")
    _os.environ["RW_HEALTH_GATE_SCRIPT"] = "/nonexistent/path/to/rw-health-gate.sh"
    try:
        result = asyncio.run(Z.task_rw_health_probe())
    finally:
        if env_bak is None:
            _os.environ.pop("RW_HEALTH_GATE_SCRIPT", None)
        else:
            _os.environ["RW_HEALTH_GATE_SCRIPT"] = env_bak
    assert result["exitCode"] == 2


def test_rw_health_probe_returns_dict() -> None:
    import os as _os
    env_bak = _os.environ.get("RW_HEALTH_GATE_SCRIPT")
    _os.environ["RW_HEALTH_GATE_SCRIPT"] = "/nonexistent/path/to/rw-health-gate.sh"
    try:
        result = asyncio.run(Z.task_rw_health_probe())
    finally:
        if env_bak is None:
            _os.environ.pop("RW_HEALTH_GATE_SCRIPT", None)
        else:
            _os.environ["RW_HEALTH_GATE_SCRIPT"] = env_bak
    assert isinstance(result, dict)


# ─── task_gyosei_source_link — missing caseId / empty sourceIds ──────────────

def test_gyosei_source_link_no_case_id_returns_error() -> None:
    result = asyncio.run(Z.task_gyosei_source_link())
    assert "error" in result


def test_gyosei_source_link_no_case_id_linked_zero() -> None:
    result = asyncio.run(Z.task_gyosei_source_link())
    assert result.get("linked") == 0


def test_gyosei_source_link_empty_source_ids_linked_zero() -> None:
    result = asyncio.run(Z.task_gyosei_source_link(caseId="case-001", sourceIds=[]))
    assert result.get("linked") == 0


def test_gyosei_source_link_empty_source_ids_no_error() -> None:
    result = asyncio.run(Z.task_gyosei_source_link(caseId="case-001", sourceIds=[]))
    assert "error" not in result


def test_gyosei_source_link_returns_dict() -> None:
    result = asyncio.run(Z.task_gyosei_source_link())
    assert isinstance(result, dict)


# ─── task_shinka_tick — missing actor ────────────────────────────────────────

def test_shinka_tick_no_actor_returns_error() -> None:
    result = asyncio.run(Z.task_shinka_tick())
    assert "error" in result


def test_shinka_tick_no_actor_error_mentions_actor() -> None:
    result = asyncio.run(Z.task_shinka_tick())
    assert "actor" in result["error"]


def test_shinka_tick_returns_dict() -> None:
    result = asyncio.run(Z.task_shinka_tick())
    assert isinstance(result, dict)


# ─── task_legal_corpus_search_document — missing queryText ───────────────────

def test_legal_corpus_search_document_no_query_returns_error() -> None:
    result = asyncio.run(Z.task_legal_corpus_search_document())
    assert "error" in result


def test_legal_corpus_search_document_no_query_hits_empty() -> None:
    result = asyncio.run(Z.task_legal_corpus_search_document())
    assert result.get("hits") == []


def test_legal_corpus_search_document_no_query_hit_count_zero() -> None:
    result = asyncio.run(Z.task_legal_corpus_search_document())
    assert result.get("hitCount") == 0


def test_legal_corpus_search_document_returns_dict() -> None:
    result = asyncio.run(Z.task_legal_corpus_search_document())
    assert isinstance(result, dict)


# ─── task_legal_corpus_fetch_body_text — missing canonicalUri ────────────────

def test_legal_corpus_fetch_body_text_no_uri_returns_error() -> None:
    result = asyncio.run(Z.task_legal_corpus_fetch_body_text())
    assert "error" in result


def test_legal_corpus_fetch_body_text_no_uri_body_text_empty() -> None:
    result = asyncio.run(Z.task_legal_corpus_fetch_body_text())
    assert result.get("bodyText") == ""


def test_legal_corpus_fetch_body_text_returns_dict() -> None:
    result = asyncio.run(Z.task_legal_corpus_fetch_body_text())
    assert isinstance(result, dict)


# ─── task_generic_tls_probe — host/port guards ───────────────────────────────

def test_generic_tls_probe_no_host_returns_error() -> None:
    result = asyncio.run(Z.task_generic_tls_probe())
    assert result["ok"] is False


def test_generic_tls_probe_no_host_error_mentions_host() -> None:
    result = asyncio.run(Z.task_generic_tls_probe())
    assert "host" in result.get("error", "")


def test_generic_tls_probe_invalid_port_returns_error() -> None:
    result = asyncio.run(Z.task_generic_tls_probe(host="example.com", port="notaport"))  # type: ignore[arg-type]
    assert result["ok"] is False


def test_generic_tls_probe_port_out_of_range_returns_error() -> None:
    result = asyncio.run(Z.task_generic_tls_probe(host="example.com", port=99999))
    assert result["ok"] is False


def test_generic_tls_probe_returns_dict() -> None:
    result = asyncio.run(Z.task_generic_tls_probe())
    assert isinstance(result, dict)


# ─── task_classify_t3 — score out of gray zone skips LLM ────────────────────

def test_classify_t3_score_zero_skips() -> None:
    result = asyncio.run(Z.task_classify_t3(t1Score=0))
    assert result.get("skipped") is True


def test_classify_t3_score_below_gray_zone_skips() -> None:
    result = asyncio.run(Z.task_classify_t3(t1Score=59))
    assert result.get("skipped") is True


def test_classify_t3_score_above_gray_zone_skips() -> None:
    result = asyncio.run(Z.task_classify_t3(t1Score=85))
    assert result.get("skipped") is True


def test_classify_t3_score_at_ceiling_skips() -> None:
    result = asyncio.run(Z.task_classify_t3(t1Score=100))
    assert result.get("skipped") is True


def test_classify_t3_skipped_reason_not_gray_zone() -> None:
    result = asyncio.run(Z.task_classify_t3(t1Score=0))
    assert result.get("reason") == "not-gray-zone"


def test_classify_t3_non_int_score_returns_error() -> None:
    result = asyncio.run(Z.task_classify_t3(t1Score="bad"))  # type: ignore[arg-type]
    assert "error" in result


def test_classify_t3_returns_dict() -> None:
    result = asyncio.run(Z.task_classify_t3())
    assert isinstance(result, dict)


# ─── task_generic_pds_dispatch — missing type ────────────────────────────────

def test_generic_pds_dispatch_no_type_returns_error() -> None:
    result = asyncio.run(Z.task_generic_pds_dispatch())
    assert "error" in result


def test_generic_pds_dispatch_no_type_error_mentions_type() -> None:
    result = asyncio.run(Z.task_generic_pds_dispatch())
    assert "type" in result["error"] or "NSID" in result["error"]


def test_generic_pds_dispatch_returns_dict() -> None:
    result = asyncio.run(Z.task_generic_pds_dispatch())
    assert isinstance(result, dict)


def test_generic_pds_dispatch_exposes_cid_and_uri(monkeypatch) -> None:
    monkeypatch.setattr(Z, "_PDS_LEGACY_INTERNAL_TRUST", True)

    async def _fake_to_thread(fn, *args, **kwargs):
        return 200, {"cid": "bafy-pub", "uri": "at://did:web:pd-color.etzhayyim.com/app.record/1"}

    monkeypatch.setattr(Z.asyncio, "to_thread", _fake_to_thread)
    result = asyncio.run(Z.task_generic_pds_dispatch(
        type="com.etzhayyim.apps.publicDomainColorization.publication",
        payload={"workId": "pdcolor:work:gertie"},
    ))
    assert result["cid"] == "bafy-pub"
    assert result["uri"] == "at://did:web:pd-color.etzhayyim.com/app.record/1"


# ─── task_open_patent_expired_drug_patent_screen — pure logic ────────────────

def test_open_patent_screen_no_payload_returns_dict() -> None:
    result = asyncio.run(Z.task_open_patent_expired_drug_patent_screen())
    assert isinstance(result, dict)


def test_open_patent_screen_no_payload_has_eligible_key() -> None:
    result = asyncio.run(Z.task_open_patent_expired_drug_patent_screen())
    assert "eligible" in result


def test_open_patent_screen_no_payload_not_eligible() -> None:
    result = asyncio.run(Z.task_open_patent_expired_drug_patent_screen())
    assert result["eligible"] is False


def test_open_patent_screen_no_payload_has_status() -> None:
    result = asyncio.run(Z.task_open_patent_expired_drug_patent_screen())
    assert "status" in result


# ─── task_open_patent_expired_drug_patent_collect — pure logic ───────────────

def test_open_patent_collect_no_payload_returns_dict() -> None:
    result = asyncio.run(Z.task_open_patent_expired_drug_patent_collect())
    assert isinstance(result, dict)


def test_open_patent_collect_no_payload_scanned_zero() -> None:
    result = asyncio.run(Z.task_open_patent_expired_drug_patent_collect())
    assert result.get("scannedCount") == 0


def test_open_patent_collect_no_payload_candidate_zero() -> None:
    result = asyncio.run(Z.task_open_patent_expired_drug_patent_collect())
    assert result.get("candidateCount") == 0


# ─── task_open_patent_generic_manufacturing_plan — pure logic ────────────────

def test_open_patent_plan_no_payload_returns_dict() -> None:
    result = asyncio.run(Z.task_open_patent_generic_manufacturing_plan())
    assert isinstance(result, dict)


def test_open_patent_plan_no_payload_has_vertex_id() -> None:
    result = asyncio.run(Z.task_open_patent_generic_manufacturing_plan())
    assert "vertexId" in result


def test_open_patent_plan_no_payload_status_planned() -> None:
    result = asyncio.run(Z.task_open_patent_generic_manufacturing_plan())
    assert result.get("status") == "planned"


# ─── task_open_patent_generic_manufacturing_validate_seiyaku_batch_draft — pure

def test_open_patent_validate_no_payload_has_findings() -> None:
    result = asyncio.run(Z.task_open_patent_generic_manufacturing_validate_seiyaku_batch_draft())
    assert "findings" in result


def test_open_patent_validate_empty_payload_not_passed() -> None:
    result = asyncio.run(Z.task_open_patent_generic_manufacturing_validate_seiyaku_batch_draft())
    assert result.get("passed") is False


def test_open_patent_validate_returns_dict() -> None:
    result = asyncio.run(Z.task_open_patent_generic_manufacturing_validate_seiyaku_batch_draft())
    assert isinstance(result, dict)


# ─── task_open_patent_generic_manufacturing_handoff_seiyaku — pure ───────────

def test_open_patent_handoff_no_payload_status_queued() -> None:
    result = asyncio.run(Z.task_open_patent_generic_manufacturing_handoff_seiyaku())
    assert result.get("status") == "handoff_queued"


def test_open_patent_handoff_returns_dict() -> None:
    result = asyncio.run(Z.task_open_patent_generic_manufacturing_handoff_seiyaku())
    assert isinstance(result, dict)


# ─── task_open_patent_generic_manufacturing_queue_seiyaku_batch_start — pure ─

def test_open_patent_queue_no_payload_status_skipped() -> None:
    result = asyncio.run(Z.task_open_patent_generic_manufacturing_queue_seiyaku_batch_start())
    assert result.get("status") == "skipped_invalid"


def test_open_patent_queue_returns_dict() -> None:
    result = asyncio.run(Z.task_open_patent_generic_manufacturing_queue_seiyaku_batch_start())
    assert isinstance(result, dict)


# ─── task_open_patent_generic_manufacturing_ack_seiyaku_batch_start — pure ───

def test_open_patent_ack_no_payload_status_acknowledged() -> None:
    result = asyncio.run(Z.task_open_patent_generic_manufacturing_ack_seiyaku_batch_start())
    assert result.get("status") == "acknowledged"


def test_open_patent_ack_returns_dict() -> None:
    result = asyncio.run(Z.task_open_patent_generic_manufacturing_ack_seiyaku_batch_start())
    assert isinstance(result, dict)


# ─── task_open_patent_generic_manufacturing_summarize_seiyaku_start_progress ─

def test_open_patent_summarize_no_payload_status_pending() -> None:
    result = asyncio.run(Z.task_open_patent_generic_manufacturing_summarize_seiyaku_start_progress())
    assert result.get("progressStatus") == "pending"


def test_open_patent_summarize_returns_dict() -> None:
    result = asyncio.run(Z.task_open_patent_generic_manufacturing_summarize_seiyaku_start_progress())
    assert isinstance(result, dict)


# ─── task_open_patent_expired_drug_patent_record_blocker — pure ──────────────

def test_open_patent_record_blocker_no_payload_not_active() -> None:
    result = asyncio.run(Z.task_open_patent_expired_drug_patent_record_blocker())
    assert result.get("active") is False


def test_open_patent_record_blocker_returns_dict() -> None:
    result = asyncio.run(Z.task_open_patent_expired_drug_patent_record_blocker())
    assert isinstance(result, dict)


# ─── task_open_patent_generic_manufacturing_prepare_seiyaku_batch_draft ───────

def test_open_patent_prepare_draft_no_payload_ok() -> None:
    result = asyncio.run(Z.task_open_patent_generic_manufacturing_prepare_seiyaku_batch_draft())
    assert result.get("ok") is True


def test_open_patent_prepare_draft_no_payload_status_draft_ready() -> None:
    result = asyncio.run(Z.task_open_patent_generic_manufacturing_prepare_seiyaku_batch_draft())
    assert result.get("status") == "draft_ready"


def test_open_patent_prepare_draft_returns_dict() -> None:
    result = asyncio.run(Z.task_open_patent_generic_manufacturing_prepare_seiyaku_batch_draft())
    assert isinstance(result, dict)


# ─── task_open_patent_expired_drug_patent_pipeline — pure composite ──────────

def test_open_patent_pipeline_no_payload_returns_dict() -> None:
    result = asyncio.run(Z.task_open_patent_expired_drug_patent_pipeline())
    assert isinstance(result, dict)


def test_open_patent_pipeline_no_payload_has_collected_count() -> None:
    result = asyncio.run(Z.task_open_patent_expired_drug_patent_pipeline())
    assert "collectedCount" in result


def test_open_patent_pipeline_no_payload_zero_screened() -> None:
    result = asyncio.run(Z.task_open_patent_expired_drug_patent_pipeline())
    assert result.get("screened", 0) == 0


# ─── task_generic_xrpc_invoke — NSID guards ──────────────────────────────────

def test_generic_xrpc_invoke_no_nsid_returns_error() -> None:
    result = asyncio.run(Z.task_generic_xrpc_invoke())
    assert "error" in result


def test_generic_xrpc_invoke_no_nsid_status_400() -> None:
    result = asyncio.run(Z.task_generic_xrpc_invoke())
    assert result.get("status") == 400


def test_generic_xrpc_invoke_invalid_nsid_returns_error() -> None:
    result = asyncio.run(Z.task_generic_xrpc_invoke(nsid="not.valid.!!nsid"))
    assert "error" in result


def test_generic_xrpc_invoke_no_base_url_no_actor_returns_error() -> None:
    result = asyncio.run(Z.task_generic_xrpc_invoke(nsid="com.etzhayyim.apps.foo.bar"))
    assert "error" in result


def test_generic_xrpc_invoke_bad_scheme_returns_error() -> None:
    result = asyncio.run(Z.task_generic_xrpc_invoke(
        nsid="com.etzhayyim.apps.foo.bar", baseUrl="ftp://example.com"
    ))
    assert "error" in result


def test_generic_xrpc_invoke_returns_dict() -> None:
    result = asyncio.run(Z.task_generic_xrpc_invoke())
    assert isinstance(result, dict)


def test_pd_color_xrpc_resolve_source_local_response() -> None:
    result = asyncio.run(Z.task_generic_xrpc_invoke(
        nsid="com.etzhayyim.apps.storage.resolveSourceAsset",
        payload={
            "workId": "pdcolor:work:gertie",
            "title": "Gertie the Dinosaur",
            "sourceIpfsCid": "bafy-source",
        },
    ))
    assert result["response"]["workId"] == "pdcolor:work:gertie"
    assert result["response"]["sourceIpfsCid"] == "bafy-source"


def test_pd_color_xrpc_translate_batch_local_manifest(monkeypatch) -> None:
    async def _fake_add(kind, payload):
        assert kind == "pd-color-subtitle-manifest"
        assert payload["targetLangs"] == ["ja", "en"]
        return "bafy-subtitles"

    monkeypatch.setattr(Z, "_pd_color_add_json_manifest", _fake_add)
    result = asyncio.run(Z.task_generic_xrpc_invoke(
        nsid="com.etzhayyim.apps.i18n.translateBatch",
        payload={"sourceCid": "bafy-timed-text", "sourceLang": "en", "targetLangs": ["ja", "en"]},
    ))
    assert result["response"]["manifestCid"] == "bafy-subtitles"
    assert result["response"]["translatedCount"] == 2


def test_pd_color_video_restore_frames_worker_wraps_quality_payload(monkeypatch) -> None:
    calls = []

    async def _fake_comfy(route="", body=None, outputFormat="auto", timeoutSec=0, repo=""):
        calls.append((route, body, outputFormat, timeoutSec, repo))
        return {"status": 200, "blobCid": "bafy-restored", "meta": {"manifestKind": "pd-color-restored-frames"}}

    monkeypatch.setattr(Z, "task_generic_comfyui_call", _fake_comfy)
    result = asyncio.run(Z.task_pd_color_video_restore_frames(
        sourceIpfsCid="bafy-source",
        shotMapCid="bafy-shot-map",
        workKind="animation",
        qualityProfile="archive-4k",
        targetResolution="2160p",
    ))

    assert result["blobCid"] == "bafy-restored"
    route, body, output_format, timeout_sec, _repo = calls[0]
    assert route == "/v1/video/restore"
    assert output_format == "blob"
    assert timeout_sec == 600
    assert body["sourceIpfsCid"] == "bafy-source"
    assert body["qualityProfile"] == "archive-4k"
    assert body["targetResolution"] == "2160p"
    assert body["scratchRepair"] is True


def test_pd_color_worker_records_process_event_when_run_id_present(monkeypatch) -> None:
    events = []

    async def _fake_comfy(route="", body=None, outputFormat="auto", timeoutSec=0, repo=""):
        return {"status": 200, "blobCid": "bafy-restored", "meta": {"manifestKind": "pd-color-restored-frames"}}

    async def _fake_insert(table="", values=None, **_kwargs):
        events.append((table, values))
        return {"inserted": 1}

    monkeypatch.setattr(Z, "task_generic_comfyui_call", _fake_comfy)
    monkeypatch.setattr(Z, "task_generic_db_insert", _fake_insert)
    result = asyncio.run(Z.task_pd_color_video_restore_frames(
        sourceIpfsCid="bafy-source",
        shotMapCid="bafy-shot-map",
        workKind="animation",
        runVertexId="pdcolor:run:test-process-event",
        workId="pdcolor:work:gertie",
    ))

    assert result["blobCid"] == "bafy-restored"
    table, values = events[0]
    assert table == "vertex_pd_color_process_event"
    assert values["run_vertex_id"] == "pdcolor:run:test-process-event"
    assert values["work_id"] == "pdcolor:work:gertie"
    assert values["activity"] == "Restore frames"
    assert values["task_type"] == "pdColor.video.restoreFrames"
    assert values["lifecycle"] == "complete"
    assert values["status"] == "completed"
    assert values["artifact_cid"] == "bafy-restored"


def test_pd_color_video_enhance_quality_worker_wraps_payload(monkeypatch) -> None:
    calls = []

    async def _fake_comfy(route="", body=None, outputFormat="auto", timeoutSec=0, repo=""):
        calls.append((route, body, outputFormat, timeoutSec, repo))
        return {"status": 200, "blobCid": "bafy-enhanced", "meta": {"targetResolution": body["targetResolution"]}}

    monkeypatch.setattr(Z, "task_generic_comfyui_call", _fake_comfy)
    result = asyncio.run(Z.task_pd_color_video_enhance_quality(
        colorizedFramesCid="bafy-colorized",
        shotMapCid="bafy-shot-map",
        targetResolution="1080p",
        grainPreservation=False,
    ))

    assert result["blobCid"] == "bafy-enhanced"
    route, body, output_format, timeout_sec, _repo = calls[0]
    assert route == "/v1/video/enhance-quality"
    assert output_format == "blob"
    assert timeout_sec == 600
    assert body["colorizedFramesCid"] == "bafy-colorized"
    assert body["grainPreservation"] is False


def test_pd_color_translate_subtitles_worker_calls_i18n_contract(monkeypatch) -> None:
    calls = []

    async def _fake_xrpc(nsid="", payload=None, actor="", baseUrl="", timeoutSec=0):
        calls.append((nsid, payload, actor, baseUrl, timeoutSec))
        return {"status": 200, "response": {"manifestCid": "bafy-subtitles", "translatedCount": 2}}

    monkeypatch.setattr(Z, "task_generic_xrpc_invoke", _fake_xrpc)
    result = asyncio.run(Z.task_pd_color_localization_translate_subtitles(
        timedTextCid="bafy-timed-text",
        detectedLanguage="en",
        targetLanguages=["ja", "ko"],
        title="Gertie the Dinosaur",
        workKind="animation",
        rightsEvidenceCid="ipfs://bafy-rights",
    ))

    assert result["response"]["manifestCid"] == "bafy-subtitles"
    nsid, payload, _actor, _base_url, _timeout_sec = calls[0]
    assert nsid == "com.etzhayyim.apps.i18n.translateBatch"
    assert payload["sourceLang"] == "en"
    assert payload["targetLangs"] == ["ja", "ko"]
    assert payload["contentKind"] == "timed-text"
    assert payload["preserveTimestamps"] is True


def test_pd_color_generate_dubbed_audio_worker_wraps_voice_policy(monkeypatch) -> None:
    calls = []

    async def _fake_comfy(route="", body=None, outputFormat="auto", timeoutSec=0, repo=""):
        calls.append((route, body, outputFormat, timeoutSec, repo))
        return {"status": 200, "blobCid": "bafy-dubbed", "meta": {"generatedCount": 2}}

    monkeypatch.setattr(Z, "task_generic_comfyui_call", _fake_comfy)
    result = asyncio.run(Z.task_pd_color_audio_generate_dubbed_audio(
        masterVideoCid="bafy-master",
        timedTextCid="bafy-timed-text",
        subtitleManifestCid="bafy-subtitles",
        targetLanguages=["ja", "ko"],
        voicePolicy="narration-neutral",
        voiceLipSync=True,
    ))

    assert result["blobCid"] == "bafy-dubbed"
    route, body, output_format, timeout_sec, _repo = calls[0]
    assert route == "/v1/audio/dub-localized-speech"
    assert output_format == "blob"
    assert timeout_sec == 600
    assert body["voicePolicy"] == "narration-neutral"
    assert body["preserveOriginalAudio"] is True
    assert body["lipSync"] is True


# ─── task_generic_http_fetch — URL guards ────────────────────────────────────

def test_generic_http_fetch_no_url_returns_error() -> None:
    result = asyncio.run(Z.task_generic_http_fetch())
    assert "error" in result


def test_generic_http_fetch_no_url_error_mentions_url() -> None:
    result = asyncio.run(Z.task_generic_http_fetch())
    assert "url" in result["error"]


def test_generic_http_fetch_missing_scheme_returns_error() -> None:
    result = asyncio.run(Z.task_generic_http_fetch(url="example.com/path"))
    assert "error" in result


def test_generic_http_fetch_returns_dict() -> None:
    result = asyncio.run(Z.task_generic_http_fetch())
    assert isinstance(result, dict)


# ─── task_ind_efiling_submit — jurisdiction/sourceVertexId guards ─────────────

def test_ind_efiling_submit_unsupported_jurisdiction_returns_blocked() -> None:
    result = asyncio.run(Z.task_ind_efiling_submit(jurisdiction="zzz"))
    assert result["ok"] is False
    assert result.get("status") == "blocked"


def test_ind_efiling_submit_no_jurisdiction_returns_blocked() -> None:
    result = asyncio.run(Z.task_ind_efiling_submit())
    assert result["ok"] is False


def test_ind_efiling_submit_blocked_has_error() -> None:
    result = asyncio.run(Z.task_ind_efiling_submit())
    assert "error" in result


def test_ind_efiling_submit_returns_dict() -> None:
    result = asyncio.run(Z.task_ind_efiling_submit())
    assert isinstance(result, dict)


# ─── task_news_udf_score_intel — noop cursor returns fallback scores ──────────

def test_news_udf_score_intel_noop_cursor_returns_dict() -> None:
    result = asyncio.run(Z.task_news_udf_score_intel())
    assert isinstance(result, dict)


def test_news_udf_score_intel_noop_cursor_has_credibility() -> None:
    result = asyncio.run(Z.task_news_udf_score_intel())
    assert "credibility" in result


def test_news_udf_score_intel_noop_cursor_has_priority() -> None:
    result = asyncio.run(Z.task_news_udf_score_intel())
    assert "priority" in result


# ─── task_generic_wasm_run — missing module returns error ────────────────────

def test_generic_wasm_run_no_module_path_returns_error() -> None:
    result = asyncio.run(Z.task_generic_wasm_run())
    assert result["ok"] is False


def test_generic_wasm_run_no_module_path_error_present() -> None:
    result = asyncio.run(Z.task_generic_wasm_run())
    assert "error" in result


def test_generic_wasm_run_nonexistent_module_returns_error() -> None:
    result = asyncio.run(Z.task_generic_wasm_run(modulePath="/nonexistent/path/to/module.wasm"))
    assert result["ok"] is False


def test_generic_wasm_run_returns_dict() -> None:
    result = asyncio.run(Z.task_generic_wasm_run())
    assert isinstance(result, dict)


# ─── task_generic_comfyui_call — route guards ────────────────────────────────

def test_generic_comfyui_call_no_route_returns_error() -> None:
    result = asyncio.run(Z.task_generic_comfyui_call())
    assert "error" in result


def test_generic_comfyui_call_no_route_error_mentions_route() -> None:
    result = asyncio.run(Z.task_generic_comfyui_call())
    assert "route" in result["error"]


def test_generic_comfyui_call_bad_route_prefix_returns_error() -> None:
    result = asyncio.run(Z.task_generic_comfyui_call(route="/api/images/generations"))
    assert "error" in result


def test_generic_comfyui_call_returns_dict() -> None:
    result = asyncio.run(Z.task_generic_comfyui_call())
    assert isinstance(result, dict)


def test_pd_color_comfyui_local_media_manifest(monkeypatch) -> None:
    async def _fake_add(kind, payload):
        assert kind == "pd-color-shot-map"
        assert payload["route"] == "/v1/video/shot-segmentation"
        return "bafy-shot-map"

    monkeypatch.setattr(Z, "_pd_color_add_json_manifest", _fake_add)
    result = asyncio.run(Z.task_generic_comfyui_call(
        route="/v1/video/shot-segmentation",
        body={"sourceBlobCid": "bafy-source"},
        outputFormat="json",
    ))
    assert result["blobCid"] == "bafy-shot-map"
    assert result["meta"]["shotCount"] == 1


# ─── task_netintel_* — all have broad except catch-all ───────────────────────

def test_netintel_dns_delta_returns_dict() -> None:
    result = asyncio.run(Z.task_netintel_dns_delta())
    assert isinstance(result, dict)


def test_netintel_dns_delta_has_ok_key() -> None:
    result = asyncio.run(Z.task_netintel_dns_delta())
    assert "ok" in result


def test_netintel_ip_enrich_returns_dict() -> None:
    result = asyncio.run(Z.task_netintel_ip_enrich())
    assert isinstance(result, dict)


def test_netintel_ip_enrich_has_ok_key() -> None:
    result = asyncio.run(Z.task_netintel_ip_enrich())
    assert "ok" in result


def test_netintel_whois_delta_returns_dict() -> None:
    result = asyncio.run(Z.task_netintel_whois_delta())
    assert isinstance(result, dict)


def test_netintel_whois_delta_has_ok_key() -> None:
    result = asyncio.run(Z.task_netintel_whois_delta())
    assert "ok" in result


def test_netintel_scan_banner_returns_dict() -> None:
    result = asyncio.run(Z.task_netintel_scan_banner())
    assert isinstance(result, dict)


def test_netintel_scan_banner_has_ok_key() -> None:
    result = asyncio.run(Z.task_netintel_scan_banner())
    assert "ok" in result


def test_netintel_fingerprint_delta_returns_dict() -> None:
    result = asyncio.run(Z.task_netintel_fingerprint_delta())
    assert isinstance(result, dict)


def test_netintel_fingerprint_delta_has_ok_key() -> None:
    result = asyncio.run(Z.task_netintel_fingerprint_delta())
    assert "ok" in result


# ─── task_resource_flow_detect_anomaly — noop cursor returns zero counts ──────

def test_resource_flow_detect_anomaly_noop_returns_dict() -> None:
    result = asyncio.run(Z.task_resource_flow_detect_anomaly())
    assert isinstance(result, dict)


def test_resource_flow_detect_anomaly_has_run_id() -> None:
    result = asyncio.run(Z.task_resource_flow_detect_anomaly())
    assert "runId" in result or "error" in result


def test_resource_flow_detect_anomaly_scanned_is_int() -> None:
    result = asyncio.run(Z.task_resource_flow_detect_anomaly())
    if "scanned" in result:
        assert isinstance(result["scanned"], int)
