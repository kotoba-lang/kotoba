from typing import TypedDict
from langgraph.graph import StateGraph, END

class OfficeSuiteState(TypedDict):
    license_key: str
    compliance_checked: bool
    deployment_status: str

def validate_license(state: OfficeSuiteState):
    state['compliance_checked'] = len(state.get('license_key', '')) > 10
    return state

def deploy_software(state: OfficeSuiteState):
    if state.get('compliance_checked'):
        state['deployment_status'] = 'Active'
    return state

graph = StateGraph(OfficeSuiteState)
graph.add_node('validate', validate_license)
graph.add_node('deploy', deploy_software)
graph.set_entry_point('validate')
graph.add_edge('validate', 'deploy')
graph.add_edge('deploy', END)
graph = graph.compile()
