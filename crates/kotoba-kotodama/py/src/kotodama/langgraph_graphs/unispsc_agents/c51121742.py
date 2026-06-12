from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_name: str
    gmp_verified: bool
    temp_range_valid: bool

def validate_gmp(state: ProcurementState):
    print('Validating GMP status...')
    return {'gmp_verified': True}

def validate_storage(state: ProcurementState):
    print('Checking storage temperature logs...')
    return {'temp_range_valid': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate_gmp', validate_gmp)
graph.add_node('validate_storage', validate_storage)
graph.set_entry_point('validate_gmp')
graph.add_edge('validate_gmp', 'validate_storage')
graph.add_edge('validate_storage', END)

graph = graph.compile()
