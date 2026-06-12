from typing import TypedDict
from langgraph.graph import StateGraph, END

class SimulatorState(TypedDict):
    model_number: str
    validation_passed: bool
    compliance_docs: list

def validate_specs(state: SimulatorState):
    # Simulate CAD/Spec validation logic
    state['validation_passed'] = 'ISO-13485' in state.get('compliance_docs', [])
    return state

builder = StateGraph(SimulatorState)
builder.add_node('validate', validate_specs)
builder.set_entry_point('validate')
builder.add_edge('validate', END)
graph = builder.compile()
