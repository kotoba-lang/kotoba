from typing import TypedDict
from langgraph.graph import StateGraph, END

class CueState(TypedDict):
    spec_data: dict
    validation_passed: bool
    message: str

def validate_specs(state: CueState):
    specs = state.get('spec_data', {})
    required = ['weight', 'length', 'tip_material']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed, 'message': 'Validation successful' if passed else 'Missing specs'}

def finalize_order(state: CueState):
    return {'message': 'Order ready for procurement queue'}

graph = StateGraph(CueState)
graph.add_node('validate', validate_specs)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
