from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MineralState(TypedDict):
    purity_level: float
    inspection_status: bool
    compliance_tags: List[str]

def validate_ore_purity(state: MineralState) -> MineralState:
    state['inspection_status'] = state.get('purity_level', 0) > 0.95
    return state

def finalize_procurement(state: MineralState) -> MineralState:
    if state.get('inspection_status'):
        state['compliance_tags'].append('APPROVED_FOR_EXTRACTION')
    return state

builder = StateGraph(MineralState)
builder.add_node('validate', validate_ore_purity)
builder.add_node('finalize', finalize_procurement)
builder.set_entry_point('validate')
builder.add_edge('validate', 'finalize')
builder.add_edge('finalize', END)
graph = builder.compile()
