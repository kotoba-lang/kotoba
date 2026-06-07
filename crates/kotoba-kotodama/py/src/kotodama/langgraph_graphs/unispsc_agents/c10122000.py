from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END

class MineralFuelState(TypedDict):
    material_id: str
    purity: float
    safety_compliance: bool
    logistics_approved: bool

def validate_purity(state: MineralFuelState) -> MineralFuelState:
    state['purity'] = min(max(state.get('purity', 0.0), 0.0), 100.0)
    state['safety_compliance'] = state['purity'] > 95.0
    return state

def check_logistics(state: MineralFuelState) -> MineralFuelState:
    state['logistics_approved'] = state['safety_compliance']
    return state

graph = StateGraph(MineralFuelState)
graph.add_node('validate', validate_purity)
graph.add_node('logistics', check_logistics)
graph.add_edge('validate', 'logistics')
graph.add_edge('logistics', END)
graph.set_entry_point('validate')
graph = graph.compile()
