from typing import TypedDict
from langgraph.graph import StateGraph, END

class TicketOfficeState(TypedDict):
    site_specs: dict
    compliance_report: dict
    approval_status: str

def validate_structural_specs(state: TicketOfficeState):
    # Simulate CAD compliance check for prefab office
    state['compliance_report'] = {'structural': 'passed', 'fire_code': 'verified'}
    print('Validating office structure...')
    return state

def route_procurement(state: TicketOfficeState):
    return 'approved' if state['compliance_report'].get('structural') == 'passed' else 'rejected'

graph = StateGraph(TicketOfficeState)
graph.add_node('validate', validate_structural_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
