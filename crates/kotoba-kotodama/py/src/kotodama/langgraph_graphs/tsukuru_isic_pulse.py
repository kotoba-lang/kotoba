"""
tsukuru.isic.pulse — generic LangGraph StateGraph (ADR-2605080600 Phase 5).

Replaces 21 Zeebe timer-start BPMNs `tsukuru_isic_{a-u}_*` (daily 0 0 0 * * *).
Single graph parameterized by ISIC section + industry codes; one CronJob per
ISIC section drives daily emission of an industry pulse audit event.

Graph:
  START → select_manufacturers → emit_audit → END
"""

from __future__ import annotations

from typing import TypedDict


class TsukuruIsicPulseState(TypedDict, total=False):
    section_code: str
    label: str
    industry_codes: list[str]
    bpmn_process_id: str
    manufacturer_row_count: int
    manufacturer_rows: list[dict]
    ok: bool
    error: str | None


def select_manufacturers(state: TsukuruIsicPulseState) -> dict:
    from kotodama.kotoba_datomic import get_kotoba_client # R0: Replaced sa_query with kotoba_datomic.q

    codes = state.get("industry_codes") or []
    if not codes:
        return {"manufacturer_rows": [], "manufacturer_row_count": 0, "ok": True}

    try:
        # R0: Datalog query to select manufacturer props based on industry codes
        query_edn = """
        [:find (pull ?e [:vertex_other/props])
         :in $ %
         :where
         [?e :vertex_other/label "TsukuruManufacturer"]
         [?e :vertex_other/props ?props_map]
         [(get ?props_map "industryCode") ?industry_code]
         [(contains? % ?industry_code)]]
        """
        # Execute the query with a limit of 25 directly in Python after fetching all relevant results
        results = get_kotoba_client().q(query_edn, args=(set(codes),))

        # Process results: results are [[{:vertex_other/props {...}}], ...]
        rows = [item[0].get('vertex_other/props', {}) for item in results if item and item[0]]
        # Apply limit after fetching all results that match the criteria
        rows = rows[:25] 

        return {
            "manufacturer_rows": rows,
            "manufacturer_row_count": len(rows),
            "ok": True,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "manufacturer_rows": [], "manufacturer_row_count": 0}


def emit_audit(state: TsukuruIsicPulseState) -> dict:
    import logging

    LOG = logging.getLogger(__name__)
    section = state.get("section_code", "?")
    label = state.get("label", "?")
    count = state.get("manufacturer_row_count", 0)
    LOG.info(
        "tsukuru.isic.pulse section=%s label=%s manufacturers=%d",
        section, label, count,
    )
    return {"ok": state.get("ok", True)}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(TsukuruIsicPulseState)
    builder.add_node("select_manufacturers", select_manufacturers)
    builder.add_node("emit_audit", emit_audit)
    builder.set_entry_point("select_manufacturers")
    builder.add_edge("select_manufacturers", "emit_audit")
    builder.add_edge("emit_audit", END)
    return builder.compile()
