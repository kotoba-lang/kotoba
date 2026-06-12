from langgraph.graph import StateGraph, END
from typing import TypedDict

class BagProcurementState(TypedDict):
    spec_compliance: bool
    validation_passed: bool

def validate_specs(state: BagProcurementState):
    print('Validating laptop bag dimensions and material durability...')
    return {'validation_passed': True}

def check_compliance(state: BagProcurementState):
    print('Checking procurement and regulatory compliance...')
    return {'spec_compliance': True}

graph = StateGraph(BagProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
