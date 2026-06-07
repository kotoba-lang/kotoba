from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    purity_check: bool
    safety_clearance: bool
    processing_steps: Annotated[Sequence[str], operator.add]

def validate_purity(state: CatalystState) -> CatalystState:
    # Simulate chemical purity validation logic
    return {'purity_check': True, 'processing_steps': ['Purity validated']}

def check_safety(state: CatalystState) -> CatalystState:
    # Simulate dangerous goods and dual-use screening
    return {'safety_clearance': True, 'processing_steps': ['Safety screening cleared']}

def finalize_process(state: CatalystState) -> CatalystState:
    return {'processing_steps': ['Processing complete']}

graph = StateGraph(CatalystState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_safety', check_safety)
graph.add_node('finalize', finalize_process)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'check_safety')
graph.add_edge('check_safety', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
