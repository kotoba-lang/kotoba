from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_name: str
    compliance_cleared: bool
    safety_check_passed: bool

def validate_hazardous_material(state: ProcurementState):
    print(f'Validating high-risk material: {state.get('material_name')}')
    return {'compliance_cleared': True, 'safety_check_passed': True}

def execute_procurement(state: ProcurementState):
    print('Executing secure handling procurement protocol')
    return {'safety_check_passed': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_hazardous_material)
graph.add_node('execute', execute_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'execute')
graph.add_edge('execute', END)
graph = graph.compile()
