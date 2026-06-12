from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class GasSupplyState(TypedDict):
    purity_check: bool
    impurity_data: dict
    cylinder_id: str
    is_cleared: bool

def validate_purity(state: GasSupplyState) -> GasSupplyState:
    purity = state.get('impurity_data', {}).get('purity_percentage', 0)
    state['purity_check'] = purity >= 99.999
    return state

def check_safety_compliance(state: GasSupplyState) -> GasSupplyState:
    state['is_cleared'] = state['purity_check']
    return state

builder = StateGraph(GasSupplyState)
builder.add_node('validate_purity', validate_purity)
builder.add_node('safety_check', check_safety_compliance)
builder.set_entry_point('validate_purity')
builder.add_edge('validate_purity', 'safety_check')
builder.add_edge('safety_check', END)
graph = builder.compile()
