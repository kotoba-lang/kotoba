from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProteinState(TypedDict):
    part_id: str
    compatibility_verified: bool
    compliance_checked: bool

def check_compatibility(state: ProteinState) -> dict:
    # Logic to verify part number against instrument database
    return {'compatibility_verified': True}

def check_compliance(state: ProteinState) -> dict:
    # Logic to verify regulatory documentation status
    return {'compliance_checked': True}

graph = StateGraph(ProteinState)
graph.add_node('verify_part', check_compatibility)
graph.add_node('check_reg', check_compliance)
graph.set_entry_point('verify_part')
graph.add_edge('verify_part', 'check_reg')
graph.add_edge('check_reg', END)
graph = graph.compile()
