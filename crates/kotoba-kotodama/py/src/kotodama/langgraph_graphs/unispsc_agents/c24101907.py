from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SpillContainmentState(TypedDict):
    material: str
    capacity_liters: float
    compliance_codes: List[str]
    validation_passed: bool

def validate_specs(state: SpillContainmentState):
    # Business logic for spill containment specs
    capacity = state.get('capacity_liters', 0)
    passed = capacity > 0 and 'EPA' in state.get('compliance_codes', [])
    return {'validation_passed': passed}

graph = StateGraph(SpillContainmentState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
