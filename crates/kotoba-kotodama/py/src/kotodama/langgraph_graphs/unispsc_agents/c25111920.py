from typing import TypedDict
from langgraph.graph import StateGraph, END

class FenderState(TypedDict):
    material_specs: dict
    energy_calculation: float
    compliance_report: str

def validate_material(state: FenderState) -> FenderState:
    # Simulate material compliance check
    state['compliance_report'] = 'Material passes ISO 17357 standards'
    return state

def calculate_energy(state: FenderState) -> FenderState:
    # Simulate energy absorption validation based on vessel displacement
    state['energy_calculation'] = 1200.5
    return state

graph = StateGraph(FenderState)
graph.add_node('validate', validate_material)
graph.add_node('calculate', calculate_energy)
graph.set_entry_point('validate')
graph.add_edge('validate', 'calculate')
graph.add_edge('calculate', END)
graph = graph.compile()
