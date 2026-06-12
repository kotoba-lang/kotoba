from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class CommodityState(TypedDict):
    commodity_code: str
    quality_checks: Annotated[List[str], operator.add]
    is_approved: bool

def validate_purity(state: CommodityState) -> CommodityState:
    # Logic for purity validation
    state['quality_checks'].append('Purity validated')
    return state

def approve_procurement(state: CommodityState) -> CommodityState:
    # Decision logic
    state['is_approved'] = True
    return state

graph = StateGraph(CommodityState)
graph.add_node('validate', validate_purity)
graph.add_node('approve', approve_procurement)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
