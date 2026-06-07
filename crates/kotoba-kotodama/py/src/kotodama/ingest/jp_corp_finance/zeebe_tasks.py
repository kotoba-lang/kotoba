from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kotodama.ingest.core import IngestRun, stable_run_id, upsert_run

from .extractor import extract_financial_facts_from_ocr
from .ocr import content_b64_to_temp_file, convert_upload_ocr
from .sources.kanpo import SOURCE_ID as KANPO_SOURCE_ID
from .sources.kanpo import fetch_kanpo_source
from .sources.edinet import SOURCE_ID as EDINET_SOURCE_ID
from .sources.edinet import fetch_and_normalize, normalize_documents, today_jstish
from .writer import graph_rows, upsert_graph_rows

INGEST_FAMILY = "jp-corp-finance"


def _rows_from_any(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, str) and value.strip():
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
        if isinstance(parsed, dict) and isinstance(parsed.get("results"), list):
            return [x for x in parsed["results"] if isinstance(x, dict)]
    if isinstance(value, dict) and isinstance(value.get("results"), list):
        return [x for x in value["results"] if isinstance(x, dict)]
    return []


async def task_jp_corp_finance_create_run(
    sourceId: str = EDINET_SOURCE_ID,
    mode: str = "delta",
    runId: str = "",
    inputJson: str = "",
    requestedBy: str = "",
    bpmnProcessId: str = "jp_corp_finance_daily",
) -> dict[str, Any]:
    run_id = runId or stable_run_id(INGEST_FAMILY, sourceId, mode, inputJson)
    run = IngestRun(
        ingest_family=INGEST_FAMILY,
        source_id=sourceId,
        mode=mode,
        run_id=run_id,
        status="running",
        bpmn_process_id=bpmnProcessId,
        requested_by=requestedBy or None,
        input_json=inputJson or None,
    )
    try:
        run_vertex_id = upsert_run(run)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "runId": run_id, "error": f"createRun failed: {e}"}
    return {"ok": True, "runId": run_id, "runVertexId": run_vertex_id, "sourceId": sourceId}


async def task_jp_corp_finance_plan_shards(
    sourceId: str = EDINET_SOURCE_ID,
    targetDate: str = "",
    limit: int = 1,
) -> dict[str, Any]:
    if sourceId not in {EDINET_SOURCE_ID, "kanpo", "moj-e-koukoku"}:
        return {"ok": False, "error": f"unsupported sourceId: {sourceId}"}
    date_value = targetDate or today_jstish()
    shards = [{"sourceId": sourceId, "shardKey": date_value, "targetDate": date_value}]
    return {"ok": True, "sourceId": sourceId, "shards": shards[: max(1, int(limit or 1))]}


async def task_jp_corp_finance_fetch_source(
    sourceId: str = EDINET_SOURCE_ID,
    targetDate: str = "",
    sourceUrl: str = "",
    keyword: str = "会社決算公告",
    dryRun: bool = False,
) -> dict[str, Any]:
    if sourceId == KANPO_SOURCE_ID:
        try:
            return fetch_kanpo_source(
                target_date=targetDate or today_jstish(),
                source_url=sourceUrl,
                keyword=keyword or "会社決算公告",
                dry_run=dryRun,
            )
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "sourceId": sourceId, "error": f"fetchSource kanpo failed: {e}"}
    if sourceId != EDINET_SOURCE_ID:
        return {
            "ok": True,
            "sourceId": sourceId,
            "status": "planned",
            "artifactUri": "",
            "payload": {"results": []},
            "reason": "source fetcher not implemented in P1",
        }
    if dryRun:
        return {"ok": True, "sourceId": sourceId, "targetDate": targetDate or today_jstish(), "payload": {"results": []}}
    try:
        payload, rows = fetch_and_normalize(targetDate or None)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "sourceId": sourceId, "error": f"fetchSource failed: {e}"}
    return {
        "ok": True,
        "sourceId": sourceId,
        "targetDate": targetDate or today_jstish(),
        "payload": payload,
        "recordsRead": len(payload.get("results") or []),
        "normalizedRows": [row.to_dict() for row in rows],
    }


async def task_jp_corp_finance_normalize(
    sourceId: str = EDINET_SOURCE_ID,
    payload: Any = None,
    rows: Any = None,
    targetDate: str = "",
    artifactUri: str = "",
) -> dict[str, Any]:
    if sourceId != EDINET_SOURCE_ID:
        return {"ok": True, "sourceId": sourceId, "disclosures": [], "recordsRead": len(_rows_from_any(rows))}
    source_payload = payload if isinstance(payload, dict) else {"results": _rows_from_any(rows)}
    disclosures = normalize_documents(
        source_payload,
        target_date=targetDate or today_jstish(),
        artifact_uri=artifactUri,
    )
    return {
        "ok": True,
        "sourceId": sourceId,
        "recordsRead": len(source_payload.get("results") or []),
        "disclosures": [row.to_dict() for row in disclosures],
    }


