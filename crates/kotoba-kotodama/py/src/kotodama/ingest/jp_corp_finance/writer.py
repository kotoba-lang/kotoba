from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

from .ids import ACTOR_DID, coverage_vid


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


DISCLOSURE_COLS = {
    "vertex_id",
    "_seq",
    "created_date",
    "sensitivity_ord",
    "owner_did",
    "jcn",
    "edinet_code",
    "company_name",
    "fiscal_year",
    "period_start",
    "period_end",
    "disclosure_kind",
    "statement_scope",
    "source_id",
    "source_record_id",
    "source_url",
    "artifact_uri",
    "source_published_at",
    "observed_at",
    "extraction_status",
    "confidence",
    "status",
    "actor_did",
    "org_did",
    "created_at",
}

FACT_COLS = {
    "vertex_id",
    "_seq",
    "created_date",
    "sensitivity_ord",
    "owner_did",
    "disclosure_vid",
    "jcn",
    "edinet_code",
    "fiscal_year",
    "period_end",
    "statement_type",
    "concept",
    "label_ja",
    "value_jpy",
    "value_text",
    "unit",
    "source_location",
    "extraction_method",
    "confidence",
    "actor_did",
    "org_did",
    "created_at",
}

COVERAGE_COLS = {
    "vertex_id",
    "_seq",
    "created_date",
    "sensitivity_ord",
    "owner_did",
    "jcn",
    "company_name",
    "disclosure_method",
    "latest_period_end",
    "latest_disclosure_vid",
    "coverage_status",
    "missing_reason",
    "checked_at",
    "actor_did",
    "org_did",
    "created_at",
}


def _base_row() -> dict[str, Any]:
    return {
        "_seq": None,
        "created_date": today(),
        "sensitivity_ord": 1,
        "owner_did": ACTOR_DID,
        "actor_did": ACTOR_DID,
        "org_did": "anon",
        "created_at": now_iso(),
    }


def _project(values: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    return {k: v for k, v in values.items() if k in allowed and v is not None}


def disclosure_row(row: dict[str, Any]) -> dict[str, Any]:
    values = {
        **_base_row(),
        **row,
        "status": row.get("status") or "active",
        "extraction_status": row.get("extraction_status") or "pending",
        "confidence": row.get("confidence", 0.0),
    }
    return _project(values, DISCLOSURE_COLS)


def financial_fact_row(row: dict[str, Any]) -> dict[str, Any]:
    values = {
        **_base_row(),
        **row,
        "confidence": row.get("confidence", 0.0),
    }
    return _project(values, FACT_COLS)


def coverage_rows(disclosures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_jcn: dict[str, dict[str, Any]] = {}
    checked_at = now_iso()
    for row in disclosures:
        jcn = str(row.get("jcn") or "").strip()
        if not jcn:
            continue
        current = by_jcn.get(jcn)
        period_end = str(row.get("period_end") or "")
        if current is not None and period_end < str(current.get("latest_period_end") or ""):
            continue
        by_jcn[jcn] = {
            **_base_row(),
            "vertex_id": coverage_vid(jcn),
            "jcn": jcn,
            "company_name": row.get("company_name") or None,
            "disclosure_method": row.get("source_id") or None,
            "latest_period_end": row.get("period_end") or None,
            "latest_disclosure_vid": row.get("vertex_id") or None,
            "coverage_status": "covered",
            "missing_reason": None,
            "checked_at": checked_at,
        }
    return [_project(row, COVERAGE_COLS) for row in by_jcn.values()]


def graph_rows(
    disclosures: list[dict[str, Any]],
    financial_facts: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    disclosure_items = [disclosure_row(row) for row in disclosures]
    fact_items = [financial_fact_row(row) for row in financial_facts or []]
    return {
        "vertex_jp_corp_disclosure": disclosure_items,
        "vertex_jp_corp_financial_fact": fact_items,
        "vertex_jp_corp_finance_coverage": coverage_rows(disclosure_items),
    }





def upsert_graph_rows(rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    table_pk = {
        "vertex_jp_corp_disclosure": "vertex_id",
        "vertex_jp_corp_financial_fact": "vertex_id",
        "vertex_jp_corp_finance_coverage": "vertex_id",
    }
    prepared = sum(len(items) for items in rows.values())
    processed_records = 0
    visibility: dict[str, dict[str, int]] = {}

    client = get_kotoba_client()
    for table, items in rows.items():
        # R0: insert_row performs upsert; no separate insert/update count.
        #    Each call to insert_row processes one record.
        for item in items:
            client.insert_row(table, item)
            processed_records += 1

    for table, items in rows.items():
        pk_col = table_pk[table]
        ids = [str(item[pk_col]) for item in items if item.get(pk_col)]
        # R0: In-Python filtering for visible count.
        visible = 0
        for item_id in ids:
            if client.select_first_where(table, pk_col, item_id, columns=[pk_col]):
                visible += 1
        visibility[table] = {"expected": len(ids), "visible": visible}

    visible_total = sum(v["visible"] for v in visibility.values())
    return {
        "ok": visible_total >= prepared,
        "recordsPrepared": prepared,
        "recordsInserted": processed_records, # Renamed from inserted to processed_records
        "recordsUpdated": 0, # No distinct updated count from kotoba_client insert_row
        "recordsVisible": visible_total,
        "visibility": visibility,
    }
