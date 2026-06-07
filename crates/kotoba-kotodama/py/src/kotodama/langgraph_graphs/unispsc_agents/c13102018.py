from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class CarbonFiberState(TypedDict):
    material_id: str
    spec_params: dict
    validation_passed: bool
    error_log: list

def validate_material(state: CarbonFiberState) -> dict:
    params = state.get('spec_params', {})
    # Simulated validation logic for high-strength carbon fiber
    if params.get('tensile_strength_mpa', 0) < 3000:
        return {'validation_passed': False, 'error_log': ['Tensile strength insufficient']}
    return {'validation_passed': True}

def route_by_validation(state: CarbonFiberState) -> str:
    return 'check' if state['validation_passed'] else 'END'

graph = StateGraph(CarbonFiberState)
graph.add_node('validate', validate_material)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

# Compile the graph
graph = graph.compile()
