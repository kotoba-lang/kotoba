from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    purity_check: bool
    safety_clearance: bool
    history: Annotated[Sequence[str], operator.add]

def validate_purity(state: ReagentState):
    # Simulate high-precision CAD or spectrometry validation logic
    return {'purity_check': True, 'history': ['Validated purity via spectrometry']}

def perform_safety_check(state: ReagentState):
    # Simulate regulatory/dangerous goods protocol
    return {'safety_clearance': True, 'history': ['Cleared hazardous materials protocol']}

graph = StateGraph(ReagentState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('safety_check', perform_safety_check)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'safety_check')
graph.add_edge('safety_check', END)
graph = graph.compile()
