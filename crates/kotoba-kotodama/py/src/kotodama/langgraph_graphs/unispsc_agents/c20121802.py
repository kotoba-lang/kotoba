from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MotorProcurementState(TypedDict):
    spec_requirements: dict
    validation_results: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_motor_specs(state: MotorProcurementState):
    specs = state.get('spec_requirements', {})
    checks = []
    if specs.get('rated_torque_nm', 0) > 0:
        checks.append('Torque specification verified')
    else:
        checks.append('Critical error: Missing torque specification')
    return {'validation_results': checks}

def compliance_gate(state: MotorProcurementState):
    return 'compliant' if 'Critical error' not in str(state['validation_results']) else 'non_compliant'

graph = StateGraph(MotorProcurementState)
graph.add_node('validate', validate_motor_specs)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', compliance_gate, {'compliant': END, 'non_compliant': END})
graph = graph.compile()
