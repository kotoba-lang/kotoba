from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BiologicalState(TypedDict):
    product_name: str
    batch_id: str
    cold_chain_verified: bool
    safety_check_passed: bool

def verify_cold_chain(state: BiologicalState):
    return {'cold_chain_verified': True}

def validate_safety_protocols(state: BiologicalState):
    return {'safety_check_passed': True}

workflow = StateGraph(BiologicalState)
workflow.add_node('verify_chain', verify_cold_chain)
workflow.add_node('safety_check', validate_safety_protocols)
workflow.set_entry_point('verify_chain')
workflow.add_edge('verify_chain', 'safety_check')
workflow.add_edge('safety_check', END)
graph = workflow.compile()
