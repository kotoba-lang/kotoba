from __future__ import annotations

import re
import unicodedata
from typing import Any

from .ids import fact_vid


CONCEPT_PATTERNS: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("liabilities_total", "負債合計", "BS", ("負債合計", "総負債")),
    ("net_assets_total", "純資産合計", "BS", ("純資産合計", "純資産")),
    ("assets_total", "資産合計", "BS", ("資産合計", "総資産")),
    ("revenue_net_sales", "売上高", "PL", ("売上高", "営業収益", "収益")),
    ("operating_income", "営業利益", "PL", ("営業利益",)),
    ("ordinary_income", "経常利益", "PL", ("経常利益",)),
    ("net_income", "当期純利益", "PL", ("当期純利益", "純利益")),
]

NEGATIVE_MARKERS = ("△", "▲")
NUMBER_RE = re.compile(r"[△▲(（-]?\s*[0-9][0-9,]*(?:\.[0-9]+)?\s*[)）]?")


def normalize_text(value: Any) -> str:
    return unicodedata.normalize("NFKC", "" if value is None else str(value)).strip()


def concept_for_label(label: str) -> tuple[str, str, str] | None:
    text = normalize_text(label).replace(" ", "")
    if any(skip in text for skip in ("原価", "利益剰余金", "包括利益")):
        return None
    for concept, label_ja, statement_type, needles in CONCEPT_PATTERNS:
        if any(needle in text for needle in needles):
            return concept, label_ja, statement_type
    return None


def unit_multiplier(text: str) -> tuple[str, float]:
    normalized = normalize_text(text)
    if "百万円" in normalized or "百万" in normalized:
        return "JPY", 1_000_000.0
    if "千円" in normalized or "千 円" in normalized:
        return "JPY", 1_000.0
    if "億円" in normalized:
        return "JPY", 100_000_000.0
    return "JPY", 1.0


def parse_number(value: Any, context: str = "") -> float | None:
    text = normalize_text(value)
    match = NUMBER_RE.search(text)
    if not match:
        return None
    raw = match.group(0).replace(",", "").replace(" ", "")
    negative = raw.startswith("-") or raw.startswith(NEGATIVE_MARKERS) or raw.startswith("(") or raw.startswith("（")
    raw = raw.strip("-△▲()（）")
    try:
        number = float(raw)
    except ValueError:
        return None
    _, multiplier = unit_multiplier(f"{context} {text}")
    return -number * multiplier if negative else number * multiplier


def _tables_from_ocr_pages(ocr_pages: Any) -> list[tuple[int, str, list[list[Any]]]]:
    if not isinstance(ocr_pages, list):
        return []
    tables: list[tuple[int, str, list[list[Any]]]] = []
    for page in ocr_pages:
        if not isinstance(page, dict):
            continue
        page_index = int(page.get("pageIndex") or page.get("page_index") or 0)
        result = page.get("result") if isinstance(page.get("result"), dict) else page
        for table_index, table in enumerate(result.get("tables") or []):
            if not isinstance(table, dict):
                continue
            rows = table.get("rows") or []
            if isinstance(rows, list):
                title = normalize_text(table.get("title") or f"table-{table_index}")
                tables.append((page_index, title, [r for r in rows if isinstance(r, list)]))
    return tables


def _pick_value_cell(row: list[Any], label_index: int, context_prefix: str = "") -> tuple[int, float | None]:
    context = " ".join([context_prefix, *(normalize_text(cell) for cell in row)])
    candidates: list[tuple[int, float]] = []
    for idx, cell in enumerate(row):
        if idx == label_index:
            continue
        value = parse_number(cell, context)
        if value is not None:
            candidates.append((idx, value))
    if not candidates:
        return -1, None
    after = [item for item in candidates if item[0] > label_index]
    return after[-1] if after else candidates[-1]


def _disclosure_for_fact(disclosures: list[dict[str, Any]], period_end: str = "") -> dict[str, Any]:
    if not disclosures:
        return {}
    if period_end:
        for row in disclosures:
            if normalize_text(row.get("period_end")) == period_end:
                return row
    return disclosures[0]


def extract_financial_facts_from_ocr(
    *,
    disclosures: list[dict[str, Any]],
    ocr_pages: Any,
) -> list[dict[str, Any]]:
    facts: dict[str, dict[str, Any]] = {}
    disclosure = _disclosure_for_fact(disclosures)
    disclosure_vid = str(disclosure.get("vertex_id") or "")
    if not disclosure_vid:
        return []

    for page_index, title, rows in _tables_from_ocr_pages(ocr_pages):
        table_unit_text = " ".join([title, *(normalize_text(cell) for row in rows[:3] for cell in row)])
        unit, _ = unit_multiplier(table_unit_text)
        for row_index, row in enumerate(rows):
            for cell_index, cell in enumerate(row):
                concept = concept_for_label(normalize_text(cell))
                if concept is None:
                    continue
                value_col, value_jpy = _pick_value_cell(row, cell_index, table_unit_text)
                if value_jpy is None:
                    continue
                concept_id, label_ja, statement_type = concept
                source_location = f"page:{page_index + 1}:table:{title}:row:{row_index + 1}:col:{value_col + 1}"
                vertex_id = fact_vid(disclosure_vid, statement_type, concept_id, source_location)
                facts[vertex_id] = {
                    "vertex_id": vertex_id,
                    "disclosure_vid": disclosure_vid,
                    "jcn": disclosure.get("jcn") or "",
                    "edinet_code": disclosure.get("edinet_code") or "",
                    "fiscal_year": disclosure.get("fiscal_year"),
                    "period_end": disclosure.get("period_end") or "",
                    "statement_type": statement_type,
                    "concept": concept_id,
                    "label_ja": label_ja,
                    "value_jpy": value_jpy,
                    "value_text": normalize_text(row[value_col]) if value_col >= 0 else "",
                    "unit": unit,
                    "source_location": source_location,
                    "extraction_method": "ocr_table_rule",
                    "confidence": 0.72,
                }
    return list(facts.values())
