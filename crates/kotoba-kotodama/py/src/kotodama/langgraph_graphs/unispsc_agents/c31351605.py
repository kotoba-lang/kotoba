from typing import TypedDict
from langgraph.graph import StateGraph, END

class TubeState(TypedDict):
    spec_verified: bool
    pressure_test_passed: bool
    export_flagged: bool

def validate_materials(state: TubeState):
    print('Validating low alloy composition standards...')
    state['spec_verified'] = True
    return state

def perform_leak_test(state: TubeState):
    print('Conducting solvent weld integrity pressure test...')
    state['pressure_test_passed'] = True
    return state

def check_compliance(state: TubeState):
    if state['spec_verified'] and state['pressure_test_passed']:
        state['export_flagged'] = False
    return state

graph = StateGraph(TubeState)
graph.add_node('material_check', validate_materials)
graph.add_node('leak_test', perform_leak_test)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'leak_test')
graph.add_edge('leak_test', 'compliance')
graph.add_edge('compliance', END)
graph.add_edge('compliance', END)

graph = graph.compile()
