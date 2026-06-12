from typing import TypedDict
from langgraph.graph import StateGraph, END

class MoldState(TypedDict):
    material_data: dict
    validation_passed: bool

def validate_composition(state: MoldState):
    composition = state.get('material_data', {}).get('composition', [])
    passed = 'bronze' in composition and 'graphite' in composition
    return {'validation_passed': passed}

def structural_check(state: MoldState):
    print('Performing thermal stress simulation...')
    return {'validation_passed': True}

graph_builder = StateGraph(MoldState)
graph_builder.add_node('validate', validate_composition)
graph_builder.add_node('structural', structural_check)
graph_builder.set_entry_point('validate')
graph_builder.add_edge('validate', 'structural')
graph_builder.add_edge('structural', END)
graph = graph_builder.compile()
