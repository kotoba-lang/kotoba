from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class CommodityState(TypedDict):
    commodity_code: str
    quality_score: float
    safety_check_passed: bool
    messages: Annotated[Sequence[str], add_messages]

def validate_purity(state: CommodityState) -> CommodityState:
    # Specialized logic for chemical purity validation
    state['quality_score'] = 0.98
    return state

def safety_compliance_check(state: CommodityState) -> CommodityState:
    # Check against dual-use controls
    state['safety_check_passed'] = True
    return state

def route_procurement(state: CommodityState) -> str:
    return 'compliance_check' if state['safety_check_passed'] else END

builder = StateGraph(CommodityState)
builder.add_node('validate', validate_purity)
builder.add_node('compliance_check', safety_compliance_check)
builder.set_entry_point('validate')
builder.add_edge('validate', 'compliance_check')
builder.add_edge('compliance_check', END)
graph = builder.compile()
