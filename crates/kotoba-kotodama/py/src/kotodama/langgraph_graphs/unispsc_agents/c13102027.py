from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class FertilizerState(TypedDict):
    commodity_code: str
    purity_level: float
    hazard_check_passed: bool
    compliance_docs: Annotated[Sequence[str], operator.add]

def validate_purity(state: FertilizerState):
    purity = state.get('purity_level', 0.0)
    return {'hazard_check_passed': purity > 0.95}

def check_compliance(state: FertilizerState):
    return {'compliance_docs': ['MSDS_VERIFIED', 'REGULATORY_APPROVAL_ACTIVE']}

def build_graph():
    graph = StateGraph(FertilizerState)
    graph.add_node('validate', validate_purity)
    graph.add_node('compliance', check_compliance)
    graph.set_entry_point('validate')
    graph.add_edge('validate', 'compliance')
    graph.add_edge('compliance', END)
    return graph.compile()

graph = build_graph()
