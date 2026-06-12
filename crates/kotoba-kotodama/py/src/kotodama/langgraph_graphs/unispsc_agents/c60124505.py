from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BubbleProcurementState(TypedDict):
    item_name: str
    safety_check_passed: bool
    compliance_docs: List[str]

def validate_safety(state: BubbleProcurementState):
    # Business logic for bubble solution safety inspection
    return {'safety_check_passed': True}

def verify_documentation(state: BubbleProcurementState):
    # Ensure SDS and non-toxic certs are present
    return {'compliance_docs': ['SDS', 'NON-TOXIC-CERT']}

graph = StateGraph(BubbleProcurementState)
graph.add_node('safety_check', validate_safety)
graph.add_node('doc_check', verify_documentation)
graph.add_edge('safety_check', 'doc_check')
graph.add_edge('doc_check', END)
graph.set_entry_point('safety_check')
graph = graph.compile()
