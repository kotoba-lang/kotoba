from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class LockerState(TypedDict):
    material: str
    lock_type: str
    dims: List[float]
    status: str

def validate_specs(state: LockerState):
    if not state.get('material'):
        return {'status': 'REJECTED: Missing material'}
    return {'status': 'VALIDATED'}

def structural_check(state: LockerState):
    print(f'Checking integrity for {state.get(material)} lockers...')
    return {'status': 'READY_FOR_RFQ'}

graph = StateGraph(LockerState)
graph.add_node('validate', validate_specs)
graph.add_node('structural', structural_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'structural')
graph.add_edge('structural', END)
graph = graph.compile()
