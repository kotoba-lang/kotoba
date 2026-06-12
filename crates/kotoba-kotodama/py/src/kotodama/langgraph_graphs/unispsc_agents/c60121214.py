from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ArtMaterialState(TypedDict):
    product_name: str
    safety_verified: bool
    compliance_docs: List[str]

def validate_safety(state: ArtMaterialState):
    state['safety_verified'] = True
    return state

def check_compliance(state: ArtMaterialState):
    state['compliance_docs'] = ['ASTM D4236']
    return state

graph = StateGraph(ArtMaterialState)
graph.add_node('safety', validate_safety)
graph.add_node('compliance', check_compliance)
graph.add_edge('safety', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('safety')
graph = graph.compile()
