from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_spec: dict
    is_compliant: bool
    validation_log: list

def validate_safety_standards(state: ProcurementState):
    spec = state.get('item_spec', {})
    compliant = spec.get('iso_cert', False) and spec.get('blade_safety', False)
    return {'is_compliant': compliant, 'validation_log': ['Safety standards checked']}

def route_procurement(state: ProcurementState):
    return 'process' if state['is_compliant'] else 'reject'

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_safety_standards)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
