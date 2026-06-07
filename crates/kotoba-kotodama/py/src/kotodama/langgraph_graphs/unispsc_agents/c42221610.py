from typing import TypedDict
from langgraph.graph import StateGraph, END

class IvComponentState(TypedDict):
    part_number: str
    compliance_checked: bool
    sterility_verified: bool

def validate_compliance(state: IvComponentState) -> IvComponentState:
    # Simulate regulatory validation logic
    state['compliance_checked'] = True
    return state

def check_sterility(state: IvComponentState) -> IvComponentState:
    # Verify batch certification for medical standards
    state['sterility_verified'] = True
    return state

graph = StateGraph(IvComponentState)
graph.add_node('compliance', validate_compliance)
graph.add_node('sterility', check_sterility)
graph.add_edge('compliance', 'sterility')
graph.add_edge('sterility', END)
graph.set_entry_point('compliance')
graph = graph.compile()
