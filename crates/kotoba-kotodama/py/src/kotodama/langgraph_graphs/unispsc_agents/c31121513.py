from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastingState(TypedDict):
    spec_data: dict
    validation_results: list

def validate_dimensions(state: CastingState):
    print('Validating CNC precision for zinc shell mold...')
    return {'validation_results': ['dim_check_passed']}

def inspect_surface(state: CastingState):
    print('Checking surface finish and porosity...')
    return {'validation_results': ['surf_check_passed']}

graph = StateGraph(CastingState)
graph.add_node('validate', validate_dimensions)
graph.add_node('inspect', inspect_surface)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph = graph.compile()
