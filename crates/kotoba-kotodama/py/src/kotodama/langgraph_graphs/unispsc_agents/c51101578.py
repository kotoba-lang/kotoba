from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PharmProcessState(TypedDict):
    process_id: str
    compliance_checks: List[str]
    is_validated: bool

def validate_process(state: PharmProcessState) -> PharmProcessState:
    state['is_validated'] = 'GMP' in state.get('compliance_checks', [])
    return state

def execute_monitoring(state: PharmProcessState) -> PharmProcessState:
    if state.get('is_validated'):
        state['compliance_checks'].append('Monitoring Active')
    return state

builder = StateGraph(PharmProcessState)
builder.add_node('validate', validate_process)
builder.add_node('monitor', execute_monitoring)
builder.add_edge('validate', 'monitor')
builder.add_edge('monitor', END)
builder.set_entry_point('validate')
graph = builder.compile()
