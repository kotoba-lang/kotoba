from typing import TypedDict
from langgraph.graph import StateGraph, END

class SpecimenState(TypedDict):
    specimen_id: str
    compliance_cleared: bool
    hazard_check: bool

def validate_compliance(state: SpecimenState):
    print(f'Validating compliance for {state[specimen_id]}')
    return {'compliance_cleared': True}

def check_hazards(state: SpecimenState):
    print('Checking fixative toxicity and shipment protocols')
    return {'hazard_check': True}

graph = StateGraph(SpecimenState)
graph.add_node('compliance', validate_compliance)
graph.add_node('hazards', check_hazards)
graph.add_edge('compliance', 'hazards')
graph.add_edge('hazards', END)
graph.set_entry_point('compliance')
graph = graph.compile()
