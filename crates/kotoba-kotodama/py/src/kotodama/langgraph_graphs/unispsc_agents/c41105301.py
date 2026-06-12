from typing import TypedDict
from langgraph.graph import StateGraph, END

class GelBoxState(TypedDict):
    specs: dict
    validation_passed: bool

def validate_materials(state: GelBoxState):
    # Business logic for material compliance check
    material = state.get('specs', {}).get('material', 'unknown')
    return {'validation_passed': material in ['polypropylene', 'polycarbonate']}

def route_by_validation(state: GelBoxState):
    return 'validate' if not state.get('validation_passed') else END

graph = StateGraph(GelBoxState)
graph.add_node('validate', validate_materials)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()
