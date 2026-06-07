from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    spec_data: dict
    is_compliant: bool
    validation_report: str

def validate_safety_specs(state: State):
    specs = state.get('spec_data', {})
    # Check for mandatory safety certifications
    required = ['ASTM_F963', 'non_toxic_seal']
    passed = all(k in specs for k in required)
    return {'is_compliant': passed, 'validation_report': 'Safety check completed.'}

graph_builder = StateGraph(State)
graph_builder.add_node('validate', validate_safety_specs)
graph_builder.add_edge('validate', END)
graph_builder.set_entry_point('validate')
graph = graph_builder.compile()
