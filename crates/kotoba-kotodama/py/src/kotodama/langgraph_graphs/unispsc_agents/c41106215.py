from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    reagent_id: str
    purity_check: bool
    temp_validation: bool
    approved: bool

def validate_purity(state: ReagentState):
    # logic for verifying technical spec compliance
    return {'purity_check': True}

def validate_cold_chain(state: ReagentState):
    # logic for storage requirement verification
    return {'temp_validation': True}

graph = StateGraph(ReagentState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('cold_chain', validate_cold_chain)
graph.add_edge('validate_purity', 'cold_chain')
graph.add_edge('cold_chain', END)
graph.set_entry_point('validate_purity')
graph = graph.compile()
