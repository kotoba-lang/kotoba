from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AlloyProcurementState(TypedDict):
    material_code: str
    spec_requirements: dict
    validation_passed: bool
    compliance_risk: list
    logs: Annotated[Sequence[str], operator.add]

def validate_alloy_specs(state: AlloyProcurementState):
    specs = state.get('spec_requirements', {})
    required = ['alloy_composition_percent', 'tensile_strength_mpa']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed, 'logs': ['Spec validation complete']}

def perform_compliance_check(state: AlloyProcurementState):
    return {'compliance_risk': ['dual-use-export-control'], 'logs': ['Compliance screening finished']}

graph = StateGraph(AlloyProcurementState)
graph.add_node('validate', validate_alloy_specs)
graph.add_node('compliance', perform_compliance_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
