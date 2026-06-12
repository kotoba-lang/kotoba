from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class BiscuitState(TypedDict):
    product_name: str
    compliance_checks: List[str]
    is_approved: bool

def validate_food_safety(state: BiscuitState):
    checks = ['allergen_check', 'shelf_life_validation', 'certification_audit']
    return {'compliance_checks': checks, 'is_approved': True}

graph = StateGraph(BiscuitState)
graph.add_node('safety_check', validate_food_safety)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', END)
graph = graph.compile()
