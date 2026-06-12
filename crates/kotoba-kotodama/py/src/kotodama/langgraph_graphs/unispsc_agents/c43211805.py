from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class StorageKitState(TypedDict):
    kit_id: str
    components: List[str]
    compatibility_verified: bool
    compliance_cleared: bool

def check_compatibility(state: StorageKitState) -> StorageKitState:
    state['compatibility_verified'] = True
    return state

def verify_compliance(state: StorageKitState) -> StorageKitState:
    state['compliance_cleared'] = True
    return state

graph = StateGraph(StorageKitState)
graph.add_node('verify_compatibility', check_compatibility)
graph.add_node('verify_compliance', verify_compliance)
graph.set_entry_point('verify_compatibility')
graph.add_edge('verify_compatibility', 'verify_compliance')
graph.add_edge('verify_compliance', END)

graph = graph.compile()
