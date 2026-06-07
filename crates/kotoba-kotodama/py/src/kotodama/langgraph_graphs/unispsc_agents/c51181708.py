from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    batch_id: str
    quality_passed: bool
    temp_log_valid: bool

def validate_gmp(state: PharmState):
    print(f'Validating GMP for batch {state[batch_id]}')
    return {'quality_passed': True}

def verify_storage(state: PharmState):
    print('Checking temperature logs...')
    return {'temp_log_valid': True}

graph = StateGraph(PharmState)
graph.add_node('validate_gmp', validate_gmp)
graph.add_node('verify_storage', verify_storage)
graph.set_entry_point('validate_gmp')
graph.add_edge('validate_gmp', 'verify_storage')
graph.add_edge('verify_storage', END)
graph = graph.compile()
