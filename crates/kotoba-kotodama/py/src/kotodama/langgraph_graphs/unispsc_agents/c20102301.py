from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    component_id: str
    specs: dict
    validation_passed: bool
    log: List[str]

def validate_specs(state: ProcurementState):
    specs = state.get('specs', {})
    required = ['material_certification', 'dimensional_tolerance_report']
    passed = all(field in specs for field in required)
    return {'validation_passed': passed, 'log': ['Specs validated: ' + str(passed)]}

def route_procurement(state: ProcurementState):
    if state['validation_passed']:
        return 'approve'
    return 'flag_for_review'

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_procurement, {'approve': END, 'flag_for_review': END})
graph = graph.compile()
