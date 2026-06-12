from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ArtSupplyState(TypedDict):
    item_name: str
    safety_check_passed: bool
    compliance_docs: List[str]

def validate_safety(state: ArtSupplyState) -> ArtSupplyState:
    # Logic to verify MSDS and ASTM compliance
    state['safety_check_passed'] = True
    return state

def check_compliance(state: ArtSupplyState) -> str:
    return 'process' if state['safety_check_passed'] else 'reject'

graph = StateGraph(ArtSupplyState)
graph.add_node('safety_validator', validate_safety)
graph.set_entry_point('safety_validator')
graph.add_edge('safety_validator', END)
graph = graph.compile()
