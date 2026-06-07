#!/usr/bin/env python3
"""Verify the openUnispsc MCP surface through the dispatcher.

This is a DB-free gate: it calls coverageSnapshot, runs representative item
workflow scenarios, verifies UNSPSC segment fanout, okaimono catalog import and
sync, and purchase flow contracts, and dry-runs applyGraphWritePlan to confirm
the merged graph plan can be converted to parameterized SQL.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


async def _call_tool(handlers: dict[str, Any], name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from kotodama.mcp_dispatch import handle_envelope

    status, body = await handle_envelope(
        {
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        handlers,
    )
    result = body.get("result", body)
    return {"status": status, "result": result}


async def verify() -> dict[str, Any]:
    from kotodama.mcp_dispatch import build_actor_handlers

    handlers = build_actor_handlers({"openUnispsc"})
    coverage = await _call_tool(
        handlers,
        "com.etzhayyim.apps.openUnispsc.coverageSnapshot",
        {},
    )
    workflow_scenarios = {
        "manualReview": {
            "expectedStatus": "manual-review",
            "expectedRows": 5,
            "arguments": {
                "commodityCode": "46101501",
                "commodityName": "Firearms",
                "supplierDid": "did:web:supplier.example",
                "legalName": "Supplier Example",
                "country": "JPN",
                "kycCleared": True,
                "qualityScore": 0.8,
                "buyerOrgId": "did:web:buyer.example",
                "quantity": 2,
                "unitPrice": 600000,
                "currency": "USD",
                "eventAt": "2026-05-14T00:00:00Z",
            },
        },
        "ready": {
            "expectedStatus": "ready",
            "expectedRows": 3,
            "arguments": {
                "commodityCode": "25172504",
                "commodityName": "Vehicle Batteries",
                "supplierDid": "did:web:supplier.example",
                "legalName": "Supplier Example",
                "country": "JPN",
                "kycCleared": True,
                "qualityScore": 0.82,
                "buyerOrgId": "did:web:buyer.example",
                "quantity": 1,
                "unitPrice": 1000,
                "currency": "USD",
                "eventAt": "2026-05-14T00:00:00Z",
            },
        },
        "blocked": {
            "expectedStatus": "blocked",
            "expectedRows": 3,
            "arguments": {
                "commodityCode": "25172504",
                "commodityName": "Vehicle Batteries",
                "supplierDid": "did:web:supplier.example",
                "legalName": "Supplier Example",
                "country": "IRN",
                "kycCleared": True,
                "qualityScore": 0.9,
                "buyerOrgId": "did:web:buyer.example",
                "quantity": 1,
                "unitPrice": 1000,
                "currency": "USD",
                "eventAt": "2026-05-14T00:00:00Z",
            },
        },
    }
    workflows: dict[str, dict[str, Any]] = {}
    for name, scenario in workflow_scenarios.items():
        workflows[name] = await _call_tool(
            handlers,
            "com.etzhayyim.apps.openUnispsc.runItemWorkflow",
            scenario["arguments"],
        )
    catalog_sync = await _call_tool(
        handlers,
        "com.etzhayyim.apps.openUnispsc.syncCatalogItem",
        {
            "commodityCode": "43211501",
            "commodityName": "Computer servers",
            "sourceRepo": "did:web:unispsc.etzhayyim.com:seg43",
            "rkey": "43211501",
        },
    )
    purchase_plan = await _call_tool(
        handlers,
        "com.etzhayyim.apps.openUnispsc.planCatalogPurchase",
        {
            "productId": "unispsc-43211501",
            "orderId": "order-001",
            "customerDid": "did:web:customer.example",
            "buyerOrgId": "did:web:buyer.example",
            "quantity": 1,
            "unitPrice": 2400,
            "currency": "USD",
        },
    )
    sync_all = await _call_tool(
        handlers,
        "com.etzhayyim.apps.openUnispsc.syncAllCommodityDids",
        {"segmentCodes": ["44", "46"], "batchSize": 250, "dryRun": True},
    )
    segment_import = await _call_tool(
        handlers,
        "com.etzhayyim.apps.openUnispsc.importSegmentCatalog",
        {"segmentCode": "46", "pageSize": 750, "dryRun": True},
    )
    workflow = workflows["manualReview"]
    workflow_result = workflow["result"]
    apply_preview = await _call_tool(
        handlers,
        "com.etzhayyim.apps.openUnispsc.applyGraphWritePlan",
        {"graphWritePlan": workflow_result.get("graphWritePlan", {}), "dryRun": True},
    )

    coverage_result = coverage["result"]
    preview_result = apply_preview["result"]
    checks = {
        "coverageOk": coverage["status"] == 200 and coverage_result.get("ok") is True,
        "coverageComplete": coverage_result.get("missing") == [] and coverage_result.get("toolCount") == 20,
        "syncAllOk": sync_all["status"] == 200 and sync_all["result"].get("ok") is True,
        "syncAllFanout": sync_all["result"].get("orchestrationPlan", {}).get("commandsPerSegment") == 3,
        "segmentImportOk": segment_import["status"] == 200 and segment_import["result"].get("ok") is True,
        "segmentImportTransform": segment_import["result"].get("importPlan", {}).get("transformTool") == "com.etzhayyim.apps.openUnispsc.syncCatalogItem",
        "catalogSyncOk": catalog_sync["status"] == 200 and catalog_sync["result"].get("ok") is True,
        "catalogSyncRecord": catalog_sync["result"].get("catalogItem", {}).get("product_id") == "unispsc-43211501",
        "purchasePlanOk": purchase_plan["status"] == 200 and purchase_plan["result"].get("ok") is True,
        "purchasePlanInvocation": purchase_plan["result"].get("procurementInvocation", {}).get("mcpTool") == "com.etzhayyim.apps.openUnispsc.itemGetSpec",
        "applyPreviewOk": apply_preview["status"] == 200 and preview_result.get("ok") is True,
        "applyPreviewRows": preview_result.get("validatedRows") == 5,
    }
    scenario_reports: dict[str, dict[str, Any]] = {}
    for name, scenario in workflow_scenarios.items():
        result = workflows[name]["result"]
        row_count = result.get("graphWriteValidation", {}).get("validatedRows")
        status_ok = result.get("workflowStatus") == scenario["expectedStatus"]
        rows_ok = row_count == scenario["expectedRows"]
        ok = workflows[name]["status"] == 200 and result.get("ok") is True and status_ok and rows_ok
        checks[f"workflow:{name}"] = ok
        scenario_reports[name] = {
            "status": workflows[name]["status"],
            "ok": result.get("ok"),
            "workflowStatus": result.get("workflowStatus"),
            "expectedStatus": scenario["expectedStatus"],
            "validatedRows": row_count,
            "expectedRows": scenario["expectedRows"],
            "summary": result.get("summary"),
        }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "coverage": {
            "status": coverage["status"],
            "toolCount": coverage_result.get("toolCount"),
            "graphTargetCount": coverage_result.get("graphTargetCount"),
            "missing": coverage_result.get("missing"),
        },
        "workflowScenarios": scenario_reports,
        "workflow": {
            "status": workflow["status"],
            "workflowStatus": workflow_result.get("workflowStatus"),
            "summary": workflow_result.get("summary"),
            "validatedRows": workflow_result.get("graphWriteValidation", {}).get("validatedRows"),
        },
        "catalogSync": {
            "status": catalog_sync["status"],
            "catalogCollection": catalog_sync["result"].get("catalogCollection"),
            "catalogRkey": catalog_sync["result"].get("catalogRkey"),
            "productId": catalog_sync["result"].get("catalogItem", {}).get("product_id"),
        },
        "purchasePlan": {
            "status": purchase_plan["status"],
            "productId": purchase_plan["result"].get("productId"),
            "commodityCode": purchase_plan["result"].get("commodityCode"),
            "targetActorDid": purchase_plan["result"].get("procurementInvocation", {}).get("targetActorDid"),
            "mcpTool": purchase_plan["result"].get("procurementInvocation", {}).get("mcpTool"),
        },
        "syncAllCommodityDids": {
            "status": sync_all["status"],
            "segmentCount": sync_all["result"].get("segmentCount"),
            "commandsPerSegment": sync_all["result"].get("orchestrationPlan", {}).get("commandsPerSegment"),
        },
        "segmentImport": {
            "status": segment_import["status"],
            "segment": segment_import["result"].get("segment"),
            "importCommand": segment_import["result"].get("importCommand"),
            "transformTool": segment_import["result"].get("importPlan", {}).get("transformTool"),
        },
        "applyPreview": {
            "status": apply_preview["status"],
            "validatedRows": preview_result.get("validatedRows"),
            "statementCount": len(preview_result.get("sqlStatements", [])),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument("--report-path", help="Optional path to write the JSON verifier report.")
    args = parser.parse_args()
    result = asyncio.run(verify())
    payload = json.dumps(result, indent=2 if args.pretty else None, sort_keys=True)
    if args.report_path:
        path = Path(args.report_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
