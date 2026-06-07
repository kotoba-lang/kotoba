"""Pure-path tests for ma.py, robotics.py task functions, and gov_* ingest_official_sources.

- ma tasks: pure computation (no DB/HTTP with default/empty args)
- robotics tasks: pure computation (no DB/HTTP)
- gov_* ingest_official_sources: needs sync_cursor + _pds_xrpc mocked
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import ma as MA  # noqa: E402
from kotodama.primitives import robotics as ROB  # noqa: E402


# ══════════════════════════════════════════════════════════════════════════════
# ma.py — pure task functions
# ══════════════════════════════════════════════════════════════════════════════

# ─── task_ma_trade_broker_negotiate ─────────────────────────────────────────

def test_ma_negotiate_returns_dict() -> None:
    result = asyncio.run(MA.task_ma_trade_broker_negotiate())
    assert isinstance(result, dict)


def test_ma_negotiate_status_negotiation_ready() -> None:
    result = asyncio.run(MA.task_ma_trade_broker_negotiate())
    assert result["status"] == "negotiation-ready"


def test_ma_negotiate_has_required_approvals() -> None:
    result = asyncio.run(MA.task_ma_trade_broker_negotiate())
    assert isinstance(result["requiredApprovals"], list)
    assert len(result["requiredApprovals"]) > 0


def test_ma_negotiate_with_deal_id() -> None:
    result = asyncio.run(MA.task_ma_trade_broker_negotiate(dealId="deal-001"))
    assert result["dealId"] == "deal-001"


def test_ma_negotiate_has_term_sheet_range() -> None:
    result = asyncio.run(MA.task_ma_trade_broker_negotiate(
        valuationRangeLowUsd=1_000_000.0,
        valuationRangeHighUsd=5_000_000.0,
    ))
    assert result["termSheetRangeUsd"]["low"] == 1_000_000.0
    assert result["termSheetRangeUsd"]["high"] == 5_000_000.0


# ─── task_ma_outreach_compose_draft ─────────────────────────────────────────

def test_ma_outreach_draft_returns_dict() -> None:
    result = asyncio.run(MA.task_ma_outreach_compose_draft())
    assert isinstance(result, dict)


def test_ma_outreach_draft_has_outreach_draft_key() -> None:
    result = asyncio.run(MA.task_ma_outreach_compose_draft())
    assert "outreachDraft" in result


def test_ma_outreach_draft_has_status() -> None:
    result = asyncio.run(MA.task_ma_outreach_compose_draft())
    assert "status" in result


def test_ma_outreach_draft_approval_required_by_default() -> None:
    result = asyncio.run(MA.task_ma_outreach_compose_draft(approvalRequired=True))
    assert result.get("approvalRequired") is True or result.get("pendingApproval") is not None


# ─── task_ma_outreach_prepare_mailer_send ────────────────────────────────────

def test_ma_prepare_mailer_no_approval_returns_error() -> None:
    result = asyncio.run(MA.task_ma_outreach_prepare_mailer_send())
    assert result["ok"] is False
    assert result["sendReady"] is False


def test_ma_prepare_mailer_returns_dict() -> None:
    result = asyncio.run(MA.task_ma_outreach_prepare_mailer_send())
    assert isinstance(result, dict)


def test_ma_prepare_mailer_approval_required_status() -> None:
    result = asyncio.run(MA.task_ma_outreach_prepare_mailer_send(
        outreachApproved=False,
        approvalStatus="",
    ))
    assert result["status"] == "approval-required"


# ─── task_ma_outreach_send_approved ─────────────────────────────────────────

def test_ma_send_approved_not_ready_returns_error() -> None:
    result = asyncio.run(MA.task_ma_outreach_send_approved(sendReady=False))
    assert result["ok"] is False
    assert result["sent"] is False


def test_ma_send_approved_dry_run_with_payload() -> None:
    result = asyncio.run(MA.task_ma_outreach_send_approved(
        sendReady=True,
        mailerSendPayload={"to": "a@b.com", "subject": "Test", "text": "Hello"},
        dryRun=True,
    ))
    assert result["ok"] is True
    assert result["sent"] is False
    assert result.get("dryRun") is True


def test_ma_send_approved_returns_dict() -> None:
    result = asyncio.run(MA.task_ma_outreach_send_approved())
    assert isinstance(result, dict)


# ─── task_ma_integration_close_and_handoff ───────────────────────────────────

def test_ma_integration_close_returns_dict() -> None:
    result = asyncio.run(MA.task_ma_integration_close_and_handoff())
    assert isinstance(result, dict)


def test_ma_integration_close_status_handoff_ready() -> None:
    result = asyncio.run(MA.task_ma_integration_close_and_handoff(
        status="negotiation-ready",
    ))
    assert result["status"] == "handoff-ready"


def test_ma_integration_close_has_pmi_handoff_id() -> None:
    result = asyncio.run(MA.task_ma_integration_close_and_handoff())
    assert "pmiHandoffId" in result


def test_ma_integration_close_with_deal_id() -> None:
    result = asyncio.run(MA.task_ma_integration_close_and_handoff(dealId="deal-xyz"))
    assert result["dealId"] == "deal-xyz"


# ══════════════════════════════════════════════════════════════════════════════
# robotics.py — pure task functions
# ══════════════════════════════════════════════════════════════════════════════

# ─── task_process_catalog ─────────────────────────────────────────────────────

def test_robotics_process_catalog_returns_dict() -> None:
    result = asyncio.run(ROB.task_process_catalog())
    assert isinstance(result, dict)


def test_robotics_process_catalog_has_catalog_key() -> None:
    result = asyncio.run(ROB.task_process_catalog())
    assert "roboticsProcessCatalog" in result


def test_robotics_process_catalog_has_forms() -> None:
    result = asyncio.run(ROB.task_process_catalog())
    assert "forms" in result["roboticsProcessCatalog"]


# ─── task_process_dependencies ───────────────────────────────────────────────

def test_robotics_process_dependencies_returns_dict() -> None:
    result = asyncio.run(ROB.task_process_dependencies())
    assert isinstance(result, dict)


def test_robotics_process_dependencies_has_key() -> None:
    result = asyncio.run(ROB.task_process_dependencies())
    assert "roboticsProcessDependencies" in result


# ─── task_workflow_plan ───────────────────────────────────────────────────────

def test_robotics_workflow_plan_returns_dict() -> None:
    result = asyncio.run(ROB.task_workflow_plan())
    assert isinstance(result, dict)


def test_robotics_workflow_plan_has_key() -> None:
    result = asyncio.run(ROB.task_workflow_plan())
    assert "roboticsWorkflowPlan" in result


def test_robotics_workflow_plan_with_asset_kind() -> None:
    result = asyncio.run(ROB.task_workflow_plan(assetKind="arm"))
    assert isinstance(result, dict)


# ─── task_kami_scene_plan ─────────────────────────────────────────────────────

def test_robotics_kami_scene_plan_returns_dict() -> None:
    result = asyncio.run(ROB.task_kami_scene_plan())
    assert isinstance(result, dict)


def test_robotics_kami_scene_plan_has_key() -> None:
    result = asyncio.run(ROB.task_kami_scene_plan())
    assert "roboticsKamiScene" in result


def test_robotics_kami_scene_plan_with_cell_id() -> None:
    result = asyncio.run(ROB.task_kami_scene_plan(cellId="cell-001"))
    assert isinstance(result, dict)


# ─── task_transport_plan ──────────────────────────────────────────────────────

def test_robotics_transport_plan_returns_dict() -> None:
    result = asyncio.run(ROB.task_transport_plan())
    assert isinstance(result, dict)


def test_robotics_transport_plan_has_key() -> None:
    result = asyncio.run(ROB.task_transport_plan())
    assert "roboticsTransportPlan" in result


def test_robotics_transport_plan_with_route() -> None:
    result = asyncio.run(ROB.task_transport_plan(
        origin="Dock A", destination="Warehouse B",
    ))
    assert isinstance(result, dict)


# ─── additional robotics tasks (pure) ────────────────────────────────────────

_ROBOTICS_REMAINING = [
    ("task_sales_plan", "roboticsSalesPlan"),
    ("task_mission_plan", "roboticsMission"),
    ("task_telemetry_schema", "roboticsTelemetrySchema"),
    ("task_mission_simulate", "roboticsMissionSimulation"),
    ("task_approval_record", "roboticsApprovalRecord"),
    ("task_telemetry_ingest", "roboticsTelemetryFrame"),
    ("task_mission_status", "roboticsMissionStatus"),
    ("task_fulfillment_close", "roboticsFulfillmentClose"),
    ("task_product_package_validate", "roboticsProductPackageValidation"),
    ("task_product_file_catalog", "roboticsProductFileCatalog"),
    ("task_product_process_plan", "roboticsManufacturingProcessPlan"),
    ("task_product_rfq_export", "roboticsRfqExport"),
    ("task_automotive_package_profile", "automotiveManufacturingProfile"),
    ("task_automotive_file_catalog", "roboticsProductFileCatalog"),
    ("task_automotive_supply_process_link", "automotiveSupplyProcessGraph"),
    ("task_automotive_routing_plan", "automotiveRoutingPlan"),
    ("task_automotive_quality_gate", "automotiveQualityGateResult"),
    ("task_automotive_eol_plan", "automotiveEolPlan"),
    ("task_ems_company_search", "roboticsEmsCompanySearch"),
    ("task_ems_company_profile", "roboticsEmsCompanyProfiles"),
    ("task_ems_supplier_shortlist", "roboticsEmsSupplierShortlist"),
]


@pytest.mark.parametrize("fn,key", _ROBOTICS_REMAINING)
def test_robotics_extra_task_returns_dict(fn: str, key: str) -> None:
    result = asyncio.run(getattr(ROB, fn)())
    assert isinstance(result, dict)


@pytest.mark.parametrize("fn,key", _ROBOTICS_REMAINING)
def test_robotics_extra_task_has_top_key(fn: str, key: str) -> None:
    result = asyncio.run(getattr(ROB, fn)())
    assert key in result


# ══════════════════════════════════════════════════════════════════════════════
# gov_* ingest_official_sources (mocked HTTP + noop cursor)
# ══════════════════════════════════════════════════════════════════════════════

_GOV_INGEST_CODES = ["ago", "hkg", "kor", "prk", "rus", "zaf"]


def _make_noop_cursor() -> MagicMock:
    cur = MagicMock()
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    cur.description = []
    cm = MagicMock()
    cm.return_value.__enter__.return_value = cur
    cm.return_value.__exit__.return_value = False
    return cm


def _make_pds_xrpc_mock() -> AsyncMock:
    return AsyncMock(return_value={"status": 200, "ok": True})


@pytest.mark.parametrize("code", _GOV_INGEST_CODES)
def test_gov_ingest_official_sources_returns_dict(code: str) -> None:
    import importlib
    mod = sys.modules.get(f"kotodama.primitives.gov_{code}") or importlib.import_module(
        f"kotodama.primitives.gov_{code}"
    )
    from kotodama.db_sync import sync_cursor as _real_sc
    mock_sc = _make_noop_cursor()
    mock_pds = _make_pds_xrpc_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    mod._pds_xrpc = mock_pds  # type: ignore[attr-defined]
    try:
        result = asyncio.run(
            getattr(mod, f"task_gov_{code}_ingest_official_sources")(
                limit=1, includeOrgSites=False,
            )
        )
        assert isinstance(result, dict)
    finally:
        mod.sync_cursor = _real_sc  # type: ignore[attr-defined]
        # restore _pds_xrpc by re-importing
        fresh = importlib.import_module(f"kotodama.primitives.gov_{code}")
        # _pds_xrpc is a module-level function — revert by getting the original
        import types
        if hasattr(fresh, "_pds_xrpc"):
            mod._pds_xrpc = getattr(fresh, "_pds_xrpc")  # type: ignore[attr-defined]


@pytest.mark.parametrize("code", _GOV_INGEST_CODES)
def test_gov_ingest_official_sources_ok_true(code: str) -> None:
    import importlib
    mod = sys.modules.get(f"kotodama.primitives.gov_{code}") or importlib.import_module(
        f"kotodama.primitives.gov_{code}"
    )
    from kotodama.db_sync import sync_cursor as _real_sc
    mock_sc = _make_noop_cursor()
    mock_pds = _make_pds_xrpc_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    mod._pds_xrpc = mock_pds  # type: ignore[attr-defined]
    try:
        result = asyncio.run(
            getattr(mod, f"task_gov_{code}_ingest_official_sources")(
                limit=1, includeOrgSites=False,
            )
        )
        assert result.get("ok") is True
    finally:
        mod.sync_cursor = _real_sc  # type: ignore[attr-defined]
        fresh = importlib.import_module(f"kotodama.primitives.gov_{code}")
        if hasattr(fresh, "_pds_xrpc"):
            mod._pds_xrpc = getattr(fresh, "_pds_xrpc")  # type: ignore[attr-defined]


@pytest.mark.parametrize("code", _GOV_INGEST_CODES)
def test_gov_ingest_official_sources_has_enqueued(code: str) -> None:
    import importlib
    mod = sys.modules.get(f"kotodama.primitives.gov_{code}") or importlib.import_module(
        f"kotodama.primitives.gov_{code}"
    )
    from kotodama.db_sync import sync_cursor as _real_sc
    mock_sc = _make_noop_cursor()
    mock_pds = _make_pds_xrpc_mock()
    mod.sync_cursor = mock_sc  # type: ignore[attr-defined]
    mod._pds_xrpc = mock_pds  # type: ignore[attr-defined]
    try:
        result = asyncio.run(
            getattr(mod, f"task_gov_{code}_ingest_official_sources")(
                limit=1, includeOrgSites=False,
            )
        )
        assert "enqueued" in result
    finally:
        mod.sync_cursor = _real_sc  # type: ignore[attr-defined]
        fresh = importlib.import_module(f"kotodama.primitives.gov_{code}")
        if hasattr(fresh, "_pds_xrpc"):
            mod._pds_xrpc = getattr(fresh, "_pds_xrpc")  # type: ignore[attr-defined]
