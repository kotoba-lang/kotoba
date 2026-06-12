from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    part_number: str
    material_certified: bool
    pressure_test_passed: bool
    is_compliant: bool

def validate_material(state: ProcurementState):
    state['material_certified'] = True
    return state

def run_pressure_inspection(state: ProcurementState):
    state['pressure_test_passed'] = True
    state['is_compliant'] = state['material_certified'] and state['pressure_test_passed']
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_material)
graph.add_node('inspect', run_pressure_inspection)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph = graph.compile()
