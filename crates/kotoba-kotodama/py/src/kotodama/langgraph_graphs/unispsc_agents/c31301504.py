from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    material_grade: str
    dimensions: dict
    inspection_passed: bool

def validate_materials(state: ForgingState):
    print(f'Validating material grade: {state.get('material_grade')}')
    return {'inspection_passed': True}

def check_dimensions(state: ForgingState):
    print('Verifying dimensional tolerances...')
    return {'inspection_passed': True}

graph = StateGraph(ForgingState)
graph.add_node('validate', validate_materials)
graph.add_node('measure', check_dimensions)
graph.set_entry_point('validate')
graph.add_edge('validate', 'measure')
graph.add_edge('measure', END)
graph = graph.compile()
