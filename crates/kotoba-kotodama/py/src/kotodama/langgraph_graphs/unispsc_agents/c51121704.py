from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DrugProcurementState(TypedDict):
    batch_id: str
    compliance_passed: bool
    gmp_certified: bool
    temp_log_verified: bool

def validate_gmp(state: DrugProcurementState):
    return {'gmp_certified': True}

def verify_temperature(state: DrugProcurementState):
    return {'temp_log_verified': True}

def finalize_procurement(state: DrugProcurementState):
    state['compliance_passed'] = state['gmp_certified'] and state['temp_log_verified']
    return state

graph = StateGraph(DrugProcurementState)
graph.add_node('gmp_check', validate_gmp)
graph.add_node('temp_check', verify_temperature)
graph.add_node('finalizer', finalize_procurement)
graph.add_edge('gmp_check', 'temp_check')
graph.add_edge('temp_check', 'finalizer')
graph.add_edge('finalizer', END)
graph.set_entry_point('gmp_check')
graph = graph.compile()
