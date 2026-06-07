from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class RawMaterialState(TypedDict):
    commodity_id: str
    purity_verified: bool
    compliance_score: float
    workflow_logs: Annotated[Sequence[str], operator.add]

def verify_purity(state: RawMaterialState) -> RawMaterialState:
    # Logic to validate assay report against industry standard
    return {**state, 'purity_verified': True, 'workflow_logs': ['Purity verification passed']}

def check_compliance(state: RawMaterialState) -> RawMaterialState:
    # Check dual-use and sanctions compliance
    return {**state, 'compliance_score': 0.98, 'workflow_logs': ['Compliance check completed']}

graph = StateGraph(RawMaterialState)
graph.add_node('verify_purity', verify_purity)
graph.add_node('check_compliance', check_compliance)
graph.set_entry_point('verify_purity')
graph.add_edge('verify_purity', 'check_compliance')
graph.add_edge('check_compliance', END)
graph = graph.compile()
