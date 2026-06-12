from typing import TypedDict
from langgraph.graph import StateGraph, END

class BlisterPackState(TypedDict):
    material_specs: dict
    compliance_validated: bool
    inspection_passed: bool

def validate_materials(state: BlisterPackState):
    # Simulate material compliance check for blister pack film/foil
    print('Validating barrier properties...')
    state['compliance_validated'] = True
    return state

def run_quality_inspection(state: BlisterPackState):
    # Simulate seal integrity inspection
    print('Performing seal integrity test...')
    state['inspection_passed'] = True
    return state

graph = StateGraph(BlisterPackState)
graph.add_node('validate', validate_materials)
graph.add_node('inspect', run_quality_inspection)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph = graph.compile()
