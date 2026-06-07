from typing import TypedDict
from langgraph.graph import StateGraph, END

class ChainProcurementState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_report: str

def validate_chain_specs(state: ChainProcurementState):
    specs = state.get('spec_data', {})
    passed = 'tensile_strength' in specs and 'pitch_size' in specs
    return {'validation_passed': passed, 'compliance_report': 'Passed' if passed else 'Failed'}

def finalize_order(state: ChainProcurementState):
    return {'compliance_report': 'Order ready for procurement portal'}

graph = StateGraph(ChainProcurementState)
graph.add_node('validate', validate_chain_specs)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
