from typing import TypedDict
from langgraph.graph import StateGraph, END

class DishwasherState(TypedDict):
    model_number: str
    spec_verified: bool
    compliance_report: str

def validate_specs(state: DishwasherState):
    # Simulate CAD/Spec validation logic
    state['spec_verified'] = True if state.get('model_number') else False
    return state

def generate_report(state: DishwasherState):
    state['compliance_report'] = 'Validated' if state['spec_verified'] else 'Failed'
    return state

graph = StateGraph(DishwasherState)
graph.add_node('validate', validate_specs)
graph.add_node('report', generate_report)
graph.set_entry_point('validate')
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph = graph.compile()
