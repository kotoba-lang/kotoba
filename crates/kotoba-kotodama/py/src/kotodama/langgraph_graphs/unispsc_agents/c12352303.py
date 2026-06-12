from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ComponentState(TypedDict):
    material_data: dict
    validation_results: List[str]
    is_compliant: bool

def validate_material(state: ComponentState):
    # Simulate material compliance check
    m = state.get('material_data', {})
    results = []
    if m.get('purity', 0) > 0.99:
        results.append('Purity check passed')
    else:
        results.append('Purity check failed')
    return {'validation_results': results}

def perform_geometry_check(state: ComponentState):
    # Simulate high-precision dimensional validation
    return {'is_compliant': 'Purity check passed' in state['validation_results']}

graph = StateGraph(ComponentState)
graph.add_node('material', validate_material)
graph.add_node('geometry', perform_geometry_check)
graph.add_edge('material', 'geometry')
graph.add_edge('geometry', END)
graph.set_entry_point('material')
graph = graph.compile()
