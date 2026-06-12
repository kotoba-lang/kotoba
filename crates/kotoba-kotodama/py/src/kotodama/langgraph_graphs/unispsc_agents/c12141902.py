from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    material_id: str
    purity_validated: bool
    safety_cleared: bool
    log: Annotated[Sequence[str], operator.add]

def validate_catalyst(state: CatalystState) -> CatalystState:
    # Logic for purity verification
    return {**state, 'purity_validated': True, 'log': ['Purity check passed']}

def safety_compliance(state: CatalystState) -> CatalystState:
    # Logic for dual-use/safety check
    return {**state, 'safety_cleared': True, 'log': ['Safety clearance approved']}

graph = StateGraph(CatalystState)
graph.add_node('validate', validate_catalyst)
graph.add_node('safety', safety_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
