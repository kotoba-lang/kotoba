from langgraph.graph import StateGraph, END
from typing import TypedDict, List
class BerylliumState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_risk: str
def validate_material_specs(state: BerylliumState):
    specs = state.get('spec_data', {})
    purity = specs.get('purity', 0)
    state['validation_passed'] = purity >= 99.0
    return state
def check_export_compliance(state: BerylliumState):
    state['compliance_risk'] = 'Critical' if state.get('validation_passed') else 'None'
    return state
graph = StateGraph(BerylliumState)
graph.add_node('validate', validate_material_specs)
graph.add_node('compliance', check_export_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
