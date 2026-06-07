from typing import TypedDict
from langgraph.graph import StateGraph, END

class LabSupplyState(TypedDict):
    material_specs: dict
    validation_passed: bool
    compliance_score: float

def validate_sealant(state: LabSupplyState):
    specs = state.get('material_specs', {})
    state['validation_passed'] = specs.get('chem_resistant', False) and specs.get('purity_level', 0) > 99
    state['compliance_score'] = 1.0 if state['validation_passed'] else 0.0
    return state

graph = StateGraph(LabSupplyState)
graph.add_node('validate_sealant', validate_sealant)
graph.set_entry_point('validate_sealant')
graph.add_edge('validate_sealant', END)
graph = graph.compile()
