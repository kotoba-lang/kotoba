from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SteelProcurementState(TypedDict):
    material_grade: str
    dimensions: dict
    compliance_passed: bool

def validate_specs(state: SteelProcurementState):
    grade = state.get('material_grade', '')
    return {'compliance_passed': grade in ['304', '316', '316L']}

def route_verification(state: SteelProcurementState):
    return 'validate' if state['compliance_passed'] else END

graph = StateGraph(SteelProcurementState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
