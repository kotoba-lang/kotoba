from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class ExteriorTrimState(TypedDict):
    material_type: str
    spec_compliance: bool
    weather_rating: str

def validate_material(state: ExteriorTrimState):
    # Business logic for validating material specs against local building codes
    if state.get('material_type') in ['PVC', 'Composite', 'Metal']:
        return {'spec_compliance': True}
    return {'spec_compliance': False}

def prepare_installation(state: ExteriorTrimState):
    print(f'Generating installation guide for {state.get('material_type')}')
    return state

graph = StateGraph(ExteriorTrimState)
graph.add_node('validate', validate_material)
graph.add_node('install', prepare_installation)
graph.add_edge('validate', 'install')
graph.add_edge('install', END)
graph.set_entry_point('validate')
graph = graph.compile()
