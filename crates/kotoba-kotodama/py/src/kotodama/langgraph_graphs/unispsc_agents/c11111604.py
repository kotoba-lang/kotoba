from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MineralChemicalState(TypedDict):
    chemical_id: str
    purity_level: float
    hazmat_clearance: bool
    compliance_tags: List[str]
    steps: List[str]

def validate_safety(state: MineralChemicalState):
    print(f'Validating hazard clearance for {state[chemical_id]}')
    return {'hazmat_clearance': True, 'steps': state['steps'] + ['safety_check_passed']}

def perform_compliance_audit(state: MineralChemicalState):
    print('Performing regulatory compliance audit')
    return {'compliance_tags': ['export_compliant', 'iso_verified'], 'steps': state['steps'] + ['audit_completed']}

graph = StateGraph(MineralChemicalState)
graph.add_node('safety', validate_safety)
graph.add_node('audit', perform_compliance_audit)
graph.set_entry_point('safety')
graph.add_edge('safety', 'audit')
graph.add_edge('audit', END)
graph = graph.compile()
