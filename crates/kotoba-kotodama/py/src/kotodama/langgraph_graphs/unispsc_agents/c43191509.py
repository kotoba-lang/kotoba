from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SoftwareProcurementState(TypedDict):
    license_key: str
    validation_status: str
    compliance_checks: List[str]
    deployment_log: List[str]

def validate_license(state: SoftwareProcurementState):
    # Simulate license key validation against ERP
    if state.get('license_key'):
        return {'validation_status': 'VALIDATED', 'compliance_checks': ['check_oem_terms']}
    return {'validation_status': 'FAILED'}

def deploy_software(state: SoftwareProcurementState):
    # Simulate infrastructure deployment sequence
    return {'deployment_log': ['Container initialization', 'Config injection', 'Health check passed']}

graph = StateGraph(SoftwareProcurementState)
graph.add_node('validate', validate_license)
graph.add_node('deploy', deploy_software)
graph.set_entry_point('validate')
graph.add_edge('validate', 'deploy')
graph.add_edge('deploy', END)
graph = graph.compile()
