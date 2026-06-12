from typing import TypedDict
from langgraph.graph import StateGraph, END

class BeverageState(TypedDict):
    product_id: str
    compliance_checked: bool
    temp_log_verified: bool

def validate_alcohol_compliance(state: BeverageState):
    return {'compliance_checked': True}

def check_storage_requirements(state: BeverageState):
    return {'temp_log_verified': True}

graph = StateGraph(BeverageState)
graph.add_node('compliance', validate_alcohol_compliance)
graph.add_node('storage', check_storage_requirements)
graph.add_edge('compliance', 'storage')
graph.add_edge('storage', END)
graph.set_entry_point('compliance')
graph = graph.compile()
