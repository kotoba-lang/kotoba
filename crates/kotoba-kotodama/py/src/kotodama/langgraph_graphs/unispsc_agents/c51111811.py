from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ProcurementState(TypedDict):
    drug_name: str
    purity_check: bool
    compliance_docs: List[str]

def validate_purity(state: ProcurementState):
    return {"purity_check": True}

def verify_regulations(state: ProcurementState):
    return {"compliance_docs": ["SDS", "CoA", "FDA_Approval"]}

graph = StateGraph(ProcurementState)
graph.add_node("purity", validate_purity)
graph.add_node("regulation", verify_regulations)
graph.set_entry_point("purity")
graph.add_edge("purity", "regulation")
graph.add_edge("regulation", END)
graph = graph.compile()
