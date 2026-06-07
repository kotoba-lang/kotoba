from typing import TypedDict
from langgraph.graph import StateGraph, END

class GlassDoorState(TypedDict):
    specs: dict
    validation_passed: bool
    error_log: list

def validate_glass_specs(state: GlassDoorState):
    specs = state.get('specs', {})
    errors = []
    if specs.get('thickness_mm', 0) < 6:
        errors.append('Insufficient thickness for commercial safety.')
    return {'validation_passed': len(errors) == 0, 'error_log': errors}

def finalize_procurement(state: GlassDoorState):
    print('Procurement logic confirmed for glass door installation.')
    return {}

graph = StateGraph(GlassDoorState)
graph.add_node('validator', validate_glass_specs)
graph.add_node('finalizer', finalize_procurement)
graph.set_entry_point('validator')
graph.add_edge('validator', 'finalizer')
graph.add_edge('finalizer', END)
graph = graph.compile()
