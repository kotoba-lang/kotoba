from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ServoState(TypedDict):
    part_number: str
    spec_requirements: dict
    validation_logs: List[str]
    is_compliant: bool

def validate_specs(state: ServoState):
    # Simulate spec validation logic
    specs = state.get('spec_requirements', {})
    if specs.get('torque_nm', 0) > 0:
        return {'validation_logs': ['Torque validated'], 'is_compliant': True}
    return {'validation_logs': ['Invalid torque'], 'is_compliant': False}

def compliance_check(state: ServoState):
    if state.get('is_compliant'):
        return 'approved'
    return 'flagged'

graph = StateGraph(ServoState)
graph.add_node('validate', validate_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')

graph = graph.compile()
