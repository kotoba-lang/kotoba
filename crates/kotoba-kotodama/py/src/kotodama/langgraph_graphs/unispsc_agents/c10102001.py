from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class AgriculturalState(TypedDict):
    commodity_id: str
    batch_id: str
    quality_metrics: dict
    approved: bool

def validate_quality(state: AgriculturalState) -> AgriculturalState:
    moisture = state.get('quality_metrics', {}).get('moisture', 100)
    state['approved'] = moisture < 14.0
    return state

def check_supply_chain(state: AgriculturalState) -> AgriculturalState:
    return state

graph = StateGraph(AgriculturalState)
graph.add_node("validate", validate_quality)
graph.add_node("supply_chain", check_supply_chain)
graph.add_edge("validate", "supply_chain")
graph.add_edge("supply_chain", END)
graph.set_entry_point("validate")
graph = graph.compile()
