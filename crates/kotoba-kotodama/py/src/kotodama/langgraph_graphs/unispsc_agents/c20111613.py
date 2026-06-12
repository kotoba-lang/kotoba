from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MotorProcurementState(TypedDict):
    motor_specs: dict
    validation_logs: List[str]
    is_compliant: bool

def validate_specs(state: MotorProcurementState) -> MotorProcurementState:
    specs = state.get('motor_specs', {})
    logs = state.get('validation_logs', [])

    # Validate torque and IP rating against industrial standards
    if specs.get('holding_torque_nm', 0) < 0.5:
        logs.append('Insufficient torque for industrial application.')
    if specs.get('ip_rating', 0) < 65:
        logs.append('IP rating below required industrial standard.')

    return {'validation_logs': logs, 'is_compliant': len(logs) == 0}

def compile_procurement_workflow():
    graph = StateGraph(MotorProcurementState)
    graph.add_node('validate', validate_specs)
    graph.set_entry_point('validate')
    graph.add_edge('validate', END)
    return graph.compile()

graph = compile_procurement_workflow()