async def task_jp_corp_finance_webp_ocr(
    sourcePath: str = "",
    contentB64: str = "",
    filename: str = "document.pdf",
    contentType: str = "",
    maxPages: int = 3,
    webpQuality: int = 82,
    dryRun: bool = False,
) -> dict[str, Any]:
    """Convert PDF/image to WebP, pin pages to ipfs.etzhayyim.com, then OCR with Gemma 4."""
    temp_path: Path | None = None
    try:
        if contentB64:
            suffix = Path(filename or "document.pdf").suffix or ".pdf"
            temp_path = content_b64_to_temp_file(contentB64, suffix)
            source_path = str(temp_path)
        else:
            source_path = sourcePath
        if not source_path:
            return {"ok": False, "error": "sourcePath or contentB64 required"}
        return await convert_upload_ocr(
            source_path,
            content_type=contentType,
            max_pages=maxPages,
            quality=webpQuality,
            dry_run=dryRun,
        )
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"webpOcr failed: {e}"}
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _valid_fact(row: dict[str, Any]) -> bool:
    required = (
        "vertex_id",
        "disclosure_vid",
        "statement_type",
        "concept",
        "source_location",
        "extraction_method",
    )
    if not all(row.get(key) for key in required):
        return False
    value = row.get("value_jpy")
    return value is None or isinstance(value, int | float)


async def task_jp_corp_finance_validate_rows(disclosures: Any = None, financialFacts: Any = None) -> dict[str, Any]:
    rows = _rows_from_any(disclosures)
    facts = _rows_from_any(financialFacts)
    valid_disclosures = [
        row for row in rows
        if row.get("vertex_id") and row.get("source_id") and row.get("source_record_id")
    ]
    valid_facts = [row for row in facts if _valid_fact(row)]
    invalid_count = (len(rows) - len(valid_disclosures)) + (len(facts) - len(valid_facts))
    return {
        "ok": invalid_count == 0,
        "recordsPrepared": len(valid_disclosures) + len(valid_facts),
        "invalidCount": invalid_count,
        "invalidDisclosureCount": len(rows) - len(valid_disclosures),
        "invalidFactCount": len(facts) - len(valid_facts),
        "disclosures": valid_disclosures,
        "financialFacts": valid_facts,
    }


async def task_jp_corp_finance_extract_financial_facts(
    disclosures: Any = None,
    ocrPages: Any = None,
    extractState: Any = None,
) -> dict[str, Any]:
    disclosure_rows = _rows_from_any(disclosures)
    graph_state = extractState.get("final_state") if isinstance(extractState, dict) else None
    if not isinstance(graph_state, dict) and isinstance(extractState, dict):
        graph_state = extractState
    if isinstance(graph_state, dict) and isinstance(graph_state.get("financialFacts"), list):
        financial_facts = _rows_from_any(graph_state.get("financialFacts"))
        graph_disclosures = _rows_from_any(graph_state.get("disclosures"))
        return {
            "ok": True,
            "disclosures": graph_disclosures or disclosure_rows,
            "financialFacts": financial_facts,
            "factsExtracted": len(financial_facts),
            "method": "langgraph",
            "extractionStatus": graph_state.get("extractionStatus", ""),
            "reviewReasons": graph_state.get("reviewReasons", []),
        }
    try:
        facts = extract_financial_facts_from_ocr(disclosures=disclosure_rows, ocr_pages=ocrPages)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "disclosures": disclosure_rows, "financialFacts": [], "error": f"extractFinancialFacts failed: {e}"}
    return {
        "ok": True,
        "disclosures": disclosure_rows,
        "financialFacts": facts,
        "factsExtracted": len(facts),
        "method": "ocr_table_rule",
    }


async def task_jp_corp_finance_write_graph(
    disclosures: Any = None,
    financialFacts: Any = None,
    dryRun: bool = True,
    rwHealthy: bool = False,
) -> dict[str, Any]:
    disclosure_rows = _rows_from_any(disclosures)
    fact_rows = _rows_from_any(financialFacts)
    rows = graph_rows(disclosure_rows, fact_rows)
    prepared = sum(len(items) for items in rows.values())
    if dryRun:
        return {"ok": True, "dryRun": True, "recordsPrepared": prepared, "recordsWritten": 0, "tables": rows}
    if not rwHealthy:
        return {"ok": False, "degraded": True, "recordsPrepared": prepared, "error": "rwHealthy required before graph write"}
    try:
        result = upsert_graph_rows(rows)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "recordsPrepared": prepared, "recordsWritten": 0, "error": f"jpCorpFinance.writeGraph failed: {e}"}
    return {**result, "dryRun": False, "recordsWritten": result.get("recordsVisible", 0)}


async def task_jp_corp_finance_verify_visibility(
    recordsWritten: int = 0,
    recordsPrepared: int = 0,
) -> dict[str, Any]:
    return {
        "ok": recordsWritten >= 0 and recordsPrepared >= recordsWritten,
        "recordsWritten": recordsWritten,
        "recordsPrepared": recordsPrepared,
    }


async def task_jp_corp_finance_refresh_coverage(
    jcn: str = "",
    recordsPrepared: int = 0,
) -> dict[str, Any]:
    return {"ok": True, "jcn": jcn, "recordsPrepared": recordsPrepared, "status": "planned"}
