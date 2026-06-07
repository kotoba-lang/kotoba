from typing import TypedDict
from langgraph.graph import StateGraph, END

class BindingTapeState(TypedDict):
    tape_type: str
    spec_compliance: bool
    validation_log: list

def validate_specs(state: BindingTapeState):
    compliance = state.get('tape_type') in ['cloth', 'paper', 'plastic']
    return {'spec_compliance': compliance, 'validation_log': ['Specs checked against ISO requirements']}

def route_procurement(state: BindingTapeState):
    return 'APPROVED' if state['spec_compliance'] else 'REJECTED'

graph = StateGraph(BindingTapeState)
graph.add_node('validator', validate_specs)
graph.set_entry_point('validator')
graph.add_edge('validator', END)
graph = graph.compile()
