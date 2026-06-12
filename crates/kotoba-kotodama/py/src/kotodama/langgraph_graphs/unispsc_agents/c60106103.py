from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_id: str
    compliance_checked: bool
    specs_verified: bool

def validate_specs(state: ProcurementState):
    print('Validating drafting material specifications...')
    return {**state, 'specs_verified': True}

def check_compliance(state: ProcurementState):
    print('Checking standard safety compliance...')
    return {**state, 'compliance_checked': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
