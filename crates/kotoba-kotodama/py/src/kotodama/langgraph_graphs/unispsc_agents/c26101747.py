from typing import TypedDict
from langgraph.graph import StateGraph, END

class PushRodState(TypedDict):
    specs: dict
    validation_passed: bool
    error_log: list

def validate_materials(state: PushRodState):
    material = state.get('specs', {}).get('material', 'unknown')
    valid = material in ['steel', 'titanium', 'aluminum-alloy']
    return {'validation_passed': valid, 'error_log': [] if valid else ['Invalid material detected']}

def check_tolerances(state: PushRodState):
    tol = state.get('specs', {}).get('tolerance', 0.0)
    passed = tol <= 0.005 and state['validation_passed']
    return {'validation_passed': passed}

graph = StateGraph(PushRodState)
graph.add_node('material_check', validate_materials)
graph.add_node('tolerance_check', check_tolerances)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'tolerance_check')
graph.add_edge('tolerance_check', END)
graph = graph.compile()
