from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    drug_name: str
    batch_id: str
    is_compliant: bool
    temperature_logs: list

def validate_gmp(state: PharmState):
    # Simulate GMP validation for Ritonavir
    state['is_compliant'] = True
    return state

def check_temp(state: PharmState):
    # Ensure cool storage maintenance
    return state

graph = StateGraph(PharmState)
graph.add_node('validate_gmp', validate_gmp)
graph.add_node('check_temp', check_temp)
graph.set_entry_point('validate_gmp')
graph.add_edge('validate_gmp', 'check_temp')
graph.add_edge('check_temp', END)

graph = graph.compile()
