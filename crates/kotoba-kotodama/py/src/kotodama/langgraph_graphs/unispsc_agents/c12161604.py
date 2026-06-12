from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class SemiconductorState(TypedDict):
    spec_id: str
    purity_check: bool
    structural_integrity: bool
    export_approval: bool
    log: Annotated[Sequence[str], operator.add]

def validate_purity(state: SemiconductorState) -> SemiconductorState:
    # Simulate high-precision spectral analysis
    state['purity_check'] = True
    state['log'] = ['Purity validation passed: >99.9999999%']
    return state

def validate_structure(state: SemiconductorState) -> SemiconductorState:
    # Simulate X-ray diffraction check
    state['structural_integrity'] = True
    state['log'] = ['Crystal structure integrity verified']
    return state

def check_export_compliance(state: SemiconductorState) -> SemiconductorState:
    state['export_approval'] = True
    state['log'] = ['Dual-use export control compliance verified']
    return state

graph = StateGraph(SemiconductorState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('validate_structure', validate_structure)
graph.add_node('check_export_compliance', check_export_compliance)

graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'validate_structure')
graph.add_edge('validate_structure', 'check_export_compliance')
graph.add_edge('check_export_compliance', END)

graph = graph.compile()
