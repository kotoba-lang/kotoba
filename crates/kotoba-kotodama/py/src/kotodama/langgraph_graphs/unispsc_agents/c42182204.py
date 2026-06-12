from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ThermometerRackState(TypedDict):
    specifications: dict
    validation_passed: bool
    compliance_report: str

def validate_materials(state: ThermometerRackState):
    material = state.get('specifications', {}).get('material', '')
    return {'validation_passed': material in ['Stainless Steel', 'Medical Grade Plastic']}

def generate_compliance(state: ThermometerRackState):
    return {'compliance_report': 'Compliant with ISO 13485 storage standards' if state['validation_passed'] else 'Compliance failure'}

graph = StateGraph(ThermometerRackState)
graph.add_node('validate', validate_materials)
graph.add_node('report', generate_compliance)
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph.set_entry_point('validate')
graph = graph.compile()
