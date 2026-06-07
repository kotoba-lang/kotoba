from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ReferenceMaterialState(TypedDict):
    material_id: str
    purity_validated: bool
    compliance_check: bool
    messages: Annotated[list, add_messages]

def validate_purity(state: ReferenceMaterialState):
    return {"purity_validated": True}

def check_compliance(state: ReferenceMaterialState):
    return {"compliance_check": True}

graph = StateGraph(ReferenceMaterialState)
graph.add_node("purity_validation", validate_purity)
graph.add_node("regulatory_compliance", check_compliance)
graph.add_edge("purity_validation", "regulatory_compliance")
graph.add_edge("regulatory_compliance", END)
graph.set_entry_point("purity_validation")
graph = graph.compile()
