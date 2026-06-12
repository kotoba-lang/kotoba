from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class ReagentState(TypedDict):
    commodity_id: str
    batch_integrity: bool
    validation_steps: Annotated[List[str], operator.add]
    is_cleared: bool

def validate_cold_chain(state: ReagentState) -> ReagentState:
    state['validation_steps'].append('Cold chain verification successful')
    state['batch_integrity'] = True
    return state

def run_compliance_check(state: ReagentState) -> ReagentState:
    state['validation_steps'].append('Clinical compliance check passed')
    state['is_cleared'] = True
    return state

graph = StateGraph(ReagentState)
graph.add_node('cold_chain', validate_cold_chain)
graph.add_node('compliance', run_compliance_check)
graph.set_entry_point('cold_chain')
graph.add_edge('cold_chain', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
