from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class WasherState(TypedDict):
    material: str
    dimensions: dict
    approved: bool

def validate_specs(state: WasherState):
    # Business logic for technical specification check
    is_valid = bool(state.get('material') and state.get('dimensions'))
    return {'approved': is_valid}

def final_approval(state: WasherState):
    return {'approved': True}

graph = StateGraph(WasherState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', final_approval)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
