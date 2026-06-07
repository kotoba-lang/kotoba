from typing import TypedDict
from langgraph.graph import StateGraph, END
class PoleState(TypedDict):
    spec_data: dict
    validation_passed: bool
def validate_pole_specs(state: PoleState):
    specs = state.get('spec_data', {})
    required = ['max_length', 'material', 'locking_type']
    passed = all(k in specs for k in required) and specs.get('max_length', 0) > 0
    return {'validation_passed': passed}
def finalize_procurement(state: PoleState):
    return {'validation_passed': state['validation_passed']}
graph = StateGraph(PoleState)
graph.add_node('validate', validate_pole_specs)
graph.add_node('finalize', finalize_procurement)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
