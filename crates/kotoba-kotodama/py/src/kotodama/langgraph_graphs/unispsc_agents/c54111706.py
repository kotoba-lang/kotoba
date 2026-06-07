from typing import TypedDict
from langgraph.graph import StateGraph, END

class DisplaySpecState(TypedDict):
    material: str
    dimensions: dict
    is_validated: bool

def validate_material(state: DisplaySpecState):
    # Simulate material validation for display units
    if state.get('material') in ['acrylic', 'wood', 'leather', 'metal']:
        return {'is_validated': True}
    return {'is_validated': False}

def finalize_design(state: DisplaySpecState):
    print(f'Finalizing design for material: {state.get("material")}')
    return {'is_validated': True}

graph = StateGraph(DisplaySpecState)
graph.add_node('validation', validate_material)
graph.add_node('finalization', finalize_design)
graph.add_edge('validation', 'finalization')
graph.add_edge('finalization', END)
graph.set_entry_point('validation')
graph = graph.compile()
