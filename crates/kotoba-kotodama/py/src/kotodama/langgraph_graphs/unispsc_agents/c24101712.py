from typing import TypedDict
from langgraph.graph import StateGraph, END

class ConveyorState(TypedDict):
    specs: dict
    validation_results: list
    is_approved: bool

def validate_specs(state: ConveyorState):
    specs = state.get('specs', {})
    results = []
    if specs.get('load_capacity_kg', 0) <= 0:
        results.append('Invalid load capacity')
    return {'validation_results': results, 'is_approved': len(results) == 0}

graph = StateGraph(ConveyorState)
graph.add_node('validator', validate_specs)
graph.set_entry_point('validator')
graph.add_edge('validator', END)
graph = graph.compile()
