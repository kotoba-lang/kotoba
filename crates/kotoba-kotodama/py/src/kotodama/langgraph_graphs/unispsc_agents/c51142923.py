from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_id: str
    purity_check: bool
    compliance_validated: bool
    tasks: List[str]

def validate_chemistry(state: ProcurementState):
    print('Validating chemical purity for Butamben...')
    return {'purity_check': True}

def verify_regulations(state: ProcurementState):
    print('Checking pharmaceutical regulatory compliance...')
    return {'compliance_validated': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_chemistry)
graph.add_node('compliance', verify_regulations)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
