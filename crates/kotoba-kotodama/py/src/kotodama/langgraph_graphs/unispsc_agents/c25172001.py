from typing import TypedDict
from langgraph.graph import StateGraph, END

class SuspensionState(TypedDict):
    part_number: str
    spec_sheet_url: str
    validated: bool
    compliance_score: float

def validate_specs(state: SuspensionState):
    # Simulate CAD/Spec validation logic
    state['validated'] = True
    state['compliance_score'] = 0.95
    return state

def check_durability(state: SuspensionState):
    # Business logic for mechanical stress analysis
    return {'compliance_score': state['compliance_score'] + 0.04}

graph = StateGraph(SuspensionState)
graph.add_node('validate', validate_specs)
graph.add_node('durability', check_durability)
graph.add_edge('validate', 'durability')
graph.add_edge('durability', END)
graph.set_entry_point('validate')
graph = graph.compile()
