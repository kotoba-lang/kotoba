from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class DisposalState(TypedDict):
    equipment_id: str
    compliance_status: bool
    disposal_plan: str

def validate_compliance(state: DisposalState):
    state['compliance_status'] = True
    return state

def route_disposal(state: DisposalState):
    return 'process_disposal'

graph = StateGraph(DisposalState)
graph.add_node('validate', validate_compliance)
graph.add_node('process_disposal', lambda x: x)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process_disposal')
graph.add_edge('process_disposal', END)
graph = graph.compile()
