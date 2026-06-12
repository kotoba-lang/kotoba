from typing import TypedDict
from langgraph.graph import StateGraph, END

class VCCodeState(TypedDict):
    license_count: int
    compliance_status: bool

def validate_compliance(state: VCCodeState):
    return {'compliance_status': state.get('license_count', 0) > 0}

def deploy_software(state: VCCodeState):
    print('Provisioning licenses...')
    return {'compliance_status': True}

graph = StateGraph(VCCodeState)
graph.add_node('validate', validate_compliance)
graph.add_node('deploy', deploy_software)
graph.set_entry_point('validate')
graph.add_edge('validate', 'deploy')
graph.add_edge('deploy', END)
graph = graph.compile()
