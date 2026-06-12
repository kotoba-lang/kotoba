from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class BoltProcurementState(TypedDict):
    bolt_specs: dict
    validation_passed: bool
    log: List[str]

def validate_bolt_spec(state: BoltProcurementState):
    specs = state.get('bolt_specs', {})
    passed = all(k in specs for k in ['material_grade', 'tensile_strength'])
    return {'validation_passed': passed, 'log': ['Spec validation complete']}

def check_compliance(state: BoltProcurementState):
    if state.get('validation_passed'):
        return 'approve'
    return 'reject'

graph = StateGraph(BoltProcurementState)
graph.add_node('validate', validate_bolt_spec)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
