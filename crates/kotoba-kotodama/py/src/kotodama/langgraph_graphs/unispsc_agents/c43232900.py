from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class NetSoftwareState(TypedDict):
    software_name: str
    compliance_risk: bool
    validation_steps: List[str]

def validate_compliance(state: NetSoftwareState):
    state['compliance_risk'] = True
    state['validation_steps'] = ['Check ECCN rating', 'Audit encryption algorithms']
    return state

def configure_deployment(state: NetSoftwareState):
    state['validation_steps'].append('Verify network architecture segment')
    return state

graph = StateGraph(NetSoftwareState)
graph.add_node('compliance', validate_compliance)
graph.add_node('deployment', configure_deployment)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'deployment')
graph.add_edge('deployment', END)
graph = graph.compile()
