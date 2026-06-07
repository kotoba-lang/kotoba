from typing import TypedDict
from langgraph.graph import StateGraph, END

class DrugState(TypedDict):
    batch_id: str
    compliance_checked: bool
    temp_log_verified: bool

def check_compliance(state: DrugState):
    state['compliance_checked'] = True
    return {'compliance_checked': True}

def verify_storage(state: DrugState):
    state['temp_log_verified'] = True
    return {'temp_log_verified': True}

graph = StateGraph(DrugState)
graph.add_node('compliance', check_compliance)
graph.add_node('storage', verify_storage)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'storage')
graph.add_edge('storage', END)
graph = graph.compile()
