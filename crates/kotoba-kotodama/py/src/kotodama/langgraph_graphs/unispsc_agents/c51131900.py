from typing import TypedDict
from langgraph.graph import StateGraph, END

class PlasmaState(TypedDict):
    batch_id: str
    is_sterile: bool
    temp_log_valid: bool
    regulatory_approved: bool

def validate_batch(state: PlasmaState):
    state['is_sterile'] = True
    return state

def check_compliance(state: PlasmaState):
    state['regulatory_approved'] = True
    return state

graph = StateGraph(PlasmaState)
graph.add_node('validate', validate_batch)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
