from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalSupplyState(TypedDict):
    item_name: str
    is_sterile: bool
    validation_passed: bool

def validate_specs(state: DentalSupplyState):
    state['validation_passed'] = state.get('is_sterile', False)
    return state

graph = StateGraph(DentalSupplyState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
