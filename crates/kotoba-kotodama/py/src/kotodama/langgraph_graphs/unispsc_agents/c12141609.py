from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, END

class CompositeState(TypedDict):
    material_id: str
    composition_data: dict
    validation_checks: List[str]
    is_approved: bool

def validate_composition(state: CompositeState):
    # Simulate chemical validation logic
    composition = state.get('composition_data', {})
    checks = state.get('validation_checks', [])
    if composition.get('purity', 0) >= 0.999:
        checks.append('purity_passed')
    return {'validation_checks': checks}

def perform_compliance_check(state: CompositeState):
    # Simulate dual-use export control screening
    checks = state.get('validation_checks', [])
    if 'purity_passed' in checks:
        checks.append('export_compliance_passed')
        return {'validation_checks': checks, 'is_approved': True}
    return {'is_approved': False}

graph = StateGraph(CompositeState)
graph.add_node('validate_composition', validate_composition)
graph.add_node('compliance_check', perform_compliance_check)
graph.add_edge('validate_composition', 'compliance_check')
graph.add_edge('compliance_check', END)
graph.set_entry_point('validate_composition')
graph = graph.compile()
