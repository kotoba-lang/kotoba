from __future__ import annotations

import json
from typing import Any

from .gleif import apply_gleif_enrichment
from .sec_adv import plan_sec_adv_shards, normalize_sec_adv_csv, normalize_sec_adv_rows
from .types import NormalizedFund, NormalizedFundManager
from .writer import graph_rows, upsert_graph_rows


def _rows_from_any(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, str) and value.strip():
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
    return []


def _managers_from_any(value: Any) -> list[NormalizedFundManager]:
    return [NormalizedFundManager(**x) for x in _rows_from_any(value)]


def _funds_from_any(value: Any) -> list[NormalizedFund]:
    return [NormalizedFund(**x) for x in _rows_from_any(value)]


def task_fund_plan_sources(
    mode: str = "delta",
    sourceId: str = "sec-adv",
    limit: int = 10,
) -> dict[str, Any]:
    if sourceId not in {"sec-adv", "all"}:
        return {"ok": False, "error": f"unsupported fund source: {sourceId}"}
    shards = plan_sec_adv_shards(mode=mode, limit=limit)
    return {"ok": True, "sourceId": sourceId, "shards": [x.to_dict() for x in shards]}


def task_fund_fetch_raw(
    sourceId: str = "sec-adv",
    shardKey: str = "",
    sourceUrl: str = "",
) -> dict[str, Any]:
    return {
        "ok": True,
        "sourceId": sourceId,
        "shardKey": shardKey,
        "sourceUrl": sourceUrl,
        "status": "planned",
        "artifact": None,
        "reason": "network fetch is intentionally owned by a source-specific fetcher pod",
    }


def task_fund_persist_artifact(
    sourceId: str = "sec-adv",
    artifactUri: str = "",
    sha256: str = "",
    byteSize: int | None = None,
    recordCount: int | None = None,
) -> dict[str, Any]:
    if not artifactUri:
        return {"ok": False, "error": "artifactUri required"}
    return {
        "ok": True,
        "sourceId": sourceId,
        "artifact": {
            "source_id": sourceId,
            "artifact_kind": "raw",
            "uri": artifactUri,
            "sha256": sha256,
            "byte_size": byteSize,
            "record_count": recordCount,
        },
    }


def task_fund_normalize_manager(
    sourceId: str = "sec-adv",
    rows: Any = None,
    csvText: str = "",
    sourceUrl: str = "",
    sourceLicense: str = "sec-public",
) -> dict[str, Any]:
    if sourceId != "sec-adv":
        return {"ok": False, "error": f"unsupported manager source: {sourceId}"}
    managers, funds = (
        normalize_sec_adv_csv(csvText, source_url=sourceUrl, source_license=sourceLicense)
        if csvText
        else normalize_sec_adv_rows(
            _rows_from_any(rows),
            source_url=sourceUrl,
            source_license=sourceLicense,
        )
    )
    return {
        "ok": True,
        "sourceId": sourceId,
        "managers": [x.to_dict() for x in managers],
        "funds": [x.to_dict() for x in funds],
        "recordsRead": len(_rows_from_any(rows)) if not csvText else csvText.count("\n"),
    }


async def task_fund_normalize_fund(
    sourceId: str = "sec-adv",
    rows: Any = None,
    csvText: str = "",
    sourceUrl: str = "",
    sourceLicense: str = "sec-public",
) -> dict[str, Any]:
    out = task_fund_normalize_manager(sourceId, rows, csvText, sourceUrl, sourceLicense)
    return {
        "ok": out.get("ok", False),
        "sourceId": sourceId,
        "funds": out.get("funds", []),
        "recordsRead": out.get("recordsRead", 0),
        **({"error": out["error"]} if out.get("error") else {}),
    }


def task_fund_normalize_lp(sourceId: str = "", rows: Any = None) -> dict[str, Any]:
    return {
        "ok": True,
        "sourceId": sourceId,
        "investors": [],
        "recordsRead": len(_rows_from_any(rows)),
    }


def task_fund_normalize_investment(sourceId: str = "", rows: Any = None) -> dict[str, Any]:
    return {
        "ok": True,
        "sourceId": sourceId,
        "investees": [],
        "investments": [],
        "recordsRead": len(_rows_from_any(rows)),
    }


def task_fund_enrich_entity(
    entity: dict[str, Any] | None = None,
    gleifPayload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(entity, dict):
        return {"ok": False, "error": "entity required"}
    return {"ok": True, "entity": apply_gleif_enrichment(entity, gleifPayload or {})}


def task_fund_compute_returns(metrics: Any = None) -> dict[str, Any]:
    rows = _rows_from_any(metrics)
    safe = [
        {**row, "metric_kind": row.get("metric_kind") or row.get("metricKind") or "unknown"}
        for row in rows
    ]
    return {
        "ok": True,
        "metrics": safe,
        "warning": "estimated returns must not be treated as reported facts",
    }


def task_fund_write_graph(
    managers: Any = None,
    funds: Any = None,
    rwHealthy: bool = False,
    dryRun: bool = True,
) -> dict[str, Any]:
    normalized_managers = _managers_from_any(managers)
    normalized_funds = _funds_from_any(funds)
    rows = graph_rows(normalized_managers, normalized_funds)
    row_count = sum(len(v) for v in rows.values())
    if dryRun:
        return {"ok": True, "dryRun": True, "recordsPrepared": row_count, "tables": rows}
    if not rwHealthy:
        return {
            "ok": False,
            "degraded": True,
            "recordsPrepared": row_count,
            "error": "rwHealthy required before graph write",
        }
    try:
        result = upsert_graph_rows(rows)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "recordsPrepared": row_count, "error": f"fund.writeGraph failed: {e}"}
    return {"dryRun": False, **result}


def task_fund_verify_coverage(
    recordsWritten: int = 0,
    recordsPrepared: int = 0,
) -> dict[str, Any]:
    return {
        "ok": recordsWritten >= 0 and recordsPrepared >= recordsWritten,
        "recordsWritten": recordsWritten,
        "recordsPrepared": recordsPrepared,
    }
