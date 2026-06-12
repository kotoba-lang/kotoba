from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PharmaState(TypedDict):
    batch_id: str
    purity_cert: bool
    temp_log_valid: bool
    compliance_flag: bool

def validate_purity(state: PharmaState) -> PharmaState:
    state['purity_cert'] = True
    return state

def validate_cold_chain(state: PharmaState) -> PharmaState:
    state['temp_log_valid'] = True
    return state

def check_compliance(state: PharmaState) -> PharmaState:
    state['compliance_flag'] = state['purity_cert'] and state['temp_log_valid']
    return state

graph = StateGraph(PharmaState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('validate_cold_chain', validate_cold_chain)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate_purity', 'validate_cold_chain')
graph.add_edge('validate_cold_chain', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate_purity')

graph = graph.compile()
