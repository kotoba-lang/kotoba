from typing import TypedDict
from langgraph.graph import StateGraph, END
class LeadProcureState(TypedDict):
    purity_check: bool
    safety_clearance: bool
    dimensions: dict
def validate_material(state: LeadProcureState):
    state['purity_check'] = True if state.get('purity', 0) >= 99.9 else False
    return state
def check_compliance(state: LeadProcureState):
    state['safety_clearance'] = True
    return state
graph = StateGraph(LeadProcureState)
graph.add_node('validate', validate_material)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
