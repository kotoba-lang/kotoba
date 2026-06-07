from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _coverage_item(row: dict[str, Any]) -> dict[str, str]:
    return {
        "jcn": _text(row["jcn"]),
        "companyName": _text(row["company_name"]),
        "disclosureMethod": _text(row["disclosure_method"]),
        "latestPeriodEnd": _text(row["latest_period_end"]),
        "latestDisclosureVid": _text(row["latest_disclosure_vid"]),
        "coverageStatus": _text(row["coverage_status"]),
        "missingReason": _text(row["missing_reason"]),
        "checkedAt": _text(row["checked_at"]),
    }


def get_coverage(*, jcn: str = "", edinet_code: str = "") -> dict[str, Any]:
    """Return latest coverage for one company by JCN or EDINET code."""
    jcn = jcn.strip()
    edinet_code = edinet_code.strip()
    if not jcn and not edinet_code:
        return {"ok": False, "error": "jcn or edinetCode required"}
    if jcn:
        client = get_kotoba_client()
        row = client.select_first_where(
            "vertex_jp_corp_finance_coverage",
            "jcn",
            jcn,
            columns=[
                "jcn",
                "company_name",
                "disclosure_method",
                "latest_period_end",
                "latest_disclosure_vid",
                "coverage_status",
                "missing_reason",
                "checked_at",
            ],
        )
        rows = [row] if row else []
    else:
        client = get_kotoba_client()
        # R0: Multi-predicate query with JOIN, ORDER BY, and LIMIT is handled by fetching
        #     matching entities via Datalog and then sorting/limiting in Python.
        query_edn = """
            [:find (pull ?c [:vertex_jp_corp_finance_coverage/jcn
                             :vertex_jp_corp_finance_coverage/company_name
                             :vertex_jp_corp_finance_coverage/disclosure_method
                             :vertex_jp_corp_finance_coverage/latest_period_end
                             :vertex_jp_corp_finance_coverage/latest_disclosure_vid
                             :vertex_jp_corp_finance_coverage/coverage_status
                             :vertex_jp_corp_finance_coverage/missing_reason
                             :vertex_jp_corp_finance_coverage/checked_at])
             :in $edinet_code
             :where
             [?d :vertex_jp_corp_disclosure/edinet_code $edinet_code]
             [?c :vertex_jp_corp_finance_coverage/latest_disclosure_vid ?d]]
        """
        raw_results = client.q(query_edn, edinet_code)
        # Flatten the results and convert Datalog keyword keys to snake_case string keys
        processed_results = []
        for res_list in raw_results:
            if res_list and isinstance(res_list[0], dict):
                item_dict = {}
                for key, value in res_list[0].items():
                    if isinstance(key, str) and "/" in key:
                        parts = key.split("/")
                        item_dict[parts[-1].replace('-', '_')] = value
                    else:
                        item_dict[key] = value
                processed_results.append(item_dict)

        # Apply ORDER BY c.checked_at DESC and LIMIT 1 in Python
        if processed_results:
            processed_results.sort(key=lambda x: x.get("checked_at", ""), reverse=True)
            rows = [processed_results[0]]
        else:
            rows = []
    if not rows:
        return {
            "ok": True,
            "found": False,
            "jcn": jcn,
            "edinetCode": edinet_code,
            "coverageStatus": "missing",
            "missingReason": "coverage_not_found",
        }
    return {"ok": True, "found": True, **_coverage_item(rows[0])}


def list_missing(
    *,
    coverage_status: str = "missing",
    missing_reason: str = "",
    limit: int = 100,
    cursor: str = "",
) -> dict[str, Any]:
    """List missing/stale/source_unknown/failed coverage rows, ordered by JCN."""
    allowed_statuses = {"missing", "stale", "source_unknown", "failed"}
    status = (coverage_status or "missing").strip()
    if status not in allowed_statuses:
        return {"ok": False, "items": [], "error": f"unsupported coverageStatus: {status}"}
    bounded_limit = max(1, min(_int(limit, 100), 500))
    # 'status' is used in select_where; 'missing_reason' and 'cursor' are handled in Python filtering
    client = get_kotoba_client()
    # R0: Multi-predicate query with ORDER BY, and LIMIT are handled by fetching
    #     a broader set with 'select_where' and then filtering/sorting/limiting in Python.
    all_matching_status_rows = client.select_where(
        "vertex_jp_corp_finance_coverage",
        "coverage_status",
        status,
        columns=[
            "jcn",
            "company_name",
            "disclosure_method",
            "latest_period_end",
            "latest_disclosure_vid",
            "coverage_status",
            "missing_reason",
            "checked_at",
        ],
        limit=2000 # Fetch a broader set as per instructions
    )

    # Apply additional predicates (missing_reason, jcn > cursor), ORDER BY jcn ASC, and LIMIT in Python
    filtered_rows = []
    for row in all_matching_status_rows:
        if missing_reason and row.get("missing_reason") != missing_reason:
            continue
        if cursor and row.get("jcn", "") <= cursor: # jcn > %s
            continue
        filtered_rows.append(row)

    # Apply ORDER BY jcn ASC
    filtered_rows.sort(key=lambda x: x.get("jcn", ""))

    # Apply LIMIT %s
    rows = filtered_rows[:bounded_limit + 1]
    page = rows[:bounded_limit]
    next_cursor = _text(page[-1]["jcn"]) if len(rows) > bounded_limit and page else ""
    return {
        "ok": True,
        "items": [_coverage_item(row) for row in page],
        "cursor": next_cursor,
    }
