from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ServoProcurementState(TypedDict):
    servo_id: str
    spec_requirements: dict
    validation_log: List[str]
    is_compliant: bool

def validate_specs(state: ServoProcurementState) -> ServoProcurementState:
    specs = state.get('spec_requirements', {})
    log = state.get('validation_log', [])
    if 'nominal_torque_nm' in specs and specs['nominal_torque_nm'] > 0:
        log.append('Torque specification validated.')
    else:
        log.append('Invalid torque specification.')
    return {'validation_log': log}

def check_compliance(state: ServoProcurementState) -> ServoProcurementState:
    log = state.get('validation_log', [])
    state['is_compliant'] = 'Invalid torque specification.' not in log
    return state

graph = StateGraph(ServoProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)

graph = graph.compile()
