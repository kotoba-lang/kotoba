from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_grade: str
    dimensions: str
    inspection_passed: bool
    compliance_docs: List[str]

def validate_material_specs(state: ProcurementState):
    print(f'Validating material: {state.get('material_grade')}')
    return {'inspection_passed': True}

def check_compliance(state: ProcurementState):
    print('Verifying Mill Test Reports...')
    return {'compliance_docs': ['MTR_001', 'ISO_Cert']}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_material_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
