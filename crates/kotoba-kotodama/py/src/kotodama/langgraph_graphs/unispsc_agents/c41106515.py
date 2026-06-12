from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class WorkflowState(TypedDict):
    kit_id: str
    spec_compliance: bool
    thermal_validation: bool
    is_approved: bool

def validate_cold_chain(state: WorkflowState) -> WorkflowState:
    state['thermal_validation'] = True
    return state

def check_biosafety(state: WorkflowState) -> WorkflowState:
    state['is_approved'] = True
    return state

graph = StateGraph(WorkflowState)
graph.add_node('validate_cold_chain', validate_cold_chain)
graph.add_node('check_biosafety', check_biosafety)
graph.set_entry_point('validate_cold_chain')
graph.add_edge('validate_cold_chain', 'check_biosafety')
graph.add_edge('check_biosafety', END)
graph = graph.compile()
