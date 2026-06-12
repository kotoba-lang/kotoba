from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class LivestockState(TypedDict):
    commodity_code: str
    quality_checks: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_livestock_standards(state: LivestockState):
    checks = state.get('quality_checks', [])
    is_compliant = len(checks) >= 3
    return {'is_compliant': is_compliant}

def process_livestock_logistics(state: LivestockState):
    return {'quality_checks': ['sanitary_audit_passed', 'traceability_verified']}

graph = StateGraph(LivestockState)
graph.add_node('logistics', process_livestock_logistics)
graph.add_node('validation', validate_livestock_standards)
graph.set_entry_point('logistics')
graph.add_edge('logistics', 'validation')
graph.add_edge('validation', END)
graph = graph.compile()
