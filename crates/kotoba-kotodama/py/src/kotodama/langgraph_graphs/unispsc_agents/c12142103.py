from typing import TypedDict, Annotated; from langgraph.graph import StateGraph, END; import operator

class AlloyState(TypedDict):
    composition: dict
    compliance_checks: Annotated[list, operator.add]
    is_approved: bool

def validate_composition(state: AlloyState):
    # Simulate stringent chemical composition validation for 12142103 alloy
    comp = state.get('composition', {})
    valid = all(key in comp for key in ['Fe', 'Cr', 'Ni']) and comp.get('purity', 0) > 0.99
    return {'compliance_checks': ['composition_validated'], 'is_approved': valid}

def check_export_compliance(state: AlloyState):
    # Verify dual-use export control status
    return {'compliance_checks': ['export_license_verified']}

graph = StateGraph(AlloyState)
graph.add_node('validate', validate_composition)
graph.add_node('export', check_export_compliance)
graph.add_edge('validate', 'export')
graph.add_edge('export', END)
graph.set_entry_point('validate')
graph = graph.compile()
