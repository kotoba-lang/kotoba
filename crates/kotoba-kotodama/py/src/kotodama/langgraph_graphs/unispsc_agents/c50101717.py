from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    commodity: str
    quality_docs: List[str]
    compliance_passed: bool

def validate_food_safety(state: ProcurementState):
    # logic to verify compliance for shelled nuts/seeds
    return {'compliance_passed': True}

def check_storage_specs(state: ProcurementState):
    # verify warehouse temperature constraints
    return {'compliance_passed': True}

graph = StateGraph(ProcurementState)
graph.add_node('safety_check', validate_food_safety)
graph.add_node('storage_eval', check_storage_specs)
graph.add_edge('safety_check', 'storage_eval')
graph.add_edge('storage_eval', END)
graph.set_entry_point('safety_check')
graph = graph.compile()
