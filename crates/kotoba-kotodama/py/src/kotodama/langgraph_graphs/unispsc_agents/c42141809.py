from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    lead_set_type: str
    compliance_docs: bool
    is_approved: bool

def validate_medical_specs(state: State) -> State:
    state['is_approved'] = state.get('compliance_docs', False)
    return state

def process_procurement(state: State) -> State:
    print(f'Processing procurement for: {state.get("lead_set_type")}')
    return state

graph = StateGraph(State)
graph.add_node('validation', validate_medical_specs)
graph.add_node('procurement', process_procurement)
graph.add_edge('validation', 'procurement')
graph.add_edge('procurement', END)
graph.set_entry_point('validation')
graph = graph.compile()
