from typing import TypedDict
from langgraph.graph import StateGraph, END

class WoundSolutionState(TypedDict):
    product_name: str
    is_sterile: bool
    regulatory_approved: bool
    passed_qc: bool

def validate_sterility(state: WoundSolutionState) -> dict:
    return {'passed_qc': state.get('is_sterile') and state.get('regulatory_approved')}

graph = StateGraph(WoundSolutionState)
graph.add_node('validate', validate_sterility)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
