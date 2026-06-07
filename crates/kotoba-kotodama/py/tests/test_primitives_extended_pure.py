"""Pure-path tests for additional primitives.

Covers:
- primitives/pds_discover_cache.py: task_pds_discover_cache_warm (no secret → error dict)
- primitives/pds_domain_coverage.py: task_pds_domain_coverage_expand (no secret → error dict)
- primitives/pds_heartbeat.py: task_pds_heartbeat_run (no secret → error dict)
- primitives/pds_key_rotation.py: task_pds_signing_keys_rotate_stale (no secret → error dict)
- primitives/pds_mitama_cron.py: task_pds_mitama_cron_triggers_resync (no secret → error dict)
- primitives/pds_outbox.py: task_pds_write_outbox_sync (no secret → error dict)
- primitives/kotoba-kotodama_organizer.py: task_kotoba-kotodama_organizer_run (no URL → error dict)
- primitives/murakumo_fleet.py: task_murakumo_fleet_health_check (patched cursor)
- primitives/vector_embedding.py: task_vector_embedding_backfill_batch (invalid surface → pure error)
- primitives/intel.py: dryRun=True + empty-input pure paths
- primitives/projector.py: pure early-return paths
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import kotodama.primitives.pds_discover_cache as PDC
import kotodama.primitives.pds_domain_coverage as PDO
import kotodama.primitives.pds_heartbeat as PHB
import kotodama.primitives.pds_key_rotation as PKR
import kotodama.primitives.pds_mitama_cron as PMC
import kotodama.primitives.pds_outbox as POB
import kotodama.primitives.kotoba-kotodama_organizer as MO
import kotodama.primitives.murakumo_fleet as MF
import kotodama.primitives.vector_embedding as VE
import kotodama.primitives.intel as IT
import kotodama.primitives.projector as PR


def _noop_cursor_mock() -> MagicMock:
    cur = MagicMock()
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    cur.description = []
    cm = MagicMock()
    cm.return_value.__enter__.return_value = cur
    cm.return_value.__exit__.return_value = False
    return cm


def _patch(mod, mock_sc):
    from kotodama.db_sync import sync_cursor as _real
    mod.sync_cursor = mock_sc
    return _real


def _restore(mod, real):
    mod.sync_cursor = real


# ══════════════════════════════════════════════════════════════════════════════
# pds_discover_cache
# ══════════════════════════════════════════════════════════════════════════════

def test_pds_discover_cache_no_secret_returns_dict() -> None:
    real = _patch(PDC, _noop_cursor_mock())
    try:
        result = asyncio.run(PDC.task_pds_discover_cache_warm())
        assert isinstance(result, dict)
    finally:
        _restore(PDC, real)


def test_pds_discover_cache_no_secret_ok_false() -> None:
    real = _patch(PDC, _noop_cursor_mock())
    try:
        result = asyncio.run(PDC.task_pds_discover_cache_warm())
        assert result["ok"] is False
    finally:
        _restore(PDC, real)


def test_pds_discover_cache_no_secret_has_error() -> None:
    real = _patch(PDC, _noop_cursor_mock())
    try:
        result = asyncio.run(PDC.task_pds_discover_cache_warm())
        assert "error" in result and result["error"]
    finally:
        _restore(PDC, real)


def test_pds_discover_cache_has_audit_uri() -> None:
    real = _patch(PDC, _noop_cursor_mock())
    try:
        result = asyncio.run(PDC.task_pds_discover_cache_warm())
        assert "auditUri" in result
    finally:
        _restore(PDC, real)


# ══════════════════════════════════════════════════════════════════════════════
# pds_domain_coverage
# ══════════════════════════════════════════════════════════════════════════════

def test_pds_domain_coverage_no_secret_returns_dict() -> None:
    real = _patch(PDO, _noop_cursor_mock())
    try:
        result = asyncio.run(PDO.task_pds_domain_coverage_expand())
        assert isinstance(result, dict)
    finally:
        _restore(PDO, real)


def test_pds_domain_coverage_no_secret_ok_false() -> None:
    real = _patch(PDO, _noop_cursor_mock())
    try:
        result = asyncio.run(PDO.task_pds_domain_coverage_expand())
        assert result["ok"] is False
    finally:
        _restore(PDO, real)


def test_pds_domain_coverage_no_secret_has_error() -> None:
    real = _patch(PDO, _noop_cursor_mock())
    try:
        result = asyncio.run(PDO.task_pds_domain_coverage_expand())
        assert "error" in result and result["error"]
    finally:
        _restore(PDO, real)


def test_pds_domain_coverage_has_audit_uri() -> None:
    real = _patch(PDO, _noop_cursor_mock())
    try:
        result = asyncio.run(PDO.task_pds_domain_coverage_expand())
        assert "auditUri" in result
    finally:
        _restore(PDO, real)


# ══════════════════════════════════════════════════════════════════════════════
# pds_heartbeat
# ══════════════════════════════════════════════════════════════════════════════

def test_pds_heartbeat_no_secret_returns_dict() -> None:
    real = _patch(PHB, _noop_cursor_mock())
    try:
        result = asyncio.run(PHB.task_pds_heartbeat_run())
        assert isinstance(result, dict)
    finally:
        _restore(PHB, real)


def test_pds_heartbeat_no_secret_ok_false() -> None:
    real = _patch(PHB, _noop_cursor_mock())
    try:
        result = asyncio.run(PHB.task_pds_heartbeat_run())
        assert result["ok"] is False
    finally:
        _restore(PHB, real)


def test_pds_heartbeat_no_secret_has_error() -> None:
    real = _patch(PHB, _noop_cursor_mock())
    try:
        result = asyncio.run(PHB.task_pds_heartbeat_run())
        assert "error" in result and result["error"]
    finally:
        _restore(PHB, real)


def test_pds_heartbeat_has_apps_total() -> None:
    real = _patch(PHB, _noop_cursor_mock())
    try:
        result = asyncio.run(PHB.task_pds_heartbeat_run())
        assert "appsTotal" in result
    finally:
        _restore(PHB, real)


# ══════════════════════════════════════════════════════════════════════════════
# pds_key_rotation
# ══════════════════════════════════════════════════════════════════════════════

def test_pds_key_rotation_no_secret_returns_dict() -> None:
    real = _patch(PKR, _noop_cursor_mock())
    try:
        result = asyncio.run(PKR.task_pds_signing_keys_rotate_stale())
        assert isinstance(result, dict)
    finally:
        _restore(PKR, real)


def test_pds_key_rotation_no_secret_ok_false() -> None:
    real = _patch(PKR, _noop_cursor_mock())
    try:
        result = asyncio.run(PKR.task_pds_signing_keys_rotate_stale())
        assert result["ok"] is False
    finally:
        _restore(PKR, real)


def test_pds_key_rotation_no_secret_has_error() -> None:
    real = _patch(PKR, _noop_cursor_mock())
    try:
        result = asyncio.run(PKR.task_pds_signing_keys_rotate_stale())
        assert "error" in result and result["error"]
    finally:
        _restore(PKR, real)


def test_pds_key_rotation_has_scanned() -> None:
    real = _patch(PKR, _noop_cursor_mock())
    try:
        result = asyncio.run(PKR.task_pds_signing_keys_rotate_stale())
        assert "scanned" in result
    finally:
        _restore(PKR, real)


# ══════════════════════════════════════════════════════════════════════════════
# pds_mitama_cron
# ══════════════════════════════════════════════════════════════════════════════

def test_pds_mitama_cron_no_secret_returns_dict() -> None:
    real = _patch(PMC, _noop_cursor_mock())
    try:
        result = asyncio.run(PMC.task_pds_mitama_cron_triggers_resync())
        assert isinstance(result, dict)
    finally:
        _restore(PMC, real)


def test_pds_mitama_cron_no_secret_ok_false() -> None:
    real = _patch(PMC, _noop_cursor_mock())
    try:
        result = asyncio.run(PMC.task_pds_mitama_cron_triggers_resync())
        assert result["ok"] is False
    finally:
        _restore(PMC, real)


def test_pds_mitama_cron_no_secret_has_error() -> None:
    real = _patch(PMC, _noop_cursor_mock())
    try:
        result = asyncio.run(PMC.task_pds_mitama_cron_triggers_resync())
        assert "error" in result and result["error"]
    finally:
        _restore(PMC, real)


def test_pds_mitama_cron_has_scheduled() -> None:
    real = _patch(PMC, _noop_cursor_mock())
    try:
        result = asyncio.run(PMC.task_pds_mitama_cron_triggers_resync())
        assert "scheduled" in result
    finally:
        _restore(PMC, real)


# ══════════════════════════════════════════════════════════════════════════════
# pds_outbox
# ══════════════════════════════════════════════════════════════════════════════

def test_pds_outbox_no_secret_returns_dict() -> None:
    real = _patch(POB, _noop_cursor_mock())
    try:
        result = asyncio.run(POB.task_pds_write_outbox_sync())
        assert isinstance(result, dict)
    finally:
        _restore(POB, real)


def test_pds_outbox_no_secret_ok_false() -> None:
    real = _patch(POB, _noop_cursor_mock())
    try:
        result = asyncio.run(POB.task_pds_write_outbox_sync())
        assert result["ok"] is False
    finally:
        _restore(POB, real)


def test_pds_outbox_no_secret_has_error() -> None:
    real = _patch(POB, _noop_cursor_mock())
    try:
        result = asyncio.run(POB.task_pds_write_outbox_sync())
        assert "error" in result and result["error"]
    finally:
        _restore(POB, real)


def test_pds_outbox_has_replayed() -> None:
    real = _patch(POB, _noop_cursor_mock())
    try:
        result = asyncio.run(POB.task_pds_write_outbox_sync())
        assert "replayed" in result
    finally:
        _restore(POB, real)


# ══════════════════════════════════════════════════════════════════════════════
# kotoba-kotodama_organizer
# ══════════════════════════════════════════════════════════════════════════════

def test_kotoba-kotodama_organizer_no_url_returns_dict() -> None:
    real = _patch(MO, _noop_cursor_mock())
    try:
        result = asyncio.run(MO.task_kotoba-kotodama_organizer_run())
        assert isinstance(result, dict)
    finally:
        _restore(MO, real)


def test_kotoba-kotodama_organizer_no_url_ok_false() -> None:
    real = _patch(MO, _noop_cursor_mock())
    try:
        result = asyncio.run(MO.task_kotoba-kotodama_organizer_run())
        assert result["ok"] is False
    finally:
        _restore(MO, real)


def test_kotoba-kotodama_organizer_no_url_has_error() -> None:
    real = _patch(MO, _noop_cursor_mock())
    try:
        result = asyncio.run(MO.task_kotoba-kotodama_organizer_run())
        assert "error" in result and result["error"]
    finally:
        _restore(MO, real)


def test_kotoba-kotodama_organizer_has_summary() -> None:
    real = _patch(MO, _noop_cursor_mock())
    try:
        result = asyncio.run(MO.task_kotoba-kotodama_organizer_run())
        assert "summary" in result
    finally:
        _restore(MO, real)


# ══════════════════════════════════════════════════════════════════════════════
# murakumo_fleet
# ══════════════════════════════════════════════════════════════════════════════

def test_murakumo_fleet_patched_returns_dict() -> None:
    real = _patch(MF, _noop_cursor_mock())
    try:
        result = asyncio.run(MF.task_murakumo_fleet_health_check())
        assert isinstance(result, dict)
    finally:
        _restore(MF, real)


def test_murakumo_fleet_patched_ok_true() -> None:
    real = _patch(MF, _noop_cursor_mock())
    try:
        result = asyncio.run(MF.task_murakumo_fleet_health_check())
        assert result["ok"] is True
    finally:
        _restore(MF, real)


def test_murakumo_fleet_has_health_pct() -> None:
    real = _patch(MF, _noop_cursor_mock())
    try:
        result = asyncio.run(MF.task_murakumo_fleet_health_check())
        assert "healthPct" in result
    finally:
        _restore(MF, real)


def test_murakumo_fleet_has_litellm_reachable() -> None:
    real = _patch(MF, _noop_cursor_mock())
    try:
        result = asyncio.run(MF.task_murakumo_fleet_health_check())
        assert "litellmReachable" in result
    finally:
        _restore(MF, real)


# ══════════════════════════════════════════════════════════════════════════════
# vector_embedding — invalid surface → pure early return (no DB)
# ══════════════════════════════════════════════════════════════════════════════

def test_vector_embedding_invalid_surface_returns_dict() -> None:
    result = asyncio.run(VE.task_vector_embedding_backfill_batch(surface="xyzzy"))
    assert isinstance(result, dict)


def test_vector_embedding_invalid_surface_has_error() -> None:
    result = asyncio.run(VE.task_vector_embedding_backfill_batch(surface="xyzzy"))
    assert "error" in result


def test_vector_embedding_invalid_surface_planned_zero() -> None:
    result = asyncio.run(VE.task_vector_embedding_backfill_batch(surface="xyzzy"))
    assert result["planned"] == 0


def test_vector_embedding_invalid_surface_written_zero() -> None:
    result = asyncio.run(VE.task_vector_embedding_backfill_batch(surface="xyzzy"))
    assert result["written"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# intel — pure paths
# ══════════════════════════════════════════════════════════════════════════════

def test_intel_run_create_dry_run_returns_dict() -> None:
    result = asyncio.run(IT.task_intel_run_create(dryRun=True))
    assert isinstance(result, dict)


def test_intel_run_create_dry_run_ok_true() -> None:
    result = asyncio.run(IT.task_intel_run_create(dryRun=True))
    assert result.get("dryRun") is True
    assert "runId" in result


def test_intel_run_create_dry_run_status_running() -> None:
    result = asyncio.run(IT.task_intel_run_create(dryRun=True))
    assert result["status"] == "running"


def test_intel_run_create_dry_run_has_vertex_id() -> None:
    result = asyncio.run(IT.task_intel_run_create(dryRun=True))
    assert "vertexId" in result


def test_intel_owl_validate_empty_candidates_returns_dict() -> None:
    result = asyncio.run(IT.task_intel_owl_validate(candidates=[]))
    assert isinstance(result, dict)


def test_intel_owl_validate_empty_valid_count_zero() -> None:
    result = asyncio.run(IT.task_intel_owl_validate(candidates=[]))
    assert result["validCount"] == 0
    assert result["invalidCount"] == 0


def test_intel_owl_validate_returns_valid_candidates_list() -> None:
    result = asyncio.run(IT.task_intel_owl_validate(candidates=[]))
    assert isinstance(result["validCandidates"], list)


def test_intel_langgraph_resolve_empty_returns_dict() -> None:
    result = asyncio.run(IT.task_intel_langgraph_resolve(validCandidates=[]))
    assert isinstance(result, dict)


def test_intel_langgraph_resolve_empty_has_resolved_edges() -> None:
    result = asyncio.run(IT.task_intel_langgraph_resolve(validCandidates=[]))
    assert result["resolvedEdges"] == []


def test_intel_edge_materialize_empty_dry_run_returns_dict() -> None:
    result = asyncio.run(IT.task_intel_edge_materialize(resolvedEdges=[], dryRun=True))
    assert isinstance(result, dict)


def test_intel_edge_materialize_empty_dry_run_counts_zero() -> None:
    result = asyncio.run(IT.task_intel_edge_materialize(resolvedEdges=[], dryRun=True))
    assert result["candidateCount"] == 0
    assert result["activeCount"] == 0
    assert result["reviewCount"] == 0


def test_intel_dependency_list_try_except_returns_dict() -> None:
    result = asyncio.run(IT.task_intel_dependency_list())
    assert isinstance(result, dict)


def test_intel_dependency_list_has_edges_key() -> None:
    result = asyncio.run(IT.task_intel_dependency_list())
    assert "edges" in result or "error" in result


# ══════════════════════════════════════════════════════════════════════════════
# projector — pure early-return paths
# ══════════════════════════════════════════════════════════════════════════════

def test_projector_command_parse_empty_returns_dict() -> None:
    result = asyncio.run(PR.task_projector_command_parse(text=""))
    assert isinstance(result, dict)


def test_projector_command_parse_empty_command() -> None:
    result = asyncio.run(PR.task_projector_command_parse(text=""))
    assert result["command"] == ""


def test_projector_command_parse_no_slash_passes_through() -> None:
    result = asyncio.run(PR.task_projector_command_parse(text="hello world"))
    assert result["command"] == ""
    assert "hello" in result["argText"]


def test_projector_command_parse_returns_dict() -> None:
    result = asyncio.run(PR.task_projector_command_parse())
    assert isinstance(result, dict)


def test_projector_command_deferred_returns_dict() -> None:
    result = asyncio.run(PR.task_projector_command_deferred(command="/image"))
    assert isinstance(result, dict)


def test_projector_command_deferred_deferred_true() -> None:
    result = asyncio.run(PR.task_projector_command_deferred(command="/image"))
    assert result["deferred"] is True


def test_projector_command_deferred_has_reply() -> None:
    result = asyncio.run(PR.task_projector_command_deferred(command="/image"))
    assert "reply" in result


def test_projector_tools_discover_no_convo_returns_dict() -> None:
    result = asyncio.run(PR.task_projector_tools_discover(convoId=""))
    assert isinstance(result, dict)


def test_projector_tools_discover_no_convo_has_tools() -> None:
    result = asyncio.run(PR.task_projector_tools_discover(convoId=""))
    assert "tools" in result
    assert isinstance(result["tools"], list)


def test_projector_tool_call_no_name_returns_error() -> None:
    result = asyncio.run(PR.task_projector_tool_call(name=""))
    assert result["ok"] is False
    assert "error" in result


def test_projector_tool_call_no_name_returns_dict() -> None:
    result = asyncio.run(PR.task_projector_tool_call())
    assert isinstance(result, dict)


def test_projector_reflexion_load_no_convo_returns_dict() -> None:
    result = asyncio.run(PR.task_projector_reflexion_load(convoId=""))
    assert isinstance(result, dict)


def test_projector_reflexion_load_no_convo_empty_memories() -> None:
    result = asyncio.run(PR.task_projector_reflexion_load(convoId=""))
    assert result["memories"] == []


def test_projector_reflexion_write_no_convo_returns_dict() -> None:
    result = asyncio.run(PR.task_projector_reflexion_write(convoId="", lessonText=""))
    assert isinstance(result, dict)


def test_projector_reflexion_write_no_convo_has_reply() -> None:
    result = asyncio.run(PR.task_projector_reflexion_write(convoId="", lessonText=""))
    assert "reply" in result


def test_projector_auth_mint_no_lxm_returns_error() -> None:
    result = asyncio.run(PR.task_projector_auth_mint(lxm=""))
    assert result["ok"] is False
    assert "error" in result


def test_projector_auth_mint_no_lxm_returns_dict() -> None:
    result = asyncio.run(PR.task_projector_auth_mint(lxm=""))
    assert isinstance(result, dict)
