from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime
from typing import Any

from ..ids import disclosure_vid
from ..models import DisclosureRow, clean

EDINET_API = "https://api.edinet-fsa.go.jp/api/v2/documents.json"
SOURCE_ID = "edinet-v2"

FORM_SCOPE: dict[str, tuple[str, str]] = {
    "030000": ("EDINET_YUHO", "BS_PL_CF"),
    "043000": ("EDINET_QUARTERLY", "BS_PL_CF"),
    "050000": ("EDINET_SEMI_ANNUAL", "BS_PL_CF"),
    "020000": ("EDINET_MATERIAL_EVENT", "METADATA_ONLY"),
}


def today_jstish() -> str:
    # EDINET date parameters are date-only; UTC is sufficient for worker defaults.
    return date.today().isoformat()


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fiscal_year_from_period_end(period_end: str) -> int | None:
    if len(period_end) < 4:
        return None
    try:
        return int(period_end[:4])
    except ValueError:
        return None


def edinet_doc_url(doc_id: str) -> str:
    return (
        "https://disclosure.edinet-api.go.jp/e01ew/BLMainController.jsp"
        "?uji.verb=W1E63011CXP01&TID=W1E63011CXP01&documentId="
        + urllib.parse.quote(doc_id)
    )


def fetch_documents_json(
    target_date: str,
    *,
    subscription_key: str | None = None,
    timeout_sec: int = 30,
) -> dict[str, Any]:
    params = urllib.parse.urlencode({"date": target_date, "type": "2"})
    req = urllib.request.Request(
        f"{EDINET_API}?{params}",
        headers={
            "Accept": "application/json",
            "User-Agent": "jp-corp-finance.etzhayyim.com/0.1 contact@etzhayyim.com",
            **(
                {"Ocp-Apim-Subscription-Key": subscription_key}
                if subscription_key
                else {}
            ),
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _doc_type_code(doc: dict[str, Any]) -> str:
    return clean(
        doc.get("formCode")
        or doc.get("docTypeCode")
        or doc.get("ordinanceCode")
    )


def _period_end(doc: dict[str, Any]) -> str:
    return clean(doc.get("periodEnd") or doc.get("periodEndDate") or doc.get("fiscalYearEnd"))


def normalize_documents(
    payload: dict[str, Any],
    *,
    target_date: str,
    observed_at: str | None = None,
    artifact_uri: str = "",
) -> list[DisclosureRow]:
    observed = observed_at or now_iso()
    rows: list[DisclosureRow] = []
    for doc in payload.get("results") or []:
        if not isinstance(doc, dict):
            continue
        doc_id = clean(doc.get("docID") or doc.get("docId"))
        edinet_code = clean(doc.get("edinetCode"))
        if not doc_id or not edinet_code:
            continue
        form_code = _doc_type_code(doc)
        disclosure_kind, statement_scope = FORM_SCOPE.get(form_code, ("EDINET_OTHER", "METADATA_ONLY"))
        period_end = _period_end(doc)
        source_record_id = doc_id
        rows.append(
            DisclosureRow(
                vertex_id=disclosure_vid(SOURCE_ID, source_record_id),
                jcn=clean(doc.get("JCN") or doc.get("jcn")),
                edinet_code=edinet_code,
                company_name=clean(doc.get("filerName") or doc.get("issuerName")),
                fiscal_year=fiscal_year_from_period_end(period_end),
                period_start=clean(doc.get("periodStart") or doc.get("periodStartDate")),
                period_end=period_end,
                disclosure_kind=disclosure_kind,
                statement_scope=statement_scope,
                source_id=SOURCE_ID,
                source_record_id=source_record_id,
                source_url=edinet_doc_url(doc_id),
                artifact_uri=artifact_uri,
                source_published_at=clean(doc.get("submitDateTime") or target_date),
                observed_at=observed,
                extraction_status="normalized",
                confidence=0.98 if disclosure_kind != "EDINET_OTHER" else 0.8,
                created_at=observed,
            )
        )
    return rows


def fetch_and_normalize(
    target_date: str | None = None,
    *,
    subscription_key: str | None = None,
) -> tuple[dict[str, Any], list[DisclosureRow]]:
    date_value = target_date or today_jstish()
    payload = fetch_documents_json(
        date_value,
        subscription_key=subscription_key or os.environ.get("EDINET_SUBSCRIPTION_KEY"),
    )
    return payload, normalize_documents(payload, target_date=date_value)
