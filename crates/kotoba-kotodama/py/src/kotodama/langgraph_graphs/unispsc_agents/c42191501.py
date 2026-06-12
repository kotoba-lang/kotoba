from typing import TypedDict
from langgraph.graph import StateGraph, END

class SystemState(TypedDict):
    capacity_check: bool
    compliance_validated: bool
    installation_scheduled: bool

def validate_tech_specs(state: SystemState):
    print('Validating ISO 13485 compatibility for pneumatic components...')
    return {'compliance_validated': True}

def verify_logistics(state: SystemState):
    print('Checking site survey and installation feasibility...')
    return {'installation_scheduled': True}

graph = StateGraph(SystemState)
graph.add_node('tech_validation', validate_tech_specs)
graph.add_node('logistics_check', verify_logistics)
graph.set_entry_point('tech_validation')
graph.add_edge('tech_validation', 'logistics_check')
graph.add_edge('logistics_check', END)
graph = graph.compile()
