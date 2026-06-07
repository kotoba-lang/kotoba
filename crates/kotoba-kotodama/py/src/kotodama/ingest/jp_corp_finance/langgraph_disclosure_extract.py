from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from kotodama.primitives import langgraph_registry

from .extractor import extract_financial_facts_from_ocr

GRAPH_ID = "jp_corp_finance.disclosure_extract_v1"


class DisclosureExtractState(TypedDict, total=False):
    runId: str
    sourceId: str
    sourceUrl: str
    disclosures: list[dict[str, Any]]
    ocrPages: list[dict[str, Any]]
    financialFacts: list[dict[str, Any]]
    extractionStatus: str
    reviewReasons: list[str]
    final_state: dict[str, Any]


def _coerce_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _prepare(state: DisclosureExtractState) -> dict[str, Any]:
    disclosures = _coerce_rows(state.get("disclosures"))
    ocr_pages = _coerce_rows(state.get("ocrPages"))
    review_reasons: list[str] = []
    if not disclosures:
        review_reasons.append("no_disclosures")
    if not ocr_pages:
        review_reasons.append("no_ocr_pages")
    return {
        "disclosures": disclosures,
        "ocrPages": ocr_pages,
        "reviewReasons": review_reasons,
    }


def _extract_financial_tables(state: DisclosureExtractState) -> dict[str, Any]:
    facts = extract_financial_facts_from_ocr(
        disclosures=_coerce_rows(state.get("disclosures")),
        ocr_pages=state.get("ocrPages") or [],
    )
    return {"financialFacts": facts}


def _assess_quality(state: DisclosureExtractState) -> dict[str, Any]:
    reasons = list(state.get("reviewReasons") or [])
    facts = _coerce_rows(state.get("financialFacts"))
    if not facts:
        reasons.append("no_financial_facts")
    status = "extracted" if facts and not reasons else "needs_review"
    return {
        "extractionStatus": status,
        "reviewReasons": sorted(set(reasons)),
    }


def _finalize(state: DisclosureExtractState) -> dict[str, Any]:
    final_state = {
        "runId": state.get("runId", ""),
        "sourceId": state.get("sourceId", ""),
        "sourceUrl": state.get("sourceUrl", ""),
        "disclosures": _coerce_rows(state.get("disclosures")),
        "financialFacts": _coerce_rows(state.get("financialFacts")),
        "extractionStatus": state.get("extractionStatus", "needs_review"),
        "reviewReasons": list(state.get("reviewReasons") or []),
        "graphId": GRAPH_ID,
    }
    return {"final_state": final_state}


def build_graph() -> Any:
    graph = StateGraph(DisclosureExtractState)
    graph.add_node("prepare", _prepare)
    graph.add_node("extract_financial_tables", _extract_financial_tables)
    graph.add_node("assess_quality", _assess_quality)
    graph.add_node("finalize", _finalize)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "extract_financial_tables")
    graph.add_edge("extract_financial_tables", "assess_quality")
    graph.add_edge("assess_quality", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


disclosure_extract_graph = build_graph()
langgraph_registry.register(GRAPH_ID, disclosure_extract_graph)
