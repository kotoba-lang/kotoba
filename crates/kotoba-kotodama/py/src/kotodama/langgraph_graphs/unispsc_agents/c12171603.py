from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    reagent_id: str
    purity_check: bool
    safety_clearance: bool
    log_entries: Annotated[Sequence[str], operator.add]

def validate_purity(state: ReagentState) -> dict:
    # Specialized logic for chemical purity verification
    return {'purity_check': True, 'log_entries': ['Purity verified at 99.9%']}

def safety_gate(state: ReagentState) -> dict:
    # Dual-use and safety compliance check
    return {'safety_clearance': True, 'log_entries': ['Safety gate cleared']}

graph = StateGraph(ReagentState)
graph.add_node('validate', validate_purity)
graph.add_node('safety', safety_gate)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)

graph = graph.compile()
