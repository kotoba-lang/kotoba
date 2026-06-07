from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ChemicalProcurementState(TypedDict):
    material_code: str
    msds_received: bool
    compliance_cleared: bool
    logistics_ready: bool

def validate_msds(state: ChemicalProcurementState):
    # Simulate MSDS validation logic
    print(f'Validating MSDS for {state[material_code]}')
    return {'msds_received': True}

def check_regulatory_compliance(state: ChemicalProcurementState):
    # Simulate dual-use and dangerous goods checks
    print('Checking regulatory constraints')
    return {'compliance_cleared': True}

graph = StateGraph(ChemicalProcurementState)
graph.add_node('validate_msds', validate_msds)
graph.add_node('compliance', check_regulatory_compliance)
graph.add_edge('validate_msds', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate_msds')
graph = graph.compile()
