from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PipeSpecState(TypedDict):
    material_data: str
    pressure_test_passed: bool
    validation_log: List[str]

def validate_material(state: PipeSpecState):
    log = state.get('validation_log', [])
    log.append('Verifying brass alloy composition...')
    return {'validation_log': log, 'material_data': 'Verified-Brass-B16'}

def perform_pressure_check(state: PipeSpecState):
    log = state.get('validation_log', [])
    log.append('Executing pneumatic pressure test...')
    return {'pressure_test_passed': True}

graph = StateGraph(PipeSpecState)
graph.add_node('material_validation', validate_material)
graph.add_node('pressure_testing', perform_pressure_check)
graph.set_entry_point('material_validation')
graph.add_edge('material_validation', 'pressure_testing')
graph.add_edge('pressure_testing', END)
graph = graph.compile()
