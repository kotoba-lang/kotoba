from typing import TypedDict
from langgraph.graph import StateGraph, END

class LabelProcurementState(TypedDict):
    material: str
    dimensions: str
    adhesion_rating: str
    is_validated: bool

def validate_specs(state: LabelProcurementState):
    state['is_validated'] = all([state.get('material'), state.get('dimensions')])
    return state

graph = StateGraph(LabelProcurementState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
