from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_report: str

def validate_tool_specs(state: ProcurementState):
    specs = state.get('spec_data', {})
    required = ['material_composition', 'chemical_solvent_resistance']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed, 'compliance_report': 'Success' if passed else 'Missing fields'}

def route_by_validation(state: ProcurementState):
    return 'validate' if not state.get('validation_passed') else END

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_tool_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
