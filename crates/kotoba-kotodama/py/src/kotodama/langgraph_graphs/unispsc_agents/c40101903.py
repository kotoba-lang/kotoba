from typing import TypedDict
from langgraph.graph import StateGraph, END

class HumidityProcurementState(TypedDict):
    capacity_check: bool
    safety_compliance: bool
    vendor_approved: bool

def validate_specs(state: HumidityProcurementState):
    state['capacity_check'] = True
    return state

def check_compliance(state: HumidityProcurementState):
    state['safety_compliance'] = True
    return state

graph = StateGraph(HumidityProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
