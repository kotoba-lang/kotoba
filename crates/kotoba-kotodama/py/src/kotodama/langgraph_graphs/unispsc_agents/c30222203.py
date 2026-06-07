from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class NuclearStationState(TypedDict):
    regulatory_checks: List[str]
    safety_audit_passed: bool
    is_compliant: bool

def validate_nuclear_compliance(state: NuclearStationState):
    # Simulate regulatory validation logic for nuclear infrastructure
    checks = state.get('regulatory_checks', [])
    passed = len(checks) >= 3
    return {'safety_audit_passed': passed, 'is_compliant': passed}

def finalize_procurement(state: NuclearStationState):
    return {'is_compliant': state['is_compliant']}

graph = StateGraph(NuclearStationState)
graph.add_node('validate', validate_nuclear_compliance)
graph.add_node('procure', finalize_procurement)
graph.add_edge('validate', 'procure')
graph.add_edge('procure', END)
graph.set_entry_point('validate')
graph = graph.compile()
