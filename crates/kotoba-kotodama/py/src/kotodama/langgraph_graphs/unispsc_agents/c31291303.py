from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    part_specs: dict
    validation_passed: bool
    compliance_status: str

def validate_machined_parts(state: ProcurementState):
    specs = state.get('part_specs', {})
    # Check for critical dimensional tolerances
    if specs.get('tolerance', 0) <= 0.05:
        return {'validation_passed': True}
    return {'validation_passed': False}

def check_compliance(state: ProcurementState):
    # Verify metallurgy and environmental standards
    compliance = state.get('compliance_status', 'pending')
    return {'compliance_status': 'verified' if compliance == 'checked' else 'failed'}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_machined_parts)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
