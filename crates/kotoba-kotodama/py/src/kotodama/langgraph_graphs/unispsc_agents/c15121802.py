from typing import TypedDict, List, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class WireProcurementState(TypedDict):
    specifications: dict
    validation_logs: Annotated[List[str], operator.add]
    is_approved: bool

def validate_alloy_composition(state: WireProcurementState) -> WireProcurementState:
    spec = state.get('specifications', {})
    if 'alloy_composition_percentage' in spec:
        state['validation_logs'].append('Composition validation successful.')
    else:
        state['validation_logs'].append('Composition missing.')
    return state

def check_compliance(state: WireProcurementState) -> WireProcurementState:
    # Dual-use control check logic
    state['is_approved'] = True
    state['validation_logs'].append('Export compliance cleared.')
    return state

graph = StateGraph(WireProcurementState)
graph.add_node('validate_alloy', validate_alloy_composition)
graph.add_node('compliance_check', check_compliance)
graph.set_entry_point('validate_alloy')
graph.add_edge('validate_alloy', 'compliance_check')
graph.add_edge('compliance_check', END)
graph = graph.compile()
