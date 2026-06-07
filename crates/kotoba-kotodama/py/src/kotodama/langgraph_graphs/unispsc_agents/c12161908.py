from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ReagentState(TypedDict):
    commodity_code: str
    purity_check: bool
    safety_clearance: bool
    storage_validated: bool
    messages: Annotated[list, add_messages]

def validate_purity(state: ReagentState) -> ReagentState:
    # Simulate purity verification logic
    state['purity_check'] = True
    return state

def check_safety_protocols(state: ReagentState) -> ReagentState:
    # Simulate MSDS and safety protocol validation
    state['safety_clearance'] = True
    return state

def validate_storage(state: ReagentState) -> ReagentState:
    # Validate specific storage requirements
    state['storage_validated'] = True
    return state

graph = StateGraph(ReagentState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('safety_check', check_safety_protocols)
graph.add_node('storage_check', validate_storage)

graph.add_edge('validate_purity', 'safety_check')
graph.add_edge('safety_check', 'storage_check')
graph.add_edge('storage_check', END)
graph.set_entry_point('validate_purity')

graph = graph.compile()
