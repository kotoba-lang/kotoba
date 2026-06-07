from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    part_type: str
    spec_compliance: bool
    leak_test_passed: bool
    final_status: str

def validate_materials(state: AssemblyState):
    # Simulate copper grade validation logic
    state['spec_compliance'] = True
    return state

def check_welding(state: AssemblyState):
    # Simulate pressure/leak test logic
    state['leak_test_passed'] = True
    state['final_status'] = 'APPROVED' if state['spec_compliance'] and state['leak_test_passed'] else 'REJECTED'
    return state

graph = StateGraph(AssemblyState)
graph.add_node('validate_materials', validate_materials)
graph.add_node('check_welding', check_welding)
graph.set_entry_point('validate_materials')
graph.add_edge('validate_materials', 'check_welding')
graph.add_edge('check_welding', END)
graph = graph.compile()
