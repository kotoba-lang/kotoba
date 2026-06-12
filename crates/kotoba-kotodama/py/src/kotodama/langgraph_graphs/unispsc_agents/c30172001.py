from typing import TypedDict
from langgraph.graph import StateGraph, END

class GateState(TypedDict):
    material: str
    dimensions: dict
    is_compliant: bool

def validate_specs(state: GateState):
    # Business logic for gate structural validation
    width = state.get('dimensions', {}).get('width', 0)
    state['is_compliant'] = width > 0
    return state

workflow = StateGraph(GateState)
workflow.add_node('validate', validate_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
