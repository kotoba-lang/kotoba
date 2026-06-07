from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    commodity_code: str
    purity: float
    safety_check: bool
    approved: bool

def validate_reagent(state: ReagentState):
    # Simulated validation logic for antibody reagent
    is_safe = state.get('purity', 0) >= 99.0
    return {'safety_check': is_safe, 'approved': is_safe}

graph = StateGraph(ReagentState)
graph.add_node('validate', validate_reagent)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()
