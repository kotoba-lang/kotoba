import operator
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
class PharmaState(TypedDict):
    item_name: str
    compliance_cleared: bool
    storage_temp_verified: bool
    final_approval: bool
def check_compliance(state: PharmaState):
    return {'compliance_cleared': True}
def verify_storage(state: PharmaState):
    return {'storage_temp_verified': True}
def approve_procurement(state: PharmaState):
    return {'final_approval': state['compliance_cleared'] and state['storage_temp_verified']}
graph = StateGraph(PharmaState)
graph.add_node('compliance', check_compliance)
graph.add_node('storage', verify_storage)
graph.add_node('approval', approve_procurement)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'storage')
graph.add_edge('storage', 'approval')
graph.add_edge('approval', END)

graph = graph.compile()
