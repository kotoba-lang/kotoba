from typing import TypedDict
from langgraph.graph import StateGraph, END

class BedProcurementState(TypedDict):
    spec_compliance: bool
    safety_check: bool
    logistics_confirmed: bool

def validate_specs(state: BedProcurementState):
    state['spec_compliance'] = True
    return state

def check_safety(state: BedProcurementState):
    state['safety_check'] = True
    return state

def confirm_delivery(state: BedProcurementState):
    state['logistics_confirmed'] = True
    return state

graph = StateGraph(BedProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', check_safety)
graph.add_node('logistics', confirm_delivery)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', 'logistics')
graph.add_edge('logistics', END)
graph = graph.compile()
