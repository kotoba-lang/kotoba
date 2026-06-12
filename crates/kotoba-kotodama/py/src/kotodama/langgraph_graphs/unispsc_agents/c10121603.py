from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    commodity_code: str
    purity_level: float
    safety_clearance: bool
    log_audit: Annotated[Sequence[str], operator.add]

def validate_safety_protocols(state: ChemicalState) -> ChemicalState:
    # Specialized logic for inorganic chemical hazardous material handling
    state['safety_clearance'] = state.get('purity_level', 0) > 95.0
    state['log_audit'] = ['Safety protocols validated against hazardous materials standards']
    return state

def route_to_procurement(state: ChemicalState) -> str:
    return 'END' if state['safety_clearance'] else 'MANUAL_REVIEW'

graph = StateGraph(ChemicalState)
graph.add_node('safety_check', validate_safety_protocols)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', END)

graph = graph.compile()
