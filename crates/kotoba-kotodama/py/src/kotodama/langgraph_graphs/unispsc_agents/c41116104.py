from typing import TypedDict
from langgraph.graph import StateGraph, END

class ChemistryKitState(TypedDict):
    kit_details: dict
    validation_passed: bool
    safety_check: bool

def validate_hazardous_materials(state: ChemistryKitState):
    print('Checking HazMat compliance...')
    state['safety_check'] = True
    return state

def check_purity_specs(state: ChemistryKitState):
    print('Verifying chemical purity and certifications...')
    state['validation_passed'] = True
    return state

builder = StateGraph(ChemistryKitState)
builder.add_node('hazmat_check', validate_hazardous_materials)
builder.add_node('purity_check', check_purity_specs)
builder.add_edge('hazmat_check', 'purity_check')
builder.add_edge('purity_check', END)
builder.set_entry_point('hazmat_check')
graph = builder.compile()
