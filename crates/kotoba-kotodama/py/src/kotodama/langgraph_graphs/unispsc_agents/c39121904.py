from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class LockoutState(TypedDict):
    kit_id: str
    compliance_tags: List[str]
    requires_inspection: bool

def validate_compliance(state: LockoutState):
    return {'compliance_tags': ['OSHA_COMPLIANT']}

def audit_station(state: LockoutState):
    state['requires_inspection'] = True
    return state

graph = StateGraph(LockoutState)
graph.add_node('validate', validate_compliance)
graph.add_node('audit', audit_station)
graph.set_entry_point('validate')
graph.add_edge('validate', 'audit')
graph.add_edge('audit', END)
graph = graph.compile()
