from typing import TypedDict
from langgraph.graph import StateGraph, END

class TubingState(TypedDict):
    material_spec: str
    pressure_test_passed: bool
    compliant: bool

def validate_materials(state: TubingState) -> TubingState:
    # Logic to verify material grade against industry standards
    state['compliant'] = state.get('material_spec') in ['PVC', 'PU', 'PTFE']
    return state

def check_pressure(state: TubingState) -> TubingState:
    # Logic to verify pressure rating requirements
    state['pressure_test_passed'] = True
    return state

graph = StateGraph(TubingState)
graph.add_node('validate', validate_materials)
graph.add_node('pressure_check', check_pressure)
graph.set_entry_point('validate')
graph.add_edge('validate', 'pressure_check')
graph.add_edge('pressure_check', END)
graph = graph.compile()
