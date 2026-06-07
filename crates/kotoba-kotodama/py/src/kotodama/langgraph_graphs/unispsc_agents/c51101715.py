from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    batch_id: str
    compliance_passed: bool
    safety_check: bool

def validate_batch(state: ProcurementState):
    print(f'Validating batch {state[batch_id]} for permethrin compliance.')
    return {'compliance_passed': True}

def check_hazard_protocols(state: ProcurementState):
    print('Verifying controlled substance storage protocols.')
    return {'safety_check': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_batch)
graph.add_node('safety', check_hazard_protocols)

graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
