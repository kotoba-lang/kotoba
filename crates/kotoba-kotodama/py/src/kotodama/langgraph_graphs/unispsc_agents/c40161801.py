from typing import TypedDict
from langgraph.graph import StateGraph, END

class FilterMediaState(TypedDict):
    mesh_spec: dict
    validation_passed: bool

def validate_material(state: FilterMediaState):
    mesh = state.get('mesh_spec', {})
    # Logic checks for industrial compliance
    is_valid = all(k in mesh for k in ['grade', 'mesh_count', 'thickness'])
    print(f'Validating material specifications: {is_valid}')
    return {'validation_passed': is_valid}

def route_by_validation(state: FilterMediaState):
    return 'process' if state['validation_passed'] else END

graph = StateGraph(FilterMediaState)
graph.add_node('validate', validate_material)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
