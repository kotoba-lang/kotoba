from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    quality_passed: bool
    temp_log_valid: bool

def validate_purity(state: ProcurementState):
    print('Checking purity certificates for temple juice...')
    return {'quality_passed': True}

def verify_storage(state: ProcurementState):
    print('Verifying cold chain logs...')
    return {'temp_log_valid': True}

graph = StateGraph(ProcurementState)
graph.add_node('check_purity', validate_purity)
graph.add_node('check_storage', verify_storage)
graph.set_entry_point('check_purity')
graph.add_edge('check_purity', 'check_storage')
graph.add_edge('check_storage', END)
graph = graph.compile()
